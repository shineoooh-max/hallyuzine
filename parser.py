"""
parser.py - K-컬처 전용 RSS 수집 엔진 (노이즈 차단 + 중복 방지 + 리다이렉트 추적)
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
    "logo", "default", "noimage", "icon", "avatar", "google", "gstatic"
]

# 1차 차단: 한국 내수 행정/방송심의/정치/기업공시/사건사고 키워드
DOMESTIC_NOISE_KEYWORDS = [
    "방미심위", "방통위", "방심위", "심의", "과징금", "행정처분", "국정감사", "국회", "법안",
    "지자체", "군수", "시장", "도지사", "정부", "장관", "대통령", "정당", "선거",
    "합병", "인수", "지분", "주총", "영업이익", "실적", "공시", "상장", "유상증자", "주가",
    "부고", "별세", "빈소", "발인", "음주운전", "폭행", "소송", "기소", "구속", "징역", "사망"
]

# 2차 검증: 해외 한류 독자 관심 키워드 (최소 1개 이상 포함 필수)
HALLYU_REQUIRED_KEYWORDS = [
    "컴백", "신곡", "앨범", "빌보드", "스포티파이", "차트", "콘서트", "월드투어", "팬미팅", "아이돌", "케이팝", "k-pop", "kpop",
    "넷플릭스", "디즈니", "티빙", "쿠팡플레이", "드라마", "영화", "예능", "시청률", "박스오피스", "칸", "오스카", "에미", "주연", "캐스팅",
    "화보", "공항패션", "패션위크", "앰버서더", "뷰티", "브랜드", "컬렉션", "메이크업", "스타일",
    "성수", "팝업", "한류", "서울", "전시", "페스티벌", "웹툰", "애니", "글로벌", "해외"
]


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


def fetch_url_with_final(url: str, timeout: int = 10) -> tuple[str, str]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        raw = resp.read(1_500_000)
        try:
            return raw.decode("utf-8"), final_url
        except UnicodeDecodeError:
            return raw.decode("euc-kr", errors="ignore"), final_url


def extract_article_data(article_url: str, source_name: str) -> dict:
    try:
        html, final_url = fetch_url_with_final(article_url, timeout=10)
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
        "final_url": final_url,
        "raw_text": clean_text[:3000],
        "image_url": og_img,
        "image_credit": f"Photo via {source_name}"
    }


def fetch_rss_candidates(existing_urls: set, existing_titles: list[str], preferred_categories: list[str]) -> list[dict]:
    candidates = []
    seen_titles = list(existing_titles)

    # 기사 수가 적은 카테고리 순서대로 피드 우선 정렬
    cat_priority = {cat: idx for idx, cat in enumerate(preferred_categories)}
    sorted_feeds = sorted(config.RSS_FEEDS, key=lambda f: cat_priority.get(f["category"], 99))

    for feed in sorted_feeds:
        if len(candidates) >= 6:
            break

        category = feed["category"]
        rss_url = feed["url"]
        source_name = feed["source_name"]

        try:
            xml_data, _ = fetch_url_with_final(rss_url, timeout=10)
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
            if title_el is None or link_el is None:
                continue

            raw_title = re.sub(r"\s*-\s*[^-]+$", "", title_el.text.strip())
            link = link_el.text.strip()

            if link in existing_urls:
                continue

            # 1차 노이즈 차단
            if any(bad in raw_title for bad in DOMESTIC_NOISE_KEYWORDS):
                continue

            # 2차 한류 핵심 키워드 포함 여부 확인
            title_lower = raw_title.lower()
            if not any(kw in title_lower for kw in HALLYU_REQUIRED_KEYWORDS):
                continue

            # 3차 제목 유사도 중복 차단
            if is_duplicate_topic(raw_title, seen_titles):
                print(f"[Parser] 중복 이슈 스킵: {raw_title}", flush=True)
                continue

            detail = extract_article_data(link, source_name)
            if not detail or detail["final_url"] in existing_urls:
                continue

            print(f"[Parser] 후보 기사 확보 [{category.upper()}]: {raw_title}", flush=True)
            seen_titles.insert(0, raw_title)
            candidates.append({
                "category": category,
                "raw_title": raw_title,
                "source_url": detail["final_url"],
                "source_name": source_name,
                "raw_text": detail["raw_text"],
                "image_url": detail["image_url"],
                "image_credit": detail["image_credit"]
            })

    return candidates
