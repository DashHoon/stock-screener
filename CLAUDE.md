# 국내주식 기술적 지표 스크리너 (웹 서비스)

## 프로젝트 개요

국내주식 전 종목(~2,700개)을 대상으로 RSI 다이버전스, MACD, 볼린저밴드 시그널을 매일 계산하고, 조건 조합으로 종목을 스크리닝할 수 있는 웹 서비스. 하루 지연 시세 기반. 수익모델은 광고.

핵심 설계 원칙: **하루 1번 배치로 모든 계산을 끝내고, 서빙은 정적으로.** 상시 가동 서버 없음. 고정비 ~0원.

## 아키텍처

```
공공데이터 API ─→ GitHub Actions (일 1회 크론, 밤 시간대)
                    ├─ 수집: 전 종목 일봉 OHLCV
                    ├─ 계산: RSI/MACD/BB + 시그널 플래그
                    ├─ 저장: Supabase (이력 DB)
                    ├─ 산출: 정적 JSON (당일 플래그, 종목별 차트 데이터)
                    └─ Vercel Deploy Hook 호출 → 사이트 재빌드
Next.js (SSG) on Vercel ─→ 브라우저 (클라이언트 필터링 + 차트)
```

## 기술 스택 (확정)

| 영역 | 선택 | 비고 |
|---|---|---|
| 배치/크론 | GitHub Actions (Python) | 실행시간 제한 없음, 무료 |
| DB | Supabase (Postgres, free tier) | 이력 보관용. Supabase Cron은 사용 안 함 |
| 프론트 | Next.js, SSG/ISR | 종목별 정적 페이지 → SEO |
| 호스팅 | Vercel free tier | 배치 후 Deploy Hook으로 재빌드 |
| 차트 | lightweight-charts (TradingView OSS) | 캔들 + 지표 패널 |
| 도메인 | 초기엔 *.vercel.app | 공개 시점에 구매 (Cloudflare Registrar 또는 .kr) |

AWS는 이번 프로젝트에서 사용하지 않기로 결정함.

## 데이터 소스

- **일별 수집**: 공공데이터포털 금융위원회_주식시세정보 (`getStockPriceInfo`)
  - 하루 지연 시세. `basDt`(기준일자)로 하루치 전 종목 페이징 수집
  - 장 마감 후 저녁~익일 오전 갱신 → 크론은 밤 시간대(예: KST 22시 + 익일 오전 재시도)
  - API 키는 GitHub Secrets로 관리
  - 호출 제한 주의 (개발계정 일 1만 건 수준)
- **과거 백필**: pykrx 또는 FinanceDataReader로 1회 수행 (공공 API 호출 제한 회피)
- UI에 "전일 기준 데이터" 명시 필수 (지연 시세 고지)

## 지표 계산 스펙

배치에서 전 종목 일괄 계산. pandas 기반.

### RSI (14)
- 값, 과매수(≥70)/과매도(≤30) 플래그
- **다이버전스 (핵심 기능)**: 피벗 고점/저점 탐지 → 가격 피벗과 RSI 피벗 방향 비교
  - Regular bullish: 가격 저점 하락 + RSI 저점 상승
  - Regular bearish: 가격 고점 상승 + RSI 고점 하락
  - Hidden bullish/bearish도 판정
  - 피벗 탐지 파라미터(좌우 lookback)는 설정으로 분리

### MACD (12, 26, 9)
- 시그널선 골든크로스/데드크로스, 히스토그램 부호 전환, 0선 돌파

### 볼린저밴드 (20, 2)
- 상단/하단 터치, %B, 밴드폭(스퀴즈 판정: 밴드폭이 최근 N일 최저 수준)

## 데이터 모델

**Supabase (이력)**
- `ohlcv(code, date, open, high, low, close, volume)`
- `indicators(code, date, rsi, macd, macd_signal, macd_hist, bb_upper, bb_mid, bb_lower, pct_b, bb_width)`

**정적 JSON (서빙용)**
- `signals/latest.json` — 전 종목 당일 플래그 (스크리너가 통째로 로드, 수백 KB 수준)

```json
{
  "date": "2026-07-20",
  "stocks": [
    {
      "code": "005930", "name": "삼성전자", "close": 86000, "change_pct": 1.2,
      "flags": {
        "rsi_overbought": false, "rsi_oversold": false,
        "div_reg_bull": false, "div_reg_bear": false,
        "div_hid_bull": false, "div_hid_bear": false,
        "macd_golden": true, "macd_dead": false, "macd_zero_up": false,
        "bb_upper_touch": false, "bb_lower_touch": false, "bb_squeeze": true
      },
      "rsi": 55.3
    }
  ]
}
```

- `chart/{code}.json` — 종목별 최근 ~1년 OHLCV + 지표 (차트 페이지용)

## 프론트엔드 요구사항

1. **스크리너 (메인)**: `latest.json` 로드 → 플래그 체크박스 AND 조합 필터 → 결과 테이블(종목명, 종가, 등락률, 발생 시그널). 클라이언트 필터링만으로 처리 (2,700종목이라 충분)
2. **조건 조합 URL**: `/screen?flags=rsi_oversold,bb_lower_touch` 형태 → 공유 가능 + 주요 조합은 정적 페이지 생성 (SEO)
3. **종목 상세 `/stock/[code]`**: SSG. lightweight-charts로 캔들 + RSI/MACD/BB 패널, 다이버전스 발생 구간 마킹
4. **콘텐츠 페이지**: 지표 설명·시그널 해석 가이드 (애드센스 승인 대비, SEO)
5. 광고 슬롯 컴포넌트를 레이아웃에 미리 확보 (초기: 카카오 애드핏 + 증권사 계좌개설 CPA 제휴 배너, 이후 애드센스 병행)

## 모바일 앱 (별도 저장소)

앱은 `../kscreener-app`에 있다 (Flutter, iOS/Android). 이 저장소는 **공개**라서
분리했다. 앱은 이 저장소의 산출물을 받아 쓰는 소비자다:

- 데이터: `kscreener.com/data`의 정적 JSON (배치가 만든 것)
- 시그널 정의: `web/lib/flags.ts` → 앱의 `lib/models/signal.dart`로 옮겨 둠
- 패턴 도해: `web/components/PatternDiagram.tsx` → 앱에서 스크립트로 변환

**flags.ts나 PatternDiagram.tsx를 고치면 앱 쪽도 같이 고쳐야 한다.**
키가 어긋나면 앱 검색이 에러 없이 빈 결과를 낸다. 앱 저장소에서
`python3 tool/check_flag_parity.py`로 확인한다.

기획·수익화·성능 문서는 이 저장소에 있다 (APP_SPEC.md, APP_PLAN.md,
APP_MONETIZE.md).

## 구현 단계

1. **Phase 1 — 배치 파이프라인**: 공공 API 수집 → 지표/플래그 계산 → JSON 산출. 로컬에서 검증 (백테스트: 알려진 다이버전스 사례로 판정 로직 확인)
2. **Phase 2 — 웹 MVP**: 스크리너 + 종목 상세 차트. `*.vercel.app`으로 배포
3. **Phase 3 — 자동화 연결**: GitHub Actions 크론 + Supabase 적재 + Deploy Hook
4. **Phase 4 — 공개 준비**: 도메인, 콘텐츠 페이지, 애드핏/CPA 광고, 지연시세·면책 고지

## 주의사항

- API 키 등 시크릿은 코드에 넣지 말 것 (GitHub Secrets / 환경변수)
- 휴장일 처리: 데이터 없는 날은 배치 스킵
- 신규상장/거래정지 종목 예외 처리 (데이터 길이 부족 시 지표 계산 스킵)
- 투자 조언이 아닌 정보 제공임을 명시하는 면책 문구 필수
- 유료 종목 추천(구독) 모델은 유사투자자문업 신고 이슈가 있으므로 광고 모델 유지
