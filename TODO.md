# TODO — 국내주식 기술적 지표 스크리너

> 위에서 아래로 하나씩. 각 항목은 한 세션에 끝낼 수 있는 크기.
> 계획 전체 맥락은 [PLAN.md](PLAN.md) 참고. 👤 = 사용자가 직접 해야 하는 일.

## Phase 0 — 준비

- [x] git 저장소 초기화, `.gitignore` (.env, 데이터 캐시, node_modules)
- [x] 👤 공공데이터포털 가입 + API 키 발급 → `.env`에 기입 완료 (`.env.example`에는 넣지 말 것 — 커밋되는 파일)
- [x] `.env.example` 작성
- [x] 디렉터리 골격 생성: `batch/`, `web/`, `.github/workflows/`

## Phase 1 — 배치 파이프라인

### 1-A. 수집

- [x] Python 프로젝트 셋업 (uv + Python 3.12, pandas/pykrx/FinanceDataReader)
- [x] 종목 마스터 수집: KOSPI+KOSDAQ 전 종목 (FinanceDataReader KRX 목록 — pykrx 목록 API는 빈 값 반환하여 대체)
- [x] 종목 필터 규칙: KONEX·스팩·우선주 제외 → 2,578종목
- [x] 백필 스크립트: 전 종목 최근 2년 일봉 → parquet 캐시, 이어받기 지원 (전 종목 완료, ~8분)
- [x] 공공 API 클라이언트 (`batch/collector/daily.py`) — 실호출 검증 완료 (2,730종목 수신)
- [x] 일별 수집: 공공 API 우선 + fdr 증분 폴백, 휴장일 처리 — 전체 파이프라인 완주 확인
- [x] 검증: 공공 API vs fdr 캐시 전 종목 대조 — 2,473종목 중 불일치 3건(0.1%)
- [x] 수정주가 정합성: 일별 병합 시 25% 이상 급변 감지 → 해당 종목 캐시 재구축(`daily.is_discontinuous`), `--rebuild-all` + 워크플로 토요일 크론으로 주 1회 전 종목 재백필. 30% 미만의 작은 조정은 급변 감지로 못 잡음 → 주간 재백필이 보정 (최대 1주 지연 허용)

### 1-B. 지표 계산

- [x] RSI(14) Wilder 방식 + 과매수/과매도 플래그
- [x] MACD(12,26,9) + 골든/데드크로스, 0선 돌파 플래그
- [x] 볼린저밴드(20,2) + 터치/%B/밴드폭/스퀴즈 플래그
- [x] 데이터 길이 부족 종목 스킵 (60봉 미만, 32종목 스킵됨)
- [x] 지표값 검증: 독립 구현(`ta` 라이브러리)과 대조 — MACD/BB 완전 일치, RSI 오차 <0.06
- [x] 지표 단위 테스트 (StockCharts 공식 예제값 대조 포함)

### 1-C. 다이버전스 (핵심)

- [x] 피벗 탐지 (좌우 lookback, `config.py`로 분리)
- [x] Regular/Hidden bullish/bearish 4종 판정
- [x] 판정 근거(피벗 날짜·값 쌍) 저장 → 차트 마킹에 사용
- [x] 합성 데이터 단위 테스트 (4종 + 경계 케이스)
- [ ] 실사례 백테스트: 알려진 다이버전스 사례 3건 이상으로 파라미터(PIVOT_LEFT/RIGHT, DIV_RECENT_BARS) 튜닝
- [ ] 삼성전자 차트 마킹 결과 눈으로 재검토 후 파라미터 확정

### 1-D. 산출

- [x] `signals/latest.json` (전 종목, 864KB)
- [x] `chart/{code}.json` (종목별 250일 + 다이버전스, 총 ~62MB)
- [x] `python -m batch.run` 진입점 (전 종목 계산 12초)
- [x] JSON 크기 확인

## Phase 2 — 웹 MVP

- [x] Next.js(App Router, TS) 셋업
- [x] 공통 레이아웃: 헤더/푸터, 전일 기준 고지, 면책 문구, 광고 슬롯 자리
- [x] 스크리너: 12종 플래그 체크박스(그룹핑) + AND 필터 + 결과 테이블 + 정렬
- [x] URL 동기화 `/screen?flags=...` + 동적 SEO 메타태그
- [x] 종목 상세 `/stock/[code]` SSG + lightweight-charts (캔들+BB, 거래량, RSI, MACD 4패널, 다이버전스 마커)
- [x] 지표 가이드 페이지 초안 (`/guide`)
- [x] 모바일 레이아웃 (테이블 가로 스크롤)
- [ ] 종목 검색 (이름/코드) — 헤더 검색창
- [ ] 주요 필터 조합 정적 페이지 5~10개 (SEO)
- [ ] 👤 Vercel 계정 연결 + 첫 배포 (`*.vercel.app`)

## Phase 3 — 자동화

- [x] GitHub Actions 워크플로 작성 (`daily-batch.yml`: KST 22시 + 익일 9시 재시도, 캐시, 신선도 검사, data 브랜치 push, Deploy Hook)
- [ ] 👤 GitHub 저장소 생성 + push — **[SETUP_GUIDE.md](SETUP_GUIDE.md) A단계**
- [ ] 👤 GitHub Secrets 등록: `DATA_GO_KR_API_KEY` — 가이드 A-4 (Deploy Hook은 불필요해짐 — Vercel 자동 배포 사용)
- [ ] 👤 Vercel 프로젝트 생성(Root Directory=`web`) + Production Branch를 `data`로 — 가이드 B단계
- [ ] Supabase 이력 적재 (선택 — MVP에는 불필요, 이력 API 필요해질 때):
  - [ ] 👤 Supabase 프로젝트 생성
  - [ ] `ohlcv`/`indicators` 테이블 DDL + 배치 upsert
- [ ] workflow_dispatch로 수동 1회 실행 검증
- [ ] 2~3일 연속 무개입 자동 갱신 확인

## Phase 4 — 공개 준비

- [ ] 콘텐츠 페이지 확장: RSI/MACD/BB/다이버전스 각 1페이지 (애드센스 대비)
- [ ] SEO: sitemap.xml, robots.txt, OG 이미지
- [ ] 👤 카카오 애드핏 신청 → 광고 슬롯 연결
- [ ] 👤 증권사 계좌개설 CPA 제휴 신청 → 배너 적용
- [ ] 👤 도메인 구매 + Vercel 연결
- [ ] 면책·지연시세 고지 최종 점검, 공개
- [ ] 👤 (공개 후) 애드센스 신청
