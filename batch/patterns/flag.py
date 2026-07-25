"""플래그/페넌트 (급등락 깃대 + 짧은 조정 후 재돌파). 페넌트(수렴형)도 포함해 판정.

- 상승 플래그: 깃대(POLE_BARS 내 +POLE_MIN_PCT%) → 5~25봉 얕은 조정(깃대의
  상위 FLAG_MAX_RETRACE 이내, 고점 갱신 없음) → 조정 구간 고점 상향 돌파 = 완성
- 하락 플래그: 대칭 (급락 → 짧은 반등/횡보 → 저점 하향 이탈)
"""

import numpy as np
import pandas as pd

from batch.patterns.util import PatternHit, fit_envelope_line

POLE_BARS = 15
POLE_MIN_PCT = 20.0
FLAG_MIN_LEN = 5
FLAG_MAX_LEN = 25
FLAG_MAX_RETRACE = 0.5   # 조정 깊이 ≤ 깃대의 50%


def detect_flags(ind: pd.DataFrame) -> list[PatternHit]:
    n = len(ind)
    closes = ind["close"].astype(float).to_numpy()
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()

    out: list[PatternHit] = []
    last_end = {"bull": -(10**9), "bear": -(10**9)}

    for i in range(POLE_BARS, n):
        for bull in (True, False):
            j0 = i - POLE_BARS
            base = closes[j0]
            if base <= 0:
                continue
            chg = (closes[i] / base - 1) * 100
            if bull and chg < POLE_MIN_PCT:
                continue
            if not bull and chg > -POLE_MIN_PCT:
                continue
            tag = "bull" if bull else "bear"
            if i - last_end[tag] < FLAG_MAX_LEN:  # 같은 깃대 중복 방지
                continue

            # 깃대 끝 확장: 종가가 계속 신고(신저)면 깃대가 이어지는 중
            e = i
            while e + 1 < n and (closes[e + 1] > closes[e] if bull else closes[e + 1] < closes[e]):
                e += 1

            pole_low = float(np.min(lows[j0 : e + 1])) if bull else float(np.max(highs[j0 : e + 1]))
            pole_top = float(closes[e])  # 돌파 기준은 깃대 종가 고점(저점)
            pole_h = abs(pole_top - pole_low)
            if pole_h <= 0:
                continue

            # 조정 구간 스캔: FLAG_MIN_LEN봉 이상 조정 후 깃대 고점(저점) 종가 돌파
            completed_at = None
            flag_ext_i = None
            deadline = min(e + FLAG_MAX_LEN, n - 1)
            ok = True
            for j in range(e + 1, deadline + 1):
                if bull:
                    if closes[j] < pole_top - pole_h * FLAG_MAX_RETRACE:
                        ok = False  # 조정이 너무 깊음
                        break
                    if j - e >= FLAG_MIN_LEN and closes[j] > pole_top:
                        completed_at = j
                        flag_ext_i = int(np.argmin(lows[e + 1 : j])) + e + 1 if j > e + 1 else None
                        break
                else:
                    if closes[j] > pole_top + pole_h * FLAG_MAX_RETRACE:
                        ok = False
                        break
                    if j - e >= FLAG_MIN_LEN and closes[j] < pole_top:
                        completed_at = j
                        flag_ext_i = int(np.argmax(highs[e + 1 : j])) + e + 1 if j > e + 1 else None
                        break
            if not ok:
                continue
            i = e  # 이후 참조는 확장된 깃대 끝 기준
            forming = bool(completed_at is None and deadline == n - 1 and n - 1 > i)
            if completed_at is None and not forming:
                continue
            if flag_ext_i is None and n - 1 > i:
                seg = lows[i + 1 :] if bull else highs[i + 1 :]
                flag_ext_i = int(np.argmin(seg) if bull else np.argmax(seg)) + i + 1
            last_end[tag] = completed_at if completed_at is not None else i

            # 깃발(조정) 구간을 고점선·저점선 채널로 그린다. 예전처럼 깃대 시작~깃발
            # 저점을 잇는 꺾은선으로 그리면 대각선이 차트를 가로질러 캔들을 가린다.
            f0 = int(i)                                   # 깃대 끝 = 깃발 시작
            f1 = int(completed_at if completed_at is not None else n - 1)
            if f1 - f0 < 2:
                continue
            xs = list(range(f0, f1 + 1))
            up = fit_envelope_line(xs, [float(highs[k]) for k in xs], upper=True)
            lo = fit_envelope_line(xs, [float(lows[k]) for k in xs], upper=False)
            pts_u = [(f0, float(up.at(f0))), (f1, float(up.at(f1)))]
            pts_l = [(f0, float(lo.at(f0))), (f1, float(lo.at(f1)))]
            out.append(PatternHit(
                kind="pat_flag_bull" if bull else "pat_flag_bear",
                completed_at=completed_at,
                forming=forming,
                neckline=pole_top,
                points=pts_u,     # 깃발 고점선
                points2=pts_l,    # 깃발 저점선
                confirmed_at=int(i),
            ))
    return out
