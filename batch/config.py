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
# 이격도 = 종가 / N일 이동평균 * 100. 100이면 이평선 위에 딱 붙어 있다는 뜻.
# 20일(단기)·60일(중기)이 국내에서 가장 많이 쓰인다. 5·120은 차트 표시용.
DISPARITY_MAS = (5, 20, 60, 120)
DISPARITY_SEARCH_MAS = (20, 60)   # 검색에 노출하는 것 (latest.json에 싣는다)

# 이격도 과열/침체 시그널 임계값. 교과서에 흔한 105/95는 국내 개별주에서
# 20% 넘게 걸려 스크리닝이 안 된다(실측). RSI 70/30이 약 5% 걸리는 것에
# 맞춰 잡았다 — 600종목 22만 봉 기준:
#   20일 ≥115 4.9% / ≤85 4.0%,  60일 ≥130 4.6% / ≤75 5.2%
# 60일이 훨씬 넓은 건 추세가 붙은 종목이 60일선에서 오래 떨어져 있기 때문이다.
DISPARITY_BANDS = {20: (115.0, 85.0), 60: (130.0, 75.0)}

# 그물망(GMMA) — 단기 6개·장기 6개 지수이동평균. Guppy 원안 그대로 쓴다.
# 종가가 12개 선 위에 다 있으면 정배열, 다 아래면 역배열.
# 이벤트가 아니라 상태다 — 실측으로 정배열 24%, 역배열 33% (178종목 5.7만 봉).
GMMA_SHORT = (3, 5, 8, 10, 12, 15)
GMMA_LONG = (30, 35, 40, 45, 50, 60)
GMMA_MIN_BARS = 60   # 가장 긴 선이 자리를 잡기 전에는 판정하지 않는다

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
DIV_CHAIN_MIN = 3           # 이 개수 이상의 피벗이 이어지면 '연속 다이버전스'
DIV_RSI_BULL_ZONE = 40.0
DIV_RSI_BEAR_ZONE = 60.0

# --- 수정주가 정합성 ---
# 전일 종가 대비 이 비율(%) 이상 변동하면 기업행위(증자·분할·감자 등)로 의심하고
# 해당 종목 캐시를 통째로 재수집한다. 가격제한폭(±30%)을 넘는 변동은 정상 거래로
# 불가능하므로 확실한 신호. 25%로 낮춰 잡은 이유: 큰 수정주가 조정도 잡기 위해.
# 실제 급등락(25~30%)이 오탐되어도 비용은 해당 종목 1회 재수집뿐이라 무해하다.
# 30% 미만의 작은 조정(소규모 증자 등)은 여기서 못 잡고 주 1회 전체 재백필이 보정한다.
REBUILD_JUMP_PCT = 25.0

# --- 스윙(ZigZag) 구조 — 패턴 탐지 공통 기반 (2026-07-28 방법론 결정) ---
# 반전 임계 = max(k × ATR14, p% × 종가). 종목 변동성에 자동 적응해
# 잔파동이 스윙으로 잡히지 않는다. minor=단기 구조, major=장기 구조.
SWING_ATR_PERIOD = 14
SWING_MINOR_ATR_MULT = 2.0
SWING_MINOR_MIN_PCT = 3.0
SWING_MAJOR_ATR_MULT = 4.0
SWING_MAJOR_MIN_PCT = 6.0
SWING_TOUCH_ATR = 0.5       # 추세선 '터치' 인정 거리 (ATR 배수)
SWING_VIOL_ATR = 0.25       # 추세선 위반(잘못된 쪽 이탈) 허용 한도 (ATR 배수)

# --- 차트 패턴 (쌍바닥/더블탑) ---
# 피벗 lookback·간격 상수는 스윙 이식(2026-07-28)으로 제거 — 간격은
# double.py의 DB_GAP(스케일별)이 대체한다.
PAT_TOL_PCT = 3.0           # 두 바닥(꼭대기)의 가격 유사 허용 오차 %
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
# 일봉은 '최근분'과 '아카이브'로 나눈다.
#
# 10년 일봉을 한 파일에 담으면 종목당 105KB → 300KB가 되어, 최근 몇 달만 보고
# 나가는 대부분의 방문자에게도 8년치를 매번 딸려 보내게 된다. 그래서 최근분만
# 기본 파일에 싣고, 그 이전은 별도 파일로 빼 '전체' 기간을 볼 때만 받게 한다.
#
# 경계는 반드시 달력 날짜로 고정한다. "최근 N개월" 식으로 매일 굴리면 경계가
# 하루씩 밀려 아카이브도 매일 새로 만들어야 하므로 나눈 의미가 없어진다.
# 매년 1월에 한 해씩 자동으로 아카이브로 넘어간다 (최근분 길이 12~24개월).
CHART_DAILY_BARS = 500      # 일봉 최근분 상한 (경계가 이보다 멀면 이 개수로 자른다)
CHART_WEEKLY_BARS = 520     # 주봉 ~10년
CHART_MONTHLY_BARS = 120    # 월봉 10년

# 검색 결과 격자(바둑판)에 그릴 미니 차트. 종목당 별도 파일로 빼서 화면에 보이는
# 12개만 받는다. 종목 차트(93KB)를 12개 받으면 1.1MB라 페이지를 넘길 때마다 무겁다.
# 120봉(약 6개월)이면 플래그·삼각수렴·쌍바닥이 대부분 들어오고, 더 길면 뭉개진다.
CHART_MINI_BARS = 120

# 격자 기본 표시는 최근 20영업일 캔들이다. 라인 120봉과 둘 다 쓸 수 있게
# 한 파일에 같이 담는다 (캔들 20봉은 600바이트 — 파일이 2.0KB로 늘어난다).
CHART_MINI_CANDLES = 20


def chart_hot_from(today=None) -> str:
    """일봉 최근분의 시작일(YYYY-MM-DD). 이 날짜 이전은 아카이브 파일로 뺀다."""
    import datetime as _dt

    d = today or _dt.date.today()
    return f"{d.year - 1}-01-01"
