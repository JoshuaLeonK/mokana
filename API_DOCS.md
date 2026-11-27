# 🌿 MOKANÁ — Documentación Técnica de APIs (Panel de Administración, Bot WhatsApp & Notificaciones Resend)

**Base URL en Producción:** `https://mokana.joshual.tech`  
**Puerto Interno (Docker / VPS):** `8089`  
**Documentación Interactiva Swagger UI:** `https://mokana.joshual.tech/docs`  

---

## 1. Arquitectura de Integración en Tiempo Real

El servidor de **Mokaná** expone una API RESTful + un canal de **Server-Sent Events (SSE)** en tiempo real para que el **Panel de Administración (Frontend)** pueda:
1. **Recibir en vivo** los reportes enviados desde los **Tótems QR/NFC → Bot de WhatsApp**, ya verificados y clasificados técnicamente por **Gemini 2.5 Flash**.
2. **Enviar nuevos reportes** desde el Portal Web del Tótem y **actualizar estados/responsables/notas** desde el Panel C.R.A. (notificando de vuelta al ciudadano por WhatsApp).
3. **Configurar y administrar destinatarios de correo electrónico (vía Resend)** tanto para funcionarios de la **C.R.A.** como para los **clientes B2B (Empresas ESG/Carbono Azul y Universidades/Academia)** que compran o se suscriben a la inteligencia de datos del manglar.

---

## 2. Canal en Tiempo Real para el Frontend (Server-Sent Events - SSE)

### `GET /api/events/stream`
Permite al Panel de Administración escuchar en vivo cualquier nuevo reporte o cambio de estado sin hacer polling constante.

#### Ejemplo de consumo en React / Next.js / Vanilla JS:
```javascript
const eventSource = new EventSource("https://mokana.joshual.tech/api/events/stream");

eventSource.onmessage = (e) => {
  const payload = JSON.parse(e.data);
  if (payload.event === "report.created") {
    console.log("🚨 Nuevo reporte verificado por IA:", payload.data);
    // Agregar al inicio de la tabla y pintar marcador en el mapa
  }
  if (payload.event === "report.updated") {
    console.log("🔄 Reporte actualizado:", payload.data);
    // Actualizar estado o coordenadas GPS en el mapa
  }
  if (payload.event === "subscriber.created") {
    console.log("📧 Nuevo suscriptor B2B/CRA:", payload.data);
  }
};
```

---

## 3. Endpoints de Reportes y Clasificación Técnica IA (C.R.A.)

### 3.1. Listar todos los reportes (con filtros)
**`GET /api/reports`**

* **Query Params (Todos opcionales):**
  * `zone_id`: `zone_mallorquin` | `zone_balboa` | `zone_totumo` | `zone_tubara` | `zone_juan_acosta`
  * `category_id`: `alert_tala` | `alert_olor` | `alert_color` | `alert_fauna` | `alert_otro`
  * `severity`: `BAJA` | `MEDIA` | `ALTA` | `CRÍTICA`
  * `status`: `PENDIENTE_REVISION_CRA` | `EN_VERIFICACION_CAMPO` | `BRIGADA_DESPACHADA` | `RESUELTO` | `DESCARTADO`

#### Respuesta Ejemplo (`200 OK`):
```json
{
  "count": 1,
  "reports": [
    {
      "id": "MKN-2026-0001",
      "created_at": "2026-11-27T18:45:12.110234+00:00",
      "updated_at": "2026-11-27T18:45:14.540120+00:00",
      "source": "WHATSAPP_TOTEM",
      "status": "PENDIENTE_REVISION_CRA",
      "assigned_to": "Subdirección de Gestión Ambiental y Control Hídrico",
      "cra_notes": [],
      "conversation_id": "6b09d123...",
      "citizen": {
        "phone": "+573001501565",
        "name": "Vigía Ciudadano"
      },
      "location": {
        "zone_id": "zone_mallorquin",
        "zone_title": "Ciénaga de Mallorquín",
        "lat": 11.0458,
        "lng": -74.8461,
        "has_exact_gps": false
      },
      "incident": {
        "category_id": "alert_color",
        "category_title": "🎨 Agua con color raro",
        "citizen_description": "El agua cerca al puente tiene espuma blanca espesa y manchas oscuras.",
        "image_url": "https://cdn.zernio.com/media/evidencia_01.jpg"
      },
      "cra_technical_report": {
        "es_valida": true,
        "puntaje_confianza_ia": 94,
        "nivel_severidad": "ALTA",
        "indice_riesgo_ambiental": 82,
        "subcategoria_tecnica_cra": "Vertimiento Líquido Puntual / Eutrofización Estuarina",
        "dependencia_responsable_cra": "Subdirección de Gestión Ambiental y Control Hídrico",
        "sla_tiempo_respuesta_horas": 6,
        "titulo_hallazgo": "Presencia de espuma tensioactiva y turbidez anómala en Ciénaga de Mallorquín",
        "coherencia_foto_descripcion": "La fotografía muestra claramente acumulación de espuma superficial densa y coloración oscura en la orilla del manglar, coincidiendo al 100% con el relato del ciudadano.",
        "hallazgo_visual": "Lámina de agua con espuma blanca persistente y coloración pardo-oscura próxima a raíces de mangle.",
        "especies_mangle_riesgo": [
          "Avicennia germinans (Mangle negro)",
          "Rhizophora mangle (Mangle rojo)",
          "Ictiofauna estuarina (Lisa/Mojarra)"
        ],
        "parametros_fisicoquimicos_alterados": [
          "Oxígeno Disuelto (OD < 4 mg/L)",
          "Demanda Bioquímica de Oxígeno (DBO5)",
          "Nitratos, Fosfatos y Tensioactivos"
        ],
        "hipotesis_ambiental_quimica": "Posible descarga de aguas residuales domésticas o detergentes que reducen la transferencia de oxígeno en la interfase agua-aire y generan estrés hipóxico en neumatóforos.",
        "normativa_aplicable": "Resolución 0631 de 2015 (Vertimientos) y Resolución 1263 de 2018 (Manglares del Atlántico)",
        "accion_recomendada_cra": "Despachar comisión técnica en menos de 6 horas para muestreo in situ de OD, pH, conductividad y rastreo del punto de descarga.",
        "valor_analitico_b2b_academia": "Evidencia georreferenciada de evento agudo de contaminación útil para correlación con caudales de Arroyo León y modelos de captura de carbono azul.",
        "etiquetas_datos": [
          "#CalidadAgua",
          "#Vertimientos",
          "#Hipoxia",
          "#CarbonoAzul",
          "#Mallorquin"
        ]
      },
      "email_notifications": [
        {
          "recipient_id": "sub_cra_control",
          "email": "alertas.manglar@crautonoma.gov.co",
          "name": "Centro de Control y Despacho C.R.A.",
          "organization": "C.R.A. - Corporación Autónoma Regional del Atlántico",
          "type": "CRA",
          "subject": "[ALTA] MOKANÁ #MKN-2026-0001 | Ciénaga de Mallorquín - Presencia de espuma...",
          "status": "sent",
          "resend_id": "re_98a7bc..."
        }
      ]
    }
  ]
}
```

---

### 3.2. Obtener un reporte específico por ID
**`GET /api/reports/{report_id}`**  
Ejemplo: `GET https://mokana.joshual.tech/api/reports/MKN-2026-0001`

---

### 3.3. Crear un reporte desde la Web del Tótem o Panel Admin
**`POST /api/reports`**  
Valida automáticamente la descripción e imagen con **Gemini 2.5 Flash**, genera el informe técnico C.R.A., dispara los correos por **Resend** y emite el evento en vivo al dashboard.

#### Body (`application/json`):
```json
{
  "zone_id": "zone_mallorquin",
  "category_id": "alert_tala",
  "description": "Están cortando ramas de mangle rojo y rellenando con sacos de escombros.",
  "image_url": "https://ejemplo.com/foto_tala.jpg",
  "lat": 11.0462,
  "lng": -74.8459,
  "citizen_name": "Vigía Tótem 01",
  "citizen_phone": "+573001234567"
}
```

---

### 3.4. Actualizar Estado, Responsable, Severidad o Notas de un Reporte (Desde el Panel C.R.A.)
**`PATCH /api/reports/{report_id}`**  
Actualiza el reporte y, si `notify_citizen_whatsapp: true`, **le envía un mensaje automático por WhatsApp al ciudadano que reportó** informándole el avance institucional.

#### Body (`application/json`):
```json
{
  "status": "BRIGADA_DESPACHADA",
  "assigned_to": "Equipo Técnico Químico C.R.A. - Unidad 04",
  "nivel_severidad": "CRÍTICA",
  "note": "Se despachó unidad con sonda multiparamétrica para medición de oxígeno disuelto y pH.",
  "author": "Ing. Coordinador C.R.A.",
  "notify_citizen_whatsapp": true
}
```

---

### 3.5. Reenviar / Disparar Notificaciones por Correo de un Reporte
**`POST /api/reports/{report_id}/notify`**  
Reenvía inmediatamente por **Resend** el informe técnico del reporte a todos los responsables de la C.R.A. y suscriptores B2B (Empresas y Academia) activos.

---

## 4. Endpoints de Métricas, Zonas y Tótems QR/NFC

### 4.1. Estadísticas para Tarjetas y Gráficas del Dashboard
**`GET /api/stats`**

#### Respuesta Ejemplo (`200 OK`):
```json
{
  "total_reports": 14,
  "critical_and_high": 9,
  "by_severity": {
    "CRÍTICA": 3,
    "ALTA": 6,
    "MEDIA": 4,
    "BAJA": 1
  },
  "by_status": {
    "PENDIENTE_REVISION_CRA": 5,
    "BRIGADA_DESPACHADA": 6,
    "RESUELTO": 3
  },
  "by_zone": {
    "zone_mallorquin": 7,
    "zone_balboa": 3,
    "zone_totumo": 2,
    "zone_tubara": 1,
    "zone_juan_acosta": 1
  },
  "by_category": {
    "alert_tala": 4,
    "alert_olor": 3,
    "alert_color": 4,
    "alert_fauna": 2,
    "alert_otro": 1
  },
  "total_emails_dispatched": 42,
  "subscribers_summary": {
    "total": 6,
    "cra": 2,
    "empresas_b2b": 2,
    "academia": 2
  }
}
```

### 4.2. Catálogo de Zonas, Coordenadas y Enlaces QR/NFC de cada Tótem
**`GET /api/zones`**  
Devuelve las 5 zonas de manglar del Atlántico junto con la URL exacta `https://wa.me/573135865509?text=...` para grabar en la etiqueta NFC o imprimir en el código QR de cada Tótem.

---

## 5. Endpoints de Suscriptores de Correo (C.R.A. + Venta de Datos a Empresas y Academia)

Desde el Frontend se pueden agregar, filtrar, editar o desactivar los correos de:
1. **`CRA`**: Funcionarios y subdirecciones de la autoridad ambiental.
2. **`EMPRESA`**: Clientes corporativos B2B (empresas de bonos de carbono azul, constructoras, puertos, sector turístico, consultoras ESG).
3. **`ACADEMIA`**: Universidades, grupos de investigación marina/química e institutos científicos.

### 5.1. Listar Suscriptores
**`GET /api/subscribers`** *(Opcional: `?type=CRA`, `?type=EMPRESA` o `?type=ACADEMIA`)*

### 5.2. Crear un Nuevo Suscriptor / Cliente de Datos desde el Frontend
**`POST /api/subscribers`**

#### Body (`application/json`):
```json
{
  "name": "Dr. Carlos Mendoza - Director Laboratorio Ambiental",
  "email": "cmendoza@universidad-atlantico.edu.co",
  "organization": "Universidad del Atlántico - Grupo Química Ambiental",
  "type": "ACADEMIA",
  "plan": "PRO_DATA_B2B",
  "zones": ["zone_mallorquin", "zone_balboa"],
  "categories": ["alert_olor", "alert_color", "alert_fauna"],
  "min_severity": "MEDIA",
  "active": true
}
```

### 5.3. Editar Filtros o Estado de un Suscriptor
**`PATCH /api/subscribers/{subscriber_id}`**

### 5.4. Eliminar un Suscriptor
**`DELETE /api/subscribers/{subscriber_id}`**

---

## 6. Configuración de Resend (Correo Electrónico) desde el Frontend

### 6.1. Consultar Configuración Actual de Correo
**`GET /api/settings/notifications`**

### 6.2. Actualizar API Key de Resend y Remitente desde el Frontend
**`PUT /api/settings/notifications`**

#### Body (`application/json`):
```json
{
  "resend_api_key": "re_123456789_tu_api_key_de_resend",
  "from_email": "Mokaná Alertas C.R.A. <alertas@joshual.tech>",
  "auto_notify_email": true,
  "notify_whatsapp_on_status_change": true
}
```
