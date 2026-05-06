import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# Crea una carpeta 'data' para guardar el archivo de la base de datos
os.makedirs("data", exist_ok=True)

# Conexión a SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///data/trades.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class TradeHistory(Base):
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    order_id = Column(String)
    symbol = Column(String, index=True)
    side = Column(String)           # LONG o SHORT
    entry_price = Column(Float)
    exit_price = Column(Float)
    qty = Column(Float)
    pnl = Column(Float)             # Ganancia o pérdida en USDT
    dca_count = Column(Integer)     # Cuántas recompras se hicieron

# Crea la tabla automáticamente si no existe
Base.metadata.create_all(bind=engine)