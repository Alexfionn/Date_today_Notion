#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, datetime, io, base64
import requests
import time
from PIL import Image, ImageDraw, ImageFont

NOTION_API     = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
BLOCK_ID       = os.getenv("NOTION_DATE_BLOCK_ID")

# 👉 add this secret in GitHub
IMGBB_API_KEY  = os.getenv("IMGBB_API_KEY")

if not NOTION_TOKEN or not BLOCK_ID or not IMGBB_API_KEY:
    raise SystemExit("Missing NOTION_TOKEN, NOTION_DATE_BLOCK_ID, or IMGBB_API_KEY.")


# ─── Image generation ────────────────────────────────────────────────────────

def generate_date_png(text: str) -> bytes:
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]

    font = ImageFont.load_default()
    for path in font_candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 96)
                break
            except:
                pass

    dummy = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    img = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((20, 20), text, font=font, fill=(30, 30, 30, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─── Upload to imgbb ─────────────────────────────────────────────────────────

def upload_to_imgbb(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes)

    r = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": IMGBB_API_KEY,
            "image": encoded,
        },
        timeout=30,
    )
    r.raise_for_status()

    url = r.json()["data"]["url"]
    print(f"☁️ Uploaded to imgbb: {url}")
    return url


# ─── Notion update ───────────────────────────────────────────────────────────

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def update_block(block_id: str, image_url: str):
    payload = {
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": image_url},
        },
    }

    r = requests.patch(
        f"{NOTION_API}/blocks/{block_id}",
        headers=notion_headers(),
        data=json.dumps(payload),
    )

    if r.status_code in (200, 201):
        print("✅ Block updated")
        return

    print("⚠️ Fallback: recreate block")

    info = requests.get(f"{NOTION_API}/blocks/{block_id}", headers=notion_headers())
    info.raise_for_status()
    parent = info.json()["parent"]

    requests.delete(f"{NOTION_API}/blocks/{block_id}", headers=notion_headers())

    parent_id = parent.get("page_id") or parent.get("block_id")

    r2 = requests.patch(
        f"{NOTION_API}/blocks/{parent_id}/children",
        headers=notion_headers(),
        data=json.dumps({"children": [payload]}),
    )
    r2.raise_for_status()

    print("✅ Recreated block with image")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.date.today().strftime("%d.%m.%y")
    print(f"📅 {today}")

    png = generate_date_png(today)
    print(f"🖼️ Generated ({len(png)} bytes)")

    url = upload_to_imgbb(png)

    print("⏳ Waiting for CDN...")
    time.sleep(5)  # wait 5 seconds

    update_block(BLOCK_ID, url)
