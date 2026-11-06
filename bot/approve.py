"""Issue 댓글 명령 처리: /approve N, /publish, /skip

실행: python -m bot.approve   (issue_comment 이벤트에서)
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from .ai import OpenAIClient
from .config import POSTS_DIR, ROOT, STATE_DIR, env, load_config, read_json, write_json
from .github_api import GitHub, git_commit_push
from .hosting import host_images
from .instagram import InstagramClient
from .render import build_context, render_slides

PUBLISHED = STATE_DIR / "published.json"


# ── 댓글 파싱 ─────────────────────────────────────────
def parse_command(body: str) -> dict:
    text = body.strip()
    first, _, rest = text.partition("\n")
    first = first.strip()
    if m := re.match(r"^/approve\s+(\d+)\s*(.*)$", first, re.I):
        image_mode = "ai"
        if re.search(r"^\s*이미지\s*[:：]\s*원본", rest, re.M):
            image_mode = "original"
        rest = re.sub(r"^\s*이미지\s*[:：].*$", "", rest, flags=re.M)
        take = rest
        if mm := re.search(r"내\s*생각\s*[:：]\s*(.*)", rest, re.S):
            take = mm.group(1)
        take = (m.group(2) + "\n" + take).strip()
        return {"cmd": "approve", "n": int(m.group(1)), "image_mode": image_mode, "my_take": take}
    if re.match(r"^/publish\b", first, re.I):
        return {"cmd": "publish", "force": "force" in first.lower()}
    if re.match(r"^/skip\b", first, re.I):
        return {"cmd": "skip"}
    return {"cmd": None}


def load_candidates(issue_body: str) -> list[dict]:
    m = re.search(r"<!-- CANDIDATES:([A-Za-z0-9+/=]+) -->", issue_body or "")
    if not m:
        raise SystemExit("이 Issue 에서 후보 데이터를 찾지 못했습니다.")
    return json.loads(base64.b64decode(m.group(1)))


def build_caption(copy: dict, cfg: dict) -> str:
    tags, seen = [], set()
    for t in list(copy.get("hashtags") or []) + cfg["publish"].get("default_hashtags", []):
        t = re.sub(r"[\s#]", "", str(t))
        if t and t.lower() not in seen:
            seen.add(t.lower()); tags.append("#" + t)
    tags = tags[:25]
    body = (copy.get("caption") or "").strip()
    tag_line = " ".join(tags)
    limit = 2200 - len(tag_line) - 2
    if len(body) > limit:
        body = body[: limit - 1] + "…"
    return f"{body}\n\n{tag_line}"


# ── 초안 만들기 (자동/반자동 공통) ───────────────────
def make_draft(cfg, gh: GitHub, number: int, cand: dict, my_take: str, image_mode: str, tag: str) -> dict:
    tz = cfg["publish"]["timezone"]
    out = POSTS_DIR / f"{datetime.now(ZoneInfo(tz)):%Y%m%d}-issue{number}-{tag}"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("slide_*.jpg"):  # /redo 시 이전 결과 정리
        old.unlink()

    ai = OpenAIClient(env("OPENAI_API_KEY"), cfg["ai"]["text_model"], cfg["ai"]["image_model"])
    max_slides = int(cfg["ai"].get("max_body_slides", cfg["ai"].get("body_slides", 3)))
    copy = ai.build_cardnews(cand, my_take, max_slides, cfg["brand"])
    copy["slides"] = [s for s in copy.get("slides", []) if s.get("body") or s.get("title")][:max_slides]
    if not copy["slides"]:
        raise RuntimeError("AI가 본문 슬라이드를 만들지 못했습니다. /redo 로 다시 시도하세요.")

    cover = out / "cover.jpg"
    ai_image = True
    if image_mode == "original" and cand.get("media_url") and cand.get("media_type") != "VIDEO":
        try:
            r = requests.get(cand["media_url"], timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            if not r.headers.get("content-type", "").startswith("image/"):
                raise ValueError("이미지 주소가 아닙니다")
            cover.write_bytes(r.content)
            ai_image = False
        except Exception as e:
            gh.comment(number, f"원본 이미지를 가져오지 못해 AI 이미지로 대체합니다. ({e})")
    if ai_image:
        cover.write_bytes(ai.generate_image(copy.get("image_prompt", cand.get("caption", "")[:300]),
                                            cfg["ai"]["image_size"], cfg["ai"]["image_quality"]))

    ctx = build_context(copy, cand, cfg["brand"], cover.as_uri(), tz, ai_image)
    slides = render_slides(ctx, out)
    caption = build_caption(copy, cfg)

    urls = host_images(slides, cfg["publish"]["image_host"], f"draft: issue #{number} ({tag})")
    draft = {"issue": number, "candidate": tag, "dir": str(out.relative_to(ROOT)),
             "image_urls": urls, "caption": caption, "copy": copy, "source": cand.get("permalink")}
    write_json(out / "draft.json", draft)
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    write_json(STATE_DIR / "drafts" / f"{number}.json", draft)
    git_commit_push(f"draft: issue #{number}", [str(out.relative_to(ROOT)), "state/drafts"])
    return draft


def preview_comment(gh: GitHub, number: int, draft: dict, footer: str):
    gh.ensure_label("draft-ready", "fbca04", "미리보기 완료")
    gh.add_labels(number, ["draft-ready"])
    urls = draft["image_urls"]
    imgs = "\n".join(f'<a href="{u}"><img src="{u}" width="240"></a>' for u in urls)
    gh.comment(number,
               f"🖼️ **미리보기** ({len(urls)}장)\n\n{imgs}\n\n**캡션** (복사해서 쓰세요)\n```\n{draft['caption']}\n```\n{footer}")


# ── /approve ─────────────────────────────────────────
def do_approve(cfg, gh: GitHub, issue: dict, cmd: dict):
    cands = load_candidates(issue["body"])
    if not 1 <= cmd["n"] <= len(cands):
        gh.comment(issue["number"], f"⚠️ 1~{len(cands)} 사이 번호로 입력해 주세요.")
        return
    cand = cands[cmd["n"] - 1]
    draft = make_draft(cfg, gh, issue["number"], cand, cmd["my_take"], cmd["image_mode"], str(cmd["n"]))
    if cfg["publish"]["require_preview"]:
        preview_comment(gh, issue["number"], draft,
                        "괜찮으면 `/publish`, 생각을 고치려면 `/approve 번호` 를 다시 입력하세요.")
    else:
        do_publish(cfg, gh, issue, {"force": False})


# ── /publish ─────────────────────────────────────────
def do_publish(cfg, gh: GitHub, issue: dict, cmd: dict):
    draft = read_json(STATE_DIR / "drafts" / f"{issue['number']}.json", None)
    if not draft:
        gh.comment(issue["number"], "⚠️ 먼저 `/approve 번호` 로 초안을 만들어 주세요.")
        return
    tz = ZoneInfo(cfg["publish"]["timezone"])
    today = datetime.now(tz).strftime("%Y-%m-%d")
    log = read_json(PUBLISHED, [])
    count = sum(1 for x in log if x["date"] == today)
    cap = cfg["publish"]["max_posts_per_day"]
    if count >= cap and not cmd.get("force"):
        gh.comment(issue["number"], f"⚠️ 오늘 이미 {count}개를 발행했어요(목표 {cap}개). 그래도 올리려면 `/publish force`.")
        return

    ig = InstagramClient(env("IG_USER_ID"), env("IG_ACCESS_TOKEN"), cfg["graph_api"]["version"])
    res = ig.publish_carousel(draft["image_urls"], draft["caption"])
    log.append({"date": today, "issue": issue["number"], "media_id": res["media_id"],
                "permalink": res.get("permalink"), "source": draft.get("source")})
    write_json(PUBLISHED, log[-500:])
    git_commit_push(f"published: issue #{issue['number']}", ["state/published.json"])

    gh.ensure_label("published", "0e8a16", "인스타 발행 완료")
    gh.add_labels(issue["number"], ["published"])
    gh.comment(issue["number"], f"✅ 발행 완료! {res.get('permalink') or res['media_id']}  (오늘 {count + 1}/{cap})")
    gh.close(issue["number"])


def main():
    event = json.loads(open(env("GITHUB_EVENT_PATH"), encoding="utf-8").read())
    comment, issue = event["comment"], event["issue"]
    cmd = parse_command(comment["body"])
    if not cmd["cmd"]:
        return
    cfg = load_config()
    gh = GitHub()
    gh.react(comment["id"], "eyes")
    try:
        if cmd["cmd"] == "approve":
            do_approve(cfg, gh, issue, cmd)
        elif cmd["cmd"] == "publish":
            do_publish(cfg, gh, issue, cmd)
        elif cmd["cmd"] == "skip":
            gh.comment(issue["number"], "👌 이번 후보는 건너뜁니다.")
            gh.close(issue["number"], "not_planned")
        gh.react(comment["id"], "rocket")
    except Exception as e:
        gh.comment(issue["number"], f"❌ 처리 중 오류가 났어요:\n```\n{str(e)[:1500]}\n```\nActions 로그에서 자세히 볼 수 있어요.")
        raise


if __name__ == "__main__":
    main()
