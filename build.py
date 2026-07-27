#!/usr/bin/env python3
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.fetcher import fetch_all, deduplicate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
ASSETS_SRC = os.path.join(BASE_DIR, "src", "assets")
ASSETS_DST = os.path.join(OUTPUT_DIR, "assets")
DATA_DIR = os.path.join(OUTPUT_DIR, "data")

CATEGORY_ORDER = ["AI", "科技", "综合", "财经"]
CATEGORY_BADGE = {
    "AI": {"class": "cat-ai"},
    "科技": {"class": "cat-tech"},
    "综合": {"class": "cat-general"},
    "财经": {"class": "cat-business"},
}

# Category image fallbacks (CSS gradient descriptions)
CATEGORY_IMAGES = {
    "AI": {"gradient": "linear-gradient(135deg,#667eea,#764ba2)", "icon": "ai"},
    "科技": {"gradient": "linear-gradient(135deg,#3b82f6,#1d4ed8)", "icon": "tech"},
    "综合": {"gradient": "linear-gradient(135deg,#f97316,#ea580c)", "icon": "general"},
    "财经": {"gradient": "linear-gradient(135deg,#10b981,#047857)", "icon": "business"},
}

SOURCE_LOGOS = {
    "hackernews": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 14 14\" style=\"width:14px;height:14px\"><circle cx=\"7\" cy=\"7\" r=\"6.5\" fill=\"#ff6600\"/><text x=\"7\" y=\"10\" font-size=\"8\" text-anchor=\"middle\" fill=\"#fff\" font-weight=\"bold\">Y</text></svg>",
    "techcrunch": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 14 14\" style=\"width:14px;height:14px\"><rect x=\".5\" y=\"1.5\" width=\"13\" height=\"11\" rx=\"2\" fill=\"#00d084\"/><polygon points=\"5.5,4.5 10,7 5.5,9.5\" fill=\"#fff\"/></svg>",
    "jiqizhixin": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 14 14\" style=\"width:14px;height:14px\"><circle cx=\"7\" cy=\"7\" r=\"6.5\" fill=\"#1a8cff\"/><text x=\"7\" y=\"10\" font-size=\"6\" text-anchor=\"middle\" fill=\"#fff\" font-weight=\"bold\">J</text></svg>",
    "reuters": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 14 14\" style=\"width:14px;height:14px\"><rect x=\".5\" y=\"2.5\" width=\"13\" height=\"9\" rx=\"2\" fill=\"#ff6300\"/><text x=\"7\" y=\"9.5\" font-size=\"6\" text-anchor=\"middle\" fill=\"#fff\" font-weight=\"bold\">R</text></svg>",
}

# i18n translations
TRANSLATIONS = {
    "zh": {
        "site_title": "每日新闻",
        "tagline": "每日双语新闻",
        "nav_today": "今天",
        "nav_yesterday": "昨天",
        "filter_all": "全部",
        "filter_ai": "AI",
        "filter_tech": "科技",
        "filter_general": "综合",
        "filter_finance": "财经",
        "items_count": "条",
        "read_original": "阅读原文",
        "via": "via",
        "updated": "更新于",
        "total": "共",
        "trend_title": "关键词趋势",
        "days_ago": "天前",
        "hours_ago": "小时前",
        "minutes_ago": "分钟前",
        "just_now": "刚刚",
        "video": "视频",
        "footer_desc": "每日双语新闻 · 每日自动更新",
        "footer_sources": "数据来源: Hacker News · TechCrunch · Reuters · 机器之心",
        "today_focus": "今日焦点",
        "load_earlier": "加载更早新闻",
    },
    "en": {
        "site_title": "Daily Brief",
        "tagline": "Daily Bilingual News",
        "nav_today": "Today",
        "nav_yesterday": "Yesterday",
        "filter_all": "All",
        "filter_ai": "AI",
        "filter_tech": "Tech",
        "filter_general": "General",
        "filter_finance": "Finance",
        "items_count": "items",
        "read_original": "Read More",
        "via": "via",
        "updated": "Updated",
        "total": "Total",
        "trend_title": "Keyword Trends",
        "days_ago": "d ago",
        "hours_ago": "h ago",
        "minutes_ago": "m ago",
        "just_now": "Just now",
        "video": "Video",
        "footer_desc": "Daily Bilingual News · Auto-updated daily",
        "footer_sources": "Sources: Hacker News · TechCrunch · Reuters · 机器之心",
        "today_focus": "Today's Focus",
        "load_earlier": "Load Earlier",
    },
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "it", "its", "this", "that",
    "was", "are", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "new", "news",
    "first", "last", "get", "gets", "way", "ways", "say", "says", "said",
    "make", "makes", "made", "like", "just", "also", "one", "two", "time",
    "的", "了", "和", "是", "就", "都", "而", "及", "与", "着", "或",
    "一个", "没有", "我们", "他们", "你们", "可以", "这个", "那个", "什么",
    "发布", "宣布", "推出", "全球", "中国", "美国", "新", "大",
}

KW_MIN_LEN = {"zh": 2, "en": 4}


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



def fallback_img(category):
    img = CATEGORY_IMAGES.get(category, {"gradient": "linear-gradient(135deg,#64748b,#475569)", "icon": "general"})
    return "<div class=\"card-img-fallback\" style=\"background:" + img["gradient"] + "\">&#x26A1;</div>"


def source_logo(sid):
    return SOURCE_LOGOS.get(sid, "")


def extract_keywords(title, title_en=""):
    text = (title + " " + title_en).lower()
    # Extract English words
    words_en = re.findall(r"[a-z]{3,}", text)
    # Extract Chinese words (2-4 characters)
    words_cn = re.findall(r"[\u4e00-\u9fff]{2,5}", text)
    all_words = [w for w in words_en + words_cn if w not in STOP_WORDS]
    # Keep top meaningful words
    seen = set()
    result = []
    for w in all_words:
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result[:8]


def load_history(data_dir):
    """Load historical data from data directory."""
    dates = {}
    if not os.path.isdir(data_dir):
        return dates
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".json") and fname != "index.json":
            date = fname.replace(".json", "")
            try:
                datetime.strptime(date, "%Y-%m-%d")
                with open(os.path.join(data_dir, fname), "r", encoding="utf-8") as f:
                    dates[date] = json.load(f)
            except (ValueError, json.JSONDecodeError):
                continue
    return dates


def compute_trends(all_dates):
    """Compute keyword trends across dates."""
    keyword_daily = {}
    for date, items in all_dates.items():
        daily_kws = Counter()
        for item in items:
            for kw in item.get("keywords", []):
                daily_kws[kw] += 1
        keyword_daily[date] = dict(daily_kws.most_common(20))

    # Find top keywords overall
    all_kw = Counter()
    for items in all_dates.values():
        for item in items:
            for kw in item.get("keywords", []):
                all_kw[kw] += 1

    top_kws = [kw for kw, _ in all_kw.most_common(15)]

    # Build series
    sorted_dates = sorted(all_dates.keys())
    series = []
    for kw in top_kws:
        points = []
        for date in sorted_dates:
            points.append({"date": date, "value": keyword_daily.get(date, {}).get(kw, 0)})
        series.append({"keyword": kw, "points": points})

    return {"series": series, "dates": sorted_dates}


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
    os.makedirs(DATA_DIR, exist_ok=True)

    # Copy asset SVGs
    if os.path.isdir(ASSETS_SRC):
        for f in os.listdir(ASSETS_SRC):
            shutil.copy2(os.path.join(ASSETS_SRC, f), os.path.join(ASSETS_DST, f))

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Load historical data
    history = load_history(DATA_DIR)

    # Fetch NEW news
    print(f"Fetching news for {today}...")
    new_items = fetch_all()
    new_items = deduplicate(new_items)
    print(f"Got {len(new_items)} new items")

    # Extract keywords for new items
    for item in new_items:
        item["keywords"] = extract_keywords(item.get("title", ""), item.get("title_en", ""))

    # Store today's data
    history[today] = new_items
    with open(os.path.join(DATA_DIR, f"{today}.json"), "w", encoding="utf-8") as f:
        json.dump(new_items, f, ensure_ascii=False, indent=2)

    # Write data index
    all_dates_list = sorted(history.keys(), reverse=True)
    with open(os.path.join(DATA_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"dates": all_dates_list, "latest": today}, f, ensure_ascii=False)

    # Compute trends
    trends = compute_trends(history)
    with open(os.path.join(OUTPUT_DIR, "trends.json"), "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)

    # Build today's page
    grouped = categorize_items(new_items)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    env.filters["time_ago"] = time_ago
    env.globals["fallback_img"] = fallback_img
    env.globals["source_logo"] = source_logo

    template = env.get_template("index.html")
    html = template.render(
        items=new_items,
        grouped=grouped,
        badges=CATEGORY_BADGE,
        category_images=CATEGORY_IMAGES,
        today=today,
        update_time=update_time,
        category_order=CATEGORY_ORDER,
        all_dates=all_dates_list,
        trends=trends,
        translations_json=json.dumps(TRANSLATIONS, ensure_ascii=False),
    )

    index_file = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Written: {index_file}")
    print(f"Items: {len(new_items)}, History dates: {len(history)}")
    print("Done.")


if __name__ == "__main__":
    build()
