"""
parser.py - 한국 실시간 K-컬처 Google News RSS 수집 엔진
"""

import re
import urllib.request
from urllib.parse import urlsplit, urlunsplit, quote
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 한국 내수 행정, 사건사고, 가십 논란, 프로스포츠 노이즈 2차 차단
NOISE_KEYWORDS = [
    "방미심위", "방통위", "방심위", "심의", "과징금", "행정처분", "국정감사", "국회", "법안",
    "지자체", "군수", "시장", "도지사", "정부", "장관", "대통령", "정당", "선거",
    "합병", "인수", "지분", "주총", "영업이익", "실적", "공시", "상장", "유상증자", "주가",
    "부고", "별세", "빈소", "발인", "음주운전", "폭행", "소송", "기소", "구속", "징역", "사망",
    "고발", "논란", "경호원", "밀쳐", "내동댕이", "갑질", "혐의", "경찰", "검찰",
    "야구", "축구", "농구", "배구", "골프", "감독", "2군", "프로야구", "kbo", "epl", "손흥민",
    "운세", "별자리", "띠별", "로또", "날씨", "기상청"
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
    for old_title in existing_titles[:50]:
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
        raw = resp.read(2_500_000)
        return raw.decode("utf-8", errors="ignore")


def extract_og_image(article_url: str, timeout: int = 8) -> str | None:
    if not article_url:
        return None
    try:
        safe_url = encode_iri(article_url)
        req = urllib.request.Request(safe_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(500_000).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        for attr_name, attr_val in [("property", "og:image"), ("name", "twitter:image")]:
            meta = soup.find("meta", attrs={attr_name: attr_val})
            if meta and meta.get("content"):
                img_url = meta["content"].strip()
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                if img_url.startswith("http") and not any(
                    x in img_url.lower() for x in ["logo", "icon", "avatar", "pixel", "default"]
                ):
                    return img_url
    except Exception as e:
        print(f"[Parser] og:image 추출 실패 ({article_url}): {e}", flush=True)
    return None


def extract_rss_image(item: ET.Element, body_html: str, category: str, article_url: str = "") -> str:
    for elem in item.iter():
        tag = elem.tag.lower()
        if tag.endswith("content") or tag.endswith("thumbnail") or tag.endswith("enclosure"):
            img_url = elem.attrib.get("url", "")
            if img_url.startswith("http") and not any(x in img_url.lower() for x in ["logo", "icon", "avatar", "pixel"]):
                return img_url

    if body_html:
        soup = BeautifulSoup(body_html, "html.parser")
        for img in soup.find_all("img"):
            src = img.get("src", "").strip()
            if src.startswith("http") and not any(x in src.lower() for x in ["google", "gstatic", "logo", "icon", "gravatar", "pixel"]):
                return src

    og_img = extract_og_image(article_url)
    if og_img:
        return og_img

    return DEFAULT_CATEGORY_IMAGES.get(category, DEFAULT_CATEGORY_IMAGES["culture"])


def fetch_rss_candidates(existing_urls: set, existing_titles: list[str], preferred_categories: list[str]) -> list[dict]:
    candidates = []
    seen_titles = list(existing_titles)

    cat_priority = {cat: idx for idx, cat in enumerate(preferred_categories)}
    sorted_feeds = sorted(config.RSS_FEEDS, key=lambda f: cat_priority.get(f["category"], 99))

    for feed in sorted_feeds:
        if len(candidates) >= 10:
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
        feed_picked = 0
        for item in items[:20]:
            # 피드당 최대 4건, 전체 최대 10건 확보
            if feed_picked >= 4 or len(candidates) >= 10:
                break

            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            if title_el is None or link_el is None or not title_el.text:
                continue

            raw_title = re.sub(r"\s+-\s+[^-]+$", "", title_el.text.strip())
            link = link_el.text.strip()

            if link in existing_urls:
                continue

            title_lower = raw_title.lower()
            if any(bad in title_lower for bad in NOISE_KEYWORDS):
                continue

            if is_duplicate_topic(raw_title, seen_titles):
                continue

            desc_raw = desc_el.text if (desc_el is not None and desc_el.text) else ""
            soup = BeautifulSoup(desc_raw, "html.parser")
            clean_desc = soup.get_text(" ", strip=True)
            raw_text = f"{raw_title}\n{clean_desc}".strip()

            if len(raw_text) < 25:
                continue

            image_url = extract_rss_image(item, desc_raw, category, link)

            print(f"[Parser] 후보 확보 [{category.upper()}] ({source_name}): {raw_title} | IMG: {image_url}", flush=True)
            seen_titles.insert(0, raw_title)
            candidates.append({
                "category": category,
                "raw_title": raw_title,
                "source_url": link,
                "source_name": source_name,
                "raw_text": raw_text[:2500],
                "image_url": image_url,
                "image_credit": f"Photo via {source_name}"
            })
            feed_picked += 1

    return candidates
