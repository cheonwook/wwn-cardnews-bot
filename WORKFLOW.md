# WWN 카드뉴스 작업 가이드 (Claude용)

새 대화에서 "이 리포의 WORKFLOW.md 읽고 진행해줘 + 인스타 링크"를 받으면 이 문서대로 진행한다.

## 현재 상태
- 리포: `cheonwook/wwn-cardnews-bot` (Public). 인스타 계정 @wwn.daily
- 디자인·말투·캡션 규칙은 코드(`bot/ai.py`, `templates/card.html.j2`)와 `config.yaml`에 이미 들어 있다. 사용자가 바꾸라고 할 때만 수정한다.
- 인스타 API 토큰은 아직 미등록이다. Topic Scout 워크플로는 꺼두었고, 지금은 **반자동**(Issue → 미리보기 → 사용자가 직접 업로드)으로만 운영한다.

## 진행 순서

### 0. 원문 읽고 요약 먼저
1. 오른쪽 내장 브라우저로 링크를 연다. 인스타는 일반 웹 요청(WebFetch, curl)이 막혀 있다.
   - 브라우저 도구가 안 보이면 ToolSearch 로 `Claude_Browser` 를 검색해 불러온다.
   - 사이트 허용이 필요하면 `request_access` 를 `https://instagram.com` 범위로 호출한다.
   - 로그인 팝업이 뜨면 닫기(X)를 누른다.
2. 캡션 텍스트는 `get_page_text` 로 읽는다. 캐러셀은 다음 화살표를 누르며 장별로 확인한다. 각 장이 글 카드인지 사진만인지, 첫 장에 글자가 박혀 있는지 본다.
3. 사용자에게 아래를 보여준다.
   - 한국어 요약 3~4줄
   - 사진 설명 (장별 한 줄)
   - 생각해볼 질문 1~2개
   그리고 **내 생각 한 줄**을 받는다. 사용자가 링크와 생각을 같이 보냈으면 이 단계는 건너뛴다.
   - 사용자의 생각을 대신 지어내지 않는다. "생각 없음"이면 비워둔다.

### 1. 사실 확인
- 부고, 사건, 숫자가 들어간 주장은 웹 검색으로 확인한다.
- 오래된 이야기면(예: 2018년 사건) 시점을 사용자에게 알리고, 원문 내용에 `[Verified: ...]` 한 줄로 덧붙인다.

### 2. 형식과 이미지 정하기
- 원문이 사진 위주면 **사진만**, 글 카드면 **텍스트 카드**로 한다.
- 원문 사진을 쓴다. 캐러셀 각 장의 원본 주소(2048px)를 브라우저 JS로 모은다. 장을 넘길 때마다 아래를 실행해서 누적한다.
  ```js
  window.__wwn = window.__wwn || {};
  const pick = i => { const s=(i.srcset||'').split(',').map(x=>x.trim().split(' ')).filter(a=>a[0]);
    s.sort((a,b)=>parseInt(b[1])-parseInt(a[1])); return s.length?s[0][0]:i.src; };
  for (const i of document.querySelectorAll('img')) if (i.naturalWidth>=1000)
    window.__wwn[pick(i).split('?')[0]] ??= pick(i);
  Object.values(window.__wwn)
  ```
  - 어떤 주소가 몇 번째 장인지 헷갈리면 이미지를 페이지에 작게 띄워 확인한다.
  - 클라우드 작업 공간에서는 인스타 이미지(cdninstagram)를 내려받을 수 없다. 확인은 브라우저 안에서 한다.
- **표지 이미지 주소** = 원문 1장(글자가 박혀 있어도 그대로 넣는다. 봇이 AI로 글자만 지우고 사진 전체를 살린다).
  **본문 사진 주소** = 나머지 장 전부 (한 줄에 하나, 원문 순서대로).
  - **텍스트 카드**여도 반드시 넣는다. 봇이 원문 사진을 각 카드의 배경으로 쓰고, 장수가 적으면 원문 흐름에 맞게 고르게 골라 쓴다. 글자가 박혀 있으면 지운다.
  - 이 주소가 없으면 텍스트 카드 배경이 전부 표지 사진의 반복이 된다.
- 원문 사진이 없거나 쓰기 어려우면 비워둔다. 그러면 AI 이미지가 만들어진다(실존 인물·캐릭터는 넣지 않는다).

### 3. Issue 만들기
`.github/ISSUE_TEMPLATE/manual-card.yml` 양식과 같은 형식의 본문으로 `gh api` 를 써서 만든다.

```
### 원문 링크

https://www.instagram.com/p/XXXX/

### 원문 계정

@계정

### 카테고리

시사 | 정치 | 경제 | 사회 | 연예 중 하나

### 원문 내용

```text
(캡션 원문 그대로 + 필요하면 [Verified: ...])
```

### 본문 형식

사진만 | 텍스트 카드

### 내 생각

(사용자가 보낸 한 줄 그대로)

### 표지 이미지 주소

https://...

### 본문 사진 주소

https://...
https://...
```

```bash
gh api repos/cheonwook/wwn-cardnews-bot/issues -f title="[카드뉴스] 한글 제목" -F body=@issue.md --jq .number
```

### 4. 결과 확인
- 3~6분 뒤 Issue에 `🖼️ 미리보기` 댓글이 달린다. 백그라운드로 기다린다(댓글 created_at 필터).
- `git pull` 뒤 `posts/<날짜>-issue<번호>-manual/slide_*.jpg` 를 모아 한 장으로 확인한 다음 사용자에게 보여준다.
- 수정은 Issue 본문을 고치고(`gh api -X PATCH ... -F body=@...`) `/redo` 댓글을 단다. 인스타 이미지 주소는 며칠 지나면 만료되니, 오래된 Issue를 다시 만들 때는 주소를 새로 넣는다.
- 사용자는 미리보기 댓글에서 이미지를 저장해 인스타 앱(모바일 권장, 음악 추가 가능)으로 올린다.

## 주의
- 리포를 고치는 중에 봇이 커밋하면 충돌할 수 있다. 수정 전 `git pull`, 봇 실행 중에는 가능하면 푸시를 피한다.
- 디자인 조절값은 `config.yaml` 에 있다: `cover.fade_start / max_dark / fill`, `brand.*`, `outro.*`, `ai.max_body_slides`.
