#!/usr/bin/env python3
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.dirname(__file__))
from src.fetcher import fetch_all, deduplicate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
ASSETS_SRC = os.path.join(BASE_DIR, "src", "assets")
ASSETS_DST = os.path.join(OUTPUT_DIR, "assets")

CATEGORY_ORDER = ["AI", "科技", "综合", "财经"]
CATEGORY_BADGE = {
    "AI": {"class": "cat-ai"},
    "科技": {"class": "cat-tech"},
    "综合": {"class": "cat-general"},
    "财经": {"class": "cat-business"},
}

SOURCE_LOGOS = {
    "hackernews": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14" style="width:14px;height:14px"><circle cx="7" cy="7" r="6.5" fill="#ff6600"/><text x="7" y="10" font-size="8" text-anchor="middle" fill="#fff" font-weight="bold">Y</text></svg>',
    "techcrunch": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14" style="width:14px;height:14px"><rect x=".5" y="1.5" width="13" height="11" rx="2" fill="#00d084"/><polygon points="5.5,4.5 10,7 5.5,9.5" fill="#fff"/></svg>',
    "jiqizhixin": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14" style="width:14px;height:14px"><circle cx="7" cy="7" r="6.5" fill="#1a8cff"/><text x="7" y="10" font-size="6" text-anchor="middle" fill="#fff" font-weight="bold">J</text></svg>',
    "reuters": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14" style="width:14px;height:14px"><rect x=".5" y="2.5" width="13" height="9" rx="2" fill="#ff6300"/><text x="7" y="9.5" font-size="6" text-anchor="middle" fill="#fff" font-weight="bold">R</text></svg>',
}


def time_ago(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.total_seconds() < 0:
            return "刚刚"
        h = int(delta.total_seconds() // 3600)
        if h < 1:
            m = int(delta.total_seconds() // 60)
            return f"{m} 分钟前" if m > 0 else "刚刚"
        if h < 24:
            return f"{h} 小时前"
        d = h // 24
        return f"{d} 天前"
    except Exception:
        return ""


def source_logo(sid):
    return SOURCE_LOGOS.get(sid, "")


def categorize_items(items):
    groups = defaultdict(list)
    for item in items:
        cat = item.get("category", "综合")
        if cat not in CATEGORY_ORDER:
            cat = "综合"
        groups[cat].append(item)
    result = []
    for cat in CATEGORY_ORDER:
        if groups[cat]:
            result.append({"name": cat, "articles": groups[cat]})
    return result


def build():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ASSETS_DST, exist_ok=True)

    # Copy asset SVGs to output
    for f in os.listdir(ASSETS_SRC):
        shutil.copy2(os.path.join(ASSETS_SRC, f), os.path.join(ASSETS_DST, f))

    print("Fetching news...")
    items = fetch_all()
    items = deduplicate(items)
    print(f"Got {len(items)} items")

    # Save raw data
    data_file = os.path.join(OUTPUT_DIR, "data.json")
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    grouped = categorize_items(items)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    env.filters["time_ago"] = time_ago
    env.globals["source_logo"] = source_logo

    template = env.get_template("index.html")
    html = template.render(
        items=items,
        grouped=grouped,
        badges=CATEGORY_BADGE,
        today=today,
        update_time=update_time,
        category_order=CATEGORY_ORDER,
    )

    index_file = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Written: {index_file}")
    print(f"Items: {len(items)}")
    print("Done.")


if __name__ == "__main__":
    build()
