import os
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from core.state_manager import state
from core.config import settings
from database.models import SessionLocal, TradeHistory
from sqlalchemy import desc
import math

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"settings": settings}
    )

@router.get("/api/chart_data")
async def get_chart_data():
    """Devuelve el historial para construir el gráfico y sus indicadores"""
    return {
        "klines": state.historical_klines,
        "bb_upper": state.historical_bb_upper,
        "bb_lower": state.historical_bb_lower
    }

@router.get("/api/status")
async def get_status():
    pnl = 0.0
    pos_data = None
    
    if state.position and hasattr(state, 'last_price'):
        pnl = state.calculate_unrealized_pnl(state.last_price)
        
        # --- CÁLCULO DE TP Y SL PARA LA BARRA VISUAL ---
        entry = state.position["entry_price"]
        qty = state.position["qty"]
        tp_pct = settings.TAKE_PROFIT_PCT / 100.0
        max_loss = state.balance * (settings.MAX_RISK_PCT / 100.0)
        
        if state.position["side"] == "LONG":
            tp_price = entry * (1 + tp_pct)
            # SL es el precio donde la pérdida flotante alcanza el max_loss
            sl_price = max(0.0, entry - (max_loss / qty)) if qty > 0 else 0.0
        else:
            tp_price = entry * (1 - tp_pct)
            sl_price = entry + (max_loss / qty) if qty > 0 else 0.0
            
        pos_data = {
            **state.position,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "est_funding_fee": state.est_funding_fee
        }
        
    return {
        "is_running": state.is_running,
        "balance": round(state.balance, 2),
        "position": pos_data,
        "unrealized_pnl": round(pnl, 4),
        "last_price": getattr(state, 'last_price', 0.0),
        "indicators": state.indicators,
        "current_candle": state.current_candle
    }

@router.post("/api/toggle")
async def toggle_bot():
    if state.is_running:
        state.stop()
    else:
        state.start()
    return {"is_running": state.is_running}

@router.get("/api/logs")
async def get_logs():
    log_file = "logs/bot.log"
    logs =[]
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs = lines[-50:]
        except Exception:
            pass
    return {"logs": logs}

@router.get("/api/trades")
async def get_trades(page: int = 1, limit: int = 5):
    """Devuelve el historial de trades paginado"""
    db = SessionLocal()
    try:
        total_trades = db.query(TradeHistory).count()
        total_pages = math.ceil(total_trades / limit) if total_trades > 0 else 1
        offset = (page - 1) * limit
        
        # Traemos los trades más recientes primero
        trades = db.query(TradeHistory).order_by(desc(TradeHistory.timestamp)).offset(offset).limit(limit).all()
        
        trades_data =[]
        for t in trades:
            trades_data.append({
                "id": t.id,
                "order_id": t.order_id,
                "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "qty": t.qty,
                "pnl": t.pnl,
                "dca_count": t.dca_count
            })
            
        return {"trades": trades_data, "total_pages": total_pages, "current_page": page}
    finally:
        db.close()