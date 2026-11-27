import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import MANGROVE_ZONES, ALERT_CATEGORIES

REPORTS_FILE = os.path.join(os.path.dirname(__file__), "reports_db.json")


class ConversationStep:
    WAITING_ZONE = "WAITING_ZONE"
    WAITING_CATEGORY = "WAITING_CATEGORY"
    WAITING_DESCRIPTION = "WAITING_DESCRIPTION"
    WAITING_PHOTO = "WAITING_PHOTO"
    WAITING_OPTIONAL_GPS = "WAITING_OPTIONAL_GPS"


class StateManager:
    """
    Mantiene el estado de la conversación de cada ciudadano en WhatsApp
    y persiste los reportes validados en reports_db.json para que el Panel Web de la C.R.A. los consuma en tiempo real.
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._ensure_db()

    def _ensure_db(self) -> None:
        if not os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def get_session(self, conversation_id: str) -> Dict[str, Any]:
        if conversation_id not in self.sessions:
            self.sessions[conversation_id] = {
                "step": ConversationStep.WAITING_ZONE,
                "zone_id": None,
                "zone_title": None,
                "zone_coords": None,
                "category_id": None,
                "category_title": None,
                "description": None,
                "image_url": None,
                "gps": None,
                "last_report_id": None,
                "updated_at": time.time(),
            }
        self.sessions[conversation_id]["updated_at"] = time.time()
        return self.sessions[conversation_id]

    def reset_session(self, conversation_id: str) -> Dict[str, Any]:
        self.sessions.pop(conversation_id, None)
        return self.get_session(conversation_id)

    @staticmethod
    def detect_zone_from_text(text: str) -> Optional[Dict[str, Any]]:
        """
        Detecta si el texto inicial (ej. proveniente del QR/NFC del Tótem) ya menciona el manglar,
        o si el usuario seleccionó un ID de la lista interactiva (`zone_mallorquin`, etc.) o un número del 1 al 5.
        """
        if not text:
            return None
        clean = text.strip().lower()

        # 1. Por ID exacto de la lista interactiva
        for zone in MANGROVE_ZONES:
            if clean == zone["id"].lower() or clean == zone["title"].lower():
                return zone

        # 2. Por palabras clave (ideal para el link wa.me del Tótem QR/NFC)
        for zone in MANGROVE_ZONES:
            for kw in zone["keywords"]:
                if kw in clean:
                    return zone

        # 3. Fallback si respondió con número 1..5
        if clean.isdigit():
            idx = int(clean) - 1
            if 0 <= idx < len(MANGROVE_ZONES):
                return MANGROVE_ZONES[idx]

        return None

    @staticmethod
    def detect_category_from_text(text: str) -> Optional[Dict[str, Any]]:
        """Detecta la categoría de alerta desde el clic en la lista interactiva (`alert_tala`, etc.) o por texto/número."""
        if not text:
            return None
        clean = text.strip().lower()

        for cat in ALERT_CATEGORIES:
            if clean == cat["id"].lower() or clean == cat["title"].lower() or cat["title"].lower() in clean:
                return cat

        if clean.isdigit():
            idx = int(clean) - 1
            if 0 <= idx < len(ALERT_CATEGORIES):
                return ALERT_CATEGORIES[idx]

        return None

    def save_report(
        self,
        conversation_id: str,
        sender_phone: str,
        sender_name: str,
        session: Dict[str, Any],
        ai_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Guarda el reporte verificado junto con el Pequeño Informe Técnico de la C.R.A. y genera un código de radicado."""
        reports = self.list_reports()
        seq = len(reports) + 1
        report_id = f"MKN-2026-{seq:04d}"

        coords = session.get("gps") or session.get("zone_coords") or {"lat": 11.0458, "lng": -74.8461}

        record = {
            "id": report_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "PENDIENTE_REVISION_CRA",
            "conversation_id": conversation_id,
            "citizen": {
                "phone": sender_phone,
                "name": sender_name,
            },
            "location": {
                "zone_id": session.get("zone_id"),
                "zone_title": session.get("zone_title"),
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
                "has_exact_gps": session.get("gps") is not None,
            },
            "incident": {
                "category_id": session.get("category_id"),
                "category_title": session.get("category_title"),
                "citizen_description": session.get("description"),
                "image_url": session.get("image_url"),
            },
            "cra_technical_report": {
                "es_valida": ai_report.get("es_valida", True),
                "nivel_severidad": ai_report.get("nivel_severidad", "MEDIA"),
                "titulo_hallazgo": ai_report.get("titulo_hallazgo"),
                "coherencia_foto_descripcion": ai_report.get("coherencia_foto_descripcion"),
                "hallazgo_visual": ai_report.get("hallazgo_visual"),
                "hipotesis_ambiental_quimica": ai_report.get("hipotesis_ambiental_quimica"),
                "accion_recomendada_cra": ai_report.get("accion_recomendada_cra"),
            },
        }

        reports.insert(0, record)
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)

        session["last_report_id"] = report_id
        return record

    def update_report_gps(self, report_id: str, lat: float, lng: float) -> bool:
        """Actualiza un reporte recién creado si el usuario decide enviar su pin GPS opcional."""
        reports = self.list_reports()
        for r in reports:
            if r["id"] == report_id:
                r["location"]["lat"] = lat
                r["location"]["lng"] = lng
                r["location"]["has_exact_gps"] = True
                with open(REPORTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(reports, f, ensure_ascii=False, indent=2)
                return True
        return False

    def list_reports(self) -> List[Dict[str, Any]]:
        self._ensure_db()
        try:
            with open(REPORTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
