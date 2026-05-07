import logging
import sys
import os
from datetime import datetime
import pytz
from core.config import settings

# Asegurar que existe el directorio para logs
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("ScalpingBot")
logger.setLevel(logging.DEBUG)

# --- NUEVO: Configurar zona horaria para los logs ---
tz = pytz.timezone(settings.TIMEZONE)

def custom_time(*args):
    """Fuerza al logger a usar la zona horaria del .env"""
    return datetime.now(tz).timetuple()

formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
formatter.converter = custom_time # Inyectamos nuestra función de tiempo

# Salida a Consola
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Salida a Archivo
file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)