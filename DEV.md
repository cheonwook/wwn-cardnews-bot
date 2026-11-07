# 개발 가이드 (봇 코드·디자인을 고치는 대화용)

새 대화에서 "이 리포의 DEV.md 와 BACKLOG.md 읽고 ○○ 작업해줘"로 시작한다. 카드뉴스 제작만 할 때는 WORKFLOW.md 를 본다.

## 전체 흐름
```
Issue 양식(📝 카드뉴스 직접 만들기)
 └ .github/workflows/manual.yml → bot/manual.py (양식 파싱)
     └ bot/approve.py make_draft()
         1) 원문 사진 다운로드 → bot/cleanimg.py clean_and_read() : 박힌 글자 읽기 + 지우기 (병렬 4개)
         2) bot/ai.py build_cardnews() : 원고 JSON (텍스트 카드 + 원문 사진이면 원문 장과 1:1)
         3) 이미지 배치 → bot/render.py → templates/card.html.j2 → Playwright 로 2048x2560 JPEG
         4) bot/hosting.py : posts/ 에 커밋 → raw.githubusercontent URL
     └ Issue 에 미리보기 댓글. /redo = 다시 만들기, /publish = 인스타 발행(approve.yml, 토큰 필요)
Topic Scout (scout.yml, bot/scout.py) : 8시간마다 후보 검색. 인스타 토큰 미등록이라 꺼둠
```

## 파일 지도
| 파일 | 역할 |
|---|---|
| `config.yaml` | 브랜드, 표지 어두움(cover.*), 마무리 카드(outro.*), 장수 상한(ai.max_body_slides*), 모델명 |
| `bot/ai.py` | OpenAI 원고 프롬프트, 이미지 생성, 글자 영역 읽기(read_overlay), 글자 지우기(edit_image) |
| `bot/cleanimg.py` | 글자 띠 잘라내기(crop) / AI로 지우고 원본에 합성(inpaint). 얼굴 위 글자는 건드리지 않음 |
| `bot/approve.py` | 초안 만들기 전체 순서, 캡션 조립, 발행 |
| `bot/manual.py` | Issue 양식 파싱 (꼬리말·백틱 제거) |
| `bot/render.py` | 템플릿 컨텍스트, 표지 사진 비율 처리(cover_h), 출력 해상도(OUTPUT_WIDTH) |
| `templates/card.html.j2` | 카드 디자인 전부 (표지 / 텍스트 카드 / 사진만 / 마무리 4종) |
| `scripts/preview_template.py` | API 키 없이 로컬 미리보기 |

## 확정된 디자인 결정 (바꾸자고 하기 전까지 유지)
- 1080x1350 레이아웃을 2048x2560 으로 출력 (원문과 같은 해상도)
- 상단: 왼쪽 로고 + WORLD WIDE NEWS, 오른쪽 @wwn.daily. 카테고리 표시·페이지 번호·카드별 출처 없음
- 표지: 원문 표지 글자는 AI로 지우고 사진 전체 사용. 어두움 fade_start 62 / max_dark 0.97 / fill black
- 본문: 텍스트 카드는 원문 사진 1:1 배경, 장수 = 원문 장수(최대 8). 원문 정보 없으면 1~3장
- 에디터의 시선 슬라이드 없음(내 생각은 캡션에만, 해요체 + 이모지 적당히)
- 마무리 카드: minimal (흐린 표지 배경 + 큰 로고 + "오늘의 세계, 3분이면 충분해요")
- 카드·캡션에 '원문/캡션/검증/~에 따르면' 같은 제작 과정 표현 금지
- 원본과 거의 똑같은 AI 이미지로 대체하지 않음, AI 이미지에 실존 인물·캐릭터 금지

## 시행착오로 알게 된 것
- 클라우드 작업 공간에서는 인스타 이미지(cdninstagram)를 못 받는다. 확인은 브라우저 안에서 하고, 다운로드는 Actions 가 한다
- 인스타 이미지 주소는 며칠 뒤 만료된다
- `gh api` 로 만든 본문·댓글에는 꼬리말과 백틱이 붙는다 → manual.py 가 제거
- 봇이 커밋하는 중에 푸시하면 충돌할 수 있다 → 수정 전 `git pull`, 봇 실행 중 푸시 자제 (github_api.py 에 재시도 있음)
- Actions 에서 Chromium 설치가 가끔 멈춘다 → 캐시 + 시간 제한 + 재시도 적용됨
- 가로로 넓은 사진은 표지에서 cover_h 로 위쪽 배치(좌우 살짝만 잘림)

## 테스트 방법
- 디자인: `python scripts/preview_template.py [카테고리] [표지경로]` → preview/
- 로직: OpenAI·GitHub·다운로드를 가짜 함수로 바꿔 `bot.manual.main()` 실행 (GITHUB_EVENT_PATH 에 Issue JSON)
- 실제 확인: 기존 Issue 에 `/redo` → 3~6분 후 미리보기
