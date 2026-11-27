import hmac
import hashlib
import logging
from typing import Any, Dict, List, Optional
import httpx

from config import (
    ZERNIO_API_KEY,
    ZERNIO_ACCOUNT_ID,
    ZERNIO_BASE_URL,
    ZERNIO_WEBHOOK_SECRET,
    MANGROVE_ZONES,
    ALERT_CATEGORIES,
)

logger = logging.getLogger("mokana.zernio")


class ZernioClient:
    """Cliente HTTP asíncrono para enviar mensajes de texto, listas interactivas y botones por WhatsApp vía Zernio."""

    def __init__(self) -> None:
        self.base_url = ZERNIO_BASE_URL
        self.api_key = ZERNIO_API_KEY
        self.default_account_id = ZERNIO_ACCOUNT_ID

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
        """Verifica la firma HMAC-SHA256 enviada en X-Zernio-Signature si ZERNIO_WEBHOOK_SECRET está configurado."""
        if not ZERNIO_WEBHOOK_SECRET:
            return True
        if not signature_header:
            return False
        sig = signature_header.replace("sha256=", "").strip()
        expected = hmac.new(
            ZERNIO_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, sig)

    async def send_text(
        self,
        conversation_id: str,
        text: str,
        account_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Envía un mensaje de texto simple a la conversación activa en Zernio."""
        payload: Dict[str, Any] = {
            "accountId": account_id or self.default_account_id,
            "message": text,
        }
        if reply_to:
            payload["replyTo"] = reply_to
        return await self._post_message(conversation_id, payload)

    async def send_zone_list(
        self,
        conversation_id: str,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Envía una Lista Interactiva nativa de WhatsApp para que el usuario seleccione en qué manglar está."""
        rows = [
            {
                "id": z["id"],
                "title": z["title"][:24],  # Límite oficial de WhatsApp: 24 caracteres en row title
                "description": z["description"][:72],
            }
            for z in MANGROVE_ZONES
        ]
        body_text = (
            "🌿 *¡Hola! Soy Mokaná*, el sistema de alerta temprana para los manglares del Atlántico (C.R.A.).\n\n"
            "Para comenzar tu reporte, selecciona en el botón de abajo *¿en cuál zona de manglar te encuentras?*"
        )
        payload: Dict[str, Any] = {
            "accountId": account_id or self.default_account_id,
            "message": body_text,
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "Mokaná - Zonas de Manglar"},
                "body": {"text": body_text},
                "footer": {"text": "C.R.A. Atlántico • Ciencia Ciudadana"},
                "action": {
                    "button": "Seleccionar Manglar",
                    "sections": [
                        {
                            "title": "Manglares del Atlántico",
                            "rows": rows,
                        }
                    ],
                },
            },
        }
        return await self._post_message(conversation_id, payload)

    async def send_category_list(
        self,
        conversation_id: str,
        zone_title: str,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Envía una Lista Interactiva nativa de WhatsApp con las 5 anomalías reportables a la C.R.A."""
        rows = [
            {
                "id": cat["id"],
                "title": cat["title"][:24],
                "description": cat["description"][:72],
            }
            for cat in ALERT_CATEGORIES
        ]
        body_text = (
            f"📍 Zona detectada: *{zone_title}*\n\n"
            "¿Qué anomalía o incidente deseas reportar a la C.R.A.? Toca el botón de abajo para elegir la opción:"
        )
        payload: Dict[str, Any] = {
            "accountId": account_id or self.default_account_id,
            "message": body_text,
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "Tipo de Alerta Ambiental"},
                "body": {"text": body_text},
                "footer": {"text": "Selecciona una opción de la lista"},
                "action": {
                    "button": "Elegir Tipo de Alerta",
                    "sections": [
                        {
                            "title": "Alertas Manglar C.R.A.",
                            "rows": rows,
                        }
                    ],
                },
            },
        }
        return await self._post_message(conversation_id, payload)

    async def send_quick_buttons(
        self,
        conversation_id: str,
        text: str,
        buttons: List[Dict[str, str]],
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Envía hasta 3 botones de respuesta rápida en WhatsApp."""
        formatted_buttons = [
            {"type": "reply", "id": b["id"], "title": b["title"][:20]}
            for b in buttons[:3]
        ]
        payload: Dict[str, Any] = {
            "accountId": account_id or self.default_account_id,
            "message": text,
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "buttons": formatted_buttons,
            },
        }
        return await self._post_message(conversation_id, payload)

    async def _post_message(self, conversation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            logger.warning("ZERNIO_API_KEY no configurada. Simulando envío a %s: %s", conversation_id, payload)
            return {"simulated": True, "conversationId": conversation_id, "payload": payload}

        url = f"{self.base_url}/inbox/conversations/{conversation_id}/messages"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            if resp.status_code >= 400:
                logger.error("Error enviando mensaje a Zernio (%s): %s", resp.status_code, resp.text)
                # Si falla el formato interactivo en alguna versión, hacemos fallback automático a texto limpio
                if "interactive" in payload:
                    logger.info("Ejecutando fallback a texto plano para %s", conversation_id)
                    fallback_payload = {
                        "accountId": payload["accountId"],
                        "message": self._build_text_fallback(payload),
                    }
                    resp2 = await client.post(url, json=fallback_payload, headers=self._headers())
                    return resp2.json() if resp2.content else {"status": resp2.status_code}
            return resp.json() if resp.content else {"status": resp.status_code}

    @staticmethod
    def _build_text_fallback(payload: Dict[str, Any]) -> str:
        base_msg = payload.get("message", "")
        interactive = payload.get("interactive", {})
        if interactive.get("type") == "list":
            rows = interactive.get("action", {}).get("sections", [{}])[0].get("rows", [])
            options = "\n".join(f"*{i+1}.* {r['title']} — _{r.get('description', '')}_" for i, r in enumerate(rows))
            return f"{base_msg}\n\n{options}"
        if interactive.get("type") == "button":
            btns = interactive.get("buttons", [])
            options = " | ".join(f"[{b['title']}]" for b in btns)
            return f"{base_msg}\n\nOpciones: {options}"
        return base_msg
