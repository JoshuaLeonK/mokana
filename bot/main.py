import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import MANGROVE_ZONES, ALERT_CATEGORIES, PUBLIC_BASE_URL
from zernio_client import ZernioClient
from gemini_analyst import GeminiAnalyst
from state_manager import StateManager, ConversationStep
from email_notifier import EmailNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mokana.bot")

app = FastAPI(
    title="Mokaná - Bot de Alerta Temprana, API C.R.A. & Hub de Datos B2B",
    description=(
        "Sistema de Notificación, Gestión y Respuesta en Tiempo Real para los Manglares del Atlántico. "
        "Integra Tótems QR/NFC, Bot de WhatsApp (Zernio), IA Multimodal (Gemini 2.5 Flash) y Notificaciones por Correo (Resend)."
    ),
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

zernio = ZernioClient()
analyst = GeminiAnalyst()
state_mgr = StateManager()
mailer = EmailNotifier()

PROCESSED_EVENTS: Set[str] = set()
SSE_CLIENTS: List[asyncio.Queue] = []


async def broadcast_realtime_event(event_type: str, data: Dict[str, Any]) -> None:
    payload = {"event": event_type, "data": data}
    for q in list(SSE_CLIENTS):
        try:
            q.put_nowait(payload)
        except Exception:
            pass


# =============================================================================
# MODELOS PYDANTIC PARA EL PANEL DE ADMINISTRACIÓN (FRONTEND)
# =============================================================================

class CreateReportRequest(BaseModel):
    zone_id: str = Field(description="ID de la zona de manglar, ej. 'zone_mallorquin'")
    category_id: str = Field(description="ID de la categoría de alerta, ej. 'alert_color'")
    description: str = Field(description="Descripción breve del incidente")
    image_url: Optional[str] = Field(default=None, description="URL pública de la fotografía de evidencia")
    lat: Optional[float] = Field(default=None)
    lng: Optional[float] = Field(default=None)
    citizen_name: Optional[str] = Field(default="Vigía Web / Tótem")
    citizen_phone: Optional[str] = Field(default="web-totem")


class UpdateReportRequest(BaseModel):
    status: Optional[str] = Field(
        default=None,
        description="Nuevo estado: 'PENDIENTE_REVISION_CRA', 'EN_VERIFICACION_CAMPO', 'BRIGADA_DESPACHADA', 'RESUELTO', 'DESCARTADO'",
    )
    assigned_to: Optional[str] = Field(default=None, description="Dependencia o funcionario responsable en la C.R.A.")
    nivel_severidad: Optional[str] = Field(default=None, description="'BAJA', 'MEDIA', 'ALTA', 'CRÍTICA'")
    note: Optional[str] = Field(default=None, description="Nota de seguimiento o bitácora oficial de la C.R.A.")
    author: Optional[str] = Field(default="Panel Central C.R.A.")
    notify_citizen_whatsapp: bool = Field(default=True)


class SubscriberCreateRequest(BaseModel):
    name: str
    email: str
    organization: str
    type: str = Field(default="EMPRESA", description="'CRA' | 'EMPRESA' | 'ACADEMIA'")
    plan: str = Field(default="PRO_DATA_B2B")
    zones: List[str] = Field(default=["*"])
    categories: List[str] = Field(default=["*"])
    min_severity: str = Field(default="BAJA")
    active: bool = Field(default=True)


class SubscriberUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    type: Optional[str] = None
    plan: Optional[str] = None
    zones: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    min_severity: Optional[str] = None
    active: Optional[bool] = None


class NotificationSettingsUpdate(BaseModel):
    resend_api_key: Optional[str] = None
    from_email: Optional[str] = None
    auto_notify_email: Optional[bool] = None
    notify_whatsapp_on_status_change: Optional[bool] = None


# =============================================================================
# EXTRACCIÓN Y FLUJO DIRECTO DEL BOT DE WHATSAPP (SIN EMOJIS, CORTO Y AUTOMÁTICO)
# =============================================================================

def _extract_incoming_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    message = payload.get("message") or {}
    account = payload.get("account") or message.get("account") or {}
    conversation = payload.get("conversation") or message.get("conversation") or {}
    sender = message.get("sender") or payload.get("sender") or {}
    metadata = message.get("metadata") or payload.get("metadata") or {}

    account_id = account.get("id") or account.get("_id")
    conversation_id = (
        conversation.get("id")
        or conversation.get("_id")
        or payload.get("conversationId")
        or message.get("conversationId")
    )
    message_id = message.get("id") or message.get("_id")

    interactive_id = (
        message.get("interactiveId")
        or metadata.get("interactiveId")
        or (message.get("interactive") or {}).get("id")
        or (message.get("interactive") or {}).get("list_reply", {}).get("id")
        or (message.get("interactive") or {}).get("button_reply", {}).get("id")
    )
    text = (message.get("text") or "").strip()
    effective_input = interactive_id or text

    image_url: Optional[str] = None
    attachments = message.get("attachments") or []
    for att in attachments:
        att_type = (att.get("type") or att.get("mimeType") or "").lower()
        url = att.get("url") or att.get("mediaUrl") or att.get("attachmentUrl")
        if url and ("image" in att_type or not att_type or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            image_url = url
            break

    if not image_url and message.get("mediaUrl"):
        image_url = message.get("mediaUrl")

    gps_coords: Optional[Dict[str, float]] = None
    loc = message.get("location") or {}
    if not loc and attachments:
        for att in attachments:
            if (att.get("type") or "").lower() == "location":
                loc = att
                break
    if loc and ("latitude" in loc or "lat" in loc):
        try:
            gps_coords = {
                "lat": float(loc.get("latitude") or loc.get("lat")),
                "lng": float(loc.get("longitude") or loc.get("lng")),
            }
        except (TypeError, ValueError):
            gps_coords = None

    return {
        "account_id": account_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "sender_phone": sender.get("phoneNumber") or sender.get("id") or conversation.get("platformConversationId") or "desconocido",
        "sender_name": sender.get("name") or "Ciudadano Vigia",
        "text": text,
        "interactive_id": interactive_id,
        "effective_input": effective_input,
        "image_url": image_url,
        "gps": gps_coords,
    }


async def _finalize_and_analyze_report(
    conv_id: str,
    acc_id: Optional[str],
    data: Dict[str, Any],
    session: Dict[str, Any],
) -> None:
    """
    Se ejecuta automáticamente apenas la sesión ya cuenta con Imagen + Texto (lleguen juntos o por separado).
    Si el usuario no había elegido zona o categoría, las infiere del texto o con Gemini sin pedir nada más.
    """
    # 1. Asegurar Zona (si no se seleccionó antes, intentar detectarla del texto o usar Ciénaga de Mallorquín por defecto)
    if not session.get("zone_id"):
        detected_zone = state_mgr.detect_zone_from_text(session.get("description") or "") or MANGROVE_ZONES[0]
        session["zone_id"] = detected_zone["id"]
        session["zone_title"] = detected_zone["title"]
        session["zone_coords"] = detected_zone["coords"]

    # 2. Asegurar Categoría preliminar (si no la eligió en el desplegable, se detecta del texto o Gemini la clasifica)
    if not session.get("category_id"):
        detected_cat = state_mgr.detect_category_from_text(session.get("description") or "")
        if detected_cat:
            session["category_id"] = detected_cat["id"]
            session["category_title"] = detected_cat["title"]
        else:
            session["category_id"] = "alert_otro"
            session["category_title"] = "Determinado por IA"

    await zernio.send_text(
        conv_id,
        "Verificando imagen y descripcion con IA...",
        account_id=acc_id,
    )

    ai_result = await analyst.analyze_report(
        zone_title=session["zone_title"],
        category_title=session["category_title"],
        user_description=session["description"],
        image_url=session["image_url"],
    )

    # Si el usuario no había tocado el desplegable de anomalías, usamos la categoría que Gemini infirió de la foto+texto
    if session["category_title"] == "Determinado por IA" or session["category_id"] == "alert_otro":
        inferred_id = ai_result.get("categoria_inferida_id")
        inferred_cat = next((c for c in ALERT_CATEGORIES if c["id"] == inferred_id), None)
        if inferred_cat:
            session["category_id"] = inferred_cat["id"]
            session["category_title"] = inferred_cat["title"]

    if not ai_result.get("es_valida", True):
        motivo = ai_result.get("motivo_rechazo") or "La imagen no coincide con la descripcion enviada."
        # Limpiamos solo la imagen para que pueda mandar la foto correcta sin perder su texto
        session["image_url"] = None
        await zernio.send_text(
            conv_id,
            f"No se pudo validar el reporte: {motivo}\nEnvia una foto real que coincida con la descripcion.",
            account_id=acc_id,
        )
        return

    saved_record = state_mgr.save_report(
        conversation_id=conv_id,
        sender_phone=data["sender_phone"],
        sender_name=data["sender_name"],
        session=session,
        ai_report=ai_result,
        source="WHATSAPP_TOTEM",
    )

    settings = state_mgr.get_settings()
    email_logs: List[Dict[str, Any]] = []
    if settings.get("auto_notify_email", True):
        subscribers = state_mgr.list_subscribers()
        email_logs = await mailer.dispatch_notifications(saved_record, subscribers, settings)
        saved_record = state_mgr.attach_email_logs(saved_record["id"], email_logs) or saved_record

    await broadcast_realtime_event("report.created", saved_record)

    cra_rep = saved_record["cra_technical_report"]
    final_message = (
        f"Reporte registrado y notificado a la C.R.A.\n"
        f"Radicado: {saved_record['id']}\n"
        f"Zona: {session['zone_title']}\n"
        f"Anomalia: {session['category_title']}\n"
        f"Prioridad: {cra_rep['nivel_severidad']} (Riesgo {cra_rep['indice_riesgo_ambiental']}/100)\n"
        f"Informe: {cra_rep['titulo_hallazgo']}. {cra_rep['accion_recomendada_cra']}"
    )

    state_mgr.reset_session(conv_id)
    session_after = state_mgr.get_session(conv_id)
    session_after["last_report_id"] = saved_record["id"]
    session_after["step"] = ConversationStep.WAITING_OPTIONAL_GPS

    await zernio.send_text(conv_id, final_message, account_id=acc_id)


async def process_whatsapp_message(payload: Dict[str, Any]) -> None:
    """
    Flujo ultra-corto, sin emojis, con listas desplegables nativas y soporte directo de Imagen + Texto:
    - Si llegan imagen y texto juntos (en un solo mensaje) o en mensajes separados (primero foto y luego texto,
      o primero texto y luego foto), la IA procesa y registra el reporte inmediatamente sin pedir más pasos.
    - Si el usuario prefiere ir paso a paso, usa los desplegables limpios de Zona y Anomalía.
    """
    data = _extract_incoming_data(payload)
    conv_id = data["conversation_id"]
    acc_id = data["account_id"]
    if not conv_id:
        return

    text = data["text"]
    interactive_id = data["interactive_id"]
    effective_input = data["effective_input"]
    image_url = data["image_url"]
    gps = data["gps"]

    session = state_mgr.get_session(conv_id)
    lower_text = text.lower()

    # Comandos de reinicio
    if lower_text in {"hola", "inicio", "menu", "menú", "nuevo", "reiniciar", "cancelar"} and not image_url:
        session = state_mgr.reset_session(conv_id)
        await zernio.send_zone_list(conv_id, account_id=acc_id)
        return

    # Si envía un Pin GPS
    if gps:
        session["gps"] = gps
        if session.get("last_report_id"):
            updated = state_mgr.update_report_gps(session["last_report_id"], gps["lat"], gps["lng"])
            if updated:
                await broadcast_realtime_event("report.updated", updated)
            await zernio.send_text(
                conv_id,
                f"Ubicacion GPS actualizada en el reporte {session['last_report_id']}.",
                account_id=acc_id,
            )
            return

    # 1. ¿El usuario seleccionó una Zona del desplegable o mandó el mensaje automático del Tótem QR/NFC?
    is_totem_greeting = "totem" in lower_text or "tótem" in lower_text or "reportando desde" in lower_text
    detected_zone = state_mgr.detect_zone_from_text(interactive_id or "") or (
        state_mgr.detect_zone_from_text(text) if (is_totem_greeting or not session.get("zone_id")) else None
    )

    if detected_zone and (
        (interactive_id and interactive_id.startswith("zone_"))
        or is_totem_greeting
        or (not image_url and text.strip().lower() == detected_zone["title"].lower())
    ):
        session["zone_id"] = detected_zone["id"]
        session["zone_title"] = detected_zone["title"]
        session["zone_coords"] = detected_zone["coords"]
        session["step"] = ConversationStep.WAITING_CATEGORY

        # Si ya había enviado antes foto y descripción, analiza de inmediato
        if session.get("image_url") and session.get("description"):
            await _finalize_and_analyze_report(conv_id, acc_id, data, session)
            return

        await zernio.send_category_list(conv_id, detected_zone["title"], account_id=acc_id)
        return

    # 2. ¿El usuario seleccionó una Anomalía del desplegable?
    detected_cat = state_mgr.detect_category_from_text(interactive_id or "")
    if not detected_cat and not image_url:
        # Si tocó una opción del desplegable y Zernio mandó el título de la fila en `text`
        for cat in ALERT_CATEGORIES:
            if text.strip().lower() == cat["title"].lower() or text.strip().lower() == cat["id"].lower():
                detected_cat = cat
                break

    if detected_cat:
        session["category_id"] = detected_cat["id"]
        session["category_title"] = detected_cat["title"]
        session["step"] = ConversationStep.WAITING_DESCRIPTION

        # Si ya teníamos imagen y descripción guardadas, procesamos de inmediato
        if session.get("image_url") and session.get("description"):
            await _finalize_and_analyze_report(conv_id, acc_id, data, session)
            return

        await zernio.send_text(
            conv_id,
            f"Anomalia: {detected_cat['title']}. Envia una foto y una descripcion breve de lo que ocurre.",
            account_id=acc_id,
        )
        return

    # 3. Captura directa de Imagen y/o Texto (en un solo mensaje o en mensajes separados)
    if image_url:
        session["image_url"] = image_url

    if text and not is_totem_greeting:
        # Si en el texto menciona alguna zona y aún no tenía zona, la guardamos
        if not session.get("zone_id") and detected_zone:
            session["zone_id"] = detected_zone["id"]
            session["zone_title"] = detected_zone["title"]
            session["zone_coords"] = detected_zone["coords"]

        # Guardamos o concatenamos la descripción libre
        if session.get("description") and text not in session["description"]:
            session["description"] = f"{session['description']}. {text}"
        else:
            session["description"] = text

    # 4. ¡REGLA CLAVE! Si ya tenemos IMAGEN + TEXTO (hayan llegado juntos o separados), analizar de inmediato sin pedir más nada
    if session.get("image_url") and session.get("description"):
        await _finalize_and_analyze_report(conv_id, acc_id, data, session)
        return

    # 5. Si solo llegó la IMAGEN (sin texto todavía), pedir únicamente la descripción breve
    if session.get("image_url") and not session.get("description"):
        await zernio.send_text(
            conv_id,
            "Foto recibida. Escribe una descripcion breve de lo que ocurre para procesarla.",
            account_id=acc_id,
        )
        return

    # 6. Si solo llegó el TEXTO (sin imagen todavía), pedir únicamente la foto
    if session.get("description") and not session.get("image_url"):
        await zernio.send_text(
            conv_id,
            "Descripcion recibida. Envia la foto de evidencia para analizar el reporte.",
            account_id=acc_id,
        )
        return

    # 7. Si no hay ni zona ni imagen ni descripción aún, mostrar el desplegable de zonas
    if not session.get("zone_id"):
        await zernio.send_zone_list(conv_id, account_id=acc_id)
    else:
        await zernio.send_category_list(conv_id, session["zone_title"], account_id=acc_id)


# =============================================================================
# ENDPOINTS REST & TIEMPO REAL PARA EL PANEL DE ADMINISTRACIÓN
# =============================================================================

@app.get("/")
async def health_check() -> Dict[str, Any]:
    reports = state_mgr.list_reports()
    subs = state_mgr.list_subscribers()
    return {
        "service": "Mokaná WhatsApp Bot, C.R.A. Early Warning API & B2B Data Hub",
        "version": "2.1.0",
        "status": "online",
        "zones_configured": len(MANGROVE_ZONES),
        "total_reports": len(reports),
        "total_subscribers": len(subs),
        "endpoints": {
            "reports": "/api/reports",
            "stats": "/api/stats",
            "zones_and_totems": "/api/zones",
            "subscribers_b2b_cra": "/api/subscribers",
            "notification_settings": "/api/settings/notifications",
            "realtime_sse_stream": "/api/events/stream",
        },
    }


@app.post("/webhook/zernio")
async def zernio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_zernio_event: Optional[str] = Header(default=None),
    x_zernio_event_id: Optional[str] = Header(default=None),
    x_zernio_signature: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    raw_body = await request.body()
    if not zernio.verify_signature(raw_body, x_zernio_signature):
        raise HTTPException(status_code=401, detail="Firma X-Zernio-Signature inválida")

    payload = await request.json()
    event_name = x_zernio_event or payload.get("event") or "unknown"
    event_id = x_zernio_event_id or payload.get("id")

    if event_name == "webhook.test":
        return {"ok": True, "event": "webhook.test"}

    if event_id and event_id in PROCESSED_EVENTS:
        return {"ok": True, "deduplicated": True}

    if event_id:
        PROCESSED_EVENTS.add(event_id)

    if event_name == "message.received" or "message" in payload:
        background_tasks.add_task(process_whatsapp_message, payload)

    return {"ok": True, "event": event_name}


@app.get("/api/events/stream")
async def sse_events_stream(request: Request) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()
    SSE_CLIENTS.append(queue)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'event': 'connected', 'status': 'ok'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if queue in SSE_CLIENTS:
                SSE_CLIENTS.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/reports")
async def get_reports(
    zone_id: Optional[str] = Query(default=None),
    category_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    reports = state_mgr.list_reports()
    if zone_id:
        reports = [r for r in reports if r.get("location", {}).get("zone_id") == zone_id]
    if category_id:
        reports = [r for r in reports if r.get("incident", {}).get("category_id") == category_id]
    if severity:
        reports = [
            r
            for r in reports
            if (r.get("cra_technical_report", {}).get("nivel_severidad") or "").upper() == severity.upper()
        ]
    if status:
        reports = [r for r in reports if (r.get("status") or "").upper() == status.upper()]
    return {"count": len(reports), "reports": reports}


@app.get("/api/reports/{report_id}")
async def get_single_report(report_id: str) -> Dict[str, Any]:
    rep = state_mgr.get_report_by_id(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Reporte {report_id} no encontrado")
    return rep


@app.post("/api/reports")
async def create_report_from_web(body: CreateReportRequest) -> Dict[str, Any]:
    zone = next((z for z in MANGROVE_ZONES if z["id"] == body.zone_id), MANGROVE_ZONES[0])
    cat = next((c for c in ALERT_CATEGORIES if c["id"] == body.category_id), ALERT_CATEGORIES[0])

    ai_result = await analyst.analyze_report(
        zone_title=zone["title"],
        category_title=cat["title"],
        user_description=body.description,
        image_url=body.image_url,
    )

    if not ai_result.get("es_valida", True):
        return {
            "ok": False,
            "es_valida": False,
            "motivo_rechazo": ai_result.get("motivo_rechazo"),
            "ai_analysis": ai_result,
        }

    pseudo_session = {
        "zone_id": zone["id"],
        "zone_title": zone["title"],
        "zone_coords": zone["coords"],
        "category_id": cat["id"],
        "category_title": cat["title"],
        "description": body.description,
        "image_url": body.image_url,
        "gps": {"lat": body.lat, "lng": body.lng} if (body.lat is not None and body.lng is not None) else None,
    }

    saved = state_mgr.save_report(
        conversation_id="web_portal",
        sender_phone=body.citizen_phone or "web-totem",
        sender_name=body.citizen_name or "Vigia Web / Totem",
        session=pseudo_session,
        ai_report=ai_result,
        source="WEB_TOTEM",
    )

    settings = state_mgr.get_settings()
    if settings.get("auto_notify_email", True):
        subscribers = state_mgr.list_subscribers()
        email_logs = await mailer.dispatch_notifications(saved, subscribers, settings)
        saved = state_mgr.attach_email_logs(saved["id"], email_logs) or saved

    await broadcast_realtime_event("report.created", saved)
    return {"ok": True, "report": saved}


@app.patch("/api/reports/{report_id}")
async def update_report_status(report_id: str, body: UpdateReportRequest) -> Dict[str, Any]:
    updated = state_mgr.update_report(report_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Reporte {report_id} no encontrado")

    conv_id = updated.get("conversation_id")
    if body.notify_citizen_whatsapp and conv_id and conv_id != "web_portal":
        nota_txt = f"\nNota C.R.A.: {body.note}" if body.note else ""
        msg = (
            f"Actualizacion de reporte {updated['id']} (C.R.A.)\n"
            f"Zona: {updated['location']['zone_title']}\n"
            f"Estado: {updated['status']}\n"
            f"Responsable: {updated.get('assigned_to', 'C.R.A.')}"
            f"{nota_txt}"
        )
        await zernio.send_text(conv_id, msg)

    await broadcast_realtime_event("report.updated", updated)
    return {"ok": True, "report": updated}


@app.post("/api/reports/{report_id}/notify")
async def manual_notify_report(report_id: str) -> Dict[str, Any]:
    rep = state_mgr.get_report_by_id(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Reporte {report_id} no encontrado")

    subscribers = state_mgr.list_subscribers()
    settings = state_mgr.get_settings()
    email_logs = await mailer.dispatch_notifications(rep, subscribers, settings)
    updated = state_mgr.attach_email_logs(report_id, email_logs) or rep
    await broadcast_realtime_event("report.updated", updated)
    return {"ok": True, "emails_dispatched": len(email_logs), "deliveries": email_logs}


@app.get("/api/stats")
async def get_dashboard_stats() -> Dict[str, Any]:
    reports = state_mgr.list_reports()
    subs = state_mgr.list_subscribers()

    by_severity = {"CRÍTICA": 0, "ALTA": 0, "MEDIA": 0, "BAJA": 0}
    by_status: Dict[str, int] = {}
    by_zone: Dict[str, int] = {z["id"]: 0 for z in MANGROVE_ZONES}
    by_category: Dict[str, int] = {c["id"]: 0 for c in ALERT_CATEGORIES}
    total_emails_sent = 0

    for r in reports:
        sev = (r.get("cra_technical_report", {}).get("nivel_severidad") or "MEDIA").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1

        st = r.get("status", "PENDIENTE_REVISION_CRA")
        by_status[st] = by_status.get(st, 0) + 1

        zid = r.get("location", {}).get("zone_id")
        if zid:
            by_zone[zid] = by_zone.get(zid, 0) + 1

        cid = r.get("incident", {}).get("category_id")
        if cid:
            by_category[cid] = by_category.get(cid, 0) + 1

        total_emails_sent += len(r.get("email_notifications") or [])

    return {
        "total_reports": len(reports),
        "critical_and_high": by_severity.get("CRÍTICA", 0) + by_severity.get("ALTA", 0),
        "by_severity": by_severity,
        "by_status": by_status,
        "by_zone": by_zone,
        "by_category": by_category,
        "total_emails_dispatched": total_emails_sent,
        "subscribers_summary": {
            "total": len(subs),
            "cra": sum(1 for s in subs if s.get("type") == "CRA"),
            "empresas_b2b": sum(1 for s in subs if s.get("type") == "EMPRESA"),
            "academia": sum(1 for s in subs if s.get("type") == "ACADEMIA"),
        },
    }


@app.get("/api/zones")
async def get_zones_and_totems(whatsapp_phone: str = Query(default="573135865509")) -> Dict[str, Any]:
    enriched_zones = []
    for z in MANGROVE_ZONES:
        prefilled = f"Hola Mokana, estoy reportando desde el Totem de {z['title']}"
        wa_link = f"https://wa.me/{whatsapp_phone}?text={quote(prefilled)}"
        enriched_zones.append(
            {
                **z,
                "totem_code": f"TOTEM-{z['id'].replace('zone_', '').upper()}",
                "whatsapp_qr_nfc_url": wa_link,
                "prefilled_message": prefilled,
            }
        )
    return {
        "whatsapp_bot_number": f"+{whatsapp_phone}",
        "public_api_url": PUBLIC_BASE_URL,
        "zones": enriched_zones,
        "categories": ALERT_CATEGORIES,
    }


@app.get("/api/subscribers")
async def list_subscribers(type: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    subs = state_mgr.list_subscribers()
    if type:
        subs = [s for s in subs if (s.get("type") or "").upper() == type.upper()]
    return {"count": len(subs), "subscribers": subs}


@app.post("/api/subscribers")
async def create_subscriber(body: SubscriberCreateRequest) -> Dict[str, Any]:
    created = state_mgr.add_subscriber(body.model_dump())
    await broadcast_realtime_event("subscriber.created", created)
    return {"ok": True, "subscriber": created}


@app.patch("/api/subscribers/{subscriber_id}")
async def update_subscriber(subscriber_id: str, body: SubscriberUpdateRequest) -> Dict[str, Any]:
    updated = state_mgr.update_subscriber(subscriber_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Suscriptor {subscriber_id} no encontrado")
    return {"ok": True, "subscriber": updated}


@app.delete("/api/subscribers/{subscriber_id}")
async def remove_subscriber(subscriber_id: str) -> Dict[str, Any]:
    ok = state_mgr.delete_subscriber(subscriber_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Suscriptor {subscriber_id} no encontrado")
    return {"ok": True, "deleted_id": subscriber_id}


@app.get("/api/settings/notifications")
async def get_notification_settings() -> Dict[str, Any]:
    s = state_mgr.get_settings()
    masked_key = ""
    raw_key = s.get("resend_api_key") or ""
    if raw_key:
        masked_key = f"{raw_key[:6]}...{raw_key[-4:]}" if len(raw_key) > 10 else "***"
    return {
        "from_email": s.get("from_email"),
        "auto_notify_email": s.get("auto_notify_email", True),
        "notify_whatsapp_on_status_change": s.get("notify_whatsapp_on_status_change", True),
        "has_resend_api_key": bool(raw_key),
        "resend_api_key_masked": masked_key,
    }


@app.put("/api/settings/notifications")
async def update_notification_settings(body: NotificationSettingsUpdate) -> Dict[str, Any]:
    updated = state_mgr.update_settings(body.model_dump(exclude_none=True))
    return {
        "ok": True,
        "from_email": updated.get("from_email"),
        "auto_notify_email": updated.get("auto_notify_email", True),
        "notify_whatsapp_on_status_change": updated.get("notify_whatsapp_on_status_change", True),
        "has_resend_api_key": bool(updated.get("resend_api_key")),
    }
