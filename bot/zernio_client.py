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
    """Cliente HTTP asíncrono para enviar mensajes cortos y listas desplegables limpias (sin emojis) por WhatsApp vía Zernio."""

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
        """Lista desplegable nativa de WhatsApp para elegir la zona del manglar (sin emojis, texto breve)."""
        rows = [
            {
                "id": z["id"],
                "title": z["title"][:24],
                "description": z["description"][:72],
            }
            for z in MANGROVE_ZONES
        ]
        body_text = "Bienvenido a Mokana (C.R.A.). Selecciona la zona de manglar o envia directamente una foto con la descripcion del reporte."
        payload: Dict[str, Any] = {
            "accountId": account_id or self.default_account_id,
            "interactive": {
                "type": "list",
                "body": {"text": body_text},
                "action": {
                    "button": "Elegir manglar",
                    "sections": [
                        {
                            "title": "Zonas de manglar",
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
        """Lista desplegable nativa de WhatsApp para elegir la anomalía (sin emojis, sin números, texto breve)."""
        rows = [
            {
                "id": cat["id"],
                "title": cat["title"][:24],
                "description": cat["description"][:72],
            }
            for cat in ALERT_CATEGORIES
        ]
        body_text = f"Zona: {zone_title}. Selecciona la anomalia en el desplegable o envia directamente una foto con tu descripcion."
        payload: Dict[str, Any] = {
            "accountId": account_id or self.default_account_id,
            "interactive": {
                "type": "list",
                "body": {"text": body_text},
                "action": {
                    "button": "Elegir anomalia",
                    "sections": [
                        {
                            "title": "Tipo de anomalia",
                            "rows": rows,
                        }
                    ],
                },
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
                logger.warning("Respuesta %s en primer intento interactive (%s). Reintentando con campo message incluido.", resp.status_code, resp.text)
                if "interactive" in payload and "message" not in payload:
                    payload_with_msg = {
                        **payload,
                        "message": payload["interactive"].get("body", {}).get("text", "Selecciona una opcion:"),
                    }
                    resp2 = await client.post(url, json=payload_with_msg, headers=self._headers())
                    if resp2.status_code < 400:
                        return resp2.json() if resp2.content else {"status": resp2.status_code}
                    logger.error("Error enviando lista interactiva a Zernio (%s): %s", resp2.status_code, resp2.text)
            return resp.json() if resp.content else {"status": resp.status_code}
