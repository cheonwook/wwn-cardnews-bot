# 📰 해외 이슈 카드뉴스 자동화 봇

해외 인스타그램의 화제 게시물(좋아요 5천+)을 8시간마다 찾아서 **GitHub 알림**으로 보내줍니다.
내가 댓글로 고르고 생각을 적으면, 한국어 카드뉴스를 만들어 **인스타그램에 자동 발행**합니다.

```
[8시간마다] Topic Scout ─▶ GitHub Issue (후보 3개, 휴대폰 푸시)
                                   │
           나: "/approve 2  내 생각: ..." 댓글
                                   ▼
  번역·재구성(OpenAI) ─▶ AI 표지 이미지 ─▶ 카드 7장 렌더링 ─▶ 미리보기 댓글
                                   │
                         나: "/publish" 댓글
                                   ▼
                     인스타그램 캐러셀 발행 ✅ (Issue 자동 종료)
```

하루 3번 알림이 오고, 알림마다 1개씩 고르면 하루 3개를 발행하게 됩니다.

---

## 1. 준비물

| 항목 | 용도 |
|---|---|
| GitHub 계정 | 리포지토리, Actions(무료), 알림 |
| 인스타그램 **비즈니스/크리에이터** 계정 + 연결된 **Facebook 페이지** | 후보 검색과 발행 API |
| Meta 개발자 앱 | Instagram Graph API 토큰 |
| OpenAI API 키 | 번역, 원고, 이미지 생성 |

## 2. 설치 순서

### ① GitHub 리포 만들기
1. 새 리포지토리를 만들고 이 폴더의 파일을 모두 올립니다. `.github` 폴더도 포함해야 합니다.
2. **Public 리포를 권장합니다.** 인스타그램 서버가 카드 이미지를 가져가려면 공개 URL이 필요하기 때문입니다.
   - Private으로 두려면 [imgbb](https://api.imgbb.com/)에서 무료 키를 발급받고, `config.yaml`의 `image_host: "imgbb"`로 바꾼 뒤 `IMGBB_API_KEY` Secret을 추가하세요.
3. **Settings → Actions → General → Workflow permissions**를 **Read and write permissions**로 설정합니다.

### ② 인스타그램 / Meta 설정
1. 인스타그램 앱에서 **프로페셔널 계정(비즈니스 또는 크리에이터)**으로 전환하고, Facebook 페이지와 연결합니다.
2. [developers.facebook.com](https://developers.facebook.com)에서 앱을 만듭니다(유형: Business). **Instagram API (Facebook 로그인 방식)** 제품을 추가하세요.
3. 다음 권한을 요청합니다: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`
4. **토큰 발급 방법**은 두 가지입니다.
   - 권장: Meta 비즈니스 설정 → 시스템 사용자 → 토큰 생성. **만료되지 않습니다.**
   - 간단한 방법: [Graph API 탐색기](https://developers.facebook.com/tools/explorer)에서 사용자 토큰을 받아 장기 토큰으로 교환합니다. 60일마다 갱신해야 합니다.
5. **IG_USER_ID 확인:** 탐색기에서 `me/accounts?fields=instagram_business_account`를 실행하면 나오는 숫자 ID입니다.

> ⚠️ **해시태그 검색**을 쓰려면 Meta 앱 심사에서 *Instagram Public Content Access* 기능 승인이 필요할 수 있습니다.
> 승인 전에는 해시태그 조회만 실패하고 **계정 감시(Business Discovery)는 그대로 동작**합니다. 실패 내역은 알림 Issue 하단에 접힌 채로 표시됩니다.

### ③ GitHub Secrets 등록
리포의 **Settings → Secrets and variables → Actions → New repository secret**에서 등록합니다.

| 이름 | 값 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `IG_USER_ID` | 위에서 확인한 인스타 비즈니스 계정 ID |
| `IG_ACCESS_TOKEN` | Meta 액세스 토큰 |
| `IMGBB_API_KEY` | (imgbb를 쓸 때만) |

### ④ 알림 받기
- 리포 상단의 **Watch → All Activity**를 선택합니다.
- 휴대폰에 **GitHub 모바일 앱**을 설치하고 알림을 켜면 푸시 알림을 받을 수 있습니다. Issue 본문에서 나를 @멘션하므로 이메일로도 옵니다.

### ⑤ 테스트
**Actions 탭 → Topic Scout → Run workflow**로 바로 한 번 실행해 보세요. 몇 분 뒤 Issue가 생기면 성공입니다.

---

## 3. 사용법 (Issue 댓글 명령)

```
/approve 2
내 생각:
결국 우리 대출 이자에도 영향이 올 것 같아요.
금리 뉴스는 내 통장 얘기라는 걸 다시 느낍니다.
```

| 명령 | 동작 |
|---|---|
| `/approve 번호` + `내 생각:` | 원고를 만들고 AI 이미지를 생성해 카드를 렌더링한 뒤 **미리보기 댓글**을 답니다 |
| `이미지: 원본` 줄 추가 | AI 생성 대신 원본 게시물 이미지를 표지에 사용합니다 (아래 주의사항 참고) |
| `/publish` | 미리보기한 초안을 인스타그램에 발행하고 Issue를 닫습니다 |
| `/publish force` | 하루 목표 개수를 넘었어도 발행합니다 |
| `/approve 번호` 다시 입력 | 생각을 고쳐서 초안을 새로 만듭니다 |
| `/skip` | 이번 후보를 건너뛰고 Issue를 닫습니다 |

명령은 **리포 주인이 단 댓글에만** 반응합니다.

미리보기 없이 바로 발행하려면 `config.yaml`에서 `require_preview: false`로 바꾸세요.

## 3-1. 반자동 모드 (인스타 연결 전에도 사용 가능)

1. 리포의 **Issues → New issue → 📝 카드뉴스 직접 만들기** 를 선택
2. 원문 링크·계정·카테고리, **원문 내용**(캡션/기사 붙여넣기, 영어 OK), **내 생각**을 입력하고 Submit
3. 3~5분 뒤 미리보기 이미지 7장과 캡션이 댓글로 달려요
4. 이미지를 저장(또는 댓글의 링크에서 압축 파일로 한 번에 받기)해서 인스타그램/Meta Business Suite 에 직접 올리기

- 내용 수정: Issue 본문을 Edit 한 뒤 `/redo` 댓글
- 인스타 연결 후에는 같은 Issue 에서 `/publish` 로 자동 발행
- 표지 이미지 주소를 넣으면 그 이미지를, 비우면 AI 이미지를 사용

## 4. 카드뉴스 구성 (기본 7장, 1080×1350)

1. **표지**: AI 이미지, 카테고리 태그, 제목, 부제
2. **본문 4장**: 소제목, 본문, 핵심 구절 형광펜 강조
3. **에디터의 시선**: 내가 쓴 생각을 맞춤법과 흐름만 다듬어서 넣습니다
4. **출처**: 원문 계정·링크, 번역·AI 이미지 고지, 저장/팔로우 유도

디자인: 사진이 위에서 검정으로 녹아드는 풀블리드 표지, 로고 구분선, 굵은 압축형 제목(Black Han Sans + Anton)
- 제목의 `[[강조]]` 부분은 강조색으로 표시 (AI가 자동으로 핵심어 2~3곳 지정)
- 강조색: `config.yaml` 의 `brand.accent` (기본 #4A90FF)
- 실제 로고를 쓰려면 정사각형 PNG를 `templates/logo.png` 로 넣으세요 (없으면 'WWN' 글자 배지)

- 디자인 수정: `templates/card.html.j2`
- 색상 수정: `bot/render.py`의 `CATEGORY_STYLE`
- 로컬에서 API 키 없이 미리보기:
  ```bash
  pip install -r requirements.txt && python -m playwright install chromium
  python scripts/preview_template.py 정치     # → preview/slide_XX.jpg
  ```

## 5. 자주 바꾸는 설정 (`config.yaml`)

- `brand.handle`, `brand.name`: **내 계정명과 브랜드명으로 꼭 바꾸세요**
- `scout.accounts`, `scout.hashtags`: 감시할 해외 계정과 해시태그
  - 감시 대상은 비즈니스/크리에이터 계정이어야 합니다
- `scout.min_likes`, `scout.max_age_hours`: 후보 기준
- `ai.text_model`, `ai.image_model`: OpenAI 모델명. 새 모델이 나오면 여기만 바꾸면 됩니다
- **알림 시간**: `.github/workflows/scout.yml`의 cron (UTC 기준)
  - 기본값은 한국 시간 12:07 / 20:07 / 04:07입니다

## 6. 꼭 알아둘 점

- **저작권**
  - 원본 사진을 그대로 재게시하면 신고로 게시물이 삭제되거나 계정이 제재될 수 있습니다. 그래서 기본값을 AI 이미지로 두었고, 출처는 항상 표기됩니다.
  - AI 이미지 프롬프트에서는 실존 인물의 얼굴, 로고, 글자를 제외합니다.
- **정확성**
  - 원고는 원문 캡션에 있는 사실만 쓰도록 지시되어 있습니다. 그래도 정치·경제 뉴스는 **미리보기에서 숫자와 이름을 한 번 확인**하는 것을 권장합니다.
- **API 한도**
  - 인스타 발행 API는 24시간에 수십 건까지 허용되므로, 하루 3개는 여유가 있습니다.
  - 해시태그 검색은 7일 동안 서로 다른 해시태그 30개까지 가능합니다.
- **비용 (대략)**
  - GitHub Actions: Public 리포는 무료
  - OpenAI: 게시물 1개당 텍스트 소액 + 이미지 1장 (모델과 품질 설정에 따라 다름)
- **토큰 만료**
  - 60일 토큰을 쓰는 경우 만료되면 발행이 실패하고 Issue에 오류 댓글이 달립니다.
  - 시스템 사용자 토큰을 쓰면 신경 쓸 필요가 없습니다.

## 파일 구조

```
config.yaml                설정
bot/scout.py               후보 수집 → Issue 알림
bot/approve.py             댓글 명령 처리 (approve/publish/skip)
bot/instagram.py           Graph API (검색·발행)
bot/ai.py                  OpenAI 번역·원고·이미지
bot/render.py              템플릿 → JPEG
bot/hosting.py             이미지 공개 URL 업로드
templates/card.html.j2     카드뉴스 템플릿
.github/workflows/         scout.yml(8시간마다), approve.yml(댓글 반응)
state/                     중복 방지·발행 기록 (봇이 자동 커밋)
posts/                     생성된 카드 이미지 (봇이 자동 커밋)
```
