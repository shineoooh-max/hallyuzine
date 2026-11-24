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

# 4. 한국 실시간 한류 전용 Google News RSS (최근 24시간 when:1d + 노이즈 제외 연산자)
RSS_FEEDS = [
    {
        "category": "music",
        "url": "https://news.google.com/rss/search?q=(빌보드+케이팝+OR+신곡+발매+OR+월드투어+OR+음반+초동)+-야구+-축구+-감독+-고발+-논란+when:1d&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "Korea Music Desk"
    },
    {
        "category": "ott",
        "url": "https://news.google.com/rss/search?q=(넷플릭스+드라마+OR+한국영화+박스오피스+OR+디즈니플러스+드라마)+-야구+-축구+-감독+-고발+-논란+when:1d&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "Korea Screen Desk"
    },
    {
        "category": "style",
        "url": "https://news.google.com/rss/search?q=(패션+화보+OR+공항패션+OR+글로벌+앰버서더+OR+패션위크)+-야구+-축구+-감독+-고발+-논란+when:1d&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "Seoul Style Desk"
    },
    {
        "category": "culture",
        "url": "https://news.google.com/rss/search?q=(성수+팝업스토어+OR+한류+열풍+OR+K컬처+전시)+-야구+-축구+-감독+-고발+-논란+when:1d&hl=ko&gl=KR&ceid=KR:ko",
        "source_name": "Seoul Culture Desk"
    }
]

# 5. 구글 애드센스 설정
ADSENSE_CLIENT = "ca-pub-XXXXXXXXXXXXXXXX"
ADSENSE_SLOT_FACTBOX_BELOW = "1234567890"
ADSENSE_SLOT_SIDEBAR_FIXED = "2345678901"
ADSENSE_SLOT_MULTIPLEX_END = "3456789012"

# 6. 발행 및 빌드 제어
ITEMS_PER_RUN = 1
POSTS_META_PATH = "posts_meta.json"
DEBATE_META_PATH = "weekly_debate.json"
OUTPUT_DIR = "dist"
