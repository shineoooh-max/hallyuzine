"""
parser.py - 해외 서버 차단 우회형 K-컬처 RSS 수집 엔진
"""

import re
import urllib.request
from urllib.parse import urlsplit, urlunsplit, quote
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
}

DOMESTIC_NOISE_KEYWORDS = [
    "방미심위", "방통위", "방심위", "심의", "과징금", "행정처분", "국정감사", "국회", "법안",
    "지자체", "군수", "시장", "도지사", "정부", "장관", "대통령", "정당", "선거",
    "합병", "인수", "지분", "주총", "영업이익", "실적", "공시", "상장", "유상증자", "주가",
    "부고", "별세", "빈소", "발인", "음주운전", "폭행", "소송", "기소", "구속", "징역", "사망"
]

DEFAULT_CATEGORY_IMAGES = {
    "music": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1200&q=80",
    "ott": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1200&q=80",
    "style": "https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=1200&q=80",
    "culture": "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=1200&q=80",
}


def tokenize_title(title: str) -> set[str]:
    clean = re.sub(r"\[.*?\]|\(.*?\)|[^가-힣a-zA-Z0-9\s]", " ", title.lower())
    return {w for w in clean.split() if len(w) >= 2}


def is_duplicate_topic(raw_title: str, existing_titles: list[str]) -> bool:
    new_tokens = tokenize_title(raw_title)
    if not new_tokens:
        return False
    for old_title in existing_titles[:40]:
        old_tokens = tokenize_title(old_title)
        if not old_tokens:
            continue
        overlap = len(new_tokens & old_tokens)
        ratio = overlap / min(len(new_tokens), len(old_tokens))
        if ratio >= 0.45 or overlap >= 3:
            return True
    return False


def encode_iri(url: str) -> str:
    parts = urlsplit(url)
    path = quote(parts.path, safe="/:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="=&?:@!$'()*+,;/-._~")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def fetch_xml(url: str, timeout: int = 12) -> str:
    safe_url = encode_iri(url)
    req = urllib.request.Request(safe_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(2_000_000)
        return raw.decode("utf-8", errors="ignore")


def extract_rss_image(item: ET.Element, desc_html: str, category: str) -> str:
    for elem in item.iter():
        tag = elem.tag.lower()
        if tag.endswith("content") or tag.endswith("thumbnail") or tag.endswith("enclosure"):
            img_url = elem.attrib.get("url", "")
            if img_url.startswith("http") and not any(x in img_url.lower() for x in ["logo", "icon", "avatar"]):
                return img_url

    if desc_html:
        soup = BeautifulSoup(desc_html, "html.parser")
        img = soup.find("img")
        if img and img.get("src", "").startswith("http"):
            src = img["src"]
            if not any(x in src.lower() for x in ["google", "gstatic", "logo", "icon"]):
                return src

    return DEFAULT_CATEGORY_IMAGES.get(category, DEFAULT_CATEGORY_IMAGES["culture"])


def fetch_rss_candidates(existing_urls: set, existing_titles: list[str], preferred_categories: list[str]) -> list[dict]:
    candidates = []
    seen_titles = list(existing_titles)

    cat_priority = {cat: idx for idx, cat in enumerate(preferred_categories)}
    sorted_feeds = sorted(config.RSS_FEEDS, key=lambda f: cat_priority.get(f["category"], 99))

    for feed in sorted_feeds:
        if len(candidates) >= 6:
            break

        category = feed["category"]
        rss_url = feed["url"]
        source_name = feed["source_name"]

        try:
            xml_data = fetch_xml(rss_url, timeout=12)
            root = ET.fromstring(xml_data)
        except Exception as e:
            print(f"[Parser] RSS 오류 ({source_name}): {e}", flush=True)
            continue

        items = root.findall(".//item")
        for item in items[:15]:
            if len(candidates) >= 6:
                break

            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            if title_el is None or link_el is None or not title_el.text:
                continue

            raw_title = re.sub(r"\s*-\s*[^-]+$", "", title_el.text.strip())
            link = link_el.text.strip()

            if link in existing_urls:
                continue

            if any(bad in raw_title for bad in DOMESTIC_NOISE_KEYWORDS):
                continue

            if is_duplicate_topic(raw_title, seen_titles):
                continue

            desc_raw = desc_el.text if (desc_el is not None and desc_el.text) else ""
            soup = BeautifulSoup(desc_raw, "html.parser")
            clean_desc = soup.get_text(" ", strip=True)
            raw_text = f"{raw_title}\n{clean_desc}".strip()

            if len(raw_text) < 25:
                continue

            image_url = extract_rss_image(item, desc_raw, category)

            print(f"[Parser] 후보 기사 확보 [{category.upper()}] ({source_name}): {raw_title}", flush=True)
            seen_titles.insert(0, raw_title)
            candidates.append({
                "category": category,
                "raw_title": raw_title,
                "source_url": link,
                "source_name": source_name,
                "raw_text": raw_text[:2500],
                "image_url": image_url,
                "image_credit": f"Editorial Visual / {source_name}"
            })

    return candidates
