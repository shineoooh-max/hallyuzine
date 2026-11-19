"""
config.py - HALLYUZINE 핵심 환경설정 및 메타데이터
"""

# 1. 사이트 기본 정보
SITE_NAME = "HALLYUZINE"
SITE_TAGLINE = "The Global Editorial Magazine for K-Culture & Pop Trends"
SITE_URL = "https://hallyuzine.koo1000.com"  # 실제 연결할 도메인 또는 GitHub Pages URL로 수정
LANGUAGE = "en"

# 2. Gemini 모델 설정
GEMINI_MODEL = "gemini-2.5-flash"

# 3. 4대 핵심 카테고리 및 전용 서브페이지 파일명 매핑 (옵션 B)
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

# 4. 국내 공식 소스 RSS 피드 (카테고리별 매핑)
RSS_FEEDS = [
    {
        "category": "music",
        "url": "https://www.yna.co.kr/rss/entertainment.xml",
        "source_name": "Yonhap News"
    },
    {
        "category": "ott",
        "url": "https://www.yna.co.kr/rss/culture.xml",
        "source_name": "Yonhap Culture"
    }
]

# 5. 구글 애드센스 설정 (비침해형 슬롯)
ADSENSE_CLIENT = "ca-pub-XXXXXXXXXXXXXXXX"
ADSENSE_SLOT_FACTBOX_BELOW = "1234567890"   # 본문 Fact Box 하단 네이티브 배너
ADSENSE_SLOT_SIDEBAR_FIXED = "2345678901"   # 데스크톱 우측 300x600 고정 배너
ADSENSE_SLOT_MULTIPLEX_END = "3456789012"   # 본문 종료 후 멀티플렉스 추천

# 6. 발행 및 빌드 제어
ITEMS_PER_RUN = 4               # 1회 실행당 최대 신규 발행 건수 (1일 2회 실행 시 하루 8건)
POSTS_META_PATH = "posts_meta.json"
OUTPUT_DIR = "dist"
