import logging
from typing import Any, Dict, List
import httpx

from config import RESEND_API_KEY, RESEND_FROM_EMAIL

logger = logging.getLogger("mokana.email")

SEVERITY_COLORS = {
    "CRÍTICA": "#dc2626",
    "ALTA": "#ea580c",
    "MEDIA": "#d97706",
    "BAJA": "#16a34a",
}

SEVERITY_RANK = {
    "BAJA": 1,
    "MEDIA": 2,
    "ALTA": 3,
    "CRÍTICA": 4,
}


class EmailNotifier:
    """
    Motor de notificaciones por correo electrónico vía RESEND API (https://api.resend.com/emails) para:
    1. Autoridad Ambiental (C.R.A. - Responsables de despacho y control)
    2. Empresas B2B (ESG, Carbono Azul, Consultoras, Sector Portuario/Turístico)
    3. Academia y Centros de Investigación (Universidades, Grupos de Biología/Química)
    Todo configurable dinámicamente desde el Frontend Administrativo.
    """

    @staticmethod
    def should_notify_recipient(recipient: Dict[str, Any], report: Dict[str, Any]) -> bool:
        """Filtra si un suscriptor o responsable debe recibir el correo según sus filtros configurados en el Frontend."""
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
        """Construye una plantilla HTML ejecutiva adaptada al rol del destinatario (C.R.A., Empresa B2B o Academia)."""
        cra = report.get("cra_technical_report", {})
        loc = report.get("location", {})
        inc = report.get("incident", {})
        severity = (cra.get("nivel_severidad") or "ALTA").upper()
        badge_color = SEVERITY_COLORS.get(severity, "#ea580c")

        role = (recipient.get("type") or "CRA").upper()
        org_name = recipient.get("organization") or recipient.get("name") or "Suscriptor Mokaná"

        if role == "CRA":
            header_subtitle = "ALERTA TEMPRANA OFICIAL • DESPACHO Y RESPUESTA INSTITUCIONAL C.R.A."
        elif role == "EMPRESA":
            header_subtitle = f"INTELIGENCIA DE DATOS AMBIENTALES & ESG • SUSCRIPCIÓN CORPORATIVA ({org_name})"
        else:
            header_subtitle = f"RED CIENTÍFICA Y MONITOREO ESTUARINO • SUSCRIPCIÓN ACADÉMICA ({org_name})"

        especies_html = ", ".join(cra.get("especies_mangle_riesgo") or ["Manglar estuarino"])
        parametros_html = ", ".join(cra.get("parametros_fisicoquimicos_alterados") or ["En evaluación"])
        etiquetas_html = " ".join(
            f"<span style='background:#e2e8f0;color:#1e293b;padding:3px 8px;border-radius:12px;font-size:12px;margin-right:4px;'>{tag}</span>"
            for tag in (cra.get("etiquetas_datos") or [])
        )

        image_url = inc.get("image_url") or ""
        image_block = (
            f"<div style='margin:16px 0;'><p style='margin:0 0 6px 0;font-weight:bold;color:#0f172a;'>📸 Evidencia Fotográfica Verificada por IA:</p>"
            f"<a href='{image_url}' target='_blank' style='color:#0284c7;'>Ver fotografía en alta resolución</a><br/>"
            f"<img src='{image_url}' alt='Evidencia Manglar' style='max-width:100%;max-height:340px;border-radius:8px;margin-top:8px;border:1px solid #cbd5e1;'/></div>"
            if image_url
            else ""
        )

        return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background-color:#f1f5f9;margin:0;padding:24px;color:#1e293b;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
    <div style="background:#064e3b;color:#ffffff;padding:20px 24px;">
      <div style="font-size:11px;letter-spacing:1.2px;color:#a7f3d0;font-weight:bold;">{header_subtitle}</div>
      <h1 style="margin:6px 0 0 0;font-size:22px;">🌿 MOKANÁ — Reporte #{report.get('id')}</h1>
    </div>

    <div style="padding:24px;">
      <div style="background:#f8fafc;padding:14px 16px;border-radius:8px;border-left:5px solid {badge_color};margin-bottom:20px;">
        <div style="font-size:12px;color:#64748b;">PRIORIDAD / SEVERIDAD IA</div>
        <div style="font-size:18px;font-weight:bold;color:{badge_color};">
          {severity} (Índice de Riesgo: {cra.get('indice_riesgo_ambiental', 78)}/100 • Confianza IA: {cra.get('puntaje_confianza_ia', 90)}% • SLA: {cra.get('sla_tiempo_respuesta_horas', 6)}h)
        </div>
      </div>

      <h2 style="font-size:18px;margin:0 0 12px 0;color:#0f172a;">{cra.get('titulo_hallazgo')}</h2>

      <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:18px;">
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;color:#64748b;width:36%;">📍 Zona / Tótem:</td>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;font-weight:bold;">{loc.get('zone_title')} ({loc.get('lat')}, {loc.get('lng')})</td>
        </tr>
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">🚨 Categoría Reportada:</td>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">{inc.get('category_title')} → <b>{cra.get('subcategoria_tecnica_cra')}</b></td>
        </tr>
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">🏛️ Dependencia C.R.A.:</td>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">{cra.get('dependencia_responsable_cra')}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">💬 Relato del Vigía:</td>
          <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;font-style:italic;">"{inc.get('citizen_description')}"</td>
        </tr>
      </table>

      {image_block}

      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin-bottom:16px;">
        <h3 style="margin:0 0 10px 0;font-size:15px;color:#065f46;">🔬 Clasificación Técnica e Informe Físico-Químico (C.R.A.)</h3>
        <p style="margin:6px 0;font-size:13.5px;"><b>• Coherencia Imagen/Texto:</b> {cra.get('coherencia_foto_descripcion')}</p>
        <p style="margin:6px 0;font-size:13.5px;"><b>• Hallazgo Visual:</b> {cra.get('hallazgo_visual')}</p>
        <p style="margin:6px 0;font-size:13.5px;"><b>• Hipótesis Ambiental y Química:</b> {cra.get('hipotesis_ambiental_quimica')}</p>
        <p style="margin:6px 0;font-size:13.5px;"><b>• Parámetros Fisicoquímicos Críticos:</b> {parametros_html}</p>
        <p style="margin:6px 0;font-size:13.5px;"><b>• Especies en Riesgo:</b> {especies_html}</p>
        <p style="margin:6px 0;font-size:13.5px;"><b>• Normativa Aplicable:</b> {cra.get('normativa_aplicable')}</p>
        <p style="margin:10px 0 0 0;font-size:13.5px;background:#dcfce7;padding:8px 10px;border-radius:6px;"><b>✅ Plan de Acción Recomendado C.R.A.:</b> {cra.get('accion_recomendada_cra')}</p>
      </div>

      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin-bottom:16px;">
        <h3 style="margin:0 0 8px 0;font-size:15px;color:#1e40af;">📊 Inteligencia de Datos para Academia & Empresas (B2B / ESG)</h3>
        <p style="margin:0 0 10px 0;font-size:13.5px;color:#1e3a8a;">{cra.get('valor_analitico_b2b_academia')}</p>
        <div>{etiquetas_html}</div>
      </div>

      <div style="font-size:12px;color:#64748b;text-align:center;margin-top:20px;border-top:1px solid #e2e8f0;padding-top:12px;">
        Generado automáticamente por <b>MOKANÁ</b> • Red de Tótems Inteligentes y Ciencia Ciudadana del Atlántico<br/>
        Fecha UTC: {report.get('created_at')}
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
        """
        Envía correos vía Resend API (`POST https://api.resend.com/emails`) a todos los responsables C.R.A.
        y suscriptores B2B (Empresas/Academia) cuyos filtros coincidan con el reporte.
        """
        matched = [r for r in recipients if self.should_notify_recipient(r, report)]
        delivery_logs: List[Dict[str, Any]] = []

        api_key = email_settings.get("resend_api_key") or RESEND_API_KEY
        from_email = email_settings.get("from_email") or RESEND_FROM_EMAIL

        cra = report.get("cra_technical_report", {})
        loc = report.get("location", {})
        severity = cra.get("nivel_severidad", "ALTA")
        subject = f"[{severity}] MOKANÁ #{report.get('id')} | {loc.get('zone_title')} - {cra.get('titulo_hallazgo')}"

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
                else:
                    logger.info(
                        "Notificación registrada (sin RESEND_API_KEY aún) para %s [%s]",
                        to_email,
                        rec.get("type"),
                    )

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
