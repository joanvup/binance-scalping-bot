from core.logger import logger

class BotState:
    def __init__(self):
        self.is_running: bool = False
        self.balance: float = 0.0
        self.position: dict | None = None
        self.last_price: float = 0.0
        
        # --- NUEVO: Datos para el Gráfico y Dashboard ---
        self.historical_klines =[] # Guarda las últimas 100 velas
        self.historical_bb_upper = [] 
        self.historical_bb_lower =[]
        self.historical_rsi =[]
        # --- NUEVO: Financiación (Funding) ---
        self.funding_rate: float = 0.0
        self.est_funding_fee: float = 0.0
        
        self.current_candle = None  # Vela actual moviéndose en vivo
        self.indicators = {         # Valores en vivo
            "rsi": 0.0,
            "lower_bb": 0.0,
            "upper_bb": 0.0
        }

    def start(self):
        self.is_running = True
        logger.info("Estado del bot cambiado a: CORRIENDO")

    def stop(self):
        self.is_running = False
        logger.info("Estado del bot cambiado a: DETENIDO")

    def update_balance(self, new_balance: float):
        self.balance = new_balance

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        if not self.position:
            return 0.0
        
        entry = self.position["entry_price"]
        qty = self.position["qty"]
        
        if self.position["side"] == "LONG":
            return (current_price - entry) * qty
        elif self.position["side"] == "SHORT":
            return (entry - current_price) * qty
            
        return 0.0

state = BotState()