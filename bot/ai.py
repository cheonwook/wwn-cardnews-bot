"""OpenAI 텍스트(번역·재구성)와 이미지 생성."""
from __future__ import annotations

import base64
import json
import time

import requests

API = "https://api.openai.com/v1"


class OpenAIClient:
    def __init__(self, api_key: str, text_model: str, image_model: str):
        self.key = api_key
        self.text_model = text_model
        self.image_model = image_model

    def _post(self, path: str, payload: dict, timeout: int = 180) -> dict:
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        last = None
        for attempt in range(3):
            r = requests.post(f"{API}{path}", headers=headers, json=payload, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            break
        raise RuntimeError(f"OpenAI {path} 실패 {last.status_code}: {last.text[:500]}")

    def chat_json(self, system: str, user: str) -> dict:
        data = self._post("/chat/completions", {
            "model": self.text_model,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        })
        return json.loads(data["choices"][0]["message"]["content"])

    # ── 1) 스카우트: 후보 한 줄 요약 ────────────────────
    def summarize_candidates(self, candidates: list[dict]) -> list[dict]:
        items = [{"i": i, "category_hint": c.get("category"), "caption": (c.get("caption") or "")[:1200]}
                 for i, c in enumerate(candidates)]
        system = ("너는 한국 인스타그램 카드뉴스 에디터다. 해외 게시물 캡션을 보고 한국 독자용 제목과 요약을 만든다. "
                  "캡션에 없는 사실은 만들지 않는다.")
        user = ("각 게시물에 대해 JSON 으로 답하라: "
                '{"items":[{"i":0,"title_ko":"20자 내외 제목","summary_ko":"핵심 1~2문장",'
                '"category":"정치|연예|시사|사회|경제 중 하나"}]}\n\n' + json.dumps(items, ensure_ascii=False))
        return self.chat_json(system, user).get("items", [])

    # ── 2) 승인 후: 카드뉴스 원고 ───────────────────────
    def build_cardnews(self, cand: dict, my_take: str, max_slides: int, brand: dict) -> dict:
        system = (
            "너는 한국어 인스타그램 카드뉴스 전문 에디터다.\n"
            "규칙:\n"
            "1. 원문 캡션에 있는 사실만 사용한다. 추측·과장 금지. 숫자·이름·날짜는 원문 그대로.\n"
            "2. 직역하지 말고 한국 독자가 맥락을 이해하도록 자연스럽게 번역·재구성한다(고유명사는 한글 표기 후 필요시 괄호 원어).\n"
            "3. 슬라이드 한 장의 본문은 90자 이내, 짧은 문장 2~3개.\n"
            "3-1. 끝까지 읽히는 게 최우선이다. 핵심만 남기고, 같은 내용을 나눠 장수를 늘리거나 반복하지 않는다. "
            "원문이 짧으면 본문은 1장이면 충분하다.\n"
            "4. '내 생각'은 사용자가 쓴 의견의 취지·어조·1인칭 시점을 그대로 유지하고 맞춤법과 흐름만 다듬는다. "
            "새로운 주장을 추가하지 않는다. 사용자가 비워두면 빈 문자열.\n"
            "5. image_prompt 는 영어로, 기사 분위기를 상징하는 에디토리얼 일러스트/사진풍 장면. "
            "실존 인물의 얼굴·로고·국기 문장·글자는 넣지 않는다. "
            "만화·영화·게임의 캐릭터나 마스코트(또는 그것을 닮은 모습)도 넣지 않는다. 대신 분위기를 상징하는 사물·장소로 표현한다.\n"
        )
        user = (
            f"원문 출처: {cand.get('source_account') or cand.get('source_type')} / {cand.get('permalink')}\n"
            f"카테고리: {cand.get('category')}\n"
            f"원문 캡션:\n\"\"\"\n{cand.get('caption', '')[:3500]}\n\"\"\"\n\n"
            f"사용자의 생각(원문 그대로):\n\"\"\"\n{my_take.strip()}\n\"\"\"\n\n"
            f"본문 슬라이드는 1~{max_slides}장 중 내용에 맞는 최소 장수. 다음 JSON 형식으로만 답하라:\n"
            "{\n"
            '  "headline": "표지 제목: 사실을 담은 한 문장, 18~34자. 가장 중요한 단어 2~3곳(인물·숫자·핵심 사건)을 [[ ]]로 감싼다. 예: \\"[[호날두]], 23년 만에 [[국가대표 은퇴]] 선언\\"",\n'
            '  "subheadline": "표지 부제 30자 이내",\n'
            '  "slides": [{"title": "소제목 14자 이내, 핵심어 1곳을 [[ ]]로", "body": "본문", "highlight": "강조할 핵심 구절(본문 안에 있는 표현) 또는 빈 문자열"}],\n'
            '  "my_take": "다듬은 내 생각",\n'
            '  "caption": "인스타 캡션 본문: 첫 줄 후킹 문장, 3~5줄 요약, 빈 줄 후 내 생각 한 줄(\'내 생각:\' 같은 라벨 없이 자연스러운 문장으로), 마지막 줄 \'출처: @계정\' 표기. 해시태그 제외",\n'
            '  "hashtags": ["한글/영문 해시태그 8~12개, # 제외"],\n'
            '  "image_prompt": "English prompt"\n'
            "}"
        )
        return self.chat_json(system, user)

    # ── 3) 이미지 생성 ─────────────────────────────────
    def generate_image(self, prompt: str, size: str, quality: str) -> bytes:
        full = (prompt.strip() + ". Vertical editorial cover image for a news card, cinematic lighting, "
                "strong focal subject, generous dark negative space in the lower third for headline text. "
                "No text, no letters, no logos, no watermarks, no real identifiable people, "
                "no cartoon/film/game characters or mascots.")
        payload = {"model": self.image_model, "prompt": full, "size": size,
                   "quality": quality, "output_format": "jpeg", "n": 1}
        try:
            data = self._post("/images/generations", payload, timeout=300)
        except RuntimeError as e:
            if "size" in str(e).lower() and size != "1024x1536":
                payload["size"] = "1024x1536"
                data = self._post("/images/generations", payload, timeout=300)
            else:
                raise
        return base64.b64decode(data["data"][0]["b64_json"])
