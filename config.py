"""
config.py - HALLYUZINE 핵심 환경설정 및 메타데이터
"""

# 1. 사이트 기본 정보
SITE_NAME = "HALLYUZINE"
SITE_TAGLINE = "The Global Editorial Magazine for K-Culture & Pop Trends"
SITE_URL = "https://hallyuzine.koo1000.com"
LANGUAGE = "en"

# 2. Gemini 모델 설정
GEMINI_MODEL = "gemini-3.8-flash"

# 3. 4대 핵심 카테고리 및 전용 서브페이지 파일명 매핑
CATEGORIES = {
    "music": {
        "label": "MUSIC & CHARTS",
        "slug": "music.html",
        "description": "K-POP comebacks, Billboard & Spotify chart breakdowns, and world tour coverage."
    },
    "ott": {
        "label": "SCREEN & OTT",
        "slug": "ott.html",
        "description": "Netflix & global OTT rankings, K-Drama casting, and Korean cinema insights."
    },
    "style": {
        "label": "STYLE & GLAM",
        "slug": "style.html",
        "description": "Idol airport fashion decoded, luxury brand ambassadors, and K-Beauty trends."
    },
    "culture": {
        "label": "CULTURE & SPOTS",
        "slug": "culture.html",
        "description": "K-Drama filming locations, Seoul hotspots, and global fandom culture."
    }
}

# 4. 국내 주요 연예/엔터 공식 RSS 피드
RSS_FEEDS = [
    {
        "category": "music",
        "url": "https://www.yna.co.kr/rss/entertainment.xml",
        "source_name": "Yonhap Entertainment"
    },
    {
        "category": "ott",
        "url": "https://rss.donga.com/enter.xml",
        "source_name": "Sports Donga Entertainment"
    },
    {
        "category": "style",
        "url": "https://www.hankyung.com/feed/entertainment",
        "source_name": "Hankyung Entertainment"
    },
    {
        "category": "culture",
        "url": "https://www.khan.co.kr/rss/rssdata/culture_news.xml",
        "source_name": "Kyunghyang Culture"
    }
]

# 5. 구글 애드센스 설정
ADSENSE_CLIENT = "ca-pub-XXXXXXXXXXXXXXXX"
ADSENSE_SLOT_FACTBOX_BELOW = "1234567890"
ADSENSE_SLOT_SIDEBAR_FIXED = "2345678901"
ADSENSE_SLOT_MULTIPLEX_END = "3456789012"

# 6. 발행 및 빌드 제어
ITEMS_PER_RUN = 2
POSTS_META_PATH = "posts_meta.json"
OUTPUT_DIR = "dist"
