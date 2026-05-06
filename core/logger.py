import logging
import sys
import os

# Asegurar que existe el directorio para logs
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("ScalpingBot")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

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