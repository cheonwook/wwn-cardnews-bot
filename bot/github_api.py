"""GitHub REST API (Issue 알림/댓글) + 리포지토리 커밋 헬퍼."""
from __future__ import annotations

import subprocess

import requests

from .config import ROOT, env


class GitHub:
    def __init__(self):
        self.token = env("GITHUB_TOKEN")
        self.repo = env("GITHUB_REPOSITORY")          # owner/name (Actions 가 자동 제공)
        self.base = f"https://api.github.com/repos/{self.repo}"
        self.h = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}

    @property
    def owner(self) -> str:
        return self.repo.split("/")[0]

    def _r(self, method, path, **kw):
        r = requests.request(method, f"{self.base}{path}", headers=self.h, timeout=60, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub {method} {path} → {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def ensure_label(self, name: str, color: str, desc: str = ""):
        try:
            self._r("POST", "/labels", json={"name": name, "color": color, "description": desc})
        except RuntimeError:
            pass  # 이미 존재

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        return self._r("POST", "/issues", json={"title": title, "body": body, "labels": labels})

    def get_issue(self, number: int) -> dict:
        return self._r("GET", f"/issues/{number}")

    def comment(self, number: int, body: str) -> dict:
        return self._r("POST", f"/issues/{number}/comments", json={"body": body})

    def add_labels(self, number: int, labels: list[str]):
        self._r("POST", f"/issues/{number}/labels", json={"labels": labels})

    def close(self, number: int, reason: str = "completed"):
        self._r("PATCH", f"/issues/{number}", json={"state": "closed", "state_reason": reason})

    def react(self, comment_id: int, content: str = "eyes"):
        try:
            self._r("POST", f"/issues/comments/{comment_id}/reactions", json={"content": content})
        except RuntimeError:
            pass


def git_commit_push(message: str, paths: list[str]) -> None:
    """작업 결과(상태 파일·이미지)를 리포에 커밋. 동시 실행 대비 rebase 재시도."""
    def run(*args, check=True):
        return subprocess.run(args, cwd=ROOT, check=check, capture_output=True, text=True)

    run("git", "config", "user.name", "cardnews-bot")
    run("git", "config", "user.email", "cardnews-bot@users.noreply.github.com")
    run("git", "add", *paths)
    if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    run("git", "commit", "-m", message)
    for _ in range(4):
        if run("git", "push", check=False).returncode == 0:
            return
        run("git", "pull", "--rebase", "-X", "theirs", check=False)
    raise RuntimeError("git push 실패")
