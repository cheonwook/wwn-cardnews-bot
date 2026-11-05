"""인스타가 가져갈 수 있도록 이미지를 공개 URL 로 올리기."""
from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from .config import ROOT, env
from .github_api import git_commit_push


def host_images(paths: list[Path], method: str, commit_msg: str) -> list[str]:
    if method == "imgbb":
        key = env("IMGBB_API_KEY")
        urls = []
        for p in paths:
            r = requests.post("https://api.imgbb.com/1/upload", data={
                "key": key, "image": base64.b64encode(p.read_bytes()).decode()}, timeout=120)
            r.raise_for_status()
            urls.append(r.json()["data"]["url"])
        return urls

    # github_raw: 리포가 Public 이어야 인스타 서버가 접근 가능
    repo = env("GITHUB_REPOSITORY")
    branch = env("GITHUB_REF_NAME", required=False, default="main")
    rel = [str(p.relative_to(ROOT)) for p in paths]
    git_commit_push(commit_msg, rel)
    urls = [f"https://raw.githubusercontent.com/{repo}/{branch}/{r}" for r in rel]
    # raw CDN 반영 대기
    for _ in range(12):
        if requests.head(urls[0], timeout=20).status_code == 200:
            break
        time.sleep(5)
    else:
        raise RuntimeError("raw.githubusercontent.com 에서 이미지를 찾을 수 없습니다. 리포가 Public 인지 확인하세요 "
                           "(Private 리포라면 config.yaml 의 image_host 를 imgbb 로 바꾸세요).")
    return urls
