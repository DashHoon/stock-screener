# 국내주식 기술적 지표 스크리너

국내주식 전 종목(~2,500개)의 RSI 다이버전스 / MACD / 볼린저밴드 시그널을
하루 1회 배치로 계산하고, 조건 조합으로 스크리닝하는 웹 서비스.
하루 지연 시세 기반, 상시 서버 없음(배치 + 정적 서빙).

- 계획서: [PLAN.md](PLAN.md) · 할 일: [TODO.md](TODO.md) · 스펙: [CLAUDE.md](CLAUDE.md)

## 구조

```
batch/            Python 배치 (수집 → 지표/시그널 계산 → JSON 산출)
web/              Next.js SSG (스크리너 + 종목 차트)
web/public/data/  배치 산출물 (gitignore, 배치 실행으로 재생성)
.github/workflows/daily-batch.yml  일별 자동화 (Actions)
```

## 개발 환경

```bash
# 배치 (Python 3.12 + uv)
uv sync && uv pip install 'setuptools<81'   # setuptools<81: pykrx의 pkg_resources 의존
uv run pytest                                # 단위 테스트
uv run python -m batch.run --backfill        # 최초 1회: 전 종목 2년 백필 (~8분)
uv run python -m batch.run                   # 일별: 수집 갱신 + 계산 + JSON 산출
uv run python -m batch.run --no-collect      # 캐시 그대로 계산·산출만

# 웹
cd web && npm install && npm run dev
```

## 데이터 소스

- 일별: 공공데이터포털 금융위원회_주식시세정보 (`DATA_GO_KR_API_KEY` 필요,
  없으면 FinanceDataReader 증분 수집으로 폴백)
- 백필/종목 마스터: FinanceDataReader (pykrx의 종목 목록 API는 2026-07 현재
  KRX 엔드포인트 변경으로 빈 값을 반환해 사용하지 않음)

## 면책

본 프로젝트가 제공하는 모든 정보는 참고용이며 투자 조언이 아닙니다.
