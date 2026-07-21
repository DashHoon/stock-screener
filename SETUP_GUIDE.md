# 배포 셋업 가이드 — GitHub · Vercel 처음 하는 분용

이 문서만 따라 하면 됩니다. 전체 소요시간 약 20~30분.
막히면 어느 단계 몇 번에서 막혔는지 화면 내용과 함께 알려주세요.

## 전체 그림 (왜 이걸 하는가)

```
[내 컴퓨터] ──push──> [GitHub 저장소]
                          │
                          ├─ GitHub Actions: 매일 밤 자동으로 배치 실행
                          │   └─ 산출 데이터를 "data" 브랜치에 저장
                          │
                          └──감지──> [Vercel] data 브랜치가 바뀔 때마다
                                      사이트를 다시 빌드해서 공개
```

- **GitHub** = 코드 보관 + 매일 밤 배치를 대신 돌려주는 무료 서버
- **Vercel** = 완성된 사이트를 인터넷에 공개해주는 무료 호스팅

---

# A. GitHub에서 할 일

## A-1. 저장소(repository) 만들기

1. https://github.com 로그인 (계정 없으면 Sign up)
2. 우측 상단 **`+`** 버튼 → **New repository**
3. 다음과 같이 입력:
   - **Repository name**: `stock-screener` (원하는 이름 아무거나)
   - **Public / Private**: **Public 권장** — Public이면 GitHub Actions가 무제한 무료입니다.
     (Private도 월 2,000분 무료라 동작은 하지만, 코드에 비밀정보가 없으므로 Public이 이득)
   - ⚠️ **"Add a README file", ".gitignore", "license" 는 전부 체크하지 마세요.**
     (이미 내 컴퓨터에 코드가 있어서, 빈 저장소여야 충돌 없이 올라갑니다)
4. **Create repository** 클릭
5. 생성 직후 나오는 페이지의 주소를 복사해 두세요.
   `https://github.com/<내아이디>/stock-screener.git` 형태입니다.

## A-2. 인증 토큰(PAT) 만들기 — push할 때 비밀번호 대신 사용

GitHub는 비밀번호로 push할 수 없고 토큰이 필요합니다.

1. GitHub 우측 상단 프로필 사진 → **Settings**
2. 왼쪽 맨 아래 **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
3. 입력:
   - **Token name**: `stock-screener-push` (아무거나)
   - **Expiration**: 90 days (만료되면 다시 만들면 됩니다)
   - **Repository access**: "Only select repositories" → 방금 만든 저장소 선택
   - **Permissions** → Repository permissions → **Contents**를 **Read and write**로
4. **Generate token** → 나온 토큰 문자열(`github_pat_...`)을 복사해 메모장에 잠깐 보관
   ⚠️ 이 화면을 벗어나면 다시 볼 수 없습니다. 잃어버리면 새로 만들면 됩니다.

## A-3. 코드 올리기 (push)

터미널을 열고 아래를 한 줄씩 실행하세요. (`<내아이디>`는 본인 것으로 바꾸기)

```bash
cd /Volumes/WorkDrive/WebService/StockScreener
git remote add origin https://github.com/<내아이디>/stock-screener.git
git push -u origin main
```

- Username 물으면: GitHub 아이디 입력
- **Password 물으면: 비밀번호가 아니라 A-2에서 만든 토큰을 붙여넣기**

성공하면 GitHub 저장소 페이지를 새로고침했을 때 `batch/`, `web/` 등 폴더가 보입니다.

> 💡 이 단계는 Claude에게 맡길 수도 있습니다: 터미널에서 `brew install gh` 후
> `gh auth login` (브라우저 로그인)만 해주시면, 이후 push·저장소 관리를 대신 할 수 있습니다.

> ✅ 안심 포인트: API 키가 든 `.env` 파일은 `.gitignore`에 등록돼 있어 **절대 올라가지 않습니다.**

## A-4. 비밀 키(Secret) 등록 — 배치가 공공 API를 쓸 수 있게

1. GitHub 저장소 페이지 → 상단 **Settings** 탭
2. 왼쪽 메뉴 **Secrets and variables** → **Actions**
3. **New repository secret** 클릭:
   - **Name**: `DATA_GO_KR_API_KEY` (정확히 이대로, 대문자·언더스코어)
   - **Secret**: 공공데이터포털 인증키 (내 컴퓨터 `.env` 파일 안에 있는 값)
4. **Add secret**

`VERCEL_DEPLOY_HOOK_URL`은 **등록하지 않아도 됩니다** — Vercel이 데이터 변경을 자동 감지하도록 설정할 것이라 필요 없습니다.

## A-5. Actions 켜져 있는지 확인

저장소 상단 **Actions** 탭 클릭 → "daily-batch"라는 워크플로가 보이면 정상입니다.
(버튼으로 활성화하라고 나오면 활성화를 눌러주세요. 아직 실행은 하지 마세요 — Vercel 설정 후 같이 합니다.)

---

# B. Vercel에서 할 일

## B-1. 가입 + GitHub 연동

1. https://vercel.com → **Sign Up**
2. **"Continue with GitHub"** 선택 ← 중요. 이걸로 가입해야 GitHub 연동이 자동으로 됩니다
3. 플랜은 **Hobby (무료)** 선택. 개인 이름 입력하는 정도만 물어봅니다

## B-2. 프로젝트 만들기 (저장소 가져오기)

1. Vercel 대시보드 → **Add New...** → **Project**
2. "Import Git Repository" 목록에 `stock-screener`가 보이면 **Import**
   - 안 보이면: **Adjust GitHub App Permissions** 클릭 → GitHub 화면에서 해당 저장소 접근 허용
3. 설정 화면에서 **딱 하나만 바꿉니다**:
   - **Root Directory**: `Edit` 버튼 클릭 → `web` 선택 (또는 입력)
     ← 우리 저장소는 사이트 코드가 `web/` 폴더 안에 있기 때문
   - Framework Preset이 "Next.js"로 자동 인식되는지만 확인 (그 외 설정 손대지 않기)
4. **Deploy** 클릭 → 1~3분 기다림

> ⚠️ 이 첫 배포는 **데이터가 없는 상태**라 사이트가 뜨긴 해도 "데이터 로드 실패"로
> 보이고 종목 페이지도 없습니다. **정상입니다.** C단계에서 데이터가 들어오면 해결됩니다.

## B-3. 배포 기준 브랜치를 `data`로 바꾸기 ← 가장 중요한 설정

배치가 매일 밤 데이터를 `data` 브랜치에 넣기 때문에, Vercel이 그 브랜치를 바라봐야 합니다.

1. 방금 만든 프로젝트 → 상단 **Settings** 탭
2. 왼쪽 메뉴 **Git** (화면에 따라 **Environments → Production**일 수 있음)
3. **Production Branch** 항목을 `main` → **`data`** 로 변경, 저장

## B-4. 사이트 주소 확인

프로젝트 첫 화면(Overview)에 `https://stock-screener-xxxx.vercel.app` 형태의 주소가 있습니다.
이게 서비스 주소입니다 (나중에 도메인을 사면 여기에 연결).

---

# C. 첫 실행 — 전체 파이프라인 검증

여기부터는 Claude와 같이 하는 게 좋습니다. **A, B가 끝나면 알려주세요.**
직접 하려면:

1. GitHub 저장소 → **Actions** 탭 → 왼쪽 **daily-batch** → 오른쪽 **Run workflow** 버튼
   → 옵션 그대로(rebuild 체크 안 함) → 초록색 **Run workflow**
2. 10~20분 대기 (첫 실행은 전 종목 수집 때문에 오래 걸림). 초록 체크 표시가 뜨면 성공
3. 저장소 브랜치 목록에 **`data`** 브랜치가 새로 생겼는지 확인
4. Vercel이 자동으로 새 배포를 시작합니다 (Vercel 프로젝트 → Deployments에서 진행 확인)
5. 사이트 주소 접속 → 스크리너에 2,500여 종목이 뜨면 **완성** 🎉

이후에는 손댈 것 없이 평일 밤 10시(+ 오전 재시도)와 토요일 새벽(전체 보정)에 자동으로 돌아갑니다.

---

# 문제가 생기면

| 증상 | 원인/해결 |
|---|---|
| push 시 "Authentication failed" | 비밀번호 대신 **토큰**(A-2)을 넣었는지 확인 |
| push 시 "repository not found" | 주소의 아이디/저장소명 오타, 또는 토큰의 Repository access에 저장소 미포함 |
| Actions 실행이 빨간 X | 실행 로그 화면을 열어 어느 단계인지 확인 → Claude에게 로그 공유 |
| Vercel 빌드 실패 | Root Directory가 `web`인지 확인 (B-2) |
| 사이트에 "데이터 로드 실패" | 아직 C를 안 했거나, Production Branch가 `data`가 아님 (B-3) |
| Secret 이름 헷갈림 | `DATA_GO_KR_API_KEY` — 복사해서 붙여넣기 권장 |
