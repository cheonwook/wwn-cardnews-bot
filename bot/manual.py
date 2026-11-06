"""반자동 모드: Issue 양식에 직접 넣은 원문으로 카드뉴스 만들기.

- '카드뉴스 직접 만들기' 양식으로 Issue 를 열면 실행
- 같은 Issue 에 `/redo` 댓글 → (본문을 고친 뒤) 다시 생성
- 인스타 연결 후에는 `/publish` 로 자동 발행 (approve.yml 이 처리)

실행: python -m bot.manual
"""
from __future__ import annotations

import json
import os
import re

from .approve import make_draft, preview_comment
from .config import env, load_config
from .github_api import GitHub

MARKER = "### 원문 내용"
FIELDS = {
    "원문 링크": "permalink",
    "원문 계정": "account",
    "카테고리": "category",
    "원문 내용": "caption",
    "내 생각": "my_take",
    "표지 이미지 주소": "image_url",
}


def parse_form(body: str) -> dict:
    """GitHub Issue 양식 본문(### 제목 + 값)을 dict 로."""
    out, key, buf = {}, None, []

    def flush():
        if key:
            val = "\n".join(buf).strip()
            val = re.sub(r"^```\w*\n?|\n?```$", "", val).strip()  # render: text 코드블록 제거
            out[key] = "" if val in ("_No response_", "None") else val

    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and m.group(1) in FIELDS:
            flush()
            key, buf = FIELDS[m.group(1)], []
        else:
            buf.append(line)
    flush()
    return out


def main():
    event = json.loads(open(env("GITHUB_EVENT_PATH"), encoding="utf-8").read())
    issue = event["issue"]
    comment = event.get("comment")
    if comment and not comment["body"].strip().lower().startswith("/redo"):
        return

    cfg = load_config()
    gh = GitHub()
    if comment:
        gh.react(comment["id"], "eyes")
    gh.ensure_label("manual-card", "5319e7", "반자동 카드뉴스")
    gh.add_labels(issue["number"], ["manual-card"])

    f = parse_form(issue["body"])
    if not f.get("caption"):
        gh.comment(issue["number"], "⚠️ '원문 내용'이 비어 있어요. Issue 본문을 수정한 뒤 `/redo` 를 입력하세요.")
        return

    account = (f.get("account") or "").strip().lstrip("@")
    category = f.get("category") if f.get("category") in ("정치", "경제", "사회", "연예", "시사") else "시사"
    cand = {
        "caption": f["caption"],
        "permalink": f.get("permalink", ""),
        "source_account": account or None,
        "source_type": "직접 입력",
        "category": category,
        "media_url": f.get("image_url") or None,
    }
    image_mode = "original" if cand["media_url"] else "ai"

    try:
        draft = make_draft(cfg, gh, issue["number"], cand, f.get("my_take", ""), image_mode, "manual")
        run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}"
        footer = (
            "**올리는 방법**\n"
            "1. 위 이미지를 하나씩 눌러 저장하거나, "
            f"[여기]({run_url})에서 맨 아래 **cardnews** 압축 파일을 한 번에 받으세요.\n"
            "2. 인스타그램(또는 Meta Business Suite 예약)에 순서대로 올리고 캡션을 붙여넣으세요.\n\n"
            "내용을 고치려면 Issue 본문을 수정(... → Edit)한 뒤 `/redo` 를 입력하세요."
        )
        if os.environ.get("IG_ACCESS_TOKEN"):
            footer += "\n인스타 자동 발행: `/publish`"
        preview_comment(gh, issue["number"], draft, footer)
        if gh_out := os.environ.get("GITHUB_OUTPUT"):
            with open(gh_out, "a", encoding="utf-8") as fh:
                fh.write(f"dir={draft['dir']}\n")
        if comment:
            gh.react(comment["id"], "rocket")
    except Exception as e:
        gh.comment(issue["number"], f"❌ 처리 중 오류가 났어요:\n```\n{str(e)[:1500]}\n```\nActions 로그에서 자세히 볼 수 있어요.")
        raise


if __name__ == "__main__":
    main()
