"""
parser.py - 글로벌 K-컬처 전용 정밀 필터 및 저작권 안전 이미지 판별 엔진
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

# 공식 배포 사진 판별 패턴 (괄호/대괄호 포함: [사진제공=하이브], (제공=넷플릭스) 등)
OFFICIAL_CREDIT_PATTERN = re.compile(
    r"(?:사진\s*제공|자료\s*제공|제공|사진)\s*[=:]\s*([가-힣A-Za-z0-9\s\(\)·&\-\+]{2,25})"
)

# 해외 독자 타깃 글로벌 한류 필수 키워드 (최소 1개 이상 포함 필수)
GLOBAL_HALLYU_KEYWORDS = [
    "가요", "아이돌", "그룹", "솔로", "컴백", "앨범", "싱글", "음원", "차트", "빌보드", "스포티파이",
    "콘서트", "월드투어", "팬미팅", "뮤직비디오", "티저", "엔터", "하이브", "SM", "JYP", "YG",
    "드라마", "배우", "영화", "감독", "넷플릭스", "디즈니", "티빙", "쿠팡플레이", "칸", "오스카",
    "예능", "화보", "앰버서더", "패션", "뷰티", "한류", "K팝", "K-팝", "케이팝", "방탄", "블랙핑크"
]

# 내수용 B2B 기업/행정 노이즈 차단 키워드
DOMESTIC_NOISE_KEYWORDS = [
    "합병", "인수", "지분", "주총", "영업이익", "실적", "공시", "상장", "유상증자",
    "도서관", "지자체", "군수", "시장", "국회", "법안", "국정감사", "부고", "별세",
    "열애설", "결별", "논란", "사과문", "음주", "폭행", "소송", "기소"
]


def fetch_url(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(1_500_000)
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

    full_text = soup.get_text(" ", strip=True)
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    clean_text = "\n".join([p for p in paragraphs if len(p) > 25])
    if len(clean_text) < 180:
        return {}

    og_img_tag = soup.find("meta", property="og:image")
    og_img = og_img_tag["content"].strip() if og_img_tag and og_img_tag.get("content") else ""

    if not og_img or any(bad in og_img.lower() for bad in BANNED_IMG_KEYWORDS):
        return {}

    credit_match = OFFICIAL_CREDIT_PATTERN.search(full_text)
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
    target_limit = config.ITEMS_PER_RUN + 3

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
        for item in items[:30]:
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

            # 1차 방어: 내수 기업/가십 차단
            if any(bad in raw_title for bad in DOMESTIC_NOISE_KEYWORDS):
                continue

            # 2차 방어: 글로벌 한류 핵심 키워드 포함 여부 검증
            if not any(kw in raw_title for kw in GLOBAL_HALLYU_KEYWORDS):
                continue

            detail = extract_safe_article_data(link)
            if not detail:
                continue

            print(f"[Parser] 글로벌 한류 기사 확보: {raw_title}", flush=True)
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
