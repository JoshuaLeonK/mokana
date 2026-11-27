import asyncio
import csv
import html
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
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

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

zernio = ZernioClient()
analyst = GeminiAnalyst()
state_mgr = StateManager()
mailer = EmailNotifier()

PROCESSED_EVENTS: Set[str] = set()
SSE_CLIENTS: List[asyncio.Queue] = []

# =============================================================================
# CIBERSEGURIDAD: RATE LIMITING, COOLDOWN DE 20s Y PROTECCIÓN ANTI-FLOOD
# =============================================================================
REPORT_COOLDOWN_SECONDS = 20.0
FLOOD_WINDOW_SECONDS = 20.0
MAX_MESSAGES_PER_WINDOW = 5

USER_RATE_STATE: Dict[str, Dict[str, Any]] = {}


def _sanitize_text(raw: str, max_len: int = 500) -> str:
    """Limpia etiquetas HTML/JS y caracteres de control para evitar XSS o inyección en correos y dashboard."""
    if not raw:
        return ""
    cleaned = re.sub(r"<[^>]*>", "", raw)
    cleaned = html.escape(cleaned, quote=False)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def _check_user_security_limits(user_key: str, is_heavy_action: bool = False) -> Optional[int]:
    """
    Evalúa límites de ciberseguridad por usuario (conversación/teléfono):
    1. Si `is_heavy_action` (análisis de reporte/imagen), exige mínimo 20 segundos desde el último análisis.
    2. Si el usuario envía más de 5 mensajes en 20 segundos (ataque de flood/bot), bloquea por 20 segundos.
    Retorna `None` si está permitido, o el número de segundos restantes de espera si está bloqueado.
    """
    now = time.time()
    st = USER_RATE_STATE.setdefault(
        user_key,
        {"msg_timestamps": [], "last_heavy_ts": 0.0, "last_warn_ts": 0.0},
    )

    # Limpiar timestamps fuera de la ventana de 20s
    st["msg_timestamps"] = [ts for ts in st["msg_timestamps"] if now - ts < FLOOD_WINDOW_SECONDS]
    st["msg_timestamps"].append(now)

    # 1. Protección contra ráfaga de mensajes (bot flood)
    if len(st["msg_timestamps"]) > MAX_MESSAGES_PER_WINDOW:
        wait_s = max(1, int(FLOOD_WINDOW_SECONDS - (now - st["msg_timestamps"][0])))
        return wait_s

    # 2. Cooldown estricto de 20 segundos entre reportes / análisis de imagen
    if is_heavy_action:
        elapsed = now - st["last_heavy_ts"]
        if elapsed < REPORT_COOLDOWN_SECONDS:
            return max(1, int(REPORT_COOLDOWN_SECONDS - elapsed))
        st["last_heavy_ts"] = now

    return None


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
        media_id = att.get("mediaId") or att.get("id") or (att.get("payload") or {}).get("id")
        if not url and media_id and ("image" in att_type or not att_type):
            url = f"https://zernio.com/api/v1/whatsapp/media/{media_id}"
        if url and ("image" in att_type or "media" in url.lower() or not att_type or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            image_url = url
            break

    if not image_url and message.get("mediaUrl"):
        image_url = message.get("mediaUrl")
    if not image_url and message.get("mediaId"):
        image_url = f"https://zernio.com/api/v1/whatsapp/media/{message.get('mediaId')}"

    gps_coords: Optional[Dict[str, Any]] = None
    loc = (
        metadata.get("location")
        or message.get("location")
        or payload.get("location")
        or {}
    )
    if not loc and attachments:
        for att in attachments:
            if (att.get("type") or "").lower() == "location":
                loc = att.get("payload") or att
                break
    if loc and ("latitude" in loc or "lat" in loc):
        try:
            gps_coords = {
                "lat": float(loc.get("latitude") if loc.get("latitude") is not None else loc.get("lat")),
                "lng": float(loc.get("longitude") if loc.get("longitude") is not None else loc.get("lng")),
                "name": loc.get("name"),
                "address": loc.get("address"),
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
        "Procesando y verificando evidencia...",
        account_id=acc_id,
    )

    ai_result = await analyst.analyze_report(
        zone_title=session["zone_title"],
        category_title=session["category_title"],
        user_description=session["description"],
        image_url=session["image_url"],
    )

    # Actualizar la URL de la imagen con la copia pública guardada en nuestro servidor (/static/uploads/...)
    if ai_result.get("saved_image_url"):
        session["image_url"] = ai_result["saved_image_url"]

    # Si el usuario no había tocado el desplegable de anomalías, usamos la categoría inferida
    if session["category_title"] == "Determinado por IA" or session["category_id"] == "alert_otro":
        inferred_id = ai_result.get("categoria_inferida_id")
        inferred_cat = next((c for c in ALERT_CATEGORIES if c["id"] == inferred_id), None)
        if inferred_cat:
            session["category_id"] = inferred_cat["id"]
            session["category_title"] = inferred_cat["title"]

    if not ai_result.get("es_valida", True):
        motivo = ai_result.get("motivo_rechazo") or "La imagen enviada no corresponde a una evidencia real de la anomalia reportada."
        session["image_url"] = None
        await zernio.send_text(
            conv_id,
            f"Reporte rechazado en verificacion: {motivo}\nPor favor envia una fotografia real tomada en el manglar.",
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
        f"Informe: {cra_rep['titulo_hallazgo']}. {cra_rep['accion_recomendada_cra']}\n\n"
        f"Opcional: Toca el boton de abajo para enviar tu ubicacion GPS exacta del incidente."
    )

    state_mgr.reset_session(conv_id)
    session_after = state_mgr.get_session(conv_id)
    session_after["last_report_id"] = saved_record["id"]
    session_after["step"] = ConversationStep.WAITING_OPTIONAL_GPS

    # Enviamos el mensaje de cierre con el botón interactivo nativo de WhatsApp "Enviar ubicación"
    await zernio.send_location_request(conv_id, final_message, account_id=acc_id)


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

    user_key = f"{data['sender_phone']}:{conv_id}"
    text = _sanitize_text(data["text"])
    interactive_id = data["interactive_id"]
    effective_input = data["effective_input"]
    image_url = data["image_url"]
    gps = data["gps"]

    # Control de ciberseguridad: bloqueo anti-flood y cooldown de 20 segundos entre reportes con imagen
    wait_seconds = _check_user_security_limits(user_key, is_heavy_action=bool(image_url))
    if wait_seconds is not None:
        st = USER_RATE_STATE.get(user_key, {})
        now = time.time()
        # Solo enviamos 1 mensaje de aviso cada 10s para que un bot atacante no provoque spam de respuestas
        if now - st.get("last_warn_ts", 0.0) >= 10.0:
            st["last_warn_ts"] = now
            await zernio.send_text(
                conv_id,
                f"Control de seguridad: por favor espera {wait_seconds} segundos antes de enviar una nueva solicitud.",
                account_id=acc_id,
            )
        return

    session = state_mgr.get_session(conv_id)
    lower_text = text.lower()

    # 1. Comandos de saludo/reinicio cuando NO mencionan ninguna zona ni traen imagen
    detected_zone_in_text = state_mgr.detect_zone_from_text(interactive_id or "") or state_mgr.detect_zone_from_text(text)

    if lower_text in {"hola", "inicio", "menu", "menú", "nuevo", "reiniciar", "cancelar"} and not image_url:
        session = state_mgr.reset_session(conv_id)
        await zernio.send_zone_list(conv_id, account_id=acc_id)
        return

    # Si envía un Pin GPS (antes o después de finalizar el reporte)
    if gps:
        session["gps"] = gps
        target_report_id = session.get("last_report_id")
        # Si la sesión se reinició pero el usuario acaba de enviar un reporte hace poco, buscamos su último reporte por conversation_id
        if not target_report_id:
            for existing_rep in state_mgr.list_reports():
                if existing_rep.get("conversation_id") == conv_id:
                    target_report_id = existing_rep["id"]
                    break

        if target_report_id:
            updated = state_mgr.update_report_gps(
                target_report_id,
                gps["lat"],
                gps["lng"],
                location_name=gps.get("name"),
                address=gps.get("address"),
            )
            if updated:
                await broadcast_realtime_event("report.updated", updated)
            await zernio.send_text(
                conv_id,
                f"Coordenadas GPS registradas ({gps['lat']:.5f}, {gps['lng']:.5f}) en el expediente {target_report_id}.",
                account_id=acc_id,
            )
            return

    # 2. ¿El mensaje es para indicar/seleccionar la ZONA del manglar?
    # Ejemplos: "hola estoy en mallorquin", link del Tótem QR/NFC, o clic en el desplegable de zonas
    is_totem_or_location_greeting = any(
        phrase in lower_text
        for phrase in ("totem", "tótem", "reportando desde", "estoy en", "hola")
    )
    has_incident_keywords = state_mgr.detect_category_from_text(text) is not None

    if detected_zone_in_text and (
        (interactive_id and interactive_id.startswith("zone_"))
        or session["step"] == ConversationStep.WAITING_ZONE
        or (is_totem_or_location_greeting and not image_url and not has_incident_keywords)
    ):
        # Si venía de un saludo tipo "hola estoy en mallorquin" sin foto ni anomalía, reiniciamos limpio en esa zona
        if is_totem_or_location_greeting and not image_url and not has_incident_keywords:
            session = state_mgr.reset_session(conv_id)

        session["zone_id"] = detected_zone_in_text["id"]
        session["zone_title"] = detected_zone_in_text["title"]
        session["zone_coords"] = detected_zone_in_text["coords"]
        session["step"] = ConversationStep.WAITING_CATEGORY

        # Solo si en ese mismo mensaje ya mandó una FOTO + una descripción real de anomalía, analiza directo
        if image_url and has_incident_keywords:
            session["image_url"] = image_url
            session["description"] = text
            await _finalize_and_analyze_report(conv_id, acc_id, data, session)
            return

        # De lo contrario, pasa al Paso 2: Mostrar el desplegable de Anomalías
        await zernio.send_category_list(conv_id, detected_zone_in_text["title"], account_id=acc_id)
        return

    # 3. ¿El usuario seleccionó una Anomalía del desplegable?
    detected_cat = None
    if interactive_id and interactive_id.startswith("alert_"):
        detected_cat = state_mgr.detect_category_from_text(interactive_id)
    elif not image_url:
        for cat in ALERT_CATEGORIES:
            if text.strip().lower() == cat["title"].lower() or text.strip().lower() == cat["id"].lower():
                detected_cat = cat
                break

    if detected_cat:
        session["category_id"] = detected_cat["id"]
        session["category_title"] = detected_cat["title"]
        session["step"] = ConversationStep.WAITING_DESCRIPTION

        if session.get("image_url") and session.get("description"):
            await _finalize_and_analyze_report(conv_id, acc_id, data, session)
            return

        await zernio.send_text(
            conv_id,
            f"Anomalia: {detected_cat['title']}. Envia una foto y una descripcion breve de lo que ocurre.",
            account_id=acc_id,
        )
        return

    # 4. Si todavía estaba en WAITING_CATEGORY y escribió texto normal sin haber elegido del desplegable (ni mandó foto),
    # recordarle usar el desplegable de anomalías a menos que ya esté describiendo una anomalía con foto.
    if session["step"] == ConversationStep.WAITING_CATEGORY and not image_url and not session.get("category_id"):
        if has_incident_keywords and len(text.split()) >= 4:
            # Escribió una descripción clara de anomalía ("hay peces muertos en la orilla"): asignamos la categoría detectada y pedimos la foto
            inferred_cat = state_mgr.detect_category_from_text(text)
            if inferred_cat:
                session["category_id"] = inferred_cat["id"]
                session["category_title"] = inferred_cat["title"]
            session["description"] = text
            session["step"] = ConversationStep.WAITING_PHOTO
            await zernio.send_text(
                conv_id,
                "Descripcion recibida. Envia la foto de evidencia para analizar el reporte.",
                account_id=acc_id,
            )
            return
        else:
            await zernio.send_category_list(conv_id, session["zone_title"] or "Manglar del Atlantico", account_id=acc_id)
            return

    # 5. Captura de Imagen y/o Texto (en un solo mensaje o en mensajes separados)
    if image_url:
        session["image_url"] = image_url

    if text and not is_totem_or_location_greeting:
        if not session.get("zone_id") and detected_zone_in_text:
            session["zone_id"] = detected_zone_in_text["id"]
            session["zone_title"] = detected_zone_in_text["title"]
            session["zone_coords"] = detected_zone_in_text["coords"]

        if session.get("description") and text not in session["description"]:
            session["description"] = f"{session['description']}. {text}"
        else:
            session["description"] = text
    elif text and image_url:
        # Si mandó foto con caption que incluye saludo ("hola estoy en mallorquin y hay espuma"), guardamos el caption como descripción
        session["description"] = text

    # 6. Si ya tenemos IMAGEN + TEXTO (hayan llegado juntos o separados), analizar de inmediato sin pedir más nada
    if session.get("image_url") and session.get("description"):
        await _finalize_and_analyze_report(conv_id, acc_id, data, session)
        return

    # 7. Si solo llegó la IMAGEN (sin texto todavía), pedir únicamente la descripción breve
    if session.get("image_url") and not session.get("description"):
        session["step"] = ConversationStep.WAITING_DESCRIPTION
        await zernio.send_text(
            conv_id,
            "Foto recibida. Escribe una descripcion breve de lo que ocurre para procesarla.",
            account_id=acc_id,
        )
        return

    # 8. Si solo llegó el TEXTO (después de haber seleccionado la anomalía) pero falta la imagen, pedir únicamente la foto
    if session.get("description") and not session.get("image_url"):
        session["step"] = ConversationStep.WAITING_PHOTO
        await zernio.send_text(
            conv_id,
            "Descripcion recibida. Envia la foto de evidencia para analizar el reporte.",
            account_id=acc_id,
        )
        return

    # 9. Por defecto: si no hay zona, mostrar desplegable de zonas; si ya hay zona, mostrar desplegable de anomalías
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


@app.get("/api/reports/export")
async def export_open_data_report(
    format: str = Query(
        default="csv",
        description="Formato de datos abiertos: 'csv' (Excel / Datos.gov.co), 'geojson' (SIG / ArcGIS / QGIS) o 'json' (Informe General Completo)",
    ),
    zone_id: Optional[str] = Query(default=None, description="Filtrar opcionalmente por zona"),
    severity: Optional[str] = Query(default=None, description="Filtrar opcionalmente por severidad"),
) -> Response:
    """
    Descarga el Informe General de Monitoreo de Manglares del Atlántico en formatos estándar de Datos Abiertos:
    - `csv`: Archivo CSV (UTF-8 con BOM compatible con Excel, Power BI, R, Pandas y portal Datos Abiertos Colombia).
    - `geojson`: Colección geográfica RFC 7946 lista para importar en QGIS, ArcGIS (C.R.A. / INVEMAR), Mapbox o Leaflet.
    - `json`: Dataset estructurado completo con resumen ejecutivo, metadatos de esquema y todos los expedientes.
    """
    reports = state_mgr.list_reports()
    if zone_id:
        reports = [r for r in reports if r.get("location", {}).get("zone_id") == zone_id]
    if severity:
        reports = [
            r
            for r in reports
            if (r.get("cra_technical_report", {}).get("nivel_severidad") or "").upper() == severity.upper()
        ]

    fmt = format.strip().lower()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

    # 1. FORMATO CSV (Estándar Datos Abiertos / Excel)
    if fmt == "csv":
        output = io.StringIO()
        # BOM UTF-8 para que Microsoft Excel en español abra tildes y caracteres especiales sin errores
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "radicado_id",
            "fecha_creacion_utc",
            "fecha_actualizacion_utc",
            "estado_gestion_cra",
            "dependencia_asignada",
            "zona_id",
            "zona_manglar",
            "latitud",
            "longitud",
            "gps_exacto_usuario",
            "categoria_id",
            "categoria_reportada",
            "subcategoria_tecnica_cra",
            "nivel_severidad",
            "indice_riesgo_0_100",
            "sla_respuesta_horas",
            "titulo_hallazgo",
            "descripcion_ciudadano",
            "hallazgo_visual_campo",
            "diagnostico_fisicoquimico",
            "parametros_comprometidos",
            "especies_en_riesgo",
            "normativa_aplicable",
            "accion_recomendada_cra",
            "evidencia_fotografica_url",
            "etiquetas_datos_abiertos",
        ])

        for r in reports:
            loc = r.get("location", {})
            inc = r.get("incident", {})
            cra = r.get("cra_technical_report", {})
            writer.writerow([
                r.get("id", ""),
                r.get("created_at", ""),
                r.get("updated_at", ""),
                r.get("status", ""),
                r.get("assigned_to", ""),
                loc.get("zone_id", ""),
                loc.get("zone_title", ""),
                loc.get("lat", ""),
                loc.get("lng", ""),
                "SI" if loc.get("has_exact_gps") else "NO",
                inc.get("category_id", ""),
                inc.get("category_title", ""),
                cra.get("subcategoria_tecnica_cra", ""),
                cra.get("nivel_severidad", ""),
                cra.get("indice_riesgo_ambiental", ""),
                cra.get("sla_tiempo_respuesta_horas", ""),
                cra.get("titulo_hallazgo", ""),
                inc.get("citizen_description", ""),
                cra.get("hallazgo_visual", ""),
                cra.get("hipotesis_ambiental_quimica", ""),
                "; ".join(cra.get("parametros_fisicoquimicos_alterados") or []),
                "; ".join(cra.get("especies_mangle_riesgo") or []),
                cra.get("normativa_aplicable", ""),
                cra.get("accion_recomendada_cra", ""),
                inc.get("image_url", ""),
                " ".join(cra.get("etiquetas_datos") or []),
            ])

        csv_bytes = output.getvalue().encode("utf-8")
        filename = f"mokana_informe_general_manglares_{timestamp_str}.csv"
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # 2. FORMATO GEOJSON (Estándar SIG / ArcGIS / QGIS RFC 7946)
    if fmt == "geojson":
        features = []
        for r in reports:
            loc = r.get("location", {})
            inc = r.get("incident", {})
            cra = r.get("cra_technical_report", {})
            lat = float(loc.get("lat") or 11.0458)
            lng = float(loc.get("lng") or -74.8461)
            features.append({
                "type": "Feature",
                "id": r.get("id"),
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat],
                },
                "properties": {
                    "id": r.get("id"),
                    "created_at": r.get("created_at"),
                    "status": r.get("status"),
                    "assigned_to": r.get("assigned_to"),
                    "zone_id": loc.get("zone_id"),
                    "zone_title": loc.get("zone_title"),
                    "has_exact_gps": loc.get("has_exact_gps", False),
                    "category_id": inc.get("category_id"),
                    "category_title": inc.get("category_title"),
                    "citizen_description": inc.get("citizen_description"),
                    "image_url": inc.get("image_url"),
                    "nivel_severidad": cra.get("nivel_severidad"),
                    "indice_riesgo_ambiental": cra.get("indice_riesgo_ambiental"),
                    "subcategoria_tecnica_cra": cra.get("subcategoria_tecnica_cra"),
                    "sla_tiempo_respuesta_horas": cra.get("sla_tiempo_respuesta_horas"),
                    "titulo_hallazgo": cra.get("titulo_hallazgo"),
                    "hipotesis_ambiental_quimica": cra.get("hipotesis_ambiental_quimica"),
                    "parametros_fisicoquimicos_alterados": cra.get("parametros_fisicoquimicos_alterados", []),
                    "especies_mangle_riesgo": cra.get("especies_mangle_riesgo", []),
                    "normativa_aplicable": cra.get("normativa_aplicable"),
                    "accion_recomendada_cra": cra.get("accion_recomendada_cra"),
                },
            })

        geojson_payload = {
            "type": "FeatureCollection",
            "metadata": {
                "dataset": "Sistema Mokana - Monitoreo en Tiempo Real de Manglares del Atlántico",
                "authority": "C.R.A. - Corporación Autónoma Regional del Atlántico",
                "crs": "EPSG:4326 (WGS84)",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_features": len(features),
            },
            "features": features,
        }
        filename = f"mokana_manglares_atlantico_{timestamp_str}.geojson"
        return Response(
            content=json.dumps(geojson_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            media_type="application/geo+json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # 3. FORMATO JSON (Dataset Completo de Datos Abiertos + Resumen General)
    stats = await get_dashboard_stats()
    open_data_json = {
        "metadata": {
            "dataset_title": "Informe General de Monitoreo y Alertas Tempranas en Manglares del Atlántico — Sistema Mokana",
            "organization": "C.R.A. (Corporación Autónoma Regional del Atlántico) & Red Mokana",
            "license": "Open Data Commons Attribution License (ODC-By) / Datos Abiertos Colombia",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": len(reports),
        },
        "executive_summary": stats,
        "zones_catalog": MANGROVE_ZONES,
        "records": reports,
    }
    filename = f"mokana_informe_general_{timestamp_str}.json"
    return Response(
        content=json.dumps(open_data_json, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@app.post("/api/settings/test-email")
async def test_email_dispatch(to_email: str = Query(default="adalbertoleonk@gmail.com")) -> Dict[str, Any]:
    """Dispara un correo de prueba inmediato con la plantilla de Mokana para verificar la conexión con Resend."""
    sample_report = {
        "id": "MKN-2026-TEST",
        "created_at": "2026-11-27T20:20:00Z",
        "location": {
            "zone_id": "zone_mallorquin",
            "zone_title": "Cienaga de Mallorquin",
            "lat": 11.0458,
            "lng": -74.8461,
        },
        "incident": {
            "category_id": "alert_erosion",
            "category_title": "Erosion o perdida suelo",
            "citizen_description": "Prueba de sistema Mokana: socavacion y perdida de sedimento en la zona de raices de mangle.",
            "image_url": f"{PUBLIC_BASE_URL}/static/mokana-logo.jpg",
        },
        "cra_technical_report": {
            "es_valida": True,
            "puntaje_confianza_ia": 96,
            "nivel_severidad": "ALTA",
            "indice_riesgo_ambiental": 84,
            "subcategoria_tecnica_cra": "Erosion Costera y Desestabilizacion de Sustrato de Manglar",
            "dependencia_responsable_cra": "Subdireccion de Gestion Ambiental y Ecosistemas Costeros C.R.A.",
            "sla_tiempo_respuesta_horas": 6,
            "titulo_hallazgo": "Erosion activa en borde estuarino de Cienaga de Mallorquin",
            "coherencia_foto_descripcion": "Verificacion exitosa del motor multimodal de Mokana.",
            "hallazgo_visual": "Evidencia de socavacion en borde costero y exposicion radicular.",
            "especies_mangle_riesgo": ["Rhizophora mangle (Mangle rojo)", "Avicennia germinans (Mangle negro)"],
            "parametros_fisicoquimicos_alterados": ["Solidos Suspendidos Totales (SST)", "Turbidez", "Estabilidad de sedimento"],
            "hipotesis_ambiental_quimica": "Alteracion hidrodinamica y perdida de suelo que compromete la fijacion del manglar.",
            "normativa_aplicable": "Resolucion 1263 de 2018 - Zonificacion de Manglares del Atlantico",
            "accion_recomendada_cra": "Inspeccion tecnica de control de erosion y restauracion con propagulos de Rhizophora mangle.",
            "valor_analitico_b2b_academia": "Dato clave para modelos de retroceso de linea de costa y proteccion de infraestructura costera.",
            "etiquetas_datos": ["#ErosionCostera", "#ManglarAtlantico", "#CarbonoAzul", "#AlertaCRA"],
        },
    }
    test_recipient = [
        {
            "id": "sub_cra_test",
            "name": "Adalberto Leon - Responsable C.R.A.",
            "email": to_email,
            "organization": "C.R.A. Atlantico",
            "type": "CRA",
            "zones": ["*"],
            "categories": ["*"],
            "min_severity": "BAJA",
            "active": True,
        }
    ]
    settings = state_mgr.get_settings()
    deliveries = await mailer.dispatch_notifications(sample_report, test_recipient, settings)
    return {"ok": True, "has_resend_api_key": bool(settings.get("resend_api_key")), "deliveries": deliveries}
