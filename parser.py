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

CATEGORY_KEYWORDS = {
    "music": [
        "케이팝", "k-pop", "kpop", "아이돌", "걸그룹", "보이그룹", "음반", "앨범", "신곡",
        "컴백", "빌보드", "스포티파이", "콘서트", "월드투어", "투어", "뮤직비디오", "음원",
        "차트", "가수", "싱어송라이터", "밴드", "힙합", "페스티벌", "데뷔", "팬미팅", "버추얼",
        "album", "comeback", "billboard", "spotify", "concert", "tour", "single", "idol", "singer", "band", "music"
    ],
    "ott": [
        "넷플릭스", "디즈니+", "디즈니플러스", "티빙", "쿠팡플레이", "웨이브", "드라마", "영화",
        "박스오피스", "배우", "주연", "개봉", "시사회", "영화제", "영화상", "청룡", "백상",
        "시청률", "시리즈", "예능", "방송", "극장", "오스카", "칸", "어벤져스",
        "netflix", "disney", "drama", "film", "movie", "cinema", "box office", "actor", "actress", "series", "cast", "premiere"
    ],
    "style": [
        "패션", "화보", "공항패션", "앰버서더", "앰배서더", "명품", "브랜드", "컬렉션", "패션위크",
        "뷰티", "화장품", "메이크업", "스킨케어", "올리브영", "스타일링", "룩북", "런웨이", "모델", "향수", "주얼리",
        "fashion", "beauty", "luxury", "ambassador", "couture", "runway", "style", "skincare", "makeup", "cosmetic", "brand"
    ],
    "culture": [
        "성수", "팝업", "팝업스토어", "전시", "박물관", "미술관", "한류", "k-컬처", "k컬처",
        "서울", "여행", "관광", "한식", "푸드", "카페", "디저트", "축제", "전통", "사찰", "책", "출판", "라이프스타일",
        "seoul", "popup", "pop-up", "exhibition", "museum", "hallyu", "k-culture", "culture", "food", "cuisine", "travel", "lifestyle", "mindfulness"
    ],
}


def classify_category(title: str, body: str) -> str:
    title_l = title.lower()
    body_l = body.lower()
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title_l:
                scores[cat] += 2
            elif kw in body_l:
                scores[cat] += 1
    best_cat = max(scores, key=lambda c: scores[c])
    return best_cat if scores[best_cat] > 0 else "culture"


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


def clean_source_name(source_name: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", "", source_name or "").strip() or "HALLYUZINE"


def _normalize_img_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def _is_valid_press_image(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    low = url.lower()
    blocked = [
        "logo", "icon", "avatar", "pixel", "default", "banner", "ads/", "ad_",
        "btn_", "sprite", "blank", "share", "sns", "profile", "reporter",
        "journalist", "google", "gstatic", "gravatar", ".svg", ".gif", "1x1",
        "noimage", "no_image", "placeholder", "loading"
    ]
    return not any(b in low for b in blocked)


def extract_article_images(article_url: str, max_images: int = 5, timeout: int = 10) -> list[str]:
    if not article_url:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def add_url(raw_url: str) -> None:
        if len(found) >= max_images:
            return
        u = _normalize_img_url(raw_url)
        if not _is_valid_press_image(u):
            return
        key = u.split("?")[0]
        if key not in seen:
            seen.add(key)
            found.append(u)

    try:
        safe_url = encode_iri(article_url)
        req = urllib.request.Request(safe_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(700_000).decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        # 1. 대표 메타 이미지 (og:image, twitter:image) 우선 확보
        for attr_name, attr_val in [("property", "og:image"), ("name", "twitter:image")]:
            meta = soup.find("meta", attrs={attr_name: attr_val})
            if meta and meta.get("content"):
                add_url(meta["content"])

        # 2. 본문 영역 내 고화질 보도사진 추가 수집 (최대 max_images장)
        body_selectors = [
            "#articletxt", ".article-body", ".article_txt", ".view_con",
            ".news-view", "article", "main"
        ]
        containers = []
        for sel in body_selectors:
            el = soup.select_one(sel)
            if el is not None:
                containers.append(el)
                break
        if not containers:
            containers = [soup]

        for container in containers:
            for img in container.find_all("img"):
                if len(found) >= max_images:
                    break
                src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
                # 작은 아이콘/썸네일 크기 속성 제외
                w_attr = str(img.get("width", "")).replace("px", "").strip()
                h_attr = str(img.get("height", "")).replace("px", "").strip()
                if w_attr.isdigit() and int(w_attr) < 180:
                    continue
                if h_attr.isdigit() and int(h_attr) < 120:
                    continue
                add_url(src)
    except Exception as e:
        print(f"[Parser] 원문 이미지 추출 실패 ({article_url}): {e}", flush=True)

    return found


def extract_rss_images(item: ET.Element, body_html: str, category: str, article_url: str = "", max_images: int = 5) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()

    def add_url(raw_url: str) -> None:
        if len(images) >= max_images:
            return
        u = _normalize_img_url(raw_url)
        if not _is_valid_press_image(u):
            return
        key = u.split("?")[0]
        if key not in seen:
            seen.add(key)
            images.append(u)

    for elem in item.iter():
        tag = elem.tag.lower()
        if tag.endswith("content") or tag.endswith("thumbnail") or tag.endswith("enclosure"):
            add_url(elem.attrib.get("url", ""))

    if body_html:
        soup = BeautifulSoup(body_html, "html.parser")
        for img in soup.find_all("img"):
            add_url(img.get("src", ""))

    if len(images) < max_images and article_url:
        for img_u in extract_article_images(article_url, max_images=max_images):
            add_url(img_u)

    if not images:
        images.append(DEFAULT_CATEGORY_IMAGES.get(category, DEFAULT_CATEGORY_IMAGES["culture"]))

    return images


def fetch_rss_candidates(existing_urls: set, existing_titles: list[str], preferred_categories: list[str]) -> list[dict]:
    raw_candidates = []
    seen_titles = list(existing_titles)

    for feed in config.RSS_FEEDS:
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
            if feed_picked >= 6:
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

            category = classify_category(raw_title, clean_desc)
            seen_titles.insert(0, raw_title)
            raw_candidates.append({
                "item": item,
                "desc_raw": desc_raw,
                "category": category,
                "raw_title": raw_title,
                "source_url": link,
                "source_name": source_name,
                "raw_text": raw_text[:2500],
            })
            feed_picked += 1

    # 부족한 카테고리 우선순위로 정렬 후 상위 8건에 대해 이미지 추출
    cat_priority = {cat: idx for idx, cat in enumerate(preferred_categories)}
    raw_candidates.sort(key=lambda c: cat_priority.get(c["category"], 99))

    candidates = []
    for rc in raw_candidates[:8]:
        image_urls = extract_rss_images(rc["item"], rc["desc_raw"], rc["category"], rc["source_url"], max_images=5)
        clean_src = clean_source_name(rc["source_name"])
        print(
            f"[Parser] 후보 확보 [{rc['category'].upper()}] ({clean_src}): {rc['raw_title']} | IMGS({len(image_urls)}): {image_urls[0]}",
            flush=True,
        )
        candidates.append({
            "category": rc["category"],
            "raw_title": rc["raw_title"],
            "source_url": rc["source_url"],
            "source_name": clean_src,
            "raw_text": rc["raw_text"],
            "image_url": image_urls[0],
            "image_urls": image_urls,
            "image_credit": f"(Photo: {clean_src})"
        })

    return candidates
