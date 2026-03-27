#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, datetime, io, base64, time
import requests
from PIL import Image, ImageDraw, ImageFont

NOTION_API     = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
BLOCK_ID       = os.getenv("NOTION_DATE_BLOCK_ID")  # only used to find parent
IMGBB_API_KEY  = os.getenv("IMGBB_API_KEY")

if not NOTION_TOKEN or not BLOCK_ID or not IMGBB_API_KEY:
    raise SystemExit("Missing NOTION_TOKEN, NOTION_DATE_BLOCK_ID, or IMGBB_API_KEY.")


# ─── Image generation ────────────────────────────────────────────────────────

def load_font(size=96):
    custom_font = "fonts/plant.ttf"  # ✅ FIXED

    if os.path.exists(custom_font):
        return ImageFont.truetype(custom_font, size)

    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
    )


def generate_date_png(text: str) -> bytes:
    font = load_font(96)

    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)

    bbox = draw.textbbox((0, 0), text, font=font)
    x0, y0, x1, y1 = bbox

    w = x1 - x0
    h = y1 - y0

    padding = 40

    img = Image.new(
        "RGBA",
        (w + padding, h + padding),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(img)

    # key fix: compensate for bbox baseline offset
    draw.text(
        (padding // 2, padding // 2 - y0),
        text,
        font=font,
        fill=(255, 255, 255, 255),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─── Upload ──────────────────────────────────────────────────────────────────

def upload_to_imgbb(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes)

    r = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": encoded},
        timeout=30,
    )
    r.raise_for_status()

    return r.json()["data"]["url"]


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


# ─── FIXED LOGIC ─────────────────────────────────────────────────────────────

def replace_image(block_id: str, image_url: str):
    headers = notion_headers()

    # 1. get parent
    info = requests.get(f"{NOTION_API}/blocks/{block_id}", headers=headers)
    info.raise_for_status()
    parent = info.json()["parent"]

    parent_id = parent.get("page_id") or parent.get("block_id")

    # 2. get children
    children = requests.get(
        f"{NOTION_API}/blocks/{parent_id}/children",
        headers=headers,
    ).json()["results"]

    # 3. delete ALL image blocks (clean slate)
    for child in children:
        if child["type"] == "image":
            requests.delete(
                f"{NOTION_API}/blocks/{child['id']}",
                headers=headers,
            )

    # 4. insert fresh one
    r = requests.patch(
        f"{NOTION_API}/blocks/{parent_id}/children",
        headers=headers,
        data=json.dumps({
            "children": [create_image_block(image_url)]
        }),
    )
    r.raise_for_status()

    print("✅ Image replaced cleanly")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.date.today().strftime("%d.%m.%y")

    png = generate_date_png(today)

    url = upload_to_imgbb(png)

    time.sleep(5)

    replace_image(BLOCK_ID, url)
