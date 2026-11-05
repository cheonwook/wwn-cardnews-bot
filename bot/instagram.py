"""Instagram Graph API (Facebook Login 방식) 클라이언트.

- 후보 수집: Business Discovery, Hashtag Search
- 발행: Content Publishing (캐러셀)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

MEDIA_FIELDS = "id,caption,like_count,comments_count,media_type,media_url,permalink,timestamp"


class GraphError(RuntimeError):
    pass


class InstagramClient:
    def __init__(self, ig_user_id: str, access_token: str, version: str = "v26.0"):
        self.ig_user_id = ig_user_id
        self.token = access_token
        self.base = f"https://graph.facebook.com/{version}"

    # ── 공통 ──────────────────────────────────────────
    def _req(self, method: str, path: str, **params):
        params["access_token"] = self.token
        url = f"{self.base}/{path.lstrip('/')}"
        for attempt in range(3):
            r = requests.request(method, url, params=params if method == "GET" else None,
                                 data=params if method != "GET" else None, timeout=60)
            if r.status_code < 500:
                break
            time.sleep(2 * (attempt + 1))
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise GraphError(f"{err.get('message', r.text)} (code={err.get('code')}, sub={err.get('error_subcode')})")
        return data

    # ── 후보 수집 ─────────────────────────────────────
    def business_discovery(self, username: str, limit: int = 20) -> list[dict]:
        fields = (f"business_discovery.username({username})"
                  f"{{username,name,media.limit({limit}){{{MEDIA_FIELDS}}}}}")
        data = self._req("GET", self.ig_user_id, fields=fields)
        bd = data.get("business_discovery", {})
        items = bd.get("media", {}).get("data", [])
        for m in items:
            m["source_account"] = bd.get("username", username)
            m["source_type"] = "account"
        return items

    def hashtag_id(self, tag: str) -> str | None:
        data = self._req("GET", "ig_hashtag_search", user_id=self.ig_user_id, q=tag)
        ids = data.get("data", [])
        return ids[0]["id"] if ids else None

    def hashtag_top_media(self, tag: str, limit: int = 30) -> list[dict]:
        hid = self.hashtag_id(tag)
        if not hid:
            return []
        data = self._req("GET", f"{hid}/top_media", user_id=self.ig_user_id,
                         fields=MEDIA_FIELDS, limit=limit)
        items = data.get("data", [])
        for m in items:
            # 해시태그 결과에는 작성자 username 이 제공되지 않음 → 링크로 출처 표기
            m["source_account"] = None
            m["source_type"] = f"#{tag}"
        return items

    # ── 발행 ──────────────────────────────────────────
    def _wait_container(self, container_id: str, timeout_s: int = 300):
        start = time.time()
        while time.time() - start < timeout_s:
            st = self._req("GET", container_id, fields="status_code").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise GraphError(f"컨테이너 {container_id} 상태: {st}")
            time.sleep(5)
        raise GraphError(f"컨테이너 {container_id} 처리 시간 초과")

    def publish_carousel(self, image_urls: list[str], caption: str) -> dict:
        if not 2 <= len(image_urls) <= 10:
            raise ValueError("캐러셀은 이미지 2~10장이어야 합니다.")
        children = []
        for url in image_urls:
            c = self._req("POST", f"{self.ig_user_id}/media", image_url=url, is_carousel_item="true")
            children.append(c["id"])
        for cid in children:
            self._wait_container(cid)
        parent = self._req("POST", f"{self.ig_user_id}/media", media_type="CAROUSEL",
                           children=",".join(children), caption=caption)
        self._wait_container(parent["id"])
        pub = self._req("POST", f"{self.ig_user_id}/media_publish", creation_id=parent["id"])
        media_id = pub["id"]
        info = self._req("GET", media_id, fields="permalink")
        return {"media_id": media_id, "permalink": info.get("permalink")}

    def publishing_quota(self) -> dict:
        try:
            return self._req("GET", f"{self.ig_user_id}/content_publishing_limit",
                             fields="quota_usage,config")
        except GraphError:
            return {}


def parse_ts(ts: str) -> datetime:
    # 예: 2026-11-05T10:01:00+0000
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)
