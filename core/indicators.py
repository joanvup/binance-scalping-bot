import pandas as pd
import pandas_ta as ta
from core.logger import logger

class IndicatorCalculator:
    def __init__(self, bb_length=20, bb_std=2.0, rsi_length=14):
        self.bb_length = bb_length
        self.bb_std = bb_std
        self.rsi_length = rsi_length

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula BBL (Banda Inferior), BBU (Banda Superior) y RSI.
        Es resiliente ante la falta de historial (ej. Testnet sin suficientes datos).
        """
        try:
            # Asegurar que la columna close es float
            df['close'] = df['close'].astype(float)
            
            # 1. Crear las columnas vacías por defecto (Protección contra fallos)
            if 'lower_bb' not in df.columns:
                df['lower_bb'] = float('nan')
                df['upper_bb'] = float('nan')
                df['rsi'] = float('nan')

            # Si hay menos velas que la longitud de las BB, devolvemos el DF con NaN
            if len(df) < self.bb_length:
                return df

            # 2. Calcular Bandas de Bollinger
            bb = ta.bbands(df['close'], length=self.bb_length, std=self.bb_std)
            
            # Si el cálculo fue exitoso y no devolvió None
            if bb is not None and not bb.empty:
                bbl_col =[c for c in bb.columns if c.startswith('BBL')][0]
                bbu_col =[c for c in bb.columns if c.startswith('BBU')][0]
                df['lower_bb'] = bb[bbl_col]
                df['upper_bb'] = bb[bbu_col]

            # 3. Calcular RSI
            rsi = ta.rsi(df['close'], length=self.rsi_length)
            
            # Si el cálculo del RSI fue exitoso
            if rsi is not None and not rsi.empty:
                df['rsi'] = rsi

            return df
            
        except Exception as e:
            logger.error(f"Error calculando indicadores: {e}")
            return df