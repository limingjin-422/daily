import feedparser
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

USER_AGENT = "DailyBrief/1.0 (news aggregator; +https://github.com/your-username/news-site)"

HEADERS = {"User-Agent": USER_AGENT}

CATEGORY_KEYWORDS = {
    "AI": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "llm", "gpt", "claude", "gemini", "openai", "anthropic", "google ai",
        "neural", "transformer", "大模型", "人工智能", "机器学习", "深度学习",
        "gpt", "ai 模型", "chatgpt", "智能",
    ],
    "科技": [
        "tech", "apple", "google", "microsoft", "meta", "amazon", "tesla",
        "芯片", "半导体", "foldable", "space", "robot", "quantum", "startup",
        "iphone", "vision pro", "脑机", "bci", "超算", "supercomputer",
    ],
}

CATEGORY_KEYWORDS["综合"] = []


def categorize(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if cat == "综合":
            continue
        for kw in kws:
            if kw.lower() in text:
                return cat
    return "综合"


def parse_time(t_str: Optional[str]) -> Optional[str]:
    if not t_str:
        return None
    try:
        dt = feedparser._parse_date(t_str)
        if dt:
            return datetime(*dt[:6], tzinfo=timezone.utc).isoformat()
    except Exception:
        pass
    return None


def time_ago(iso_str: Optional[str]) -> str:
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
            return f"{int(delta.total_seconds() // 60)} 分钟前"
        if h < 24:
            return f"{h} 小时前"
        d = h // 24
        return f"{d} 天前"
    except Exception:
        return ""


def _fetch_json(url: str, timeout: int = 15):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _fetch_feed(url: str, timeout: int = 15):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return feedparser.parse(r.text)


# ----------------------------------------------------------------
# Source fetchers
# ----------------------------------------------------------------

def fetch_hackernews(max_items: int = 10):
    """Fetch top stories from Hacker News API."""
    items = []
    try:
        top_ids = _fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:max_items]
        for sid in top_ids:
            try:
                story = _fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
                if not story or story.get("type") != "story" or story.get("title") is None:
                    continue
                items.append({
                    "title": story["title"],
                    "title_en": story["title"],
                    "url": story.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "summary": "",
                    "source": "Hacker News",
                    "source_id": "hackernews",
                    "category": categorize(story["title"], story.get("text", "")),
                    "image_url": None,
                    "has_video": False,
                    "published": parse_time(story.get("time") and datetime.fromtimestamp(story["time"], tz=timezone.utc).isoformat()),
                })
            except Exception as e:
                log.warning(f"HN item {sid} failed: {e}")
    except Exception as e:
        log.error(f"HN top stories failed: {e}")
    log.info(f"Hacker News: {len(items)} items")
    return items


def fetch_techcrunch(max_items: int = 10):
    """Fetch from TechCrunch RSS."""
    items = []
    try:
        feed = _fetch_feed("https://techcrunch.com/feed/")
        for entry in feed.entries[:max_items]:
            img = _rss_image(entry)
            items.append({
                "title": entry.get("title", ""),
                "title_en": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": _clean_html(entry.get("summary", "")),
                "source": "TechCrunch",
                "source_id": "techcrunch",
                "category": categorize(entry.get("title", ""), entry.get("summary", "")),
                "image_url": img,
                "has_video": "youtube" in entry.get("link", "").lower() or bool(entry.get("media_player")),
                "published": parse_time(entry.get("published")),
            })
    except Exception as e:
        log.error(f"TechCrunch failed: {e}")
    log.info(f"TechCrunch: {len(items)} items")
    return items


def fetch_jiqizhixin(max_items: int = 10):
    """Fetch from 机器之心 RSS."""
    items = []
    try:
        feed = _fetch_feed("https://www.jiqizhixin.com/rss")
        for entry in feed.entries[:max_items]:
            img = _rss_image(entry)
            items.append({
                "title": entry.get("title", ""),
                "title_en": _extract_en_title(entry.get("title", "")),
                "url": entry.get("link", ""),
                "summary": _clean_html(entry.get("summary", "")),
                "source": "机器之心",
                "source_id": "jiqizhixin",
                "category": "AI",
                "image_url": img,
                "has_video": False,
                "published": parse_time(entry.get("published")),
            })
    except Exception as e:
        log.error(f"机器之心 failed: {e}")
    log.info(f"机器之心: {len(items)} items")
    return items


def fetch_reuters_tech(max_items: int = 10):
    """Fetch from Reuters Technology RSS."""
    items = []
    try:
        feed = _fetch_feed("https://www.reutersagency.com/feed/?taxonomy=industry&post_type=bureau&industry=tech")
        if not feed.entries:
            feed = _fetch_feed("https://www.reuters.com/tools/rss/technology-news")
        for entry in feed.entries[:max_items]:
            img = _rss_image(entry)
            items.append({
                "title": entry.get("title", ""),
                "title_en": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": _clean_html(entry.get("summary", "")),
                "source": "Reuters",
                "source_id": "reuters",
                "category": categorize(entry.get("title", ""), entry.get("summary", "")),
                "image_url": img,
                "has_video": False,
                "published": parse_time(entry.get("published")),
            })
    except Exception as e:
        log.error(f"Reuters failed: {e}")
    log.info(f"Reuters: {len(items)} items")
    return items


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _rss_image(entry) -> Optional[str]:
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            url = m.get("url", "")
            if url and ("jpg" in url.lower() or "png" in url.lower() or "jpeg" in url.lower()):
                return url
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    return None


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


def _extract_en_title(title: str) -> str:
    m = re.search(r"[A-Za-z][A-Za-z\s\-\.\,\/\(\)\:]+", title)
    return m.group(0).strip() if m else ""


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------

SOURCES = {
    "hackernews": fetch_hackernews,
    "techcrunch": fetch_techcrunch,
    "jiqizhixin": fetch_jiqizhixin,
    "reuters": fetch_reuters_tech,
}


def fetch_all(max_per_source: int = 10) -> list[dict]:
    all_items = []
    for name, fn in SOURCES.items():
        log.info(f"Fetching {name}...")
        try:
            items = fn(max_per_source)
            all_items.extend(items)
        except Exception as e:
            log.error(f"{name} crashed: {e}")
        time.sleep(1)
    return all_items


def deduplicate(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = item["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


if __name__ == "__main__":
    news = fetch_all()
    news = deduplicate(news)
    print(json.dumps(news, ensure_ascii=False, indent=2))
