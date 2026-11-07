"""원문 이미지에 박힌 글자(제목·로고 등) 없애기.

1) 비전으로 덧씌운 글자 영역 찾기
2) 글자가 위/아래 띠에만 있으면 → 그 띠를 잘라냄 (사진 원본 그대로, 가장 안전)
3) 사진 중간에 걸치면 → 그 영역만 OpenAI 이미지 편집으로 지움 (얼굴 위 글자는 지우지 않음)
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter, ImageStat

MIN_KEEP = 0.45   # 잘라낸 뒤 원본 높이의 최소 비율
PAD = 0.03
BLEND = 0.10   # 글자 띠 위아래로 더 넓혀서 지움 (원문 디자인의 어두운 그라데이션까지 포함)


def _jpeg(im: Image.Image, max_side: int | None = None) -> bytes:
    im = im.convert("RGB")
    if max_side and max(im.size) > max_side:
        im = im.copy(); im.thumbnail((max_side, max_side))
    b = io.BytesIO(); im.save(b, "JPEG", quality=92); return b.getvalue()


MAX_EDIT_TRIES = 3   # 글자 지우기 최대 시도 횟수
BLACK_MEAN = 20      # 지운 자리의 평균 밝기(0~255)가 이보다 어두우면 AI가 검게 채운 것으로 봄


def _filled_black(img: Image.Image, boxes: list[list[int]]) -> bool:
    """AI가 지운 자리를 사진으로 복원하지 않고 새까맣게 채웠는지 검사."""
    for x0, y0, x1, y1 in boxes:
        if x1 <= x0 or y1 <= y0:
            continue
        if ImageStat.Stat(img.crop((x0, y0, x1, y1)).convert("L")).mean[0] < BLACK_MEAN:
            return True
    return False


def _grow(r: dict, W: int, H: int) -> list[int]:
    """글자 박스를 넓힘. 가로로 긴 띠(제목 영역)는 위아래로 BLEND 만큼 더."""
    band = (r["x1"] - r["x0"]) > 0.6
    ext = BLEND if band else PAD
    return [int(max(0, r["x0"] - PAD) * W), int(max(0, r["y0"] - ext) * H),
            int(min(1, r["x1"] + PAD) * W), int(min(1, r["y1"] + ext) * H)]


def clean_and_read(ai, data: bytes, quality: str = "medium", log=print, prefer: str = "crop") -> tuple[bytes, str]:
    """prefer='crop': 글자 띠를 잘라냄(본문 사진용) / 'inpaint': 글자만 지우고 사진 전체를 살림(표지용)."""
    im = Image.open(io.BytesIO(data)); im.load()
    W, H = im.size
    try:
        regions, text = ai.read_overlay(_jpeg(im, 1024))
    except Exception as e:  # 분석 실패 시 원본 사용
        log(f"글자 영역 분석 실패, 원본 사용: {e}")
        return data, ""
    if not regions:
        return data, text

    top = min(r["y0"] for r in regions)
    bottom = max(r["y1"] for r in regions)

    # 2) 위/아래 띠 잘라내기: 글자 띠 밖의 가장 큰 깨끗한 구간
    bands = []  # (start, end) 깨끗한 세로 구간
    occupied = sorted((max(0, r["y0"] - PAD), min(1, r["y1"] + PAD)) for r in regions)
    cur = 0.0
    for a, b in occupied:
        if a > cur:
            bands.append((cur, a))
        cur = max(cur, b)
    if cur < 1:
        bands.append((cur, 1.0))
    best = max(bands, key=lambda t: t[1] - t[0], default=(0, 0))
    if prefer == "crop" and best[1] - best[0] >= MIN_KEEP:
        log(f"글자 띠 잘라냄: 세로 {best[0]:.2f}~{best[1]:.2f} 사용")
        return _jpeg(im.crop((0, int(best[0] * H), W, int(best[1] * H)))), text

    # 3) AI 편집: 얼굴 위가 아닌 글자 영역만 지움
    editable = [r for r in regions if not r["over_face"]]
    if not editable:
        log("글자가 얼굴과 겹쳐 지우지 않고 원본 사용")
        return data, text
    src = im.convert("RGBA")
    mask = Image.new("RGBA", src.size, (0, 0, 0, 255))
    d = ImageDraw.Draw(mask)
    boxes = [_grow(r, W, H) for r in editable]
    for b in boxes:
        d.rectangle(b, fill=(0, 0, 0, 0))
    pb, mb = io.BytesIO(), io.BytesIO()
    src.save(pb, "PNG"); mask.save(mb, "PNG")
    prompt = ("Remove all overlaid text, captions, logos and graphic elements inside the masked (transparent) area "
              "and reconstruct the photo there so it blends naturally with its surroundings. "
              "Keep everything outside the mask exactly as it is. Do not add any text.")
    edited = None
    for attempt in range(1, MAX_EDIT_TRIES + 1):  # AI가 글자 자리를 새까맣게 채우는 경우가 있어 다시 시도
        try:
            tried = Image.open(io.BytesIO(ai.edit_image(pb.getvalue(), mb.getvalue(), prompt, quality))).convert("RGB")
        except Exception as e:
            if best[1] - best[0] >= MIN_KEEP:
                log(f"글자 지우기 실패, 글자 띠를 잘라서 사용: {e}")
                return _jpeg(im.crop((0, int(best[0] * H), W, int(best[1] * H)))), text
            log(f"글자 지우기 실패, 원본 사용: {e}")
            return data, text
        tried = tried.resize((W, H), Image.LANCZOS)
        if not _filled_black(tried, boxes):
            edited = tried
            break
        log(f"AI가 글자 자리를 검게 채워서 다시 시도 ({attempt}/{MAX_EDIT_TRIES})")
    if edited is None:
        if best[1] - best[0] >= MIN_KEEP:
            log("글자 자리가 계속 검게 채워져 글자 띠를 잘라서 사용")
            return _jpeg(im.crop((0, int(best[0] * H), W, int(best[1] * H)))), text
        log("글자 자리가 계속 검게 채워져 원본 사용")
        return data, text
    # 편집본에서 글자 영역만 원본에 붙여넣기 → 얼굴 등 나머지는 원본 화질 그대로
    paste_mask = Image.new("L", (W, H), 0)
    pd = ImageDraw.Draw(paste_mask)
    for b in boxes:
        pd.rectangle(b, fill=255)
    paste_mask = paste_mask.filter(ImageFilter.GaussianBlur(H * 0.02))  # 경계선이 보이지 않게 부드럽게
    result = im.convert("RGB").copy()
    result.paste(edited, (0, 0), paste_mask)
    log(f"AI로 글자 영역 {len(editable)}곳 지움 (나머지는 원본 유지)")
    return _jpeg(result), text


def remove_overlay_text(ai, data: bytes, quality: str = "medium", log=print, prefer: str = "crop") -> bytes:
    return clean_and_read(ai, data, quality, log, prefer)[0]
