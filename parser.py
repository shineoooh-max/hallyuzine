"""
parser.py - 국내 공식 소스 초고속 수집 및 저작권 안전 이미지 필터 엔진
"""

import re
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
    "logo", "banner", "default", "noimage", "watermark",
    "icon", "avatar", "sns_", "share", "btn_", "reporter"
]

OFFICIAL_CREDIT_PATTERN = re.compile(
    r"(?:사진\s*제공|자료\s*제공|제공|사진)\s*[=:]\s*([가-힣A-Za-z0-9\s\(\)·&\-\+]{2,25})"
)


def fetch_url(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(500_000)  # 최대 500KB만 읽어 무한 대기 원천 차단
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("euc-kr", errors="ignore")


def extract_safe_article_data(article_url: str) -> dict:
    try:
        html = fetch_url(article_url, timeout=8)
    except Exception as e:
        print(f"[Parser] 페이지 스킵 ({article_url}): {e}", flush=True)
        return {}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    clean_text = "\n".join([p for p in paragraphs if len(p) > 25])
    if len(clean_text) < 180:
        return {}

    og_img_tag = soup.find("meta", property="og:image")
    og_img = og_img_tag["content"].strip() if og_img_tag and og_img_tag.get("content") else ""

    if not og_img or any(bad in og_img.lower() for bad in BANNED_IMG_KEYWORDS):
        return {}

    # 공식 배포 사진(사진제공=기획사/방송사) 여부 검증
    credit_match = OFFICIAL_CREDIT_PATTERN.search(clean_text)
    if not credit_match:
        return {}

    provider = credit_match.group(1).strip()
    if "기자" in provider:
        return {}

    return {
        "raw_text": clean_text[:3000],
        "image_url": og_img,
        "image_credit": f"Photo Courtesy of {provider}"
    }


def fetch_rss_candidates(existing_urls: set) -> list[dict]:
    candidates = []
    target_limit = config.ITEMS_PER_RUN + 2  # 필요한 개수(4+2=6건)만 모이면 즉시 수집 종료

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
        for item in items[:15]:
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

            skip_keywords = ["열애설", "결별", "논란", "사과문", "음주", "폭행", "소송", "부고", "별세"]
            if any(kw in raw_title for kw in skip_keywords):
                continue

            detail = extract_safe_article_data(link)
            if not detail:
                continue

            print(f"[Parser] 유효 기사 확보: {raw_title}", flush=True)
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
