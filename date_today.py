#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, datetime, io
import requests
from PIL import Image, ImageDraw, ImageFont

NOTION_API     = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
BLOCK_ID       = os.getenv("NOTION_DATE_BLOCK_ID")

if not NOTION_TOKEN or not BLOCK_ID:
    raise SystemExit("Missing NOTION_TOKEN or NOTION_DATE_BLOCK_ID.")


# ─── Image generation ────────────────────────────────────────────────────────

def generate_date_png(
    text: str,
    font_size: int = 96,
    font_color: tuple = (30, 30, 30, 255),
    padding: int = 20,
) -> bytes:
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    font = ImageFont.load_default()
    for path in font_candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                pass

    dummy = Image.new("RGBA", (1, 1))
    bbox  = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    w, h  = bbox[2] - bbox[0], bbox[3] - bbox[1]

    img  = Image.new("RGBA", (w + padding * 2, h + padding * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((padding, padding), text, font=font, fill=font_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─── Notion native file upload ────────────────────────────────────────────────

def upload_to_notion(png_bytes: bytes, filename: str = "date.png") -> str:
    auth_headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
    }

    # ✅ FIXED ENDPOINT HERE
    r = requests.post(
        f"{NOTION_API}/file_uploads",
        headers={**auth_headers, "Content-Type": "application/json"},
        data=json.dumps({"filename": filename, "content_type": "image/png"}),
        timeout=15,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create Notion upload slot: {r.status_code} {r.text}")

    slot           = r.json()
    upload_url     = slot["upload_url"]
    file_upload_id = slot["id"]

    r2 = requests.put(
        upload_url,
        headers={"Content-Type": "image/png"},
        data=png_bytes,
        timeout=30,
    )
    if r2.status_code not in (200, 201, 204):
        raise RuntimeError(f"Failed to upload PNG to Notion: {r2.status_code} {r2.text}")

    print(f"☁️ Uploaded to Notion (file_upload_id: {file_upload_id})")
    return file_upload_id


# ─── Notion block update ──────────────────────────────────────────────────────

def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _image_payload(file_upload_id: str) -> dict:
    return {
        "type": "image",
        "image": {
            "type": "file_upload",
            "file_upload": {"id": file_upload_id},
        },
    }


def update_block_with_image(block_id: str, file_upload_id: str) -> None:
    r = requests.patch(
        f"{NOTION_API}/blocks/{block_id}",
        headers=_notion_headers(),
        data=json.dumps(_image_payload(file_upload_id)),
    )
    if r.status_code in (200, 201):
        print("✅ Block updated with new image.")
        return

    print(f"⚠️ PATCH returned {r.status_code} — falling back to delete + append …")

    info   = requests.get(f"{NOTION_API}/blocks/{block_id}", headers=_notion_headers())
    info.raise_for_status()
    parent = info.json().get("parent", {})

    requests.delete(f"{NOTION_API}/blocks/{block_id}", headers=_notion_headers())

    parent_id = parent.get("page_id") or parent.get("block_id")
    if not parent_id:
        raise RuntimeError("Could not determine parent ID to re-append block.")

    r2 = requests.patch(
        f"{NOTION_API}/blocks/{parent_id}/children",
        headers=_notion_headers(),
        data=json.dumps({"children": [_image_payload(file_upload_id)]}),
    )
    if r2.status_code not in (200, 201):
        raise RuntimeError(f"Failed to append image block: {r2.status_code} {r2.text}")

    print("✅ Old block deleted and fresh image block appended.")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today_str = datetime.date.today().strftime("%d.%m.%y")
    print(f"📅 Generating PNG for: {today_str}")

    png_bytes = generate_date_png(today_str)
    print(f"🖼️ PNG generated ({len(png_bytes):,} bytes)")

    print("⬆️ Uploading to Notion …")
    file_upload_id = upload_to_notion(png_bytes, filename=f"{today_str}.png")

    update_block_with_image(BLOCK_ID, file_upload_id)
