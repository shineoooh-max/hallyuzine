"""
config.py - HALLYUZINE 핵심 환경설정 및 메타데이터
"""

# 1. 사이트 기본 정보 (추후 hallyuzine.com 연결 시 변경)
SITE_NAME = "HALLYUZINE"
SITE_TAGLINE = "The Global Broadsheet for K-Culture, Music & Screen Trends"
SITE_URL = "https://hallyuzine.pages.dev"
LANGUAGE = "en"

# 2. Gemini 모델 설정
GEMINI_MODEL = "gemini-3.8-flash"

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

# 4. 검증된 국내 연예·한류 공식 RSS 피드
RSS_FEEDS = [
    {
        "category": "music",
        "url": "https://news.google.com/rss/search?q=K-POP+OR+아이돌+OR+컴백&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "K-Pop Wire"
    },
    {
        "category": "ott",
        "url": "https://news.google.com/rss/search?q=넷플릭스+드라마+OR+한국영화+흥행&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "K-Screen Wire"
    },
    {
        "category": "style",
        "url": "https://news.google.com/rss/search?q=화보+OR+공항패션+OR+앰버서더&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "Seoul Style Wire"
    },
    {
        "category": "culture",
        "url": "https://news.google.com/rss/search?q=성수+팝업+OR+한류+열풍&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "Seoul Culture Wire"
    },
    {
        "category": "music",
        "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/entertainments/?outputType=xml",
        "source_name": "Chosun Entertainment"
    },
    {
        "category": "ott",
        "url": "https://rss.donga.com/sportsdonga/entertainment.xml",
        "source_name": "Sports Donga"
    }
]

# 5. 구글 애드센스 설정
ADSENSE_CLIENT = "ca-pub-XXXXXXXXXXXXXXXX"
ADSENSE_SLOT_FACTBOX_BELOW = "1234567890"
ADSENSE_SLOT_SIDEBAR_FIXED = "2345678901"
ADSENSE_SLOT_MULTIPLEX_END = "3456789012"

# 6. 발행 및 빌드 제어 (하루 8회 x 1건 = 8건 분산 발행)
ITEMS_PER_RUN = 1
POSTS_META_PATH = "posts_meta.json"
DEBATE_META_PATH = "weekly_debate.json"
OUTPUT_DIR = "dist"
