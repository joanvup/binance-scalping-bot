import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
import pytz

# Importaciones de nuestros módulos
from web.routes import router
from core.binance_client import binance_manager
from core.engine import TradingEngine
from core.logger import logger

# Variable global para mantener la referencia de la tarea del motor en background
engine_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de contexto de FastAPI que maneja los eventos de encendido y apagado de la aplicación.
    """
    global engine_task
    
    # ------------------ EVENTOS DE INICIO ------------------
    logger.info("Iniciando la aplicación web y conectando a Binance...")
    
    # 1. Inicializar conexión a Binance (Testnet, Dry Run o Live)
    await binance_manager.initialize()
    
    # 2. Instanciar el motor de trading
    engine = TradingEngine()
    
    # 3. Lanzar el motor de trading de forma concurrente (en segundo plano)
    # Esto permite que el motor procese WebSockets sin bloquear la interfaz web
    engine_task = asyncio.create_task(engine.start())
    
    # Entregamos el control a FastAPI para que sirva el dashboard
    yield
    
    # ------------------ EVENTOS DE APAGADO ------------------
    logger.info("Señal de apagado recibida. Cerrando conexiones seguras...")
    
    # 1. Cancelar la tarea del motor de trading
    if engine_task:
        engine_task.cancel()
        
    # 2. Cerrar la sesión de Binance de forma limpia
    await binance_manager.close()
    logger.info("Apagado completado exitosamente. ¡Hasta luego!")

# Inicialización de la app FastAPI usando el gestor de ciclo de vida moderno
app = FastAPI(
    title="Binance Scalping Bot",
    description="Bot de trading algorítmico asíncrono con interfaz web",
    version="1.0.0",
    lifespan=lifespan
)

# Incluir las rutas del dashboard web que creamos en la Fase 3
app.include_router(router)

if __name__ == "__main__":
    # Iniciar el servidor con Uvicorn
    # reload=False porque en aplicaciones de trading con websockets, el reload 
    # puede crear conexiones fantasma en el exchange.
    # Agregamos log_level="warning" para ocultar los mensajes INFO de las peticiones HTTP
    # Pero mantenemos nuestros logs del bot porque los configuramos de forma independiente
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="warning")