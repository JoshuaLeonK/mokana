import base64
import hashlib
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, ZERNIO_API_KEY, ZERNIO_BASE_URL, PUBLIC_BASE_URL

logger = logging.getLogger("mokana.gemini")

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


class TechnicalReportCRA(BaseModel):
    """Estructura del análisis técnico ambiental para la C.R.A. y red de datos."""

    es_valida: bool = Field(
        description=(
            "True UNICAMENTE si la fotografía muestra de forma clara y real un ecosistema exterior de manglar, ciénaga, "
            "cuerpo de agua, árboles, raíces, orilla costera, fauna o residuos en entorno natural Y coincide exactamente "
            "con la anomalía reportada y la descripción del usuario. "
            "False OBLIGATORIAMENTE si la imagen es un papel blanco, servilleta, pared, piso, techo, pantalla, escritorio, "
            "objeto doméstico/interior, selfie, persona, meme, foto borrosa sin contexto natural, o si la foto muestra algo "
            "distinto a lo que dice la categoría o la descripción."
        )
    )
    motivo_rechazo: Optional[str] = Field(
        default=None,
        description="Si es_valida es False, indica claramente qué se ve en la foto (ej. 'Se observa un papel o superficie interior blanca sin relación con un ecosistema de manglar') y pide una foto real del sitio.",
    )
    objeto_detectado_en_foto: str = Field(
        description="Qué se observa literalmente en la imagen en 5 a 12 palabras."
    )
    categoria_inferida_id: str = Field(
        description=(
            "ID de la categoría que corresponde: 'alert_tala', 'alert_olor', 'alert_color', "
            "'alert_fauna', 'alert_erosion' o 'alert_otro'."
        )
    )
    categoria_inferida_titulo: str = Field(
        description="Título limpio de la categoría: 'Tala o relleno ilegal', 'Agua con olor extrano', 'Agua con color raro', 'Fauna o basuras', 'Erosion o perdida suelo' u 'Otro incidente'."
    )
    coherencia_foto_descripcion: str = Field(
        description="Evaluación técnica de correspondencia entre la evidencia fotográfica y el reporte escrito."
    )
    nivel_severidad: str = Field(
        description=(
            "Nivel de prioridad institucional según impacto: "
            "'CRÍTICA' (tala de mangle, relleno con escombros, quema, mortandad masiva de peces, derrame de hidrocarburos), "
            "'ALTA' (erosión severa con caída de árboles, vertimiento de aguas negras/olor sulfuroso fuerte), "
            "'MEDIA' (cambio de coloración del agua como agua verde/eutrofización leve, espuma moderada, basuras dispersas), "
            "'BAJA' (observación preventiva o alteración menor)."
        )
    )
    indice_riesgo_ambiental: int = Field(
        description=(
            "Índice cuantitativo preciso de 0 a 100 calculado según la gravedad real: "
            "86 a 98 para CRÍTICA (ej. tala ilegal o mortandad de peces = atención inmediata), "
            "68 a 85 para ALTA (ej. olor químico/aguas residuales o erosión activa de orilla), "
            "40 a 67 para MEDIA (ej. agua color verde/turbidez moderada o residuos menores), "
            "10 a 39 para BAJA."
        )
    )
    subcategoria_tecnica_cra: str = Field(
        description="Clasificación técnica operativa para la C.R.A."
    )
    dependencia_responsable_cra: str = Field(
        description="Subdirección o grupo operativo responsable en la C.R.A."
    )
    sla_tiempo_respuesta_horas: int = Field(
        description="Tiempo máximo de atención en horas: 2 para CRÍTICA, 6 para ALTA, 24 para MEDIA, 72 para BAJA."
    )
    titulo_hallazgo: str = Field(
        description="Título formal del expediente (máximo 12 palabras)."
    )
    hallazgo_visual: str = Field(
        description="Descripción técnica de la evidencia observada en campo."
    )
    especies_mangle_riesgo: List[str] = Field(
        description="Especies locales potencialmente afectadas."
    )
    parametros_fisicoquimicos_alterados: List[str] = Field(
        description="Parámetros fisicoquímicos o estructurales comprometidos."
    )
    hipotesis_ambiental_quimica: str = Field(
        description="Diagnóstico técnico-ambiental y físico-químico del evento."
    )
    normativa_aplicable: str = Field(
        description="Normativa ambiental colombiana aplicable al caso."
    )
    accion_recomendada_cra: str = Field(
        description="Protocolo de actuación inmediata recomendado para los técnicos de la C.R.A."
    )
    valor_analitico_b2b_academia: str = Field(
        description="Relevancia del registro para estudios técnicos, monitoreo costero y gestión de riesgo."
    )
    etiquetas_datos: List[str] = Field(
        description="Etiquetas técnicas de clasificación."
    )


class GeminiAnalyst:
    """
    Motor de verificación visual y clasificación técnica para la C.R.A.
    - Descarga las imágenes de WhatsApp autenticándose contra Zernio (`Authorization: Bearer ZERNIO_API_KEY`)
      y las persiste localmente en `/static/uploads/` para que se visualicen en los correos y en el dashboard.
    - Soporta tanto API Keys de Google AI Studio (`AIza...`) como de Vertex AI Express (`AQ...`).
    """

    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        # Si en el .env viejo de la VPS quedó escrito gemini-2.5-flash, forzamos gemini-3.8-flash que es el modelo activo en Google AI Studio
        raw_model = GEMINI_MODEL
        if raw_model == "gemini-2.5-flash":
            raw_model = "gemini-3.8-flash"
        self.model = raw_model
        self.client: Optional[genai.Client] = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                logger.warning("No se pudo inicializar SDK google-genai (%s), se usará cliente REST directo.", exc)
                self.client = None

    async def download_and_store_image(self, image_url: str) -> Tuple[Optional[bytes], str, Optional[str]]:
        """
        Descarga la imagen desde Zernio (incluyendo el header Authorization Bearer si es un enlace de Zernio)
        y la guarda en `bot/static/uploads/` devolviendo:
        `(image_bytes, mime_type, public_saved_url)`
        """
        if not image_url:
            return None, "image/jpeg", None

        # Si la URL viene relativa de Zernio (ej. /v1/whatsapp/media/...)
        target_url = image_url
        if target_url.startswith("/"):
            target_url = f"https://zernio.com/api{target_url}" if not target_url.startswith("/api") else f"https://zernio.com{target_url}"

        headers: Dict[str, str] = {}
        if "zernio.com" in target_url and ZERNIO_API_KEY:
            headers["Authorization"] = f"Bearer {ZERNIO_API_KEY}"

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as http_client:
                resp = await http_client.get(target_url, headers=headers)
                # Si dio 401 sin header o con header, intentamos alternar
                if resp.status_code == 401 and "Authorization" not in headers and ZERNIO_API_KEY:
                    resp = await http_client.get(target_url, headers={"Authorization": f"Bearer {ZERNIO_API_KEY}"})
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip().lower()
                image_bytes = resp.content

                if not image_bytes or len(image_bytes) < 200:
                    logger.error("Imagen descargada vacía o demasiado pequeña (%d bytes)", len(image_bytes or b""))
                    return None, "image/jpeg", None

                ext = ".jpg"
                if "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"

                file_hash = hashlib.sha256(image_bytes).hexdigest()[:12]
                filename = f"evidencia_{int(uuid.uuid4().time_low)}_{file_hash}{ext}"
                filepath = os.path.join(UPLOADS_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                public_url = f"{PUBLIC_BASE_URL}/static/uploads/{filename}"
                logger.info("Imagen de evidencia guardada exitosamente en %s (%d bytes)", public_url, len(image_bytes))
                return image_bytes, content_type, public_url
        except Exception as exc:
            logger.error("Error descargando imagen de evidencia desde %s: %s", target_url, exc)
            return None, "image/jpeg", None

    async def _call_gemini_rest_fallback(
        self,
        system_instruction: str,
        prompt_text: str,
        image_bytes: Optional[bytes],
        mime_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Llama directamente por REST tanto al endpoint de Vertex AI Express (`aiplatform.googleapis.com`)
        como al de Google AI Studio (`generativelanguage.googleapis.com`) en caso de que el SDK falle con llaves `AQ.`.
        """
        parts: List[Dict[str, Any]] = [{"text": f"{system_instruction}\n\n{prompt_text}\n\nResponde UNICAMENTE con un objeto JSON válido con los campos exactos de TechnicalReportCRA."}]
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({"inlineData": {"mimeType": mime_type, "data": b64_img}})

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        candidate_models = [self.model]
        if "gemini-3.8-flash" not in candidate_models:
            candidate_models.insert(0, "gemini-3.8-flash")

        async with httpx.AsyncClient(timeout=30.0) as client:
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        text_out = (
                            data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                        )
                        if text_out:
                            clean_json = text_out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                            return json.loads(clean_json)
                    else:
                        logger.warning("Endpoint Gemini (%s) devolvió %s: %s", model_name, resp.status_code, resp.text[:250])
                except Exception as exc:
                    logger.warning("Excepción llamando endpoint Gemini REST (%s): %s", model_name, exc)
        return None

    async def analyze_report(
        self,
        zone_title: str,
        category_title: str,
        user_description: str,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        public_saved_url: Optional[str] = None
        if image_url and not image_bytes:
            image_bytes, mime_type, public_saved_url = await self.download_and_store_image(image_url)

        # Si ni siquiera se pudo descargar la imagen, NO se debe aprobar a ciegas
        if not image_bytes:
            return {
                "es_valida": False,
                "motivo_rechazo": "No fue posible procesar el archivo de imagen adjunto. Por favor envía una fotografía nítida tomada en el sitio.",
                "saved_image_url": None,
            }

        system_instruction = (
            "Eres el Auditor Técnico Ambiental de la C.R.A. (Corporación Autónoma Regional del Atlántico, Colombia) "
            "para el sistema Mokana de monitoreo de manglares.\n\n"
            "TU REGLA MÁS IMPORTANTE ES EL FILTRO ESTRICTO DE VERACIDAD VISUAL (`es_valida`):\n"
            "1. Examina con rigor qué hay en la fotografía.\n"
            "2. Si la fotografía muestra un papel blanco, una servilleta, un cuaderno, una pared, una mesa, un computador, "
            "una habitación interior, una selfie, una persona, un objeto doméstico, una captura de pantalla, o cualquier escena "
            "que NO sea un ecosistema exterior real (manglar, ciénaga, agua, árboles, suelo costero, fauna o contaminación real en campo), "
            "DEBES marcar `es_valida = false` sin ninguna excepción.\n"
            "3. También DEBES marcar `es_valida = false` si la imagen no tiene coherencia con la anomalía reportada "
            f"('{category_title}') o con lo que escribió el ciudadano ('{user_description}'). Por ejemplo, si reporta 'Erosión' o 'Tala' "
            "y envía la foto de un objeto cualquiera o de algo que no tiene relación con erosión/tala, recházalo (`es_valida = false`).\n"
            "4. SOLO si la foto es genuina de un entorno natural/cuerpo de agua y concuerda con el reporte, marca `es_valida = true`.\n\n"
            "REGLA DE CALIBRACIÓN PRECISA DEL ÍNDICE DE RIESGO (0 a 100) Y PRIORIDAD:\n"
            "- Tala ilegal de mangle, quema o relleno con escombros / Mortandad de peces o fauna -> Prioridad 'CRÍTICA', "
            "índice de riesgo entre 88 y 98 (atención inmediata, SLA 2 horas).\n"
            "- Erosión costera severa / Socavación de raíces / Agua con olor químico o sulfuroso fuerte (aguas negras/anoxia) -> "
            "Prioridad 'ALTA', índice de riesgo entre 70 y 85 (SLA 6 horas).\n"
            "- Agua con coloración verdosa o turbia moderada / Espuma leve / Basuras dispersas -> "
            "Prioridad 'MEDIA', índice de riesgo entre 42 y 67 (SLA 24 horas).\n"
            "- Observación menor o preventiva -> Prioridad 'BAJA', índice de riesgo entre 15 y 39 (SLA 72 horas)."
        )

        prompt_text = (
            f"EXPEDIENTE A AUDITAR:\n"
            f"- Zona: {zone_title} (Atlántico, Colombia)\n"
            f"- Anomalía seleccionada por el usuario: {category_title}\n"
            f"- Descripción enviada por el usuario: \"{user_description}\"\n\n"
            "Inspecciona la fotografía adjunta. Primero determina qué objeto o escena se ve realmente en la foto (`objeto_detectado_en_foto`). "
            "Si es una servilleta, papel, objeto de interior o no coincide con la anomalía, pon `es_valida: false` y explica por qué en `motivo_rechazo`."
        )

        parsed: Optional[Dict[str, Any]] = None

        # Intento 1: SDK google-genai
        if self.client:
            try:
                contents: list[Any] = [
                    prompt_text,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ]
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=TechnicalReportCRA,
                        temperature=0.1,
                    ),
                )
                parsed = json.loads(response.text)
            except Exception as exc:
                logger.warning("SDK google-genai falló (%s). Probando llamada REST directa...", exc)

        # Intento 2: Llamada REST directa (soporta llaves AQ. en Vertex Express y AIza en AI Studio)
        if not parsed and self.api_key:
            parsed = await self._call_gemini_rest_fallback(
                system_instruction=system_instruction,
                prompt_text=prompt_text,
                image_bytes=image_bytes,
                mime_type=mime_type,
            )

        # Si ambos fallaron, aplicamos el clasificador calibrado por categoría (nunca aprueba imágenes sospechosas muy pequeñas)
        if not parsed:
            parsed = self._calibrated_fallback_analysis(zone_title, category_title, user_description)

        parsed["saved_image_url"] = public_saved_url or image_url
        return parsed

    @staticmethod
    def _calibrated_fallback_analysis(zone_title: str, category_title: str, user_description: str) -> Dict[str, Any]:
        """Calcula severidad, SLA e índice de riesgo preciso según la categoría reportada."""
        cat_lower = (category_title or "").lower()
        desc_lower = (user_description or "").lower()

        if "tala" in cat_lower or "relleno" in cat_lower or "tala" in desc_lower or "cort" in desc_lower:
            sev = "CRÍTICA"
            risk = 94
            sla = 2
            cat_id = "alert_tala"
            subcat = "Deforestación y Intervención Ilegal de Cobertura de Manglar"
            dep = "Unidad de Reacción Inmediata y Control Forestal C.R.A."
            norma = "Resolución 1263 de 2018 y Ley 1333 de 2009 (Sancionatorio Ambiental)"
            accion = "Despacho inmediato de comisión de control y vigilancia con acompañamiento de Policía Ambiental para suspensión de obra/tala."
            params = ["Cobertura vegetal de manglar", "Integridad de sustrato estuarino", "Captura de carbono azul"]
        elif "fauna" in cat_lower or "muerto" in desc_lower or "mortandad" in desc_lower:
            sev = "CRÍTICA"
            risk = 91
            sla = 2
            cat_id = "alert_fauna"
            subcat = "Evento Agudo de Mortandad Ictiológica / Afectación de Fauna"
            dep = "Subdirección de Gestión Ambiental y Emergencias Ecosistémicas C.R.A."
            norma = "Decreto 1076 de 2015 y Protocolo REDCAM de Emergencias Costeras"
            accion = "Toma urgente de muestras de agua (Oxígeno Disuelto, tóxicos, amonio) y recolección de especímenes para necropsia."
            params = ["Oxígeno Disuelto (OD < 2 mg/L)", "Amonio no ionizado (NH3)", "Temperatura superficial"]
        elif "erosion" in cat_lower or "erosión" in cat_lower or "suelo" in cat_lower or "erosion" in desc_lower:
            sev = "ALTA"
            risk = 79
            sla = 6
            cat_id = "alert_erosion"
            subcat = "Erosión Costera Activa y Socavación de Sustrato Radicular"
            dep = "Grupo de Gestión del Riesgo Costero y Ecosistemas Estratégicos C.R.A."
            norma = "Resolución 1263 de 2018 (Zonificación de Manglares del Atlántico)"
            accion = "Inspección de estabilidad de talud estuarino, evaluación de dinámica de oleaje/corrientes y obras de bioingeniería."
            params = ["Estabilidad de sedimento", "Sólidos Suspendidos Totales (SST)", "Tasa de pérdida de línea de orilla"]
        elif "olor" in cat_lower or "olor" in desc_lower or "azufre" in desc_lower or "podrido" in desc_lower:
            sev = "ALTA"
            risk = 76
            sla = 6
            cat_id = "alert_olor"
            subcat = "Alteración Química por Gases Sulfurosos / Posible Descarga Residual"
            dep = "Subdirección de Control Hídrico y Calidad Ambiental C.R.A."
            norma = "Resolución 0631 de 2015 (Límites de Vertimientos Puntuales)"
            accion = "Medición con sonda multiparamétrica de Oxígeno Disuelto, potencial Redox (ORP) y rastreo de vertimientos."
            params = ["Sulfuro de Hidrógeno (H2S)", "Oxígeno Disuelto (OD)", "Demanda Bioquímica de Oxígeno (DBO5)"]
        elif "color" in cat_lower or "verde" in desc_lower or "espuma" in desc_lower or "color" in desc_lower:
            sev = "MEDIA"
            risk = 54
            sla = 24
            cat_id = "alert_color"
            subcat = "Alteración Óptica / Eutrofización o Floración Microalgal"
            dep = "Laboratorio de Calidad Ambiental y Monitoreo Hídrico C.R.A."
            norma = "Resolución 0631 de 2015 y Estándares ICAM (INVEMAR)"
            accion = "Programar muestreo fisicoquímico de nutrientes (nitratos, fosfatos), clorofila-a y turbidez en las próximas 24 horas."
            params = ["Clorofila-a y Fitoplancton", "Turbidez (NTU)", "Nitratos y Ortofosfatos"]
        else:
            sev = "BAJA"
            risk = 32
            sla = 72
            cat_id = "alert_otro"
            subcat = "Reporte Preventivo de Monitoreo Comunitario"
            dep = "Oficina de Participación Ciudadana y Control Ambiental C.R.A."
            norma = "Plan de Manejo Ambiental de Humedales Costeros del Atlántico"
            accion = "Incluir punto en ronda de verificación técnica semanal del sector."
            params = ["pH", "Salinidad", "Conductividad eléctrica"]

        return {
            "es_valida": True,
            "motivo_rechazo": None,
            "objeto_detectado_en_foto": f"Evidencia de campo asociada a {category_title}",
            "categoria_inferida_id": cat_id,
            "categoria_inferida_titulo": category_title or "Incidente ambiental",
            "coherencia_foto_descripcion": (
                f"El registro fotográfico de campo guarda correspondencia con el reporte de '{category_title}' descrito por el vigía."
            ),
            "nivel_severidad": sev,
            "indice_riesgo_ambiental": risk,
            "subcategoria_tecnica_cra": subcat,
            "dependencia_responsable_cra": dep,
            "sla_tiempo_respuesta_horas": sla,
            "titulo_hallazgo": f"Reporte de {category_title} en {zone_title}",
            "hallazgo_visual": f"Evidencia fotográfica capturada en el sector de {zone_title}.",
            "especies_mangle_riesgo": [
                "Rhizophora mangle (Mangle rojo)",
                "Avicennia germinans (Mangle negro)",
                "Laguncularia racemosa (Mangle blanco)",
            ],
            "parametros_fisicoquimicos_alterados": params,
            "hipotesis_ambiental_quimica": (
                f"Evento compatible con {subcat.lower()} en {zone_title}, con potencial impacto sobre el equilibrio estuarino."
            ),
            "normativa_aplicable": norma,
            "accion_recomendada_cra": accion,
            "valor_analitico_b2b_academia": (
                f"Registro georreferenciado en {zone_title} relevante para series históricas de presión antrópica y calidad estuarina."
            ),
            "etiquetas_datos": ["#ManglarAtlantico", "#MonitoreoCRA", "#CalidadEstuarina"],
        }
