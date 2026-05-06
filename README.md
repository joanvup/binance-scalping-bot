# 🤖 Binance Scalping Bot

Sistema de trading algorítmico asíncrono para **Binance Futures (USDT-M)**, diseñado para operar estrategias de scalping basadas en la reversión a la media mediante **Bandas de Bollinger** y **RSI**.

## 🚀 Características Principales

*   **Arquitectura Asíncrona:** Construido con `asyncio` y `python-binance` para una ejecución de órdenes ultra rápida y baja latencia.
*   **Gestión de Riesgo Institucional:** 
    *   Stop Loss basado en % del balance total de la cuenta.
    *   Estrategia DCA (Grid) para promediar entradas en contra.
    *   Take Profit dinámico del 1%.
*   **Dashboard Web en Tiempo Real:** Interfaz construida con `FastAPI` y `TradingView Lightweight Charts` para visualización de velas, indicadores (BB/RSI) y PNL.
*   **Auditoría de Trades:** Registro automático en base de datos `SQLite` con soporte de paginación.
*   **Resiliencia:** Sistema de auto-reconexión mediante WebSockets directos a Futuros y sincronización lógica de tiempo (anti-drift).

## 🛠️ Stack Tecnológico

*   **Backend:** Python 3.10+ | FastAPI
*   **Exchange API:** `python-binance` (Wrapper oficial async)
*   **Análisis Técnico:** `pandas` | `pandas-ta`
*   **Interfaz:** HTML5 | JavaScript | TailwindCSS | Lightweight Charts
*   **Persistencia:** SQLite | SQLAlchemy

## 📦 Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/TU_USUARIO/binance-scalping-bot.git
   cd binance-scalping-bot

   python -m venv venv
   source venv/bin/activate  # En Linux/Mac
   # venv\Scripts\activate  # En Windows
   pip install -r requirements.txt
```

2. **Configuración**
Crea un archivo .env en la raíz del proyecto con las siguientes variables:
```bash
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret
BINANCE_IS_TESTNET=True
```

3. **Ejecución**
```bash
python main.py
```

## 🏗️ Arquitectura del Proyecto
```text
binance-scalping-bot/
├── web/
│   ├── templates/          # Vistas HTML y Frontend
│   └── routes.py           # Enpoints API (FastAPI)
├── core/
│   ├── binance_client.py   # Cliente Binance (Async)
│   ├── engine.py           # Lógica de Trading (Motor)
│   ├── indicators.py       # Cálculo de Indicadores
│   ├── state_manager.py    # Gestión de Estado Global
│   └── config.py           # Configuración y Constantes
├── database/
│   ├── models.py           # Modelos SQLAlchemy
│   └── database.py         # Conexión SQLite
├── .env                    # Variables de entorno (NO versionar)
├── requirements.txt        # Dependencias del proyecto
└── main.py                 # Punto de entrada (FastAPI + Engine)
```

## 🎯 Estrategia Detallada (Backtesting)
**Tipo**: Scalping mean reversion

**Timeframe**: 1m

**Indicadores**:
- RSI(14)
- Bollinger Bands (20, 2.0)

**Lógica**:
1. Compra cuando el precio toca la banda inferior Y el RSI < 50
2. Vende cuando el precio toca la banda superior
3. Gestión de riesgo fija: 1% del balance
4. Modo DCA activo: promedio de entradas en contra

## 📈 Dashboard en Tiempo Real
- Panel web con métricas en vivo
- Historial de trades paginado
- Gráficos de velas con indicadores integrados

### Dashboard
Una vez iniciado el bot, accede desde tu navegador a:
http://localhost:8000

## ⚙️ Parámetros del Bot
EXECUTION_MODE: TESTNET (Pruebas), DRY_RUN (Simulación real), LIVE (Trading real).
INITIAL_USDT_MARGIN: Monto base de inversión por operación.
LEVERAGE: Apalancamiento configurado para el símbolo.
MAX_RISK_PCT: Porcentaje del balance total que el bot arriesgará antes de ejecutar un Stop Loss global.
⚠️ Aviso de Riesgo
Este software se proporciona "tal cual" y sin garantía de rentabilidad. El trading de criptomonedas y futuros implica un alto riesgo de pérdida de capital. Úselo primero en entornos de prueba (TESTNET o DRY_RUN) para validar su estrategia antes de operar con fondos reales.
