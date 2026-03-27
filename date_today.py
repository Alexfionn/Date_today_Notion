#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, datetime, io, base64, time
import requests
from PIL import Image, ImageDraw, ImageFont

NOTION_API     = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
BLOCK_ID       = os.getenv("NOTION_DATE_BLOCK_ID")
IMGBB_API_KEY  = os.getenv("IMGBB_API_KEY")

if not NOTION_TOKEN or not BLOCK_ID or not IMGBB_API_KEY:
    raise SystemExit("Missing NOTION_TOKEN, NOTION_DATE_BLOCK_ID, or IMGBB_API_KEY.")


# ─── Image generation ────────────────────────────────────────────────────────

def load_font(size=96):
    # 👇 put your custom font file in repo, e.g. fonts/plant.ttf
    custom_font = "fonts/plant.ttf"

    if os.path.exists(custom_font):
        return ImageFont.truetype(custom_font, size)

    # fallback
    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
    )


def generate_date_png(text: str) -> bytes:
    font = load_font(96)

    dummy = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # transparent background
    img = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))

    # ✅ WHITE TEXT
    ImageDraw.Draw(img).text((20, 20), text, font=font, fill=(255, 255, 255, 255))

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
    print(f"☁️ Uploaded: {url}")
    return url


# ─── Notion helpers ──────────────────────────────────────────────────────────

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def create_image_block(url: str):
    return {
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": url},
        },
    }


# ─── Replace block (FIXED) ───────────────────────────────────────────────────

def replace_block(block_id: str, image_url: str):
    headers = notion_headers()

    # 1. get parent + position
    info = requests.get(f"{NOTION_API}/blocks/{block_id}", headers=headers)
    info.raise_for_status()
    parent = info.json()["parent"]

    parent_id = parent.get("page_id") or parent.get("block_id")
    if not parent_id:
        raise RuntimeError("No parent found")

    # 2. delete old block FIRST
    requests.delete(f"{NOTION_API}/blocks/{block_id}", headers=headers)

    # 3. insert new block at top (cleanest deterministic behavior)
    r = requests.patch(
        f"{NOTION_API}/blocks/{parent_id}/children",
        headers=headers,
        data=json.dumps({
            "children": [create_image_block(image_url)]
        }),
    )
    r.raise_for_status()

    print("✅ Old block removed, new one inserted")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.date.today().strftime("%d.%m.%y")
    print(f"📅 {today}")

    png = generate_date_png(today)
    print(f"🖼️ Generated ({len(png)} bytes)")

    url = upload_to_imgbb(png)

    print("⏳ Waiting for CDN...")
    time.sleep(5)

    replace_block(BLOCK_ID, url)
