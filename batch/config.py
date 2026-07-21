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
# RSI 존 필터: bull형은 RSI 피벗 최솟값이 이 값 미만, bear형은 최댓값이 초과일 때만 유효.
# 전 종목 실측(2026-07-20): 중간 지대 잡음이 걸러져 히든 하락 7.5%→0.1%로 감소,
# 과매도권의 정상 상승 다이버전스는 4.3%→4.2%로 유지됨.
DIV_RSI_BULL_ZONE = 40.0
DIV_RSI_BEAR_ZONE = 60.0

# --- 수정주가 정합성 ---
# 전일 종가 대비 이 비율(%) 이상 변동하면 기업행위(증자·분할·감자 등)로 의심하고
# 해당 종목 캐시를 통째로 재수집한다. 가격제한폭(±30%)을 넘는 변동은 정상 거래로
# 불가능하므로 확실한 신호. 25%로 낮춰 잡은 이유: 큰 수정주가 조정도 잡기 위해.
# 실제 급등락(25~30%)이 오탐되어도 비용은 해당 종목 1회 재수집뿐이라 무해하다.
# 30% 미만의 작은 조정(소규모 증자 등)은 여기서 못 잡고 주 1회 전체 재백필이 보정한다.
REBUILD_JUMP_PCT = 25.0

# --- 차트 산출 ---
CHART_DAYS = 250            # 종목별 chart json에 담을 일수 (~1년)
