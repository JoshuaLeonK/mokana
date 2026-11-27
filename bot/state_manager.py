import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import MANGROVE_ZONES, ALERT_CATEGORIES, RESEND_API_KEY, RESEND_FROM_EMAIL

REPORTS_FILE = os.path.join(os.path.dirname(__file__), "reports_db.json")
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(__file__), "subscribers_db.json")
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings_db.json")

DEFAULT_SUBSCRIBERS = [
    {
        "id": "sub_cra_joshua",
        "name": "Centro de Control C.R.A. (Principal)",
        "email": "joshualion9@gmail.com",
        "organization": "C.R.A. - Corporacion Autonoma Regional del Atlantico",
        "type": "CRA",
        "plan": "INSTITUCIONAL",
        "zones": ["*"],
        "categories": ["*"],
        "min_severity": "BAJA",
        "active": True,
        "created_at": "2026-11-27T12:00:00Z",
    },
    {
        "id": "sub_cra_control",
        "name": "Adalberto Leon - Responsable C.R.A.",
        "email": "adalbertoleonk@gmail.com",
        "organization": "C.R.A. - Corporacion Autonoma Regional del Atlantico",
        "type": "CRA",
        "plan": "INSTITUCIONAL",
        "zones": ["*"],
        "categories": ["*"],
        "min_severity": "BAJA",
        "active": True,
        "created_at": "2026-11-27T12:00:00Z",
    },
]


class ConversationStep:
    WAITING_ZONE = "WAITING_ZONE"
    WAITING_CATEGORY = "WAITING_CATEGORY"
    WAITING_DESCRIPTION = "WAITING_DESCRIPTION"
    WAITING_PHOTO = "WAITING_PHOTO"
    WAITING_OPTIONAL_GPS = "WAITING_OPTIONAL_GPS"


class StateManager:
    """
    Mantiene:
    1. El estado de conversación de cada ciudadano en WhatsApp.
    2. La base de datos de reportes verificados (`reports_db.json`) con actualizaciones en vivo.
    3. Los responsables de la C.R.A. y clientes B2B (Empresas/Academia) suscritos por correo (`subscribers_db.json`).
    4. La configuración SMTP editable desde el Frontend Administrativo (`settings_db.json`).
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._ensure_dbs()

    def _ensure_dbs(self) -> None:
        if not os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

        if not os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SUBSCRIBERS, f, ensure_ascii=False, indent=2)
        else:
            # Asegurar que el correo de prueba de la C.R.A. (adalbertoleonk@gmail.com) esté presente aunque el archivo ya existiera
            try:
                with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                    existing_subs = json.load(f)
                if not any(s.get("email") == "adalbertoleonk@gmail.com" for s in existing_subs):
                    existing_subs.insert(0, DEFAULT_SUBSCRIBERS[0])
                    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
                        json.dump(existing_subs, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        if not os.path.exists(SETTINGS_FILE):
            default_settings = {
                "resend_api_key": RESEND_API_KEY,
                "from_email": RESEND_FROM_EMAIL,
                "auto_notify_email": True,
                "notify_whatsapp_on_status_change": True,
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)
        elif RESEND_API_KEY:
            # Sincronizar RESEND_API_KEY desde .env si en settings_db.json había quedado vacía antes
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    curr_s = json.load(f)
                if not curr_s.get("resend_api_key"):
                    curr_s["resend_api_key"] = RESEND_API_KEY
                    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                        json.dump(curr_s, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

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
        if not text:
            return None
        clean = text.strip().lower()

        for zone in MANGROVE_ZONES:
            if clean == zone["id"].lower() or clean == zone["title"].lower():
                return zone

        for zone in MANGROVE_ZONES:
            for kw in zone["keywords"]:
                if kw in clean:
                    return zone

        if clean.isdigit():
            idx = int(clean) - 1
            if 0 <= idx < len(MANGROVE_ZONES):
                return MANGROVE_ZONES[idx]

        return None

    @staticmethod
    def detect_category_from_text(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        clean = text.strip().lower()

        # 1. Por ID o título exacto del desplegable
        for cat in ALERT_CATEGORIES:
            if clean == cat["id"].lower() or clean == cat["title"].lower() or cat["title"].lower() in clean:
                return cat

        # 2. Por palabras clave en una descripción libre
        for cat in ALERT_CATEGORIES:
            for kw in cat.get("keywords", []):
                if kw in clean:
                    return cat

        return None

    def save_report(
        self,
        conversation_id: str,
        sender_phone: str,
        sender_name: str,
        session: Dict[str, Any],
        ai_report: Dict[str, Any],
        source: str = "WHATSAPP_TOTEM",
    ) -> Dict[str, Any]:
        """Guarda un nuevo reporte validado por IA con su Informe Técnico C.R.A. y metadatos B2B."""
        reports = self.list_reports()
        seq = len(reports) + 1
        report_id = f"MKN-2026-{seq:04d}"
        now_iso = datetime.now(timezone.utc).isoformat()

        coords = session.get("gps") or session.get("zone_coords") or {"lat": 11.0458, "lng": -74.8461}

        record = {
            "id": report_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "source": source,
            "status": "PENDIENTE_REVISION_CRA",
            "assigned_to": ai_report.get("dependencia_responsable_cra", "Subdirección de Gestión Ambiental C.R.A."),
            "cra_notes": [],
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
                "puntaje_confianza_ia": ai_report.get("puntaje_confianza_ia", 90),
                "nivel_severidad": ai_report.get("nivel_severidad", "ALTA"),
                "indice_riesgo_ambiental": ai_report.get("indice_riesgo_ambiental", 78),
                "subcategoria_tecnica_cra": ai_report.get("subcategoria_tecnica_cra"),
                "dependencia_responsable_cra": ai_report.get("dependencia_responsable_cra"),
                "sla_tiempo_respuesta_horas": ai_report.get("sla_tiempo_respuesta_horas", 6),
                "titulo_hallazgo": ai_report.get("titulo_hallazgo"),
                "coherencia_foto_descripcion": ai_report.get("coherencia_foto_descripcion"),
                "hallazgo_visual": ai_report.get("hallazgo_visual"),
                "especies_mangle_riesgo": ai_report.get("especies_mangle_riesgo", []),
                "parametros_fisicoquimicos_alterados": ai_report.get("parametros_fisicoquimicos_alterados", []),
                "hipotesis_ambiental_quimica": ai_report.get("hipotesis_ambiental_quimica"),
                "normativa_aplicable": ai_report.get("normativa_aplicable"),
                "accion_recomendada_cra": ai_report.get("accion_recomendada_cra"),
                "valor_analitico_b2b_academia": ai_report.get("valor_analitico_b2b_academia"),
                "etiquetas_datos": ai_report.get("etiquetas_datos", []),
            },
            "email_notifications": [],
        }

        reports.insert(0, record)
        self._write_reports(reports)
        session["last_report_id"] = report_id
        return record

    def attach_email_logs(self, report_id: str, email_logs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        reports = self.list_reports()
        for r in reports:
            if r["id"] == report_id:
                r["email_notifications"] = email_logs
                r["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_reports(reports)
                return r
        return None

    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        for r in self.list_reports():
            if r["id"].lower() == report_id.lower():
                return r
        return None

    def update_report(self, report_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Permite al Panel de Administración actualizar el estado, responsable, severidad o agregar notas de gestión."""
        reports = self.list_reports()
        now_iso = datetime.now(timezone.utc).isoformat()
        for r in reports:
            if r["id"].lower() == report_id.lower():
                if "status" in updates and updates["status"]:
                    r["status"] = updates["status"]
                if "assigned_to" in updates and updates["assigned_to"]:
                    r["assigned_to"] = updates["assigned_to"]
                if "nivel_severidad" in updates and updates["nivel_severidad"]:
                    r["cra_technical_report"]["nivel_severidad"] = updates["nivel_severidad"]
                if "note" in updates and updates["note"]:
                    r.setdefault("cra_notes", []).append(
                        {
                            "note": updates["note"],
                            "author": updates.get("author", "Funcionario C.R.A."),
                            "timestamp": now_iso,
                        }
                    )
                r["updated_at"] = now_iso
                self._write_reports(reports)
                return r
        return None

    def update_report_gps(
        self,
        report_id: str,
        lat: float,
        lng: float,
        location_name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        reports = self.list_reports()
        for r in reports:
            if r["id"] == report_id:
                r["location"]["lat"] = lat
                r["location"]["lng"] = lng
                r["location"]["has_exact_gps"] = True
                if location_name:
                    r["location"]["location_name"] = location_name
                if address:
                    r["location"]["address"] = address
                r["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_reports(reports)
                return r
        return None

    def list_reports(self) -> List[Dict[str, Any]]:
        self._ensure_dbs()
        try:
            with open(REPORTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write_reports(self, reports: List[Dict[str, Any]]) -> None:
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)

    # =========================================================================
    # Gestión de Responsables C.R.A. y Suscriptores B2B (Empresas / Academia)
    # =========================================================================
    def list_subscribers(self) -> List[Dict[str, Any]]:
        self._ensure_dbs()
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def add_subscriber(self, data: Dict[str, Any]) -> Dict[str, Any]:
        subs = self.list_subscribers()
        new_sub = {
            "id": data.get("id") or f"sub_{uuid.uuid4().hex[:8]}",
            "name": data.get("name", "Contacto"),
            "email": data["email"],
            "organization": data.get("organization", "Entidad Suscriptora"),
            "type": (data.get("type") or "EMPRESA").upper(),  # CRA | EMPRESA | ACADEMIA
            "plan": data.get("plan", "PRO_DATA_B2B"),
            "zones": data.get("zones") or ["*"],
            "categories": data.get("categories") or ["*"],
            "min_severity": (data.get("min_severity") or "BAJA").upper(),
            "active": data.get("active", True),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        subs.append(new_sub)
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
        return new_sub

    def update_subscriber(self, sub_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        subs = self.list_subscribers()
        for s in subs:
            if s["id"] == sub_id:
                for k in ("name", "email", "organization", "type", "plan", "zones", "categories", "min_severity", "active"):
                    if k in updates and updates[k] is not None:
                        s[k] = updates[k]
                with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(subs, f, ensure_ascii=False, indent=2)
                return s
        return None

    def delete_subscriber(self, sub_id: str) -> bool:
        subs = self.list_subscribers()
        filtered = [s for s in subs if s["id"] != sub_id]
        if len(filtered) == len(subs):
            return False
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        return True

    # =========================================================================
    # Configuración SMTP y Notificaciones (Desde el Frontend)
    # =========================================================================
    def get_settings(self) -> Dict[str, Any]:
        self._ensure_dbs()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_settings()
        for k in (
            "resend_api_key",
            "from_email",
            "auto_notify_email",
            "notify_whatsapp_on_status_change",
        ):
            if k in updates and updates[k] is not None:
                current[k] = updates[k]
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return current
