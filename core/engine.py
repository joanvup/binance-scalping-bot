import asyncio
import pandas as pd
from binance import BinanceSocketManager
from binance.exceptions import BinanceAPIException
from core.config import settings
from core.logger import logger
from core.state_manager import state
from core.binance_client import binance_manager
from core.indicators import IndicatorCalculator
from database.models import SessionLocal, TradeHistory
from datetime import datetime
import json
import websockets
import pytz

class TradingEngine:
    def __init__(self):
        self.symbol = settings.SYMBOL
        self.timesync = settings.TIMESYNCDATE
        self.interval = settings.TIMEFRAME
        self.mode = settings.EXECUTION_MODE.upper()
        self.indicator_calc = IndicatorCalculator()
        self.df: pd.DataFrame = pd.DataFrame()
        self.qty_precision = 3 
        
        self.tp_pct = settings.TAKE_PROFIT_PCT / 100.0
        self.dca_pct = settings.DCA_DROP_PCT / 100.0
        self.max_risk_pct = settings.MAX_RISK_PCT / 100.0
        self.initial_usdt_margin = settings.INITIAL_USDT_MARGIN
        self.initial_balance_dryrun = settings.INITIAL_BALANCE_DRYRUN
        # Calcular desfase en segundos para el gráfico
        self.tz = pytz.timezone(settings.TIMEZONE)
        self.tz_offset_seconds = self.tz.utcoffset(datetime.utcnow()).total_seconds()

    async def fetch_historical_data(self):
        logger.info(f"Descargando datos históricos para {self.symbol} ({self.interval})...")
        klines = await binance_manager.client.futures_klines(
            symbol=self.symbol, 
            interval=self.interval, 
            limit=100
        )
        
        parsed_data = []
        chart_data =[] # Para TradingView
        
        for k in klines:
            parsed_data.append({
                'timestamp': pd.to_datetime(k[0], unit='ms'),
                'open': float(k[1]), 'high': float(k[2]),
                'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])
            })
            # TradingView necesita el tiempo en formato Unix Timestamp (segundos)
            chart_data.append({
                'time': int(k[0] // 1000) + self.tz_offset_seconds,
                'open': float(k[1]), 'high': float(k[2]),
                'low': float(k[3]), 'close': float(k[4])
            })
            
        self.df = pd.DataFrame(parsed_data)
        self.df = self.indicator_calc.calculate(self.df)
        state.historical_klines = chart_data
        
        # --- NUEVO: Extraer historial para dibujar las líneas BB ---
        bb_up = []
        bb_low =[]
        for _, row in self.df.iterrows():
            t = int(row['timestamp'].timestamp()) + self.tz_offset_seconds
            if not pd.isna(row['upper_bb']):
                bb_up.append({'time': t, 'value': float(row['upper_bb'])})
            if not pd.isna(row['lower_bb']):
                bb_low.append({'time': t, 'value': float(row['lower_bb'])})
                
        state.historical_bb_upper = bb_up
        state.historical_bb_lower = bb_low

    def _save_trade_to_db(self, side: str, entry: float, exit_price: float, qty: float, pnl: float, dca: int, order_id: str):
        """Guarda un trade completado en la base de datos SQLite"""
        try:
            db = SessionLocal()
            trade = TradeHistory(
                order_id=order_id, # <--- AÑADIDO
                symbol=self.symbol,
                side=side,
                entry_price=entry,
                exit_price=exit_price,
                qty=qty,
                pnl=pnl,
                dca_count=dca,
                timestamp=datetime.utcnow()
            )
            db.add(trade)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Error guardando trade en DB: {e}")

    async def execute_order(self, side: str, price: float, quantity: float, reduce_only: bool = False):
        api_side = "BUY" if side == "LONG" else "SELL" if side == "SHORT" else side

        logger.info(f"[{self.mode}] Solicitando orden {api_side} | Qty: {quantity} | Precio Trigger: {price}")
        
        if self.mode == "DRY_RUN":
            self.last_order_id = "SIMULADA" 
            logger.info(f"DRY RUN: Orden {api_side} simulada exitosamente.")
            return price

        try:
            order = await binance_manager.client.futures_create_order(
                symbol=self.symbol, 
                side=api_side,  
                type='MARKET',
                quantity=round(quantity, self.qty_precision), 
                reduceOnly=reduce_only
            )
            
            # --- VERIFICACIÓN INSTITUCIONAL DEL PRECIO DE EJECUCIÓN ---
            real_price = float(order.get('avgPrice', 0.0))
            
            # Si Binance devuelve 0.0 (porque el motor de emparejamiento no ha terminado)
            if real_price == 0.0:
                logger.info("Binance procesando el llenado, consultando recibo final en 1.5 seg...")
                await asyncio.sleep(1.5) # Le damos tiempo a Binance
                try:
                    # Pedimos explícitamente el recibo de la orden
                    receipt = await binance_manager.client.futures_get_order(
                        symbol=self.symbol, 
                        orderId=order['orderId']
                    )
                    real_price = float(receipt.get('avgPrice', 0.0))
                except Exception as e:
                    logger.error(f"Error pidiendo recibo de orden: {e}")

            # Fallback final de ultra-seguridad
            if real_price == 0.0:
                real_price = price
                
            self.last_order_id = str(order['orderId'])
            logger.info(f"Orden Live/Testnet ejecutada: {order['orderId']} | Precio REAL: {real_price}")
            return real_price
            
        except BinanceAPIException as e:
            logger.error(f"Error ejecutando orden: {e}")
            return None

    async def sync_position(self):
        """Sincroniza la posición local con los datos reales de Binance (Precio de entrada real tras slippage)"""
        # Si estamos simulando (Dry Run), no hay nada que sincronizar con Binance
        if self.mode == "DRY_RUN" or not state.position:
            return
            
        try:
            # Esperamos 1 segundo para asegurarnos de que Binance ya procesó la orden en sus servidores
            await asyncio.sleep(1)
            
            # Pedimos la info real de la posición
            positions = await binance_manager.client.futures_position_information(symbol=self.symbol)
            for pos in positions:
                amt = float(pos['positionAmt'])
                # Si la cantidad no es 0, es porque esta es nuestra posición activa
                if amt != 0:
                    state.position["entry_price"] = float(pos['entryPrice'])
                    state.position["qty"] = abs(amt)
                    logger.info(f"Sincronizado con Binance -> Precio Real: {state.position['entry_price']} | Qty: {state.position['qty']}")
                    break
        except Exception as e:
            logger.error(f"Error sincronizando posición con Binance: {e}")

    async def recover_open_position(self):
        """Si el bot se reinicia, busca posiciones abiertas en Binance para retomarlas"""
        if self.mode == "DRY_RUN":
            return # En simulado no hay nada que recuperar
            
        try:
            positions = await binance_manager.client.futures_position_information(symbol=self.symbol)
            for pos in positions:
                amt = float(pos['positionAmt'])
                if amt != 0:
                    side = "LONG" if amt > 0 else "SHORT"
                    entry_price = float(pos['entryPrice'])
                    qty = abs(amt)
                    
                    # Calcular cuántos DCA se hicieron aproximadamente
                    # Qty base = (Margen * Apalancamiento) / Precio
                    base_qty = (self.initial_usdt_margin * settings.LEVERAGE) / entry_price
                    dca_count = 0
                    temp_qty = base_qty
                    
                    # Como el DCA dobla la cantidad, calculamos el nivel de DCA
                    while temp_qty * 1.5 < qty: # 1.5 de margen por el slippage
                        dca_count += 1
                        temp_qty *= 2
                        
                    state.position = {
                        "side": side,
                        "entry_price": entry_price,
                        "qty": qty,
                        "dca_count": dca_count
                    }
                    logger.warning(f"🔄 RECUPERACIÓN EXITOSA: Posición {side} retomada tras reinicio. Entrada: {entry_price} | Qty: {qty} | DCA aprox: {dca_count}")
                    break
        except Exception as e:
            logger.error(f"Error intentando recuperar posición: {e}")

    async def manage_open_position(self, current_price: float):
        pos = state.position
        if not pos: return

        entry = pos["entry_price"]
        side = pos["side"]
        unrealized_pnl = state.calculate_unrealized_pnl(current_price)
        max_loss_allowed = state.balance * self.max_risk_pct
        
        # 1. Stop Loss
        if unrealized_pnl < 0 and abs(unrealized_pnl) >= max_loss_allowed:
            logger.warning(f"🚨 STOP LOSS ALCANZADO. Cerrando...")
            exit_side = "SELL" if side == "LONG" else "BUY"
            real_exit_price = await self.execute_order(exit_side, current_price, pos["qty"], reduce_only=True)
            
            # CAMBIO DE SEGURIDAD: Validamos que no sea None (el 0.0 ahora sí pasará)
            if real_exit_price is not None: 
                real_pnl = (real_exit_price - entry) * pos["qty"] if side == "LONG" else (entry - real_exit_price) * pos["qty"]
                self._save_trade_to_db(side, entry, real_exit_price, pos["qty"], real_pnl, pos["dca_count"], self.last_order_id)
                state.position = None
            return

        # 2. Take Profit
        if side == "LONG" and current_price >= entry * (1 + self.tp_pct):
            logger.info("🟢 TAKE PROFIT LONG ALCANZADO.")
            real_exit_price = await self.execute_order("SELL", current_price, pos["qty"], reduce_only=True)
            
            if real_exit_price is not None: # CAMBIO DE SEGURIDAD
                real_pnl = (real_exit_price - entry) * pos["qty"]
                self._save_trade_to_db(side, entry, real_exit_price, pos["qty"], real_pnl, pos["dca_count"], self.last_order_id)
                state.position = None
            return
            
        elif side == "SHORT" and current_price <= entry * (1 - self.tp_pct):
            logger.info("🟢 TAKE PROFIT SHORT ALCANZADO.")
            real_exit_price = await self.execute_order("BUY", current_price, pos["qty"], reduce_only=True)
            
            if real_exit_price is not None: # CAMBIO DE SEGURIDAD
                real_pnl = (entry - real_exit_price) * pos["qty"]
                self._save_trade_to_db(side, entry, real_exit_price, pos["qty"], real_pnl, pos["dca_count"], self.last_order_id)
                state.position = None
            return

        # 3. DCA
        is_against_long = side == "LONG" and current_price <= entry * (1 - self.dca_pct)
        is_against_short = side == "SHORT" and current_price >= entry * (1 + self.dca_pct)

        if is_against_long or is_against_short:
            logger.info("🔄 PRECIO EN CONTRA. Ejecutando Recompra (DCA)...")
            dca_qty = pos["qty"]
            success = await self.execute_order(side, current_price, dca_qty)
            if success:
                new_total_qty = pos["qty"] + dca_qty
                new_avg_price = ((pos["qty"] * entry) + (dca_qty * current_price)) / new_total_qty
                state.position["qty"] = new_total_qty
                state.position["entry_price"] = new_avg_price
                state.position["dca_count"] += 1
                logger.info(f"Nuevo Precio Promedio: {new_avg_price} | Qty Total: {new_total_qty}")
                await self.sync_position() # <--- ¡IMPORTANTE! Sincronizamos después del DCA

    async def analyze_signal(self, current_price: float):
        if state.position: return 

        last_row = self.df.iloc[-1]
        rsi = last_row['rsi']
        lower_bb = last_row['lower_bb']
        upper_bb = last_row['upper_bb']

        if pd.isna(rsi) or pd.isna(lower_bb): return # Evitar errores si no hay suficientes velas

        if current_price <= lower_bb and rsi < 30:
            logger.info(f"💡 SEÑAL LONG DETECTADA: Precio={current_price}, BBL={lower_bb}, RSI={rsi}")
            qty = (self.initial_usdt_margin * settings.LEVERAGE) / current_price
            success = await self.execute_order("LONG", current_price, qty)
            if success:
                state.position = {"side": "LONG", "entry_price": current_price, "qty": qty, "dca_count": 0}
                await self.sync_position()

        elif current_price >= upper_bb and rsi > 70:
            logger.info(f"💡 SEÑAL SHORT DETECTADA: Precio={current_price}, BBU={upper_bb}, RSI={rsi}")
            qty = (self.initial_usdt_margin * settings.LEVERAGE) / current_price
            success = await self.execute_order("SHORT", current_price, qty)
            if success:
                state.position = {"side": "SHORT", "entry_price": current_price, "qty": qty, "dca_count": 0}
                await self.sync_position()

    async def _update_funding_loop(self):
        """Consulta la tasa de financiación a Binance y sincroniza el reloj periódicamente"""
        loop_count = 0
        while True:
            if self.mode != "DRY_RUN" and state.is_running:
                try:
                    # 1. Sincronizar el reloj local cada 60 minutos (10 loops de 60 segundos)
                    if loop_count % self.timesync == 0:
                        await binance_manager.sync_time()

                    # 2. Consultar Funding
                    mark_data = await binance_manager.client.futures_mark_price(symbol=self.symbol)
                    state.funding_rate = float(mark_data['lastFundingRate'])
                    mark_price = float(mark_data['markPrice'])
                    
                    if state.position:
                        qty = state.position["qty"]
                        side = state.position["side"]
                        raw_fee = qty * mark_price * state.funding_rate
                        
                        if side == "LONG":
                            state.est_funding_fee = -raw_fee
                        else:
                            state.est_funding_fee = raw_fee
                except Exception as e:
                    pass
            
            loop_count += 1
            await asyncio.sleep(60) # Esperamos 1 minuto para el próximo ciclo

    async def start(self):
        await self.fetch_historical_data()
        
        if self.mode != "DRY_RUN":
            acc_info = await binance_manager.client.futures_account()
            state.balance = float(acc_info['totalMarginBalance'])
            await self.recover_open_position()
        else:
            state.balance = self.initial_balance_dryrun

        asyncio.create_task(self._update_funding_loop())

        # --- NUEVO: Conexión explícita y directa a FUTUROS ---
        if self.mode == "TESTNET":
            ws_url = f"wss://stream.binancefuture.com/ws/{self.symbol.lower()}@kline_{self.interval}"
        else:
            ws_url = f"wss://fstream.binance.com/ws/{self.symbol.lower()}@kline_{self.interval}"

        logger.info(f"Escuchando WebSockets de Binance FUTURES ({self.mode}) para {self.symbol}...")

        # Bucle infinito protector: Si se cae el internet, se reconecta automáticamente
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info("Conectado exitosamente al stream de precios en vivo.")
                    
                    while True:
                        if not state.is_running:
                            await asyncio.sleep(1)
                            continue
                        
                        msg_str = await ws.recv()
                        msg = json.loads(msg_str)

                        if 'k' in msg:
                            kline = msg['k']
                            current_price = float(kline['c'])
                            is_kline_closed = kline['x']

                            state.last_price = current_price

                            # --- Actualizar Vela Actual ---
                            state.current_candle = {
                                'time': int(kline['t'] // 1000) + self.tz_offset_seconds,
                                'open': float(kline['o']), 'high': float(kline['h']),
                                'low': float(kline['l']), 'close': float(kline['c'])
                            }

                            try:
                                last_row = self.df.iloc[-1]
                                state.indicators["rsi"] = float(last_row['rsi']) if not pd.isna(last_row['rsi']) else 0.0
                                state.indicators["lower_bb"] = float(last_row['lower_bb']) if not pd.isna(last_row['lower_bb']) else 0.0
                                state.indicators["upper_bb"] = float(last_row['upper_bb']) if not pd.isna(last_row['upper_bb']) else 0.0
                            except Exception:
                                pass

                            # --- Gestión y Análisis ---
                            if state.position:
                                await self.manage_open_position(current_price)
                            
                            await self.analyze_signal(current_price)

                            # --- Cerrar Vela y recalcular indicadores ---
                            if is_kline_closed:
                                state.historical_klines.append(state.current_candle)
                                if len(state.historical_klines) > 100: # MANTENER LAS ULTIMAS 100 VELAS PARA EL RSI(14)
                                    state.historical_klines.pop(0)

                                new_row = {
                                    'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                                    'open': float(kline['o']), 'high': float(kline['h']),
                                    'low': float(kline['l']), 'close': float(kline['c']),
                                    'volume': float(kline['v'])
                                }
                                self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
                                self.df = self.df.tail(100) 
                                self.df = self.indicator_calc.calculate(self.df)

                                # Actualizar historial de líneas BB para el gráfico web
                                last_row = self.df.iloc[-1]
                                close_time = int(last_row['timestamp'].timestamp()) + self.tz_offset_seconds

                                if not pd.isna(last_row['upper_bb']):
                                    state.historical_bb_upper.append({'time': close_time, 'value': float(last_row['upper_bb'])})
                                    if len(state.historical_bb_upper) > 100: state.historical_bb_upper.pop(0)

                                if not pd.isna(last_row['lower_bb']):
                                    state.historical_bb_lower.append({'time': close_time, 'value': float(last_row['lower_bb'])})
                                    if len(state.historical_bb_lower) > 100: state.historical_bb_lower.pop(0)

            except Exception as e:
                logger.error(f"Red desconectada o error en el Stream: {e}. Reconectando en 5 segundos...")
                await asyncio.sleep(5)