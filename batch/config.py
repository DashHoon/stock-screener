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
# 10년: 주봉/월봉 10년 차트·백테스팅용. 긴 구간 수집은 2년 조각으로 분할된다
# (backfill._fetch_range — 수집원이 대용량 요청 연타를 조르는 문제 대응).
BACKFILL_YEARS = 10
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

# --- 차트 패턴 (쌍바닥/더블탑) ---
PAT_PIVOT_LEFT = 5          # 가격 피벗 좌우 lookback (RSI 피벗보다 넓게 — 주요 스윙만)
PAT_PIVOT_RIGHT = 5
PAT_TOL_PCT = 3.0           # 두 바닥(꼭대기)의 가격 유사 허용 오차 %
PAT_MIN_GAP = 10            # 두 바닥 사이 최소 봉 수
PAT_MAX_GAP = 60            # 두 바닥 사이 최대 봉 수
PAT_MIN_DEPTH_PCT = 5.0     # 넥라인이 바닥 대비 최소 이만큼 높아야 (잡음 제거)
PAT_BREAKOUT_WINDOW = 40    # 두 번째 바닥 확정 후 돌파를 기다리는 최대 봉 수

# --- 차트 패턴 (컵앤핸들) ---
CUP_MIN_LEN = 30            # 컵 길이(좌림→우림) 최소 봉 수 (~6주)
CUP_MAX_LEN = 180           # 최대 봉 수 (~9개월)
CUP_RIM_TOL_PCT = 6.0       # 좌우 림 높이 차 허용 %
CUP_MIN_DEPTH_PCT = 10.0    # 컵 깊이(림 대비) 최소 %
CUP_MAX_DEPTH_PCT = 50.0    # 최대 % (그 이상은 붕괴이지 컵이 아님)
CUP_BOTTOM_ZONE = (0.30, 0.70)  # 바닥 위치가 컵 구간의 이 비율 범위 안 (가운데)
CUP_ROUND_R2 = 0.55         # 종가의 2차 곡선 적합 R² 최소치 (U자 검증)
CUP_MIN_CURVE_GAIN = 0.20   # 포물선이 직선보다 이만큼은 잘 맞아야 (추세→컵 둔갑 방지)
# V자 배제: 바닥권(깊이 하위 15%) 체류 봉 비율. 포물선 U는 ~39%, 직선 V는 ~15%
CUP_FLAT_ZONE = 0.15
CUP_FLAT_FRAC = 0.25
HANDLE_MIN_LEN = 5          # 핸들 최소 봉 수 (우림 후 돌파까지 최소 대기)
HANDLE_MAX_LEN = 40         # 핸들·돌파 대기 최대 봉 수
HANDLE_MAX_DEPTH_FRAC = 0.5 # 핸들 저점이 컵 깊이의 상위 절반에 있어야 함

# --- 스크리너 기간 필터 ---
RECENT_MAX_BARS = 63        # '최근 발생' 추적 상한 (~3개월). 이보다 오래되면 생략

# --- 차트 산출 ---
# 타임프레임 계층화: 일봉은 최근 2년, 장기(10년)는 주봉/월봉으로 본다.
# (10년 일봉을 그대로 담으면 전체 ~700MB로 정적 서빙에 부적합)
CHART_DAILY_BARS = 500      # 일봉 ~2년
CHART_WEEKLY_BARS = 520     # 주봉 ~10년
CHART_MONTHLY_BARS = 120    # 월봉 10년
