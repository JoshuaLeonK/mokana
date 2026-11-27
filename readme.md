# MOKANÁ 🌿
**Sistema de Notificación, Gestión y Respuesta en Tiempo Real para los Manglares del Atlántico**  
*ManglarHack Atlántico 2026*

---

## Descripción General
**Mokaná** conecta a la ciudadanía y visitantes de los ecosistemas de manglar del Atlántico con la **C.R.A. (Corporación Autónoma Regional del Atlántico)** mediante puntos físicos de conexión (**Tótems QR / NFC** con acceso Wi-Fi), un **Bot de Alerta Temprana en WhatsApp** y una **Plataforma Central de Gestión y Respuesta en Tiempo Real**.

### Flujo del Sistema
1. **Tótem Físico (QR / NFC):** El ciudadano o vigía acerca su teléfono al tótem en campo, obtiene conexión Wi-Fi y accede inmediatamente a la Web o al **Bot de WhatsApp de Mokaná**.
2. **Reporte y Notificación (Bot de WhatsApp / Web):** Reporte guiado en segundos de incidentes críticos en el manglar:
   - Tala ilegal de mangle o relleno de escombros.
   - Agua con olor anómalo (aguas residuales, azufre/anoxia, químicos).
   - Agua con coloración anómala (espuma, manchas, turbidez extrema, vertimientos).
   - Mortandad de fauna (peces, crustáceos, aves) o acumulación crítica de residuos.
3. **Gestión y Respuesta (Dashboard C.R.A.):** Recepción en tiempo real, priorización inteligente, geolocalización por sector/tótem y seguimiento del estado de respuesta institucional.

---

## Estructura de Ramas (Git Flow del Equipo)
- `main` 🔒: Rama protegida de producción / demo final (solo acepta cambios mediante **Pull Request**).
- `develop`: Rama principal de integración del equipo.
- `feat/whatsapp-bot`: Desarrollo del Bot de WhatsApp (Meta Cloud API / Webhooks) y lógica de recepción de alertas.
- `feat/web-dashboard`: Portal del Tótem (QR/NFC) y Panel de Gestión y Respuesta para la C.R.A.
