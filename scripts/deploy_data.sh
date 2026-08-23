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

# [중요] 먼저 main을 origin에 push한다. 크론(daily-batch.yml)은 origin/main으로
# data 브랜치를 다시 빌드하므로, 로컬 main 커밋을 origin에 안 올리면 밤 크론이
# 옛 코드로 사이트를 덮어쓴다 (2026-07-25 발생). data만 push하면 이 사고가 난다.
# [중요] push 전에 타입 검사부터. 2026-08-23에 flags.ts에 시그널을 추가하면서
# types.ts의 FlagKey 유니온을 안 고쳤더니, data와 main은 올라갔는데 Vercel
# 빌드가 실패해 사이트는 옛 데이터를 그대로 서빙했다. 겉으로는 배포 성공처럼
# 보여서 알아채는 데 30분 걸렸다. tsc는 몇 초면 끝난다.
echo "[0/4] 웹 타입 검사"
(cd web && npx tsc --noEmit)

echo "[0] main → origin push (크론이 최신 코드로 빌드하도록)"
git push origin main

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
