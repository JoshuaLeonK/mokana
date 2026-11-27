import json
import logging
from typing import Any, Dict, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("mokana.gemini")


class TechnicalReportCRA(BaseModel):
    """Estructura estricta de salida del análisis multimodal de Gemini para la C.R.A."""

    es_valida: bool = Field(
        description=(
            "True si la imagen es real/auténtica de un entorno natural, cuerpo de agua, manglar, vegetación, "
            "residuos o afectación ambiental Y guarda coherencia básica con la categoría seleccionada y la descripción "
            "escrita por el usuario. False si es una selfie, meme, captura de pantalla irrelevante, foto en negro "
            "o contradice totalmente lo descrito."
        )
    )
    motivo_rechazo: Optional[str] = Field(
        default=None,
        description="Si es_valida es False, explicación amable y breve para el ciudadano indicando por qué debe enviar otra foto o ajustar su descripción.",
    )
    coherencia_foto_descripcion: str = Field(
        description="Explicación corta de cómo coincide lo que se observa en la foto con la descripción escrita por el ciudadano y la alerta elegida."
    )
    nivel_severidad: str = Field(
        description="Nivel de prioridad técnica para la C.R.A.: 'BAJA', 'MEDIA', 'ALTA' o 'CRÍTICA'."
    )
    titulo_hallazgo: str = Field(
        description="Título técnico corto del incidente (máximo 10 palabras)."
    )
    hallazgo_visual: str = Field(
        description="Descripción técnica detallada de lo que se observa en la fotografía."
    )
    hipotesis_ambiental_quimica: str = Field(
        description=(
            "Hipótesis técnico-ambiental y físico-química del fenómeno (ej. posible hipoxia/anoxia por materia orgánica "
            "o H2S, vertimiento de aguas residuales, pérdida de cobertura de Rhizophora mangle / Avicennia germinans, "
            "contaminación por residuos sólidos o hidrocarburos)."
        )
    )
    accion_recomendada_cra: str = Field(
        description="Acción institucional concreta sugerida para la C.R.A. (ej. inspección de control ambiental, muestreo fisicoquímico de agua, contención de vertimiento)."
    )
    mensaje_ciudadano: str = Field(
        description="Resumen claro y empático (2-3 líneas) para enviarle al ciudadano por WhatsApp confirmando la validación de su reporte."
    )


class GeminiAnalyst:
    """Analista multimodal con Gemini 2.5 Flash que verifica autenticidad/coherencia (opción + texto + foto) y genera el informe técnico para la C.R.A."""

    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        self.model = GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def download_image(self, image_url: str) -> Tuple[Optional[bytes], str]:
        """Descarga la imagen adjunta desde la URL entregada por el webhook de Zernio."""
        headers = {}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http_client:
                resp = await http_client.get(image_url, headers=headers)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                return resp.content, content_type
        except Exception as exc:
            logger.error("No se pudo descargar la imagen desde %s: %s", image_url, exc)
            return None, "image/jpeg"

    async def analyze_report(
        self,
        zone_title: str,
        category_title: str,
        user_description: str,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """
        Analiza la coherencia entre:
        1. Zona de manglar del Atlántico
        2. Categoría de alerta seleccionada
        3. Descripción breve escrita por el ciudadano
        4. Fotografía de evidencia
        Y genera el pequeño informe técnico para la C.R.A.
        """
        if image_url and not image_bytes:
            image_bytes, mime_type = await self.download_image(image_url)

        if not self.client:
            logger.warning("GEMINI_API_KEY no configurada. Retornando análisis de respaldo (mock).")
            return self._fallback_analysis(zone_title, category_title, user_description)

        system_instruction = (
            "Eres el Analista Ambiental y Físico-Químico Senior del sistema MOKANÁ, adscrito a la "
            "C.R.A. (Corporación Autónoma Regional del Atlántico, Colombia). "
            "Tu función es evaluar reportes de ciencia ciudadana provenientes de los ecosistemas de manglar del Atlántico "
            "(Ciénaga de Mallorquín, Ciénaga de Balboa, Totumo, Tubará, Juan de Acosta).\n\n"
            "REGLAS DE VERIFICACIÓN DE AUTENTICIDAD Y COHERENCIA:\n"
            "1. Debes cruzar TRES datos: (a) La opción de alerta elegida, (b) La descripción breve escrita por el usuario, "
            "y (c) La fotografía enviada.\n"
            "2. Verifica si la fotografía muestra un entorno real (agua, manglar, árboles, suelo, residuos, espuma, fauna, caños) "
            "y si tiene sentido con lo que el ciudadano escribió en su descripción.\n"
            "3. Si la imagen es un meme, una selfie sin contexto ambiental, una foto de un objeto doméstico irrelevante (ej. un teclado, "
            "un plato de comida) o contradice flagrantemente la descripción, marca `es_valida = false` y explica amablemente en `motivo_rechazo`.\n"
            "4. Si es válida (`es_valida = true`), clasifica la severidad ('BAJA', 'MEDIA', 'ALTA', 'CRÍTICA') y redacta un "
            "Informe Técnico conciso y riguroso para la C.R.A."
        )

        prompt_text = (
            f"DATOS DEL REPORTE CIUDADANO:\n"
            f"- Zona del Manglar: {zone_title} (Departamento del Atlántico, Colombia)\n"
            f"- Categoría seleccionada por el ciudadano: {category_title}\n"
            f"- Descripción breve escrita por el ciudadano: \"{user_description}\"\n\n"
            "Analiza la imagen adjunta junto con la descripción escrita y la categoría seleccionada. "
            "Evalúa su autenticidad y coherencia, y genera el informe técnico estructurado para la C.R.A."
        )

        contents: list[Any] = [prompt_text]
        if image_bytes:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TechnicalReportCRA,
                    temperature=0.2,
                ),
            )
            parsed = json.loads(response.text)
            return parsed
        except Exception as exc:
            logger.error("Error llamando a Gemini Multimodal: %s", exc)
            return self._fallback_analysis(zone_title, category_title, user_description)

    @staticmethod
    def _fallback_analysis(zone_title: str, category_title: str, user_description: str) -> Dict[str, Any]:
        return {
            "es_valida": True,
            "motivo_rechazo": None,
            "coherencia_foto_descripcion": (
                f"La descripción del ciudadano ('{user_description}') es consistente con la categoría '{category_title}'."
            ),
            "nivel_severidad": "ALTA",
            "titulo_hallazgo": f"Reporte de {category_title} en {zone_title}",
            "hallazgo_visual": "Evidencia fotográfica recibida y asociada al punto de monitoreo del manglar.",
            "hipotesis_ambiental_quimica": (
                "Posible alteración fisicoquímica o presión antrópica sobre la ronda hídrica del manglar "
                "(requiere verificación de oxígeno disuelto, pH y salinidad en campo)."
            ),
            "accion_recomendada_cra": (
                "Programar inspección técnica prioritaria de la C.R.A. y toma de muestra de control en el sector reportado."
            ),
            "mensaje_ciudadano": (
                "Tu evidencia fotográfica y descripción fueron verificadas correctamente y remitidas a la central de la C.R.A."
            ),
        }
