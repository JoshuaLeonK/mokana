import logging
from typing import Any, Dict, List
import httpx

from config import RESEND_API_KEY, RESEND_FROM_EMAIL, PUBLIC_BASE_URL

logger = logging.getLogger("mokana.email")

SEVERITY_COLORS = {
    "CRÍTICA": "#991b1b",
    "ALTA": "#c2410c",
    "MEDIA": "#b45309",
    "BAJA": "#15803d",
}

SEVERITY_BG = {
    "CRÍTICA": "#fef2f2",
    "ALTA": "#fff7ed",
    "MEDIA": "#fffbeb",
    "BAJA": "#f0fdf4",
}

SEVERITY_RANK = {
    "BAJA": 1,
    "MEDIA": 2,
    "ALTA": 3,
    "CRÍTICA": 4,
}


class EmailNotifier:
    """
    Motor de notificaciones oficiales por correo electrónico vía RESEND API.
    Diseño editorial, técnico e institucional (sin marcas de IA) para:
    - Autoridad Ambiental (C.R.A.)
    - Empresas Aliadas / Sector Privado
    - Academia y Centros de Investigación
    """

    @staticmethod
    def should_notify_recipient(recipient: Dict[str, Any], report: Dict[str, Any]) -> bool:
        if not recipient.get("active", True):
            return False

        zone_id = report.get("location", {}).get("zone_id")
        cat_id = report.get("incident", {}).get("category_id")
        severity = (report.get("cra_technical_report", {}).get("nivel_severidad") or "MEDIA").upper()

        zones_filter = recipient.get("zones") or []
        if zones_filter and "*" not in zones_filter and zone_id not in zones_filter:
            return False

        cats_filter = recipient.get("categories") or []
        if cats_filter and "*" not in cats_filter and cat_id not in cats_filter:
            return False

        min_sev = (recipient.get("min_severity") or "BAJA").upper()
        if SEVERITY_RANK.get(severity, 2) < SEVERITY_RANK.get(min_sev, 1):
            return False

        return True

    @staticmethod
    def build_html_email(recipient: Dict[str, Any], report: Dict[str, Any]) -> str:
        """Plantilla HTML corporativa e institucional de ingeniería ambiental (sin menciones ni estética de IA)."""
        cra = report.get("cra_technical_report", {})
        loc = report.get("location", {})
        inc = report.get("incident", {})
        severity = (cra.get("nivel_severidad") or "ALTA").upper()
        badge_color = SEVERITY_COLORS.get(severity, "#c2410c")
        badge_bg = SEVERITY_BG.get(severity, "#fff7ed")

        role = (recipient.get("type") or "CRA").upper()
        org_name = recipient.get("organization") or recipient.get("name") or "Entidad Destinataria"

        if role == "CRA":
            doc_type = "BOLETÍN OFICIAL DE ALERTA TEMPRANA Y DESPACHO AMBIENTAL"
        elif role == "EMPRESA":
            doc_type = f"REPORTE TÉCNICO DE MONITOREO COSTERO • {org_name.upper()}"
        else:
            doc_type = f"BOLETÍN DE RED CIENTÍFICA ESTUARINA • {org_name.upper()}"

        especies_html = ", ".join(cra.get("especies_mangle_riesgo") or ["Cobertura de manglar estuarino"])
        parametros_html = ", ".join(cra.get("parametros_fisicoquimicos_alterados") or ["En verificación de campo"])

        image_url = inc.get("image_url") or ""
        logo_url = f"{PUBLIC_BASE_URL}/static/mokana-logo.jpg"
        lat_val = loc.get("lat") or 11.0458
        lng_val = loc.get("lng") or -74.8461
        # Enlace directo a Google Maps / Earth en Vista Satelital 3D (con inclinación 3D 55t y zoom de ecosistema 650m)
        gmaps_3d_url = (
            f"https://www.google.com/maps/@{lat_val},{lng_val},550m/data=!3m1!1e3"
        )
        gmaps_pin_url = (
            f"https://www.google.com/maps/search/?api=1&query={lat_val},{lng_val}"
        )

        image_block = ""
        if image_url:
            image_block = f"""
      <div style="margin:22px 0;border:1px solid #cbd5e1;border-radius:6px;overflow:hidden;background:#f8fafc;">
        <div style="padding:10px 14px;background:#e2e8f0;font-size:12px;font-weight:600;color:#334155;text-transform:uppercase;letter-spacing:0.5px;">
          Anexo Fotográfico de Campo — Registro #{report.get('id')}
        </div>
        <div style="padding:14px;text-align:center;">
          <img src="{image_url}" alt="Evidencia de Campo - {loc.get('zone_title')}" style="max-width:100%;max-height:380px;border-radius:4px;border:1px solid #94a3b8;display:block;margin:0 auto;" />
          <div style="margin-top:8px;font-size:12px;">
            <a href="{image_url}" target="_blank" style="color:#0f766e;text-decoration:underline;">Abrir archivo fotográfico original</a>
          </div>
        </div>
      </div>
"""

        b2b_block = ""
        if role in ("EMPRESA", "ACADEMIA") and cra.get("valor_analitico_b2b_academia"):
            b2b_block = f"""
      <div style="margin-top:18px;border:1px solid #cbd5e1;border-radius:6px;padding:16px;background:#f8fafc;">
        <div style="font-size:12px;font-weight:700;color:#1e293b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
          Nota Técnica para Investigación y Gestión Ambiental
        </div>
        <p style="margin:0;font-size:13.5px;line-height:1.55;color:#334155;">
          {cra.get('valor_analitico_b2b_academia')}
        </p>
      </div>
"""

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Expediente {report.get('id')} - Mokana</title>
</head>
<body style="font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;background-color:#e2e8f0;margin:0;padding:28px 14px;color:#1e293b;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:6px;overflow:hidden;">

    <!-- Encabezado Institucional con Logo Mokana -->
    <div style="background:#081216;color:#ffffff;padding:24px 28px;border-bottom:4px solid #15803d;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="width:88px;vertical-align:middle;">
            <img src="{logo_url}" alt="Mokana" style="width:76px;height:76px;object-fit:contain;border-radius:50%;border:1px solid #166534;display:block;" />
          </td>
          <td style="vertical-align:middle;padding-left:12px;">
            <div style="font-size:11px;letter-spacing:1.2px;color:#86efac;font-weight:700;text-transform:uppercase;">
              {doc_type}
            </div>
            <div style="font-size:22px;font-weight:700;color:#f8fafc;margin:4px 0;">
              Sistema Mokana — Expediente {report.get('id')}
            </div>
            <div style="font-size:12px;color:#94a3b8;">
              Red de Monitoreo y Protección de los Manglares del Atlántico
            </div>
          </td>
        </tr>
      </table>
    </div>

    <div style="padding:26px 28px;">

      <!-- Barra de Estado y Nivel de Riesgo -->
      <div style="background:{badge_bg};border:1px solid {badge_color};border-left:6px solid {badge_color};border-radius:4px;padding:14px 16px;margin-bottom:22px;">
        <table style="width:100%;border-collapse:collapse;">
          <tr>
            <td>
              <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.6px;">
                Nivel de Prioridad Operativa
              </div>
              <div style="font-size:18px;font-weight:700;color:{badge_color};margin-top:2px;">
                PRIORIDAD {severity} — Índice de Riesgo: {cra.get('indice_riesgo_ambiental', 78)} / 100
              </div>
            </td>
            <td style="text-align:right;vertical-align:middle;">
              <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">
                Tiempo Máximo de Respuesta
              </div>
              <div style="font-size:15px;font-weight:700;color:#0f172a;margin-top:2px;">
                {cra.get('sla_tiempo_respuesta_horas', 6)} horas
              </div>
            </td>
          </tr>
        </table>
      </div>

      <!-- Título del Hallazgo -->
      <h2 style="font-size:17px;font-weight:700;color:#0f172a;margin:0 0 14px 0;padding-bottom:8px;border-bottom:2px solid #e2e8f0;">
        {cra.get('titulo_hallazgo')}
      </h2>

      <!-- Ficha de Localización y Recepción -->
      <table style="width:100%;border-collapse:collapse;font-size:13.5px;margin-bottom:20px;">
        <tr>
          <td style="padding:10px;background:#f8fafc;border:1px solid #cbd5e1;font-weight:600;color:#334155;width:34%;">
            Ecosistema / Ubicación
          </td>
          <td style="padding:10px;border:1px solid #cbd5e1;color:#0f172a;">
            <div style="font-weight:700;margin-bottom:6px;">{loc.get('zone_title')}</div>
            <a href="{gmaps_3d_url}" target="_blank" style="display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;padding:6px 12px;border-radius:4px;font-size:12px;font-weight:600;margin-right:6px;">
              Abrir Mapa Satelital 3D (Google Maps)
            </a>
            <a href="{gmaps_pin_url}" target="_blank" style="display:inline-block;background:#e2e8f0;color:#0f172a;text-decoration:none;padding:6px 12px;border-radius:4px;font-size:12px;font-weight:600;">
              Ver Marcador de Ruta
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 10px;background:#f8fafc;border:1px solid #cbd5e1;font-weight:600;color:#334155;">
            Tipología del Incidente
          </td>
          <td style="padding:8px 10px;border:1px solid #cbd5e1;color:#0f172a;">
            {inc.get('category_title')} — {cra.get('subcategoria_tecnica_cra')}
          </td>
        </tr>
        <tr>
          <td style="padding:8px 10px;background:#f8fafc;border:1px solid #cbd5e1;font-weight:600;color:#334155;">
            Dependencia Asignada
          </td>
          <td style="padding:8px 10px;border:1px solid #cbd5e1;color:#0f172a;">
            {cra.get('dependencia_responsable_cra')}
          </td>
        </tr>
        <tr>
          <td style="padding:8px 10px;background:#f8fafc;border:1px solid #cbd5e1;font-weight:600;color:#334155;">
            Observación Reportada en Campo
          </td>
          <td style="padding:8px 10px;border:1px solid #cbd5e1;color:#334155;">
            "{inc.get('citizen_description')}"
          </td>
        </tr>
      </table>

      <!-- Evidencia Fotográfica -->
      {image_block}

      <!-- Evaluación Técnica Ambiental -->
      <div style="border:1px solid #cbd5e1;border-radius:6px;overflow:hidden;margin-top:18px;">
        <div style="background:#0f172a;color:#ffffff;padding:10px 14px;font-size:12.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">
          Dictamen Técnico Preliminar — C.R.A. Atlántico
        </div>
        <div style="padding:16px;font-size:13.5px;line-height:1.55;color:#1e293b;">
          <p style="margin:0 0 10px 0;">
            <strong>1. Inspección de Evidencia:</strong> {cra.get('hallazgo_visual')} {cra.get('coherencia_foto_descripcion')}
          </p>
          <p style="margin:0 0 10px 0;">
            <strong>2. Diagnóstico Físico-Químico y Ecosistémico:</strong> {cra.get('hipotesis_ambiental_quimica')}
          </p>
          <p style="margin:0 0 10px 0;">
            <strong>3. Variables y Parámetros Comprometidos:</strong> {parametros_html}.
          </p>
          <p style="margin:0 0 10px 0;">
            <strong>4. Cobertura Biológica Expuesta:</strong> {especies_html}.
          </p>
          <p style="margin:0 0 12px 0;">
            <strong>5. Marco Normativo de Referencia:</strong> {cra.get('normativa_aplicable')}.
          </p>
          <div style="background:#f0fdf4;border-left:4px solid #15803d;padding:10px 12px;color:#14532d;">
            <strong>Protocolo de Actuación Recomendado:</strong> {cra.get('accion_recomendada_cra')}
          </div>
        </div>
      </div>

      {b2b_block}

      <!-- Pie de Página -->
      <div style="margin-top:24px;padding-top:14px;border-top:1px solid #cbd5e1;font-size:11.5px;color:#64748b;line-height:1.5;text-align:center;">
        <strong>Sistema Mokana</strong> • Inspirado en la herencia del pueblo indígena Mokaná, guardianes ancestrales de los manglares del Atlántico.<br/>
        Expediente generado el {report.get('created_at')} UTC • Destinatario registrado: {recipient.get('email', 'C.R.A.')}
      </div>

    </div>
  </div>
</body>
</html>
"""

    async def dispatch_notifications(
        self,
        report: Dict[str, Any],
        recipients: List[Dict[str, Any]],
        email_settings: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        matched = [r for r in recipients if self.should_notify_recipient(r, report)]
        delivery_logs: List[Dict[str, Any]] = []

        api_key = email_settings.get("resend_api_key") or RESEND_API_KEY
        from_email = email_settings.get("from_email") or RESEND_FROM_EMAIL

        cra = report.get("cra_technical_report", {})
        loc = report.get("location", {})
        severity = cra.get("nivel_severidad", "ALTA")
        subject = f"[Prioridad {severity}] Expediente {report.get('id')} — {loc.get('zone_title')} | Mokana C.R.A."

        async with httpx.AsyncClient(timeout=15.0) as client:
            for rec in matched:
                to_email = rec.get("email")
                if not to_email:
                    continue

                html_body = self.build_html_email(rec, report)
                status = "simulated_sent"
                resend_id = None
                error_msg = None

                if api_key:
                    try:
                        resp = await client.post(
                            "https://api.resend.com/emails",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "from": from_email,
                                "to": [to_email],
                                "subject": subject,
                                "html": html_body,
                            },
                        )
                        if resp.status_code in (400, 403, 422) and "onboarding@resend.dev" not in from_email:
                            resp = await client.post(
                                "https://api.resend.com/emails",
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                },
                                json={
                                    "from": "Mokana C.R.A. <onboarding@resend.dev>",
                                    "to": [to_email],
                                    "subject": subject,
                                    "html": html_body,
                                },
                            )

                        if resp.status_code in (200, 201):
                            data = resp.json()
                            resend_id = data.get("id")
                            status = "sent"
                            logger.info("Correo enviado vía Resend a %s (id=%s)", to_email, resend_id)
                        else:
                            status = "failed"
                            error_msg = resp.text
                            logger.error("Error de Resend API (%s) enviando a %s: %s", resp.status_code, to_email, resp.text)

                    except Exception as exc:
                        status = "failed"
                        error_msg = str(exc)
                        logger.error("Excepción enviando correo vía Resend a %s: %s", to_email, exc)

                delivery_logs.append(
                    {
                        "recipient_id": rec.get("id"),
                        "email": to_email,
                        "name": rec.get("name"),
                        "organization": rec.get("organization"),
                        "type": rec.get("type"),
                        "subject": subject,
                        "status": status,
                        "resend_id": resend_id,
                        "error": error_msg,
                    }
                )

        return delivery_logs
