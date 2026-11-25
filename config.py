"""
config.py - HALLYUZINE 핵심 환경설정 및 메타데이터
"""

# 1. 사이트 기본 정보
SITE_NAME = "HALLYUZINE"
SITE_TAGLINE = "The Global Broadsheet for K-Culture, Music & Screen Trends"
SITE_URL = "https://hallyuzine.pages.dev"
LANGUAGE = "en"

# 2. Gemini 모델 설정 (메인 모델 + 503 과부하 시 자동 폴백 모델)
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

# 3. 4대 핵심 카테고리 및 전용 서브페이지 파일명 매핑
CATEGORIES = {
    "music": {
        "label": "MUSIC",
        "slug": "music.html",
        "description": "K-POP comebacks, Billboard & Spotify chart breakdowns, and world tour coverage."
    },
    "ott": {
        "label": "OTT & FILM",
        "slug": "ott.html",
        "description": "Netflix & global OTT rankings, K-Drama casting, and Korean cinema insights."
    },
    "style": {
        "label": "STYLE",
        "slug": "style.html",
        "description": "Idol airport fashion decoded, luxury brand ambassadors, and K-Beauty trends."
    },
    "culture": {
        "label": "CULTURE",
        "slug": "culture.html",
        "description": "K-Drama filming locations, Seoul hotspots, and global fandom culture."
    }
}

# 4. 코리아타임스·한국경제 공식 연예/문화 RSS 피드
RSS_FEEDS = [
    {
        "category": "music",
        "url": "https://www.hankyung.com/feed/entertainment",
        "source_name": "Korea Economic Daily"
    },
    {
        "category": "ott",
        "url": "https://feed.koreatimes.co.kr/k/entertainment.xml",
        "source_name": "The Korea Times"
    },
    {
        "category": "style",
        "url": "https://www.hankyung.com/feed/life",
        "source_name": "Korea Economic Daily"
    },
    {
        "category": "culture",
        "url": "https://feed.koreatimes.co.kr/k/lifestyle.xml",
        "source_name": "The Korea Times"
    }
]

# 5. 구글 애드센스 설정
ADSENSE_CLIENT = "ca-pub-XXXXXXXXXXXXXXXX"
ADSENSE_SLOT_FACTBOX_BELOW = "1234567890"
ADSENSE_SLOT_SIDEBAR_FIXED = "2345678901"
ADSENSE_SLOT_MULTIPLEX_END = "3456789012"

# 6. 발행 및 빌드 제어
ITEMS_PER_RUN = 3
POSTS_META_PATH = "posts_meta.json"
DEBATE_META_PATH = "weekly_debate.json"
OUTPUT_DIR = "dist"
