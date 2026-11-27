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
    version="2.0.0",
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

# Deduplicación de eventos de Zernio
PROCESSED_EVENTS: Set[str] = set()

# Colas de Server-Sent Events (SSE) para empujar eventos en vivo al Panel de Administración
SSE_CLIENTS: List[asyncio.Queue] = []


async def broadcast_realtime_event(event_type: str, data: Dict[str, Any]) -> None:
    """Empuja en tiempo real cualquier reporte nuevo o actualización a todos los paneles web conectados vía SSE."""
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
    notify_citizen_whatsapp: bool = Field(
        default=True,
        description="Si es True y el reporte vino de WhatsApp, le envía un mensaje automático al ciudadano informándole el cambio de estado.",
    )


class SubscriberCreateRequest(BaseModel):
    name: str = Field(description="Nombre del responsable o contacto")
    email: str = Field(description="Correo electrónico donde recibirá los informes y alertas vía Resend")
    organization: str = Field(description="Nombre de la entidad (C.R.A., Universidad, Empresa ESG, etc.)")
    type: str = Field(default="EMPRESA", description="Rol del destinatario: 'CRA' | 'EMPRESA' | 'ACADEMIA'")
    plan: str = Field(default="PRO_DATA_B2B", description="'INSTITUCIONAL' | 'PRO_DATA_B2B' | 'ENTERPRISE_B2B'")
    zones: List[str] = Field(default=["*"], description="Lista de zone_id a suscribir o ['*'] para todas")
    categories: List[str] = Field(default=["*"], description="Lista de category_id a suscribir o ['*'] para todas")
    min_severity: str = Field(default="BAJA", description="Severidad mínima para recibir correo: 'BAJA', 'MEDIA', 'ALTA', 'CRÍTICA'")
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
    resend_api_key: Optional[str] = Field(default=None, description="API Key de Resend (re_...)")
    from_email: Optional[str] = Field(default=None, description="Remitente verificado en Resend, ej. 'Mokaná C.R.A. <alertas@joshual.tech>'")
    auto_notify_email: Optional[bool] = Field(default=None, description="Activar/desactivar envío automático de correos al crear reporte")
    notify_whatsapp_on_status_change: Optional[bool] = Field(default=None)


# =============================================================================
# EXTRACCIÓN Y FLUJO DEL BOT DE WHATSAPP (ZERNIO + GEMINI + RESEND)
# =============================================================================

def _extract_incoming_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae de manera uniforme el texto, clic interactivo, imagen adjunta o ubicación GPS
    del payload `message.received` de Zernio.
    """
    message = payload.get("message") or {}
    account = payload.get("account") or message.get("account") or {}
    conversation = payload.get("conversation") or message.get("conversation") or {}
    sender = message.get("sender") or payload.get("sender") or {}

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
        "sender_name": sender.get("name") or "Ciudadano Vigía",
        "text": text,
        "interactive_id": interactive_id,
        "effective_input": effective_input,
        "image_url": image_url,
        "gps": gps_coords,
    }


async def process_whatsapp_message(payload: Dict[str, Any]) -> None:
    data = _extract_incoming_data(payload)
    conv_id = data["conversation_id"]
    acc_id = data["account_id"]
    if not conv_id:
        logger.warning("Payload sin conversation_id: %s", payload)
        return

    text = data["text"]
    effective_input = data["effective_input"]
    image_url = data["image_url"]
    gps = data["gps"]

    session = state_mgr.get_session(conv_id)

    lower_text = text.lower()
    if lower_text in {"hola", "inicio", "menu", "menú", "nuevo", "reiniciar", "cancelar"} or "totem" in lower_text or "tótem" in lower_text:
        session = state_mgr.reset_session(conv_id)

    if gps:
        session["gps"] = gps
        if session["step"] == ConversationStep.WAITING_OPTIONAL_GPS and session.get("last_report_id"):
            updated = state_mgr.update_report_gps(session["last_report_id"], gps["lat"], gps["lng"])
            if updated:
                await broadcast_realtime_event("report.updated", updated)
            await zernio.send_text(
                conv_id,
                f"📍 *¡Ubicación GPS exacta registrada!* Se actualizó el radicado *{session['last_report_id']}* "
                "en el Centro de Monitoreo de la C.R.A.\n\nEscribe *Hola* cuando desees realizar un nuevo reporte.",
                account_id=acc_id,
            )
            state_mgr.reset_session(conv_id)
            return

    # PASO 1: Detectar Zona del Manglar (Automático por Tótem QR/NFC o por Lista Interactiva)
    if session["step"] == ConversationStep.WAITING_ZONE:
        detected_zone = state_mgr.detect_zone_from_text(effective_input) or state_mgr.detect_zone_from_text(text)
        if detected_zone:
            session["zone_id"] = detected_zone["id"]
            session["zone_title"] = detected_zone["title"]
            session["zone_coords"] = detected_zone["coords"]
            session["step"] = ConversationStep.WAITING_CATEGORY
            await zernio.send_category_list(conv_id, detected_zone["title"], account_id=acc_id)
            return
        else:
            await zernio.send_zone_list(conv_id, account_id=acc_id)
            return

    # PASO 2: Selección de la Categoría de Alerta
    if session["step"] == ConversationStep.WAITING_CATEGORY:
        maybe_zone = state_mgr.detect_zone_from_text(effective_input)
        if maybe_zone and effective_input.startswith("zone_"):
            session["zone_id"] = maybe_zone["id"]
            session["zone_title"] = maybe_zone["title"]
            session["zone_coords"] = maybe_zone["coords"]
            await zernio.send_category_list(conv_id, maybe_zone["title"], account_id=acc_id)
            return

        detected_cat = state_mgr.detect_category_from_text(effective_input)
        if detected_cat:
            session["category_id"] = detected_cat["id"]
            session["category_title"] = detected_cat["title"]
            session["step"] = ConversationStep.WAITING_DESCRIPTION
            await zernio.send_text(
                conv_id,
                f"✅ Has seleccionado: *{detected_cat['title']}* en *{session['zone_title']}*.\n\n"
                "📝 *Paso 2 de 3:* Por favor escribe una *descripción breve* de lo que estás observando "
                "(qué ocurre exactamente, magnitud o detalles clave para que nuestra IA valide la coherencia).",
                account_id=acc_id,
            )
            return
        else:
            await zernio.send_category_list(conv_id, session["zone_title"] or "Manglar del Atlántico", account_id=acc_id)
            return

    # PASO 3: Recibir Descripción Breve en Texto
    if session["step"] == ConversationStep.WAITING_DESCRIPTION:
        maybe_cat = state_mgr.detect_category_from_text(effective_input)
        if maybe_cat and effective_input.startswith("alert_"):
            session["category_id"] = maybe_cat["id"]
            session["category_title"] = maybe_cat["title"]
            await zernio.send_text(
                conv_id,
                f"✅ Categoría actualizada a: *{maybe_cat['title']}*.\n\n"
                "📝 Por favor escribe una *descripción breve* de lo que estás observando:",
                account_id=acc_id,
            )
            return

        if image_url and len(text) >= 5:
            session["description"] = text
            session["image_url"] = image_url
            session["step"] = ConversationStep.WAITING_PHOTO
        elif len(text) >= 4 and not image_url:
            session["description"] = text
            session["step"] = ConversationStep.WAITING_PHOTO
            await zernio.send_text(
                conv_id,
                "📸 *Paso 3 de 3 (Verificación IA):* ¡Descripción registrada!\n\n"
                "Ahora toma o adjunta una *FOTO* del lugar para verificar que la información concuerda "
                "y generar el informe técnico oficial para la C.R.A.\n\n"
                "_(Opcional: También puedes adjuntar tu pin de ubicación GPS 📍)_.",
                account_id=acc_id,
            )
            return
        else:
            await zernio.send_text(
                conv_id,
                "📝 Por favor escribe primero una *descripción breve en texto* (al menos una frase corta) "
                "contando qué estás viendo en el manglar:",
                account_id=acc_id,
            )
            return

    # PASO 4: Recibir Foto -> Validar Autenticidad/Coherencia con Gemini -> Informe CRA + Correos Resend
    if session["step"] == ConversationStep.WAITING_PHOTO:
        if not image_url:
            if gps:
                await zernio.send_text(
                    conv_id,
                    "📍 Ubicación GPS guardada. Ahora por favor envíame la *FOTO* 📸 de evidencia para validar el reporte.",
                    account_id=acc_id,
                )
                return

            if text:
                session["description"] = f"{session['description']}. {text}"
            await zernio.send_text(
                conv_id,
                "📸 Para completar el reporte y verificar su autenticidad, por favor adjunta una *FOTO* de la situación.",
                account_id=acc_id,
            )
            return

        session["image_url"] = image_url
        if text and text != session.get("description"):
            session["description"] = f"{session['description']} ({text})"

        await zernio.send_text(
            conv_id,
            "⏳ *Analizando evidencia con IA Multimodal (Gemini)...*\n"
            "Verificando autenticidad fotográfica, coherencia con tu descripción y clasificando el nivel de riesgo para la C.R.A.",
            account_id=acc_id,
        )

        ai_result = await analyst.analyze_report(
            zone_title=session["zone_title"],
            category_title=session["category_title"],
            user_description=session["description"],
            image_url=session["image_url"],
        )

        if not ai_result.get("es_valida", True):
            motivo = ai_result.get("motivo_rechazo") or (
                "La fotografía enviada no parece coincidir con la descripción o con una situación del manglar."
            )
            await zernio.send_text(
                conv_id,
                f"⚠️ *No pudimos validar la evidencia*\n\n"
                f"{motivo}\n\n"
                "📸 Por favor envía una *nueva foto real* que concuerde con tu descripción, "
                "o escribe *Reiniciar* si deseas cambiar el tipo de alerta.",
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

        # Disparar correos electrónicos vía Resend a Responsables C.R.A. y Suscriptores (Empresas / Academia)
        settings = state_mgr.get_settings()
        email_logs: List[Dict[str, Any]] = []
        if settings.get("auto_notify_email", True):
            subscribers = state_mgr.list_subscribers()
            email_logs = await mailer.dispatch_notifications(saved_record, subscribers, settings)
            saved_record = state_mgr.attach_email_logs(saved_record["id"], email_logs) or saved_record

        # Emitir evento en vivo al Panel de Administración
        await broadcast_realtime_event("report.created", saved_record)

        cra_rep = saved_record["cra_technical_report"]
        notified_count = len(email_logs)
        parametros_txt = ", ".join(cra_rep.get("parametros_fisicoquimicos_alterados") or [])

        final_message = (
            f"✅ *¡REPORTE VERIFICADO Y NOTIFICADO A LA C.R.A.!*\n"
            f"📋 *Radicado:* `{saved_record['id']}`\n"
            f"📍 *Zona:* {session['zone_title']}\n"
            f"🚨 *Prioridad IA:* *{cra_rep['nivel_severidad']}* (Riesgo: {cra_rep['indice_riesgo_ambiental']}/100 • Confianza: {cra_rep['puntaje_confianza_ia']}%)\n"
            f"🏛️ *Asignado a:* {cra_rep['dependencia_responsable_cra']} (SLA: {cra_rep['sla_tiempo_respuesta_horas']}h)\n\n"
            f"📄 *INFORME TÉCNICO C.R.A.:*\n"
            f"• *Clasificación:* {cra_rep['subcategoria_tecnica_cra']}\n"
            f"• *Coherencia Foto/Relato:* {cra_rep['coherencia_foto_descripcion']}\n"
            f"• *Diagnóstico Físico-Químico:* {cra_rep['hipotesis_ambiental_quimica']}\n"
            f"• *Parámetros Críticos:* {parametros_txt}\n"
            f"• *Acción Recomendada:* {cra_rep['accion_recomendada_cra']}\n\n"
            f"📧 *Notificaciones enviadas:* {notified_count} entidades notificadas por correo electrónico (C.R.A. y Red Científica/Empresarial).\n\n"
            f"_{ai_result.get('mensaje_ciudadano', 'Gracias por proteger los manglares del Atlántico.')}_\n\n"
            "📍 _(Opcional)_: Si deseas añadir tu *pin de ubicación GPS exacta*, envíalo ahora con el clip de WhatsApp, "
            "o escribe *NUEVO* para otro reporte."
        )

        session["step"] = ConversationStep.WAITING_OPTIONAL_GPS
        await zernio.send_text(conv_id, final_message, account_id=acc_id)
        return

    # PASO 5: Si escribe de nuevo después de terminar un reporte
    if session["step"] == ConversationStep.WAITING_OPTIONAL_GPS:
        session = state_mgr.reset_session(conv_id)
        detected_zone = state_mgr.detect_zone_from_text(effective_input) or state_mgr.detect_zone_from_text(text)
        if detected_zone:
            session["zone_id"] = detected_zone["id"]
            session["zone_title"] = detected_zone["title"]
            session["zone_coords"] = detected_zone["coords"]
            session["step"] = ConversationStep.WAITING_CATEGORY
            await zernio.send_category_list(conv_id, detected_zone["title"], account_id=acc_id)
        else:
            await zernio.send_zone_list(conv_id, account_id=acc_id)


# =============================================================================
# ENDPOINTS REST & TIEMPO REAL PARA EL PANEL DE ADMINISTRACIÓN
# =============================================================================

@app.get("/")
async def health_check() -> Dict[str, Any]:
    reports = state_mgr.list_reports()
    subs = state_mgr.list_subscribers()
    return {
        "service": "Mokaná WhatsApp Bot, C.R.A. Early Warning API & B2B Data Hub",
        "version": "2.0.0",
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
        logger.info("Recibido evento de prueba webhook.test de Zernio exitosamente.")
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
    """
    Stream SSE (Server-Sent Events) para que el Frontend Administrativo reciba nuevos reportes
    y actualizaciones de estado en tiempo real sin necesidad de recargar la página.
    """
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
    zone_id: Optional[str] = Query(default=None, description="Filtrar por zone_id"),
    category_id: Optional[str] = Query(default=None, description="Filtrar por category_id"),
    severity: Optional[str] = Query(default=None, description="Filtrar por severidad: BAJA, MEDIA, ALTA, CRÍTICA"),
    status: Optional[str] = Query(default=None, description="Filtrar por estado de gestión C.R.A."),
) -> Dict[str, Any]:
    """Lista todos los reportes ciudadanos e informes técnicos C.R.A. con soporte de filtros para el Panel de Administración."""
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
    """Obtiene el detalle completo de un reporte y su historial de notificaciones por correo."""
    rep = state_mgr.get_report_by_id(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Reporte {report_id} no encontrado")
    return rep


@app.post("/api/reports")
async def create_report_from_web(body: CreateReportRequest) -> Dict[str, Any]:
    """
    Permite crear un reporte directamente desde el Portal Web del Tótem o desde el Panel de Administración.
    Pasa por la misma validación y clasificación técnica de Gemini y dispara los correos vía Resend.
    """
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
        sender_name=body.citizen_name or "Vigía Web / Tótem",
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
    """
    Permite al Panel de Administración de la C.R.A. cambiar el estado de un reporte (ej. 'BRIGADA_DESPACHADA', 'RESUELTO'),
    asignar responsable, agregar notas de bitácora y notificar automáticamente al ciudadano por WhatsApp.
    """
    updated = state_mgr.update_report(report_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Reporte {report_id} no encontrado")

    # Si vino de WhatsApp y notify_citizen_whatsapp es True, le avisamos al ciudadano del avance de la C.R.A.
    conv_id = updated.get("conversation_id")
    if body.notify_citizen_whatsapp and conv_id and conv_id != "web_portal":
        nota_txt = f"\n📝 *Observación C.R.A.:* {body.note}" if body.note else ""
        msg = (
            f"🔔 *Actualización de tu reporte `{updated['id']}` (C.R.A.)*\n\n"
            f"• *Zona:* {updated['location']['zone_title']}\n"
            f"• *Nuevo Estado:* *{updated['status']}*\n"
            f"• *Responsable:* {updated.get('assigned_to', 'C.R.A.')}"
            f"{nota_txt}\n\n"
            "_Gracias por ser parte de la red de vigías de Mokaná._"
        )
        await zernio.send_text(conv_id, msg)

    await broadcast_realtime_event("report.updated", updated)
    return {"ok": True, "report": updated}


@app.post("/api/reports/{report_id}/notify")
async def manual_notify_report(report_id: str) -> Dict[str, Any]:
    """Permite desde el Frontend reenviar o disparar manualmente las notificaciones por correo (Resend) de un reporte."""
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
    """Métricas ejecutivas listas para las tarjetas superiores y gráficas del Panel de Administración."""
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
    """Devuelve las 5 zonas de manglar del Atlántico, categorías de alerta y enlaces QR/NFC exactos para cada Tótem."""
    enriched_zones = []
    for z in MANGROVE_ZONES:
        prefilled = f"Hola Mokaná, estoy reportando desde el Tótem de {z['title']}"
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


# =============================================================================
# ENDPOINTS DE SUSCRIPTORES (C.R.A. + VENTA DE DATOS A EMPRESAS Y ACADEMIA)
# =============================================================================

@app.get("/api/subscribers")
async def list_subscribers(type: Optional[str] = Query(default=None, description="CRA | EMPRESA | ACADEMIA")) -> Dict[str, Any]:
    """Lista los responsables de la C.R.A. y los clientes B2B (Empresas y Academia) que reciben informes por correo."""
    subs = state_mgr.list_subscribers()
    if type:
        subs = [s for s in subs if (s.get("type") or "").upper() == type.upper()]
    return {"count": len(subs), "subscribers": subs}


@app.post("/api/subscribers")
async def create_subscriber(body: SubscriberCreateRequest) -> Dict[str, Any]:
    """Crea desde el Frontend un nuevo destinatario de correo (Responsable C.R.A., Empresa cliente B2B o Universidad/Academia)."""
    created = state_mgr.add_subscriber(body.model_dump())
    await broadcast_realtime_event("subscriber.created", created)
    return {"ok": True, "subscriber": created}


@app.patch("/api/subscribers/{subscriber_id}")
async def update_subscriber(subscriber_id: str, body: SubscriberUpdateRequest) -> Dict[str, Any]:
    """Actualiza filtros de zonas, categorías, severidad mínima o estado activo de un suscriptor desde el Frontend."""
    updated = state_mgr.update_subscriber(subscriber_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Suscriptor {subscriber_id} no encontrado")
    return {"ok": True, "subscriber": updated}


@app.delete("/api/subscribers/{subscriber_id}")
async def remove_subscriber(subscriber_id: str) -> Dict[str, Any]:
    """Elimina un suscriptor de correo desde el Frontend."""
    ok = state_mgr.delete_subscriber(subscriber_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Suscriptor {subscriber_id} no encontrado")
    return {"ok": True, "deleted_id": subscriber_id}


# =============================================================================
# ENDPOINTS DE CONFIGURACIÓN DE CORREO (RESEND) DESDE EL FRONTEND
# =============================================================================

@app.get("/api/settings/notifications")
async def get_notification_settings() -> Dict[str, Any]:
    """Obtiene la configuración actual de notificaciones por correo (Resend) para mostrar en el Frontend."""
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
    """Permite configurar la API Key de Resend, el correo remitente y las reglas automáticas directamente desde el Frontend."""
    updated = state_mgr.update_settings(body.model_dump(exclude_none=True))
    return {
        "ok": True,
        "from_email": updated.get("from_email"),
        "auto_notify_email": updated.get("auto_notify_email", True),
        "notify_whatsapp_on_status_change": updated.get("notify_whatsapp_on_status_change", True),
        "has_resend_api_key": bool(updated.get("resend_api_key")),
    }
