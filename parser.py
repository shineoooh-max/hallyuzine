"""
parser.py - 국내 연예/엔터 RSS 수집 엔진 (og:image 직접 채택 버전)
"""

import urllib.request
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
}

BANNED_IMG_KEYWORDS = [
    "logo", "default", "noimage", "icon", "avatar"
]

# 해외 팬들에게 전혀 쓸모없는 기업 공시/행정/사건사고 키워드만 차단
DOMESTIC_NOISE_KEYWORDS = [
    "합병", "인수", "지분", "주총", "영업이익", "실적", "공시", "상장", "유상증자",
    "도서관", "지자체", "군수", "국회", "법안", "국정감사", "부고", "별세",
    "음주운전", "폭행", "소송", "기소", "구속", "징역"
]


def fetch_url(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(1_500_000)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("euc-kr", errors="ignore")


def extract_article_data(article_url: str, source_name: str) -> dict:
    try:
        html = fetch_url(article_url, timeout=8)
    except Exception as e:
        print(f"[Parser] 페이지 스킵 ({article_url}): {e}", flush=True)
        return {}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    clean_text = "\n".join([p for p in paragraphs if len(p) > 20])
    if len(clean_text) < 120:
        return {}

    og_img_tag = soup.find("meta", property="og:image")
    og_img = og_img_tag["content"].strip() if og_img_tag and og_img_tag.get("content") else ""

    if not og_img or not og_img.startswith("http"):
        return {}
    if any(bad in og_img.lower() for bad in BANNED_IMG_KEYWORDS):
        return {}

    return {
        "raw_text": clean_text[:3000],
        "image_url": og_img,
        "image_credit": f"Image via {source_name}"
    }


def fetch_rss_candidates(existing_urls: set) -> list[dict]:
    candidates = []
    target_limit = config.ITEMS_PER_RUN + 4

    for feed in config.RSS_FEEDS:
        if len(candidates) >= target_limit:
            break

        category = feed["category"]
        rss_url = feed["url"]
        source_name = feed["source_name"]

        try:
            xml_data = fetch_url(rss_url, timeout=8)
            root = ET.fromstring(xml_data)
        except Exception as e:
            print(f"[Parser] RSS 오류 ({source_name}): {e}", flush=True)
            continue

        items = root.findall(".//item")
        for item in items[:20]:
            if len(candidates) >= target_limit:
                break

            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is None or link_el is None:
                continue

            raw_title = title_el.text.strip()
            link = link_el.text.strip()

            if link in existing_urls:
                continue

            if any(bad in raw_title for bad in DOMESTIC_NOISE_KEYWORDS):
                continue

            detail = extract_article_data(link, source_name)
            if not detail:
                continue

            print(f"[Parser] 후보 기사 확보 ({source_name}): {raw_title}", flush=True)
            candidates.append({
                "category": category,
                "raw_title": raw_title,
                "source_url": link,
                "source_name": source_name,
                "raw_text": detail["raw_text"],
                "image_url": detail["image_url"],
                "image_credit": detail["image_credit"]
            })

    return candidates
