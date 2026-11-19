"""
parser.py - 국내 공식 소스 수집 및 저작권 안전 이미지 판별 엔진
"""

import re
import urllib.parse
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

# 언론사 기본 로고/배너 등 저품질 썸네일 차단 키워드
BANNED_IMG_KEYWORDS = [
    "logo", "banner", "default", "noimage", "watermark",
    "icon", "avatar", "sns_", "share", "btn_"
]

# 공식 배포 사진 판별 패턴 (예: 사진제공=하이브, 사진=넷플릭스, 제공=SM엔터테인먼트)
OFFICIAL_CREDIT_PATTERN = re.compile(
    r"(?:사진\s*제공|자료\s*제공|제공|사진)\s*[=:]\s*([가-힣A-Za-z0-9\s\(\)·&\-\+]{2,25})"
)


def fetch_url(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("euc-kr", errors="ignore")


def search_youtube_thumbnail(query: str) -> tuple[str, str]:
    """
    공식 배포 사진이 없을 경우 유튜브 검색에서 공식 영상 ID를 추출해
    저작권 분쟁 없는 1280x720 고화질 썸네일(maxresdefault.jpg)을 반환합니다.
    """
    try:
        encoded_q = urllib.parse.quote(f"{query} official")
        search_url = f"https://www.youtube.com/results?search_query={encoded_q}"
        html = fetch_url(search_url, timeout=10)
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        if video_ids:
            vid = video_ids[0]
            thumb_url = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
            return thumb_url, "Image Courtesy of Official YouTube Channel"
    except Exception:
        pass
    return "", ""


def extract_safe_article_data(article_url: str, raw_title: str) -> dict:
    """
    원문 페이지에서 본문 텍스트를 정제하고,
    공식 배포 사진(사진제공=) 여부를 검증하여 안전한 이미지만 채택합니다.
    """
    try:
        html = fetch_url(article_url)
    except Exception as e:
        print(f"[Parser] 페이지 로드 실패 ({article_url}): {e}")
        return {}

    soup = BeautifulSoup(html, "html.parser")

    # 불필요 태그 제거
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    # 본문 텍스트 추출
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    clean_text = "\n".join([p for p in paragraphs if len(p) > 25])
    if len(clean_text) < 180:
        return {}

    # 1단계: 공식 배포 사진(사진제공=기획사/방송사) 여부 검증
    image_url = ""
    image_credit = ""

    og_img_tag = soup.find("meta", property="og:image")
    og_img = og_img_tag["content"].strip() if og_img_tag and og_img_tag.get("content") else ""

    credit_match = OFFICIAL_CREDIT_PATTERN.search(clean_text)
    if og_img and credit_match:
        provider = credit_match.group(1).strip()
        # '기자'가 포함된 취재 직찍 사진은 원천 배제
        if "기자" not in provider and not any(bad in og_img.lower() for bad in BANNED_IMG_KEYWORDS):
            image_url = og_img
            image_credit = f"Photo Courtesy of {provider}"

    # 2단계: 공식 배포 사진이 없다면 공식 유튜브 썸네일로 안전 대체
    if not image_url:
        yt_img, yt_credit = search_youtube_thumbnail(raw_title)
        if yt_img:
            image_url = yt_img
            image_credit = yt_credit

    # 안전한 이미지를 끝내 확보하지 못한 기사는 저작권 보호를 위해 건너뜀
    if not image_url:
        return {}

    return {
        "raw_text": clean_text[:3500],
        "image_url": image_url,
        "image_credit": image_credit
    }


def fetch_rss_candidates(existing_urls: set) -> list[dict]:
    """
    config.py에 등록된 국내 공식 RSS 피드에서 신규 기사 후보를 수집합니다.
    """
    candidates = []

    for feed in config.RSS_FEEDS:
        category = feed["category"]
        rss_url = feed["url"]
        source_name = feed["source_name"]

        try:
            xml_data = fetch_url(rss_url)
            root = ET.fromstring(xml_data)
        except Exception as e:
            print(f"[Parser] RSS 로드 오류 ({source_name}): {e}")
            continue

        items = root.findall(".//item")
        for item in items[:12]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")

            if title_el is None or link_el is None:
                continue

            raw_title = title_el.text.strip()
            link = link_el.text.strip()
            pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

            if link in existing_urls:
                continue

            # 가십/사건사고성 키워드 1차 필터링 (에디토리얼 품격 유지)
            skip_keywords = ["열애설", "결별", "논란", "사과문", "음주", "폭행", "소송", "부고", "별세"]
            if any(kw in raw_title for kw in skip_keywords):
                continue

            detail = extract_safe_article_data(link, raw_title)
            if not detail:
                continue

            candidates.append({
                "category": category,
                "raw_title": raw_title,
                "source_url": link,
                "source_name": source_name,
                "pub_date": pub_date,
                "raw_text": detail["raw_text"],
                "image_url": detail["image_url"],
                "image_credit": detail["image_credit"]
            })

    return candidates
