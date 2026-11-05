"""Topic Scout: 해외 화제 게시물 후보를 찾아 GitHub Issue 로 알림.

실행: python -m bot.scout   (GitHub Actions 에서 8시간마다)
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .ai import OpenAIClient
from .config import STATE_DIR, env, load_config, read_json, write_json
from .github_api import GitHub, git_commit_push
from .instagram import GraphError, InstagramClient, parse_ts

SEEN = STATE_DIR / "seen.json"
LABEL = "topic-scout"


def collect(ig: InstagramClient, cfg: dict) -> tuple[list[dict], list[str]]:
    sc = cfg["scout"]
    items, errors = [], []
    for category, users in (sc.get("accounts") or {}).items():
        for u in users:
            try:
                for m in ig.business_discovery(u):
                    m["category"] = category
                    items.append(m)
            except GraphError as e:
                errors.append(f"@{u}: {e}")
    for category, tags in (sc.get("hashtags") or {}).items():
        for t in tags:
            try:
                for m in ig.hashtag_top_media(t):
                    m["category"] = category
                    items.append(m)
            except GraphError as e:
                errors.append(f"#{t}: {e}")
    return items, errors


def select(items: list[dict], seen: set[str], cfg: dict) -> list[dict]:
    sc = cfg["scout"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=sc["max_age_hours"])
    pool, ids = [], set()
    for m in items:
        mid = m.get("id")
        if not mid or mid in seen or mid in ids:
            continue
        likes = m.get("like_count")  # 좋아요 숨김 게시물은 None
        if likes is None or likes < sc["min_likes"] or not m.get("caption"):
            continue
        if m.get("timestamp") and parse_ts(m["timestamp"]) < cutoff:
            continue
        m["score"] = likes + 3 * (m.get("comments_count") or 0)
        pool.append(m)
        ids.add(mid)
    pool.sort(key=lambda x: x["score"], reverse=True)

    n = sc["candidates_per_alert"]
    if not sc.get("prefer_distinct_categories"):
        return pool[:n]
    picked, cats = [], set()
    for m in pool:                      # 1차: 카테고리 겹치지 않게
        if m["category"] not in cats:
            picked.append(m); cats.add(m["category"])
        if len(picked) == n:
            return picked
    for m in pool:                      # 2차: 부족하면 점수순으로 채움
        if m not in picked:
            picked.append(m)
        if len(picked) == n:
            break
    return picked


def issue_body(cands: list[dict], owner: str, errors: list[str]) -> str:
    lines = [f"@{owner} 새 후보 {len(cands)}개가 도착했어요. 마음에 드는 번호로 댓글을 달아주세요.\n"]
    for i, c in enumerate(cands, 1):
        src = f"@{c['source_account']}" if c.get("source_account") else c["source_type"]
        lines += [
            f"### {i}. [{c['category']}] {c.get('title_ko') or '(제목 생성 실패)'}",
            f"> {c.get('summary_ko') or (c.get('caption') or '')[:160]}",
            "",
            f"❤️ {c['like_count']:,} · 💬 {c.get('comments_count') or 0:,} · {src} · [원문 보기]({c['permalink']})",
            "",
            "<details><summary>원문 캡션</summary>\n\n" + (c.get("caption") or "")[:1500].replace("\n", "  \n") + "\n</details>",
            "",
        ]
    lines += [
        "---",
        "**사용법** (댓글로 입력)",
        "```",
        "/approve 2",
        "내 생각:",
        "여기에 내 생각이나 느낀 점을 자유롭게 적어주세요.",
        "```",
        "- 이미지를 원본으로 쓰려면 `이미지: 원본` 줄 추가 (기본은 AI 생성)",
        "- 패스하려면 `/skip`",
    ]
    if errors:
        lines += ["", "<details><summary>⚠️ 일부 소스 조회 실패</summary>\n\n" + "\n".join(f"- {e}" for e in errors[:20]) + "\n</details>"]
    payload = base64.b64encode(json.dumps(cands, ensure_ascii=False).encode()).decode()
    lines.append(f"\n<!-- CANDIDATES:{payload} -->")
    return "\n".join(lines)


def main():
    cfg = load_config()
    ig = InstagramClient(env("IG_USER_ID"), env("IG_ACCESS_TOKEN"), cfg["graph_api"]["version"])
    gh = GitHub()

    seen_list = read_json(SEEN, [])
    items, errors = collect(ig, cfg)
    print(f"수집 {len(items)}건, 오류 {len(errors)}건")
    cands = select(items, set(seen_list), cfg)
    if not cands:
        print("기준을 넘는 새 후보가 없습니다.")
        return

    keep = ("id", "caption", "like_count", "comments_count", "media_type", "media_url",
            "permalink", "timestamp", "source_account", "source_type", "category")
    cands = [{k: c.get(k) for k in keep} for c in cands]
    try:
        ai = OpenAIClient(env("OPENAI_API_KEY"), cfg["ai"]["text_model"], cfg["ai"]["image_model"])
        for s in ai.summarize_candidates(cands):
            c = cands[int(s["i"])]
            c["title_ko"], c["summary_ko"] = s.get("title_ko"), s.get("summary_ko")
            if s.get("category") in ("정치", "연예", "시사", "사회", "경제"):
                c["category"] = s["category"]
    except Exception as e:  # 요약 실패해도 알림은 보냄
        errors.append(f"AI 요약 실패: {e}")

    now = datetime.now(ZoneInfo(cfg["publish"]["timezone"]))
    gh.ensure_label(LABEL, "1f6feb", "Topic Scout 후보")
    issue = gh.create_issue(f"🔎 Topic Scout {now:%m/%d %H:%M} — " + " / ".join(c["category"] for c in cands),
                            issue_body(cands, gh.owner, errors), [LABEL])
    print("Issue:", issue["html_url"])

    seen_list = (seen_list + [c["id"] for c in cands])[-2000:]
    write_json(SEEN, seen_list)
    git_commit_push("scout: mark candidates as seen", ["state/seen.json"])


if __name__ == "__main__":
    main()
