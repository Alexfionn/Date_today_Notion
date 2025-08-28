#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ENV (required)
  NOTION_TOKEN
  NOTION_DATE_BLOCK_ID
"""

from __future__ import annotations
import os, json, datetime
import requests

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
BLOCK_ID = os.getenv("NOTION_DATE_BLOCK_ID")
if not NOTION_TOKEN or not BLOCK_ID:
    raise SystemExit("Missing NOTION_TOKEN or NOTION_DATE_BLOCK_ID.")

def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def update_date_heading(block_id: str) -> None:
    """
    Update a Notion block to today's date as DD.MM.YY in heading_2
    """
    today_str = datetime.date.today().strftime("%d.%m.%y")

    payload = {
        "heading_1": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": today_str},
                    "annotations": {"bold": True}
                }
            ]
        }
    }

    url = f"{NOTION_API}/blocks/{block_id}"
    r = requests.patch(url, headers=notion_headers(), data=json.dumps(payload))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update block: {r.status_code} {r.text}")
    print("✅ Updated block with date (heading_2):", today_str)

if __name__ == "__main__":
    update_date_heading(BLOCK_ID)
