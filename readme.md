# MOKANÁ • Plataforma Integral de Alerta Temprana y Monitoreo de Manglares

> Sistema cívico-tecnológico para la detección, verificación por visión computacional y despacho institucional de incidentes ambientales en los ecosistemas estuarinos del Departamento del Atlántico.

---

## 1. Resumen de Arquitectura e Implementación

Desarrollamos **Mokaná** como una solución de extremo a extremo que conecta la presencia ciudadana en territorio (a través de tótems físicos con tags NFC y códigos QR preconfigurados) con un canal conversacional nativo en WhatsApp, un pipeline de inspección visual con Inteligencia Artificial, y una consola institucional web para la **C.R.A. (Corporación Autónoma Regional del Atlántico)** y empresas concesionarias aliadas.

```
[ Tótem NFC / QR ] ──> [ WhatsApp Bot (Zernio API) ]
                               │
                (Imagen + Texto + Ubicación GPS)
                               ▼
            [ Motor de Inferencia Gemini 3.8 Flash ]
            ├── Filtro de Autenticidad (Anti-Falsos Positivos)
            ├── Matriz de Riesgo Calibrada (0 - 100)
            └── Dictamen Técnico Ambiental Estructurado
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [ Notificaciones Resend ]             [ Consola Web Operativa ]
 (Boletín Institucional + 3D)          (SSE en Vivo + Open Data)
```

---

## 2. Ficha Técnica del Sistema

| Parámetro | Especificación Técnica |
| :--- | :--- |
| **Backend & API Gateway** | FastAPI (Python 3.12, Uvicorn ASGI) con streaming reactivo SSE (*Server-Sent Events*). |
| **Canal Conversacional** | Meta Cloud API vía Zernio API (Webhooks autenticados, listas interactivas y solicitud nativa de GPS). |
| **Motor de Visión e IA** | Google Gemini 3.8 Flash (`generativelanguage.googleapis.com` / Vertex AI fallback). |
| **Despacho Institucional** | Resend REST API (Boletines HTML técnicos con vista satelital/3D en Google Maps y logo oficial). |
| **Seguridad & Rate Limiting** | Cooldown per-user (20s entre análisis de IA), ventana de 5 msgs/20s anti-flood y sanitización anti-XSS. |
| **Formatos de Salida Abierta** | Exportación nativa de datos abiertos en CSV, GeoJSON y JSON (`/api/reports/export`). |
| **Despliegue & Contenedores** | Docker & Docker Compose en VPS Debian/Ubuntu con Proxy Inverso Nginx y SSL Let's Encrypt. |
| **Zonas Cubiertas** | Ciénaga de Mallorquín, Balboa (Puerto Colombia), El Totumo, Tubará y Juan de Acosta. |

---

## 3. Módulo de Inteligencia Artificial & Visión Computacional

Para evitar la saturación de los funcionarios de la C.R.A. con reportes basura, imágenes no relacionadas o intentos de distorsión, implementamos un pipeline de doble validación con **Gemini 3.8 Flash**:

1. **Filtro Estricto de Autenticidad:**
   - La IA somete la evidencia gráfica a validación contextual contra la anomalía reportada (*Tala ilegal, Erosión o pérdida de suelo, Coloración anómala, Olor atípico/Vertimiento, Fauna afectada*).
   - Rechaza de forma taxativa capturas de pantalla, papeles en blanco, objetos de oficina o entornos cerrados antes de registrar el incidente.
2. **Matriz de Riesgo y Severidad Calibrada (0 – 100):**
   - **CRÍTICA (85 – 100):** Tala masiva activa de mangle, vertimientos químicos industriales, mortandad súbita de fauna.
   - **ALTA (70 – 84):** Erosión activa con desestabilización de orilla/talud, presencia de manchas oleosas.
   - **MEDIA (40 – 69):** Olores difusos o cambios temporales de turbidez estuarina.
   - **BAJA (0 – 39):** Alteraciones menores o consultas informativas de usuarios.
3. **Generación de Dictamen Ambiental Automatizado:**
   - Determina variables físico-químicas comprometidas, especies vegetales en riesgo (*Rhizophora mangle, Avicennia germinans, Laguncularia racemosa*), marco legal aplicable (Decreto 1076/2015) y coordenadas satelitales 3D.

---

## 4. Puntos de Entrada & Despliegue en Producción

- **URL Pública del Sistema:** `https://mokana.joshual.tech`
- **Consola C.R.A.:** `https://mokana.joshual.tech/cra` (Funcionario: `adalbertoleonk@gmail.com` / `admin@cra.gov.co`)
- **Consola B2B Empresa:** `https://mokana.joshual.tech/empresa` (`operaciones@puertoverde.com`)
- **Stream Reactivo SSE:** `GET /api/events/stream`
- **Exportación Open Data:** `GET /api/reports/export?format=csv|geojson|json`
- **Línea WhatsApp en Vivo:** `+57 313 5865509`

---

## 5. Instrucciones Rápidas de Ejecución (VPS)

```bash
git clone https://github.com/JoshuaLeonK/mokana.git
cd mokana/bot
touch reports_db.json && mkdir -p static/uploads
sudo docker compose up -d --build
```

---

<div align="center">
  <br/>
  <p><strong>Grupo de Desarrollo e Investigación: EFITEC</strong></p>
  <p><strong>Integrantes:</strong> Adalberto León • Ian Marriga • Margie Torres</p>
  <p><em>ManglarHack Atlántico 2026</em></p>
  <br/>
  <code>ManglarHack - EFITEC</code>
</div>
