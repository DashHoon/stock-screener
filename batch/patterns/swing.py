"""스윙(ZigZag) 구조 — 모든 차트 패턴 탐지의 공통 기반층.

사람이 차트를 읽는 방식을 코드로 옮긴 것: "의미 있는 반전"만 스윙으로 인정하고,
패턴은 스윙들의 배열로 판정한다 (2026-07-28 방법론 결정).

- 반전 임계 = max(k × ATR14, p% × 종가) — 종목 변동성에 자동 적응.
  잔파동은 애초에 스윙이 아니므로 '엉뚱한 고점·저점 연결' 문제가 원천 차단된다.
- 2스케일: minor(단기 구조용)·major(장기 구조용). 짧은 쌍바닥과 긴 라운드바텀을
  같은 확대 배율로 볼 수는 없다. 스케일 중복 검출은 dedupe_patterns가 정리.
- 스윙은 고점-저점이 엄격히 교대하며, 각 스윙에는 '확정 봉'(confirmed_at)이 있다
  — 반전 폭이 임계를 넘어선 봉. 그 전에는 그 극점이 스윙인지 알 수 없으므로,
  패턴 완성(돌파) 스캔은 반드시 confirmed_at 이후에서 시작해야 미래 참조가 없다.
  마지막 잠정 극점은 confirmed_at=None으로 포함된다 (형성 중 판정용).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from batch import config
from batch.patterns.util import Line, fit_line


@dataclass(frozen=True)
class Swing:
    idx: int                  # 극점 위치 (행 인덱스)
    price: float              # 극점 가격 (고점=high, 저점=low)
    is_high: bool
    confirmed_at: int | None  # 반전 임계 충족 봉. None = 잠정 극점 (마지막 레그)


@dataclass
class SwingCtx:
    """detect_all_patterns가 한 번 만들어 모든 탐지기에 전달하는 공통 재료."""
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    atr: np.ndarray
    minor: list[Swing]
    major: list[Swing]

    def swings(self, scale: str) -> list[Swing]:
        return self.minor if scale == "minor" else self.major


def wilder_atr(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    period: int = config.SWING_ATR_PERIOD,
) -> np.ndarray:
    """Wilder ATR. 워밍업 구간(period 이전)은 단순 확장 평균으로 채운다."""
    n = len(closes)
    if n == 0:
        return np.array([])
    prev_close = np.concatenate(([closes[0]], closes[:-1]))
    tr = np.maximum(
        highs - lows,
        np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)),
    )
    atr = np.empty(n)
    acc = tr[0]
    atr[0] = tr[0]
    for i in range(1, n):
        if i < period:
            acc += tr[i]
            atr[i] = acc / (i + 1)
        else:
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def zigzag(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, atr: np.ndarray,
    atr_mult: float, min_pct: float,
) -> list[Swing]:
    """ATR 적응형 ZigZag. 고점-저점 교대 스윙 목록 (시간순).

    상승 레그에서는 최고 고가를 잠정 고점으로 추적하다가, 저가가 잠정 고점에서
    임계 이상 반락하면 그 고점을 스윙으로 확정하고 하락 레그로 전환한다 (대칭).
    같은 봉이 신고가와 반전을 동시에 만들면(아웃사이드 바) 확장을 우선하고
    반전 판정은 다음 봉으로 미룬다 — 한 봉이 고점·저점 스윙을 겸하지 않도록.
    """
    n = len(closes)
    if n == 0:
        return []
    thr = np.maximum(atr * atr_mult, closes * (min_pct / 100.0))
    # 오염 행 방어: 종가≤0·ATR=0이면 임계가 0이 되어 매 봉이 스윙으로 폭주한다.
    # 그런 봉에서는 반전을 확정하지 않는다 (수집원 이상 데이터의 안전 강하).
    thr = np.where(thr > 0, thr, np.inf)

    swings: list[Swing] = []
    direction = 0        # +1 = 상승 레그(고점 추적), -1 = 하락 레그, 0 = 미정
    ext_i = 0            # 현재 레그의 잠정 극점 인덱스
    hi_i = lo_i = 0      # 방향 미정 구간의 러닝 극값

    for i in range(1, n):
        if direction == 0:
            if highs[i] > highs[hi_i]:
                hi_i = i
            if lows[i] < lows[lo_i]:
                lo_i = i
            # 첫 임계 돌파로 방향과 첫 스윙을 정한다
            if lo_i < i and highs[i] - lows[lo_i] >= thr[i]:
                swings.append(Swing(int(lo_i), float(lows[lo_i]), False, int(i)))
                direction = 1
                seg = slice(lo_i + 1, i + 1)
                ext_i = lo_i + 1 + int(np.argmax(highs[seg]))
            elif hi_i < i and highs[hi_i] - lows[i] >= thr[i]:
                swings.append(Swing(int(hi_i), float(highs[hi_i]), True, int(i)))
                direction = -1
                seg = slice(hi_i + 1, i + 1)
                ext_i = hi_i + 1 + int(np.argmin(lows[seg]))
            continue

        if direction > 0:
            if highs[i] > highs[ext_i]:
                ext_i = i
            if ext_i < i and highs[ext_i] - lows[i] >= thr[i]:
                swings.append(Swing(int(ext_i), float(highs[ext_i]), True, int(i)))
                direction = -1
                seg = slice(ext_i + 1, i + 1)
                ext_i = ext_i + 1 + int(np.argmin(lows[seg]))
        else:
            if lows[i] < lows[ext_i]:
                ext_i = i
            if ext_i < i and highs[i] - lows[ext_i] >= thr[i]:
                swings.append(Swing(int(ext_i), float(lows[ext_i]), False, int(i)))
                direction = 1
                seg = slice(ext_i + 1, i + 1)
                ext_i = ext_i + 1 + int(np.argmax(highs[seg]))

    if direction != 0:
        # 마지막 잠정 극점 — 아직 반전 미확정 (형성 중 패턴 판정에만 사용)
        price = float(highs[ext_i]) if direction > 0 else float(lows[ext_i])
        swings.append(Swing(int(ext_i), price, direction > 0, None))
    return swings


def build_ctx(ohlcv: pd.DataFrame) -> SwingCtx:
    highs = ohlcv["high"].astype(float).to_numpy()
    lows = ohlcv["low"].astype(float).to_numpy()
    closes = ohlcv["close"].astype(float).to_numpy()
    atr = wilder_atr(highs, lows, closes)
    return SwingCtx(
        highs=highs, lows=lows, closes=closes, atr=atr,
        minor=zigzag(highs, lows, closes, atr,
                     config.SWING_MINOR_ATR_MULT, config.SWING_MINOR_MIN_PCT),
        major=zigzag(highs, lows, closes, atr,
                     config.SWING_MAJOR_ATR_MULT, config.SWING_MAJOR_MIN_PCT),
    )


def fit_swing_trendline(
    xs: list[int], ys: list[float], atr: np.ndarray, upper: bool,
) -> tuple[Line, int]:
    """스윙 극점들로 사람이 긋는 방식의 추세선을 긋는다. (선, 터치 수) 반환.

    회귀가 아니라 두 극점을 앵커로 직선을 긋고, 나머지 극점의 위반(저항선 위로
    삐져나옴 등)이 없으면서 터치가 가장 많은 선을 고른다. 회귀 방식의 고질병 —
    이상치 하나가 기울기를 왜곡하는 문제 — 이 사라진다.

    터치 = 극점이 선에서 SWING_TOUCH_ATR×ATR 이내. 위반 = 잘못된 쪽으로
    SWING_VIOL_ATR×ATR 초과 이탈. r2는 참고용으로 채운다 (판정에 쓰지 말 것).
    """
    if len(xs) < 2:
        return fit_line(xs, ys), len(xs)
    pts = list(zip(xs, ys))
    best: tuple | None = None  # (유효, 터치수, 스팬, -총편차, Line)
    for a in range(len(pts) - 1):
        for b in range(a + 1, len(pts)):
            x0, y0 = pts[a]
            x1, y1 = pts[b]
            if x1 == x0:
                continue
            slope = (y1 - y0) / (x1 - x0)
            line = Line(slope, y0 - slope * x0, 0.0)
            touches = 0
            viol = 0.0
            dev_sum = 0.0
            for x, y in pts:
                d = y - line.at(x)          # 양수 = 선 위
                tol = float(atr[min(x, len(atr) - 1)])
                if abs(d) <= tol * config.SWING_TOUCH_ATR:
                    touches += 1
                excess = d - tol * config.SWING_VIOL_ATR if upper else -d - tol * config.SWING_VIOL_ATR
                if excess > 0:
                    viol += excess
                dev_sum += abs(d)
            cand = (viol <= 0, touches, x1 - x0, -dev_sum, line)
            if best is None or cand[:4] > best[:4]:
                best = cand
    if best is None:  # 모든 쌍이 동일 x — 퇴화 입력 (호출자 병합 목록 방어)
        level = max(ys) if upper else min(ys)
        return Line(0.0, float(level), 0.0), len(xs)
    line = best[4]
    # r2는 정보용 (기존 Line 소비자 호환)
    y_arr = np.asarray(ys, dtype=float)
    fit = np.array([line.at(x) for x in xs])
    ss_tot = float(np.sum((y_arr - y_arr.mean()) ** 2))
    r2 = 1.0 if ss_tot <= 0 else max(0.0, 1 - float(np.sum((y_arr - fit) ** 2)) / ss_tot)
    return Line(line.slope, line.intercept, r2), int(best[1])
