import os
from dotenv import load_dotenv

load_dotenv()

ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY", "")
ZERNIO_ACCOUNT_ID = os.getenv("ZERNIO_ACCOUNT_ID", "")
ZERNIO_WEBHOOK_SECRET = os.getenv("ZERNIO_WEBHOOK_SECRET", "")
ZERNIO_BASE_URL = os.getenv("ZERNIO_BASE_URL", "https://zernio.com/api/v1").rstrip("/")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PORT = int(os.getenv("PORT", "8089"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://mokana.joshual.tech").rstrip("/")

# Configuración Resend para notificaciones por correo (configurable desde .env o desde el Frontend vía API)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Mokaná Alertas C.R.A. <alertas@joshual.tech>")

# Zonas de Manglar del Departamento del Atlántico
MANGROVE_ZONES = [
    {
        "id": "zone_mallorquin",
        "title": "Ciénaga de Mallorquín",
        "description": "Barranquilla / Puerto Colombia (Ecoparque, Arroyo León)",
        "keywords": ["mallorquin", "mallorquín", "totem-mallorquin", "arroyo leon", "la playa", "puerto mocho"],
        "coords": {"lat": 11.0458, "lng": -74.8461},
    },
    {
        "id": "zone_balboa",
        "title": "Ciénaga de Balboa",
        "description": "Puerto Colombia (Salgar, Pradomar, Puerto Caimán)",
        "keywords": ["balboa", "puerto colombia", "totem-balboa", "salgar", "pradomar", "caiman"],
        "coords": {"lat": 11.0032, "lng": -74.9485},
    },
    {
        "id": "zone_totumo",
        "title": "Ciénaga del Totumo",
        "description": "Piojó / Lomita Arena (Frontera departamental)",
        "keywords": ["totumo", "piojo", "piojó", "totem-totumo"],
        "coords": {"lat": 10.7425, "lng": -75.2342},
    },
    {
        "id": "zone_tubara",
        "title": "Manglares de Tubará",
        "description": "Puerto Velero / Bocatocino / Caño Dulce",
        "keywords": ["tubara", "tubará", "puerto velero", "velero", "bocatocino", "totem-tubara"],
        "coords": {"lat": 10.9467, "lng": -75.0258},
    },
    {
        "id": "zone_juan_acosta",
        "title": "Manglares Juan de Acosta",
        "description": "Santa Verónica / Salinas del Rey / Turipaná",
        "keywords": ["juan de acosta", "santa veronica", "santa verónica", "turipana", "totem-acosta"],
        "coords": {"lat": 10.8781, "lng": -75.0836},
    },
]

# Categorías de Alerta hacia la C.R.A.
ALERT_CATEGORIES = [
    {
        "id": "alert_tala",
        "title": "🪓 Tala o relleno ilegal",
        "description": "Tala de mangle, quema o relleno con escombros",
    },
    {
        "id": "alert_olor",
        "title": "👃 Agua con olor extraño",
        "description": "Olor a azufre/podrido, aguas negras o químico",
    },
    {
        "id": "alert_color",
        "title": "🎨 Agua con color raro",
        "description": "Espuma, manchas de aceite o cambio de color",
    },
    {
        "id": "alert_fauna",
        "title": "🐟 Fauna o basuras",
        "description": "Peces muertos, fauna afectada o plásticos",
    },
    {
        "id": "alert_otro",
        "title": "📝 Otro incidente",
        "description": "Reportar otra anomalía ambiental en el manglar",
    },
]
