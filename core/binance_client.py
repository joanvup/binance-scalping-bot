#from binance.client import AsyncClient
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from core.config import settings
from core.logger import logger
import time

class BinanceManager:
    def __init__(self):
        self.client: AsyncClient = None
        self.mode = settings.EXECUTION_MODE.upper()

    async def initialize(self):
        """Inicializa el cliente asíncrono según el modo configurado"""
        try:
            if self.mode == "TESTNET":
                logger.info("Iniciando Binance Client en modo TESTNET...")
                # Instanciamos la clase DIRECTAMENTE (sin el .create y sin el await) 
                # para saltarnos el ping forzado a Spot.
                self.client = AsyncClient(
                    api_key=settings.BINANCE_API_KEY_TESTNET,
                    api_secret=settings.BINANCE_API_SECRET_TESTNET,
                    testnet=True
                )
            else:
                logger.info(f"Iniciando Binance Client en modo {self.mode}...")
                self.client = AsyncClient(
                    api_key=settings.BINANCE_API_KEY_LIVE,
                    api_secret=settings.BINANCE_API_SECRET_LIVE,
                    testnet=False
                )
            
            # Nosotros usamos nuestro propio ping dirigido exclusivamente a los servidores de Futuros
            await self.client.futures_ping()
            logger.info("Conexión exitosa a Binance Futures API.")
            
            # --- Sincronización Inicial de Reloj ---
            await self.sync_time()
            
            if self.mode in ["LIVE", "TESTNET"]:
                await self._setup_symbol_leverage(settings.SYMBOL, settings.LEVERAGE)

        except Exception as e:
            logger.error(f"Error al inicializar Binance Client: {e}")
            raise

    async def sync_time(self):
        """Calcula la diferencia de tiempo entre tu PC y Binance Futures (Time Offset)"""
        try:
            server_time_res = await self.client.futures_time()
            server_time = server_time_res['serverTime']
            local_time = int(time.time() * 1000)
            
            # Inyectamos la diferencia directamente en el motor de la librería python-binance
            self.client.timestamp_offset = server_time - local_time
            logger.info(f"Reloj sincronizado lógicamente. Offset aplicado: {self.client.timestamp_offset} ms.")
        except Exception as e:
            logger.error(f"Error sincronizando el reloj con Binance: {e}")

    async def _setup_symbol_leverage(self, symbol: str, leverage: int):
        """Configura el apalancamiento y el margen cruzado (Cross) del símbolo"""
        try:
            # Configurar a Margen Cruzado (generalmente recomendado para esta estrategia de balance)
            try:
                await self.client.futures_change_margin_type(symbol=symbol, marginType='CROSSED')
                logger.info(f"Modo de margen configurado a CROSSED para {symbol}")
            except BinanceAPIException as e:
                # Si ya está en margin cruzado, Binance devuelve error -4046
                if e.code != -4046:
                    raise e
                    
            # Configurar el apalancamiento
            await self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logger.info(f"Apalancamiento de {symbol} ajustado a {leverage}x")
            
        except Exception as e:
            logger.error(f"Error al configurar símbolo {symbol}: {e}")

    async def close(self):
        """Cierra la sesión del cliente de manera segura"""
        if self.client:
            await self.client.close_connection()
            logger.info("Conexión con Binance cerrada correctamente.")

# Instancia global para ser importada en el resto de la aplicación
binance_manager = BinanceManager()