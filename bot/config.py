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

# Zonas de Manglar del Departamento del Atlántico (Títulos <= 24 caracteres y sin emojis para listas desplegables nativas de WhatsApp)
MANGROVE_ZONES = [
    {
        "id": "zone_mallorquin",
        "title": "Cienaga de Mallorquin",
        "description": "Barranquilla / Puerto Colombia",
        "keywords": ["mallorquin", "mallorquín", "totem-mallorquin", "arroyo leon", "la playa", "puerto mocho"],
        "coords": {"lat": 11.0458, "lng": -74.8461},
    },
    {
        "id": "zone_balboa",
        "title": "Cienaga de Balboa",
        "description": "Puerto Colombia / Salgar / Pradomar",
        "keywords": ["balboa", "puerto colombia", "totem-balboa", "salgar", "pradomar", "caiman"],
        "coords": {"lat": 11.0032, "lng": -74.9485},
    },
    {
        "id": "zone_totumo",
        "title": "Cienaga del Totumo",
        "description": "Piojo / Lomita Arena",
        "keywords": ["totumo", "piojo", "piojó", "totem-totumo"],
        "coords": {"lat": 10.7425, "lng": -75.2342},
    },
    {
        "id": "zone_tubara",
        "title": "Manglares de Tubara",
        "description": "Puerto Velero / Bocatocino",
        "keywords": ["tubara", "tubará", "puerto velero", "velero", "bocatocino", "totem-tubara"],
        "coords": {"lat": 10.9467, "lng": -75.0258},
    },
    {
        "id": "zone_juan_acosta",
        "title": "Manglares Juan de Acosta",
        "description": "Santa Veronica / Salinas del Rey",
        "keywords": ["juan de acosta", "santa veronica", "santa verónica", "turipana", "totem-acosta"],
        "coords": {"lat": 10.8781, "lng": -75.0836},
    },
]

# Categorías de Alerta hacia la C.R.A. (Sin emojis y títulos <= 24 caracteres para lista desplegable nativa de WhatsApp)
ALERT_CATEGORIES = [
    {
        "id": "alert_tala",
        "title": "Tala o relleno ilegal",
        "description": "Corte de mangle, quema o escombros",
        "keywords": ["tala", "arbol", "árbol", "cort", "relleno", "escombro", "quema", "mangle"],
    },
    {
        "id": "alert_olor",
        "title": "Agua con olor extrano",
        "description": "Olor a azufre, aguas negras o quimico",
        "keywords": ["olor", "huele", "hedor", "podrido", "azufre", "fecal", "aguas negras", "quimico"],
    },
    {
        "id": "alert_color",
        "title": "Agua con color raro",
        "description": "Espuma, manchas, aceite o turbidez",
        "keywords": ["color", "espuma", "mancha", "aceite", "oscura", "verde", "roja", "turbia", "vertimiento"],
    },
    {
        "id": "alert_fauna",
        "title": "Fauna o basuras",
        "description": "Peces muertos, animales o plasticos",
        "keywords": ["pez", "peces", "muerto", "mortandad", "fauna", "ave", "basura", "plastico", "residuo"],
    },
    {
        "id": "alert_erosion",
        "title": "Erosion o perdida suelo",
        "description": "Erosion costera, socavacion o caida de orilla",
        "keywords": ["erosion", "erosión", "socav", "orilla", "sedimento", "derrumbe", "costa", "playa", "suelo"],
    },
    {
        "id": "alert_otro",
        "title": "Otro incidente",
        "description": "Otra anomalia en el manglar",
        "keywords": ["otro", "incidente", "anomalia"],
    },
]
