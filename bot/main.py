import logging
from typing import Any, Dict, Optional, Set
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from config import MANGROVE_ZONES
from zernio_client import ZernioClient
from gemini_analyst import GeminiAnalyst
from state_manager import StateManager, ConversationStep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mokana.bot")

app = FastAPI(
    title="Mokaná - Bot de Alerta Temprana & API C.R.A.",
    description="Bot de WhatsApp con Zernio + IA Multimodal Gemini 2.5 Flash para monitoreo de manglares del Atlántico.",
    version="1.0.0",
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

# Deduplicación de eventos de Zernio (por X-Zernio-Event-Id o payload['id'])
PROCESSED_EVENTS: Set[str] = set()


def _extract_incoming_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae de manera uniforme el texto, clic interactivo, imagen adjunta o ubicación GPS
    del payload `message.received` de Zernio.
    """
    account = payload.get("account") or {}
    conversation = payload.get("conversation") or {}
    message = payload.get("message") or {}
    sender = message.get("sender") or {}

    account_id = account.get("id")
    conversation_id = conversation.get("id") or payload.get("conversationId")
    message_id = message.get("id")

    # Si el usuario tocó una opción de una Lista Interactiva o un Botón Rápido en WhatsApp
    interactive_id = (
        message.get("interactiveId")
        or (message.get("interactive") or {}).get("id")
        or (message.get("interactive") or {}).get("list_reply", {}).get("id")
        or (message.get("interactive") or {}).get("button_reply", {}).get("id")
    )
    text = (message.get("text") or "").strip()
    effective_input = interactive_id or text

    # Extraer imagen si el ciudadano adjuntó foto
    image_url: Optional[str] = None
    attachments = message.get("attachments") or []
    for att in attachments:
        att_type = (att.get("type") or att.get("mimeType") or "").lower()
        url = att.get("url") or att.get("mediaUrl") or att.get("attachmentUrl")
        if url and ("image" in att_type or not att_type or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            image_url = url
            break

    # Soporte por si la URL de imagen viene directo en el objeto message
    if not image_url and message.get("mediaUrl"):
        image_url = message.get("mediaUrl")

    # Extraer coordenadas GPS opcionales si el ciudadano envió un pin de ubicación
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
        "sender_phone": sender.get("id") or conversation.get("platformConversationId") or "desconocido",
        "sender_name": sender.get("name") or "Ciudadano Vigía",
        "text": text,
        "interactive_id": interactive_id,
        "effective_input": effective_input,
        "image_url": image_url,
        "gps": gps_coords,
    }


async def process_whatsapp_message(payload: Dict[str, Any]) -> None:
    """
    Lógica principal del flujo conversacional de Mokaná:
    1. Detección automática del manglar desde el texto del Tótem (QR/NFC) o selección en Lista Interactiva.
    2. Selección del tipo de alerta en Lista Interactiva.
    3. Descripción breve en texto por parte del ciudadano.
    4. Fotografía de evidencia (+ Pin GPS opcional).
    5. Verificación de autenticidad/coherencia (Foto + Descripción + Categoría) con Gemini 2.5 Flash
       + Generación de Pequeño Informe Técnico para la C.R.A. + Respuesta final al ciudadano.
    """
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

    # Si en cualquier momento el usuario envía un comando de reinicio o un nuevo enlace de Tótem QR/NFC
    lower_text = text.lower()
    if lower_text in {"hola", "inicio", "menu", "menú", "nuevo", "reiniciar", "cancelar"} or "totem" in lower_text or "tótem" in lower_text:
        session = state_mgr.reset_session(conv_id)

    # Guardar GPS opcional si el usuario lo envía en cualquier punto de la conversación
    if gps:
        session["gps"] = gps
        if session["step"] == ConversationStep.WAITING_OPTIONAL_GPS and session.get("last_report_id"):
            state_mgr.update_report_gps(session["last_report_id"], gps["lat"], gps["lng"])
            await zernio.send_text(
                conv_id,
                f"📍 *¡Ubicación GPS exacta registrada!* Se actualizó el radicado *{session['last_report_id']}* "
                "en el mapa en tiempo real de la C.R.A.\n\nEscribe *Hola* cuando desees realizar un nuevo reporte.",
                account_id=acc_id,
            )
            state_mgr.reset_session(conv_id)
            return

    # =========================================================================
    # PASO 1: Detectar Zona del Manglar (Automático por Tótem o por Lista)
    # =========================================================================
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

    # =========================================================================
    # PASO 2: Selección de la Categoría de Alerta (Lista Interactiva)
    # =========================================================================
    if session["step"] == ConversationStep.WAITING_CATEGORY:
        # Si el usuario decidió cambiar de zona tocando otra zona de la lista anterior
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
                "(qué ocurre exactamente, tamaño o detalles clave para que nuestra IA valide la coherencia).",
                account_id=acc_id,
            )
            return
        else:
            await zernio.send_category_list(conv_id, session["zone_title"] or "Manglar del Atlántico", account_id=acc_id)
            return

    # =========================================================================
    # PASO 3: Recibir Descripción Breve en Texto
    # =========================================================================
    if session["step"] == ConversationStep.WAITING_DESCRIPTION:
        # Si el usuario permite cambiar de categoría tocando otro botón de la lista de alertas
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

        # Si el ciudadano envió de una vez la FOTO con la descripción en el pie de foto (caption)
        if image_url and len(text) >= 5:
            session["description"] = text
            session["image_url"] = image_url
            session["step"] = ConversationStep.WAITING_PHOTO
            # Pasa directo al análisis con Gemini en el bloque del Paso 4
        elif len(text) >= 4 and not image_url:
            session["description"] = text
            session["step"] = ConversationStep.WAITING_PHOTO
            await zernio.send_text(
                conv_id,
                "📸 *Paso 3 de 3 (Verificación):* ¡Descripción registrada!\n\n"
                "Ahora toma o adjunta una *FOTO* del lugar para verificar que la información concuerda "
                "y generar el informe técnico para la C.R.A.\n\n"
                "_(Opcional: Después o antes puedes adjuntar tu pin de ubicación GPS 📍)_.",
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

    # =========================================================================
    # PASO 4: Recibir Foto -> Validar Autenticidad/Coherencia con Gemini -> Informe CRA
    # =========================================================================
    if session["step"] == ConversationStep.WAITING_PHOTO:
        if not image_url:
            # Si mandó solo un GPS opcional mientras estaba en el paso de foto
            if gps:
                await zernio.send_text(
                    conv_id,
                    "📍 Ubicación GPS guardada. Ahora por favor envíame la *FOTO* 📸 de evidencia para validar el reporte.",
                    account_id=acc_id,
                )
                return

            # Si mandó más texto, lo anexamos a su descripción y le recordamos subir la foto
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
            "⏳ *Analizando evidencia con IA (Gemini)...*\n"
            "Estamos verificando la coherencia entre tu descripción y la fotografía para generar el informe técnico a la C.R.A.",
            account_id=acc_id,
        )

        ai_result = await analyst.analyze_report(
            zone_title=session["zone_title"],
            category_title=session["category_title"],
            user_description=session["description"],
            image_url=session["image_url"],
        )

        # ¿Qué pasa si Gemini detecta que la foto NO es auténtica o NO concuerda con la descripción?
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

        # Si es válida: guardamos en base de datos y armamos el Pequeño Informe Técnico + Respuesta Final
        saved_record = state_mgr.save_report(
            conversation_id=conv_id,
            sender_phone=data["sender_phone"],
            sender_name=data["sender_name"],
            session=session,
            ai_report=ai_result,
        )

        cra_rep = saved_record["cra_technical_report"]
        final_message = (
            f"✅ *¡REPORTE VERIFICADO Y ENVIADO A LA C.R.A.!*\n"
            f"📋 *Radicado:* `{saved_record['id']}`\n"
            f"📍 *Zona:* {session['zone_title']}\n"
            f"🚨 *Prioridad asignada:* *{cra_rep['nivel_severidad']}*\n\n"
            f"📄 *INFORME TÉCNICO PRELIMINAR (C.R.A.):*\n"
            f"• *Hallazgo:* {cra_rep['titulo_hallazgo']}\n"
            f"• *Coherencia Foto/Relato:* {cra_rep['coherencia_foto_descripcion']}\n"
            f"• *Diagnóstico Ambiental:* {cra_rep['hipotesis_ambiental_quimica']}\n"
            f"• *Acción Sugerida:* {cra_rep['accion_recomendada_cra']}\n\n"
            f"_{ai_result.get('mensaje_ciudadano', 'Gracias por proteger los manglares del Atlántico.')}_\n\n"
            "📍 _(Opcional)_: Si deseas añadir tu *pin de ubicación GPS exacta*, envíalo ahora con el clip de WhatsApp, "
            "o escribe *NUEVO* para otro reporte."
        )

        session["step"] = ConversationStep.WAITING_OPTIONAL_GPS
        await zernio.send_text(conv_id, final_message, account_id=acc_id)
        return

    # =========================================================================
    # PASO 5: Estado posterior al cierre (si escribe algo más sin ser GPS)
    # =========================================================================
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
# ENDPOINTS HTTP (Webhook de Zernio + API en Tiempo Real para el Panel C.R.A.)
# =============================================================================

@app.get("/")
async def health_check() -> Dict[str, Any]:
    return {
        "service": "Mokaná WhatsApp Bot & C.R.A. Early Warning API",
        "status": "online",
        "zones_configured": len(MANGROVE_ZONES),
        "total_reports": len(state_mgr.list_reports()),
    }


@app.post("/webhook/zernio")
async def zernio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_zernio_event: Optional[str] = Header(default=None),
    x_zernio_event_id: Optional[str] = Header(default=None),
    x_zernio_signature: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Endpoint oficial que recibe los eventos de Zernio (`message.received`, `webhook.test`, etc.).
    Responde 200 OK en menos de 5 segundos (requisito de Zernio) y procesa el mensaje en background.
    """
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
        logger.info("Evento duplicado ignorado: %s", event_id)
        return {"ok": True, "deduplicated": True}

    if event_id:
        PROCESSED_EVENTS.add(event_id)

    if event_name == "message.received" or "message" in payload:
        background_tasks.add_task(process_whatsapp_message, payload)

    return {"ok": True, "event": event_name}


@app.get("/api/reports")
async def get_reports() -> Dict[str, Any]:
    """Devuelve todos los reportes ciudadanos validados y sus informes técnicos para el Dashboard Web de la C.R.A."""
    reports = state_mgr.list_reports()
    return {"count": len(reports), "reports": reports}


@app.get("/api/zones")
async def get_zones() -> Dict[str, Any]:
    """Devuelve las 5 zonas de manglar del Atlántico configuradas y los enlaces QR/NFC sugeridos para cada Tótem."""
    return {"zones": MANGROVE_ZONES}
