#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENV (required)
  NOTION_TOKEN          – Notion integration token
  NOTION_DATE_BLOCK_ID  – ID of the block to replace with the date image

Dependencies:
  pip install requests pillow
"""
from __future__ import annotations
import os, json, datetime, io
import requests
from PIL import Image, ImageDraw, ImageFont

NOTION_API      = "https://api.notion.com/v1"
NOTION_VERSION  = "2022-06-28"
NOTION_TOKEN    = os.getenv("NOTION_TOKEN")
BLOCK_ID        = os.getenv("NOTION_DATE_BLOCK_ID")

if not NOTION_TOKEN or not BLOCK_ID:
    raise SystemExit("Missing NOTION_TOKEN or NOTION_DATE_BLOCK_ID.")


# ─── Image generation ────────────────────────────────────────────────────────

def generate_date_png(
    text: str,
    font_size: int = 96,
    font_color: tuple = (30, 30, 30, 255),   # RGBA – change alpha for transparency
    padding: int = 20,
) -> bytes:
    """
    Render *text* onto a fully transparent PNG and return raw PNG bytes.
    Falls back to Pillow's built-in bitmap font if no TTF is available.
    """
    # Try to load a nice system font; fall back to default if unavailable
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",   # Linux
        "/System/Library/Fonts/Helvetica.ttc",                      # macOS
        "C:/Windows/Fonts/arialbd.ttf",                             # Windows
    ]
    font = ImageFont.load_default()
    for path in font_candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                pass

    # Measure text size using a temporary draw surface
    dummy = Image.new("RGBA", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    bbox  = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Create a transparent canvas
    img  = Image.new("RGBA", (text_w + padding * 2, text_h + padding * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((padding, padding), text, font=font, fill=font_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─── Anonymous image hosting (0x0.st) ────────────────────────────────────────

def upload_to_0x0(png_bytes: bytes, filename: str = "date.png") -> str:
    """
    Upload PNG bytes to https://0x0.st (no account needed).
    Returns the public URL of the uploaded file.
    """
    resp = requests.post(
        "https://0x0.st",
        files={"file": (filename, png_bytes, "image/png")},
        timeout=15,
    )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Unexpected response from 0x0.st: {url!r}")
    return url


# ─── Notion block update ──────────────────────────────────────────────────────

def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def update_block_with_image(block_id: str, image_url: str) -> None:
    """
    Patch a Notion block to be an 'image' block pointing at *image_url*.

    Note: the existing block type must match, OR you delete + re-append.
    The safest approach is to update the parent page's children list;
    here we PATCH the block directly (works if it was already an image block)
    and fall back to delete + append otherwise.
    """
    payload = {
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": image_url},
        },
    }
    url = f"{NOTION_API}/blocks/{block_id}"
    r = requests.patch(url, headers=notion_headers(), data=json.dumps(payload))

    if r.status_code in (200, 201):
        print("✅ Block patched as image block.")
        return

    # If patching fails (e.g. block type mismatch), fall back:
    # delete the old block and append a new image block to its parent.
    print(f"⚠️  PATCH returned {r.status_code}; trying delete + append …")
    _delete_and_append_image(block_id, image_url)


def _delete_and_append_image(block_id: str, image_url: str) -> None:
    """Delete the old block and append a fresh image block to its parent."""
    # 1. Retrieve parent info
    r = requests.get(f"{NOTION_API}/blocks/{block_id}", headers=notion_headers())
    r.raise_for_status()
    block_data = r.json()
    parent = block_data.get("parent", {})

    # 2. Delete old block
    requests.delete(f"{NOTION_API}/blocks/{block_id}", headers=notion_headers())

    # 3. Append image to parent
    parent_id = parent.get("page_id") or parent.get("block_id")
    if not parent_id:
        raise RuntimeError("Could not determine parent ID to re-append block.")

    append_payload = {
        "children": [
            {
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": image_url},
                },
            }
        ]
    }
    r2 = requests.patch(
        f"{NOTION_API}/blocks/{parent_id}/children",
        headers=notion_headers(),
        data=json.dumps(append_payload),
    )
    if r2.status_code not in (200, 201):
        raise RuntimeError(f"Failed to append image block: {r2.status_code} {r2.text}")
    print("✅ Old block deleted and new image block appended.")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today_str = datetime.date.today().strftime("%d.%m.%y")
    print(f"📅 Generating PNG for: {today_str}")

    png_bytes = generate_date_png(today_str)
    print(f"🖼️  PNG generated ({len(png_bytes):,} bytes)")

    print("⬆️  Uploading to 0x0.st …")
    image_url = upload_to_0x0(png_bytes, filename=f"{today_str}.png")
    print(f"🔗 Image URL: {image_url}")

    update_block_with_image(BLOCK_ID, image_url)