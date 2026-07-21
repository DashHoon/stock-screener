"""배치 파이프라인 설정. 지표 파라미터는 전부 여기서만 바꾼다."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "batch" / "data"
CACHE_DIR = DATA_DIR / "cache"
OHLCV_CACHE_DIR = CACHE_DIR / "ohlcv"
STOCKS_CACHE = CACHE_DIR / "stocks.parquet"

# 산출물은 웹 빌드가 읽는다
OUTPUT_DIR = ROOT / "web" / "public" / "data"
SIGNALS_DIR = OUTPUT_DIR / "signals"
CHART_DIR = OUTPUT_DIR / "chart"

# --- 수집 ---
BACKFILL_YEARS = 2          # 백필 기간
MIN_ROWS_FOR_INDICATORS = 60  # 이보다 짧은 종목(신규상장 등)은 지표 계산 스킵

# --- RSI ---
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# --- MACD ---
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- 볼린저밴드 ---
BB_PERIOD = 20
BB_STD = 2
BB_SQUEEZE_WINDOW = 120     # 밴드폭이 최근 N일 최저 수준이면 스퀴즈

# --- 다이버전스 ---
PIVOT_LEFT = 3              # 피벗 판정 좌측 lookback (bars)
PIVOT_RIGHT = 3             # 피벗 판정 우측 lookback (확정 지연)
DIV_MIN_BARS = 5            # 피벗 쌍 사이 최소 간격
DIV_MAX_BARS = 60           # 피벗 쌍 사이 최대 간격
DIV_RECENT_BARS = 3         # 마지막 N개 봉 안에서 확정된 다이버전스만 당일 플래그로 인정

# --- 차트 산출 ---
CHART_DAYS = 250            # 종목별 chart json에 담을 일수 (~1년)
