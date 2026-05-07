import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    TIMEZONE: str = "America/Bogota"
    EXECUTION_MODE: str = "TESTNET" # TESTNET, DRY_RUN, LIVE
    TIMESYNCDATE:int = 60 # sincronizar fecha y hora cada 60 segundos
    
    # Binance Live
    BINANCE_API_KEY_LIVE: str = ""
    BINANCE_API_SECRET_LIVE: str = ""
    
    # Binance Testnet
    BINANCE_API_KEY_TESTNET: str = ""
    BINANCE_API_SECRET_TESTNET: str = ""
    
    # Parámetros de Trading base (sobreescribibles en el dashboard web)
    SYMBOL: str = "HBARUSDT"
    TIMEFRAME: str = "5m"
    LEVERAGE: int = 10
    TAKE_PROFIT_PCT: float = 1.0   # 1% como en el video
    DCA_DROP_PCT: float = 2.0      # Distancia de caída para recomprar
    MAX_RISK_PCT: float = 10.0     # 10% del balance de la cuenta como stop loss
    INITIAL_USDT_MARGIN: float = 50.0
    INITIAL_BALANCE_DRYRUN: float = 100.0 # Balance inicial para el modo DRY_RUN

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def is_live(self) -> bool:
        return self.EXECUTION_MODE.upper() == "LIVE"

    @property
    def is_testnet(self) -> bool:
        return self.EXECUTION_MODE.upper() == "TESTNET"

    @property
    def is_dry_run(self) -> bool:
        return self.EXECUTION_MODE.upper() == "DRY_RUN"

settings = Settings()