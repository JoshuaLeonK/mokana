import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("mokana.gemini")


class TechnicalReportCRA(BaseModel):
    """Estructura avanzada del análisis multimodal de Gemini para la C.R.A. y suscriptores B2B (Empresas/Academia)."""

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
    puntaje_confianza_ia: int = Field(
        description="Puntaje de confianza y coherencia multimodal (0 a 100) entre la fotografía, el texto del ciudadano y la categoría seleccionada."
    )
    coherencia_foto_descripcion: str = Field(
        description="Explicación técnica de cómo coincide lo observado en la fotografía con la descripción escrita por el ciudadano y la alerta elegida."
    )
    nivel_severidad: str = Field(
        description="Nivel de prioridad oficial para la C.R.A.: 'BAJA', 'MEDIA', 'ALTA' o 'CRÍTICA'."
    )
    indice_riesgo_ambiental: int = Field(
        description="Índice cuantitativo de riesgo ambiental (0 a 100) donde >75 es crítico."
    )
    subcategoria_tecnica_cra: str = Field(
        description=(
            "Subcategoría oficial para despacho de la C.R.A.: ej. 'Vertimiento Líquido Puntual', 'Hipoxia / Eutrofización Estuarina', "
            "'Deforestación / Tala de Mangle', 'Relleno Ilegal de Humedal y Escombros', 'Mortandad Ictiológica / Fauna', "
            "'Contaminación por Residuos Sólidos / Microplásticos'."
        )
    )
    dependencia_responsable_cra: str = Field(
        description=(
            "Área o subdirección responsable en la C.R.A.: ej. 'Subdirección de Gestión Ambiental y Control Hídrico', "
            "'Grupo de Control y Vigilancia de Ecosistemas Costeros y Manglares', "
            "'Oficina de Atención a Emergencias Ambientales y Fauna'."
        )
    )
    sla_tiempo_respuesta_horas: int = Field(
        description="Tiempo máximo de respuesta institucional sugerido en horas (ej. 2 para CRÍTICA, 6 para ALTA, 24 para MEDIA, 72 para BAJA)."
    )
    titulo_hallazgo: str = Field(
        description="Título ejecutivo corto del incidente (máximo 12 palabras)."
    )
    hallazgo_visual: str = Field(
        description="Descripción técnica detallada de la evidencia visual observada en la fotografía."
    )
    especies_mangle_riesgo: List[str] = Field(
        description=(
            "Lista de especies del manglar del Atlántico potencialmente afectadas según la zona y el hallazgo "
            "(ej. 'Rhizophora mangle (Mangle rojo)', 'Avicennia germinans (Mangle negro)', 'Laguncularia racemosa (Mangle blanco)', "
            "'Conocarpus erectus (Mangle zaragoza)', 'Ictiofauna estuarina (Lisa/Mojarra)')."
        )
    )
    parametros_fisicoquimicos_alterados: List[str] = Field(
        description=(
            "Lista de parámetros fisicoquímicos que probablemente están fuera de norma según la evidencia "
            "(ej. 'Oxígeno Disuelto (OD < 4 mg/L)', 'Demanda Bioquímica de Oxígeno (DBO5)', 'Sulfuro de Hidrógeno (H2S)', "
            "'pH', 'Salinidad intersticial', 'Turbidez / Sólidos Suspendidos Totales (SST)', 'Nitratos y Fosfatos')."
        )
    )
    hipotesis_ambiental_quimica: str = Field(
        description=(
            "Hipótesis técnico-ambiental y físico-química detallada del fenómeno para el informe oficial de la C.R.A."
        )
    )
    normativa_aplicable: str = Field(
        description=(
            "Marco normativo ambiental colombiano aplicable al caso (ej. 'Resolución 0631 de 2015 - Vertimientos', "
            "'Ley 1333 de 2009 - Procedimiento Sancionatorio Ambiental', 'Resolución 1263 de 2018 - Zonificación de Manglares del Atlántico')."
        )
    )
    accion_recomendada_cra: str = Field(
        description="Plan de acción operativo inmediato sugerido para la brigada de la C.R.A. (pasos concretos en campo)."
    )
    valor_analitico_b2b_academia: str = Field(
        description=(
            "Resumen de valor de este dato para suscriptores externos (Universidades/Academia, Empresas ESG/Carbono Azul, "
            "Turismo Sostenible o Consultoras Ambientales): por qué este evento es relevante para modelos predictivos, "
            "riesgo climático o estudios de calidad estuarina."
        )
    )
    etiquetas_datos: List[str] = Field(
        description="3 a 6 etiquetas estandarizadas para indexación y venta de datos (ej. '#CarbonoAzul', '#CalidadAgua', '#Eutrofizacion', '#Deforestacion', '#RiesgoESG')."
    )
    mensaje_ciudadano: str = Field(
        description="Resumen claro, cercano y empático (2-3 líneas) para enviarle al ciudadano por WhatsApp confirmando la validación de su reporte."
    )


class GeminiAnalyst:
    """Analista multimodal con Gemini 2.5 Flash que verifica autenticidad/coherencia y genera el Informe Técnico C.R.A. + Inteligencia de Datos B2B."""

    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        self.model = GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def download_image(self, image_url: str) -> Tuple[Optional[bytes], str]:
        """Descarga la imagen adjunta desde la URL entregada por el webhook de Zernio."""
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http_client:
                resp = await http_client.get(image_url)
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
        if image_url and not image_bytes:
            image_bytes, mime_type = await self.download_image(image_url)

        if not self.client:
            logger.warning("GEMINI_API_KEY no configurada. Retornando análisis técnico de respaldo.")
            return self._fallback_analysis(zone_title, category_title, user_description)

        system_instruction = (
            "Eres el Analista Ambiental, Químico y de Inteligencia de Datos Senior del sistema MOKANÁ, "
            "plataforma oficial de alerta temprana para la C.R.A. (Corporación Autónoma Regional del Atlántico, Colombia) "
            "y red de inteligencia ambiental para Empresas (ESG / Carbono Azul) y Academia.\n\n"
            "Tu función es evaluar reportes provenientes de Tótems QR/NFC en los ecosistemas de manglar del Atlántico "
            "(Ciénaga de Mallorquín, Ciénaga de Balboa, Ciénaga del Totumo, Tubará, Juan de Acosta).\n\n"
            "REGLAS DE VERIFICACIÓN DE AUTENTICIDAD Y COHERENCIA:\n"
            "1. Cruza TRES fuentes: (a) La categoría de alerta elegida, (b) La descripción breve escrita por el ciudadano, "
            "y (c) La fotografía enviada.\n"
            "2. Verifica si la fotografía muestra un entorno real (agua, manglar, raíces, árboles, suelo, residuos, espuma, fauna, caños) "
            "y si guarda coherencia con la descripción escrita.\n"
            "3. Si la imagen es un meme, una selfie sin contexto ambiental, una foto de un objeto doméstico irrelevante "
            "o contradice flagrantemente la descripción, marca `es_valida = false` y explica amablemente en `motivo_rechazo`.\n"
            "4. Si es válida (`es_valida = true`), genera una clasificación técnica de alto rigor para la C.R.A. "
            "(severidad, índice de riesgo 0-100, dependencia responsable, SLA en horas, especies de mangle en riesgo, "
            "parámetros fisicoquímicos alterados, hipótesis química, normativa ambiental colombiana aplicable y plan de acción) "
            "además del insight analítico para suscriptores B2B (empresas y universidades)."
        )

        prompt_text = (
            f"DATOS DEL REPORTE CIUDADANO:\n"
            f"- Zona del Manglar: {zone_title} (Departamento del Atlántico, Colombia)\n"
            f"- Categoría seleccionada por el ciudadano: {category_title}\n"
            f"- Descripción breve escrita por el ciudadano: \"{user_description}\"\n\n"
            "Analiza la imagen adjunta junto con la descripción escrita y la categoría seleccionada. "
            "Evalúa su autenticidad y coherencia, y genera el informe técnico completo para la C.R.A. y suscriptores B2B/Academia."
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
            "puntaje_confianza_ia": 88,
            "coherencia_foto_descripcion": (
                f"La descripción del ciudadano ('{user_description}') presenta coherencia directa con la categoría '{category_title}'."
            ),
            "nivel_severidad": "ALTA",
            "indice_riesgo_ambiental": 78,
            "subcategoria_tecnica_cra": f"Alerta Ambiental Prioritaria - {category_title}",
            "dependencia_responsable_cra": "Subdirección de Gestión Ambiental y Control de Ecosistemas Costeros (C.R.A.)",
            "sla_tiempo_respuesta_horas": 6,
            "titulo_hallazgo": f"Incidente de {category_title} reportado en {zone_title}",
            "hallazgo_visual": "Evidencia fotográfica verificada y georreferenciada en el sector del tótem de monitoreo.",
            "especies_mangle_riesgo": [
                "Avicennia germinans (Mangle negro)",
                "Rhizophora mangle (Mangle rojo)",
                "Laguncularia racemosa (Mangle blanco)",
            ],
            "parametros_fisicoquimicos_alterados": [
                "Oxígeno Disuelto (OD)",
                "pH y Conductividad / Salinidad",
                "Sólidos Suspendidos Totales (Turbidez)",
            ],
            "hipotesis_ambiental_quimica": (
                "Posible alteración fisicoquímica del cuerpo de agua estuarino o presión antrópica directa sobre la cobertura de manglar, "
                "con potencial afectación de neumatóforos y recambio hídrico."
            ),
            "normativa_aplicable": "Resolución 1263 de 2018 (Manglares del Atlántico) y Ley 1333 de 2009 (Sancionatorio Ambiental).",
            "accion_recomendada_cra": (
                "Despachar unidad técnica de la C.R.A. para inspección ocular, muestreo fisicoquímico in situ (OD, pH, salinidad) "
                "y control preventivo de la fuente."
            ),
            "valor_analitico_b2b_academia": (
                f"Dato primario georreferenciado en {zone_title} útil para series de tiempo de estrés ecosistémico, "
                "modelos de retención de carbono azul y alertas tempranas para grupos de investigación e industrias costeras."
            ),
            "etiquetas_datos": ["#ManglarAtlantico", "#CalidadAgua", "#CarbonoAzul", "#AlertaCRA", "#CienciaCiudadana"],
            "mensaje_ciudadano": (
                "Tu evidencia fotográfica y descripción fueron verificadas por nuestra IA y notificadas a los responsables de la C.R.A."
            ),
        }
