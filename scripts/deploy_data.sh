#!/bin/bash
# 수동 배포 스크립트 — 항상 "최신 수집 → 전체 재산출 → 백테스트 → data 브랜치 push" 순서로 실행한다.
#
# 왜 필요한가: 산출물만 손으로 push하면 로컬의 묵은 데이터가 크론이 배포한 최신
# 데이터를 덮어쓰는 사고가 난다 (2026-07-22/23 두 차례 발생). 수동 배포는 반드시
# 이 스크립트로만 할 것.
#
# 사용: ./scripts/deploy_data.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[1/4] 최신 시세 수집 + 전체 재산출"
.venv/bin/python -m batch.run

echo "[2/4] 백테스트 통계 + 클라이언트 데이터셋"
.venv/bin/python -m batch.backtest.run
.venv/bin/python -m batch.backtest.dataset

echo "[3/4] data 브랜치 구성"
WT=$(mktemp -d)/data-wt
git worktree add -q "$WT" -B data-push main
rm -rf "$WT/.github"
rsync -a --delete web/public/data/ "$WT/web/public/data/"
cd "$WT"
git add -A && git add -f web/public/data
DATE=$(python3 -c "import json;print(json.load(open('web/public/data/signals/latest.json'))['date'])")
git -c core.hooksPath=/dev/null commit -q -m "data: $DATE (수동 배포)"

echo "[4/4] push (Vercel 자동 배포 트리거)"
git push -f origin HEAD:data
cd - > /dev/null
git worktree remove -f "$WT"
echo "완료: data $DATE"
