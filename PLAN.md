# 국내주식 기술적 지표 스크리너 — 구현 계획서

> 기준 문서: [CLAUDE.md](CLAUDE.md) · 작성일: 2026-07-21

## 1. 목표

국내주식 전 종목(~2,700개)의 RSI 다이버전스 / MACD / 볼린저밴드 시그널을 **하루 1회 배치**로 계산하고, 조건 조합으로 스크리닝할 수 있는 웹 서비스를 만든다.

- 상시 서버 없음. 배치(GitHub Actions) + 정적 서빙(Vercel SSG)으로 **고정비 ~0원**
- 하루 지연 시세 기반, 수익모델은 광고 (애드핏 + CPA → 애드센스)

## 2. 전체 구조

```
공공데이터 API ─→ GitHub Actions (일 1회, 밤)
                   ├─ 수집: 전 종목 일봉 OHLCV
                   ├─ 계산: RSI/MACD/BB + 시그널 플래그
                   ├─ 저장: Supabase (이력)
                   ├─ 산출: signals/latest.json, chart/{code}.json
                   └─ Vercel Deploy Hook → 사이트 재빌드
Next.js SSG on Vercel ─→ 브라우저 (클라이언트 필터링 + lightweight-charts)
```

## 3. 저장소 구성 (제안)

```
StockScreener/
├─ batch/                  # Python 배치 파이프라인
│  ├─ collector/           #   공공 API 수집, pykrx 백필
│  ├─ indicators/          #   RSI/MACD/BB/다이버전스 계산
│  ├─ output/              #   JSON 산출, Supabase 적재
│  ├─ config.py            #   피벗 lookback 등 파라미터
│  └─ tests/               #   지표·다이버전스 단위 테스트
├─ web/                    # Next.js 앱
│  ├─ app/                 #   /(스크리너), /screen, /stock/[code], /guide
│  ├─ components/          #   필터, 테이블, 차트, 광고 슬롯
│  └─ public/data/         #   빌드 시 참조하는 정적 JSON (배치 산출물)
└─ .github/workflows/      # daily-batch.yml
```

## 4. 단계별 계획

### Phase 1 — 배치 파이프라인 (로컬 검증까지)

**목표**: 로컬에서 `python -m batch.run` 한 번으로 수집→계산→JSON 산출이 끝난다.

1. **환경 셋업**: Python 프로젝트 초기화, 의존성(pandas, requests, pykrx), `.env` 방식의 시크릿 관리
2. **종목 마스터**: KRX 전 종목 코드/이름 수집 (KOSPI+KOSDAQ), ETF/스팩 등 제외 규칙 결정
3. **백필**: pykrx로 전 종목 최근 2년 일봉 1회 수집 → 로컬 parquet/CSV 캐시
4. **일별 수집**: 공공데이터포털 `getStockPriceInfo`를 `basDt` 페이징으로 하루치 전 종목 수집. 휴장일(데이터 없음) 스킵 처리
5. **지표 계산**: RSI(14), MACD(12,26,9), BB(20,2) — pandas 벡터화, 데이터 길이 부족 종목 스킵
6. **다이버전스 판정** (핵심): 피벗 고점/저점 탐지 → regular/hidden bullish/bearish 4종 판정. lookback 파라미터는 config로 분리
7. **플래그 산출**: CLAUDE.md의 `flags` 스키마 그대로 `signals/latest.json` + 종목별 `chart/{code}.json`(최근 1년) 생성
8. **검증**: 지표값을 pykrx/증권사 HTS 값과 대조, 알려진 다이버전스 사례로 판정 로직 백테스트, 단위 테스트 작성

**완료 기준**: 전 종목 JSON이 생성되고, 표본 종목의 지표값·다이버전스 판정이 외부 기준과 일치.

### Phase 2 — 웹 MVP

**목표**: `*.vercel.app`에서 스크리너와 종목 차트가 동작한다.

1. **Next.js 셋업**: App Router + TypeScript, 정적 JSON을 데이터 소스로 사용
2. **스크리너 페이지 (메인)**: `latest.json` 로드 → 12개 플래그 체크박스 AND 필터 → 결과 테이블(종목명·종가·등락률·시그널 배지), 정렬
3. **URL 공유**: `/screen?flags=rsi_oversold,bb_lower_touch` — URL ↔ 필터 상태 동기화, 주요 조합은 정적 페이지 생성(SEO)
4. **종목 상세 `/stock/[code]`**: SSG(generateStaticParams). lightweight-charts로 캔들 + RSI/MACD/BB 패널, 다이버전스 구간 마킹
5. **공통 레이아웃**: "전일 기준 데이터" 고지, 면책 문구, 광고 슬롯 컴포넌트(자리만 확보)
6. **배포**: Vercel 연결, 프리뷰 확인

**완료 기준**: 실제 배치 산출 JSON으로 스크리닝→종목 차트 열람 흐름이 완결.

### Phase 3 — 자동화 연결

**목표**: 사람 손 없이 매일 밤 데이터가 갱신된다.

1. **Supabase**: `ohlcv`, `indicators` 테이블 생성, 배치에서 upsert 적재
2. **GitHub Actions**: KST 22시 크론 + 익일 오전 재시도 워크플로. API 키·Supabase 키는 GitHub Secrets
3. **산출물 전달**: 산출 JSON(~63MB)은 main 이력을 오염시키지 않도록 **`data` 브랜치에 force-push**하고, Vercel은 `data` 브랜치를 배포 대상으로 연결 → **Deploy Hook 호출**. OHLCV 캐시는 Actions cache로 유지해 매일 증분 수집만 수행
4. **운영 안전장치**: 수집 실패/데이터 미갱신 시 배포 스킵, 실패 알림(Actions 이메일)

**완료 기준**: 개입 없이 2~3일 연속 자동 갱신 성공.

### Phase 4 — 공개 준비

1. 콘텐츠 페이지: 지표 설명, 시그널 해석 가이드 (SEO + 애드센스 승인 대비)
2. SEO: 메타태그, sitemap, OG 이미지, 주요 필터 조합 정적 페이지
3. 광고: 카카오 애드핏 + 증권사 계좌개설 CPA 배너 → 이후 애드센스
4. 도메인 구매·연결, 지연시세·투자책임 면책 최종 점검

## 5. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| 공공 API 일 1만 건 제한 | 일별 수집은 페이징 호출 수십 건 수준이라 여유. 백필은 pykrx로 우회 |
| API 갱신 시점 불확실 (저녁~익일 오전) | 22시 1차 + 익일 오전 재시도, 미갱신 시 배포 스킵 |
| 다이버전스 오탐/미탐 | 피벗 파라미터 config 분리, 알려진 사례 백테스트, 판정 근거(피벗 좌표) 저장 |
| Supabase free tier 용량(500MB) | ohlcv 이력만 적재 시 수년치 여유. 초과 시 오래된 이력 아카이브 |
| 유사투자자문업 규제 | 종목 "추천" 표현 금지, 정보 제공 면책 문구, 광고 모델 유지 |

## 6. 작업 순서

할 일은 [TODO.md](TODO.md)에 작게 쪼개 두었다. 위에서 아래로 하나씩 처리하면 Phase 1→4 순서로 진행된다.
