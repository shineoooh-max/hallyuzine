"""
builder.py - HALLYUZINE 영문 매거진 생성 및 정적 HTML 조립 엔진
"""

import os
import re
import json
import time
import shutil
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
import config
import parser

KST = timezone(timedelta(hours=9))


def load_template(filename: str) -> str:
    path = os.path.join("templates", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_posts_meta() -> list[dict]:
    if not os.path.exists(config.POSTS_META_PATH):
        return []
    with open(config.POSTS_META_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_posts_meta(posts: list[dict]) -> None:
    with open(config.POSTS_META_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    clean = re.sub(r"[\s-]+", "-", clean).strip("-")
    return clean[:65] if clean else f"issue-{int(time.time())}"


def generate_editorial_article(client: genai.Client, candidate: dict) -> dict | None:
    """
    국내 연예/문화 팩트 원문을 받아 Esquire/Elle 톤의 세련된 영문 매거진 기사와
    THE DOSSIER(핵심 요약 카드) JSON으로 변환합니다.
    """
    prompt = f"""
You are a senior editor at HALLYUZINE, a global digital magazine covering Korean pop culture, cinema, fashion, and Seoul lifestyle for English-speaking readers.

Transform the following Korean news source into an original, authoritative, magazine-grade English feature article.
Do NOT write cheap gossip or clickbait. Focus on verified facts, industry context, artistic direction, chart/OTT impact, or fashion/cultural details.

[SOURCE TITLE]
{candidate['raw_title']}

[SOURCE FACTS]
{candidate['raw_text']}

Return ONLY a valid JSON object with the exact keys below:
{{
  "category": "Choose strictly one of: music, ott, style, culture",
  "title": "Punchy, sophisticated magazine headline in English (max 85 chars, no 'K-' hyphenated cliches if avoidable)",
  "subtitle": "Compelling 1-sentence editorial deck summarizing why this matters globally (max 150 chars)",
  "dossier_facts": [
    "Fact 1: Key release date, platform, or official title",
    "Fact 2: Artists, cast, directors, or luxury brands involved",
    "Fact 3: Notable milestone, chart record, or cultural significance"
  ],
  "body_html": "Well-structured English editorial body (350-500 words) formatted strictly with <h3> chapter subheadings and <p> paragraphs. Break into 3 engaging, bite-sized chapters for effortless mobile reading. Do NOT include <h1>, <h2>, <html>, or markdown."
}}
"""
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.65,
            ),
        )
        data = json.loads(response.text)
        if data.get("category") not in config.CATEGORIES:
            data["category"] = candidate["category"]
        return data
    except Exception as e:
        print(f"[Gemini] 기사 생성 실패 ({candidate['raw_title']}): {e}")
        return None


def render_header(
    page_title: str,
    meta_desc: str,
    canonical_url: str,
    og_type: str,
    og_image: str,
    active_nav: str,
    issue_date: str,
    json_ld: str = ""
) -> str:
    tpl = load_template("base_header.html")
    nav_flags = {
        "<!--{{NAV_HOME_ACTIVE}}-->": "active" if active_nav == "home" else "",
        "<!--{{NAV_MUSIC_ACTIVE}}-->": "active" if active_nav == "music" else "",
        "<!--{{NAV_OTT_ACTIVE}}-->": "active" if active_nav == "ott" else "",
        "<!--{{NAV_STYLE_ACTIVE}}-->": "active" if active_nav == "style" else "",
        "<!--{{NAV_CULTURE_ACTIVE}}-->": "active" if active_nav == "culture" else "",
    }
    replacements = {
        "<!--{{PAGE_TITLE}}-->": page_title,
        "<!--{{META_DESCRIPTION}}-->": meta_desc,
        "<!--{{CANONICAL_URL}}-->": canonical_url,
        "<!--{{OG_TYPE}}-->": og_type,
        "<!--{{OG_IMAGE}}-->": og_image,
        "<!--{{ISSUE_DATE}}-->": issue_date,
        "<!--{{JSON_LD_SCHEMA}}-->": json_ld,
        **nav_flags
    }
    for marker, val in replacements.items():
        tpl = tpl.replace(marker, val)
    return tpl


def render_footer(current_year: str) -> str:
    tpl = load_template("base_footer.html")
    return tpl.replace("<!--{{CURRENT_YEAR}}-->", current_year)


def build_site() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    client = genai.Client(api_key=api_key)
    posts = load_posts_meta()
    existing_urls = {p["source_url"] for p in posts}

    now_kst = datetime.now(KST)
    issue_date_str = now_kst.strftime("%b %d, %Y").upper()
    current_year = str(now_kst.year)

    print("[Builder] 신규 국내 공식 소스 탐색 시작...")
    candidates = parser.fetch_rss_candidates(existing_urls)
    print(f"[Builder] 수집된 유효 후보 기사 수: {len(candidates)}건")

    created_count = 0
    for cand in candidates:
        if created_count >= config.ITEMS_PER_RUN:
            break

        print(f"[Builder] 영문 매거진 변환 중 ({created_count + 1}/{config.ITEMS_PER_RUN}): {cand['raw_title']}")
        ai_data = generate_editorial_article(client, cand)
        if not ai_data:
            time.sleep(5)
            continue

        cat_key = ai_data["category"]
        cat_info = config.CATEGORIES[cat_key]
        date_prefix = now_kst.strftime("%Y%m%d")
        slug = f"{date_prefix}-{slugify(ai_data['title'])}.html"

        post_record = {
            "slug": slug,
            "category": cat_key,
            "category_label": cat_info["label"],
            "category_slug": cat_info["slug"],
            "title": ai_data["title"],
            "subtitle": ai_data["subtitle"],
            "dossier_facts": ai_data.get("dossier_facts", []),
            "body_html": ai_data["body_html"],
            "image_url": cand["image_url"],
            "image_credit": cand["image_credit"],
            "source_url": cand["source_url"],
            "published_iso": now_kst.isoformat(),
            "published_display": now_kst.strftime("%B %d, %Y")
        }

        posts.insert(0, post_record)
        existing_urls.add(cand["source_url"])
        created_count += 1

        # 무료 티어 분당 요청 제한(RPM) 보호용 5초 대기
        time.sleep(5)

    # 최대 120건까지만 메타데이터 유지
    posts = posts[:120]
    save_posts_meta(posts)

    # 출력 디렉터리 초기화 및 재생성
    if os.path.exists(config.OUTPUT_DIR):
        shutil.rmtree(config.OUTPUT_DIR)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    if not posts:
        print("[Builder] 발행할 기사가 없어 기본 빈 페이지만 생성합니다.")
        return

    # 1. 개별 기사 상세 페이지(article.html) 빌드
    article_tpl = load_template("article.html")
    for idx, post in enumerate(posts):
        next_post = posts[(idx + 1) % len(posts)]
        related_posts = [p for p in posts if p["slug"] != post["slug"]][:4]

        dossier_items = "\n".join([f"<li>{fact}</li>" for fact in post["dossier_facts"]])
        dossier_html = f"<ul>{dossier_items}</ul>"

        next_card_html = f"""
        <a href="{next_post['slug']}" class="next-issue-block">
          <div class="next-issue-thumb">
            <img src="{next_post['image_url']}" alt="{next_post['title']}" loading="lazy" />
          </div>
          <div>
            <div class="next-issue-kicker">NEXT ISSUE &rarr; {next_post['category_label']}</div>
            <h3 class="next-issue-title">{next_post['title']}</h3>
          </div>
        </a>
        """

        sidebar_html = "\n".join([
            f"""
            <a href="{rp['slug']}" class="sidebar-item">
              <span class="cat-tag">{rp['category_label']}</span>
              <h3 class="sidebar-item-title">{rp['title']}</h3>
            </a>
            """
            for rp in related_posts
        ])

        json_ld = f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": {json.dumps(post['title'])},
          "description": {json.dumps(post['subtitle'])},
          "image": [{json.dumps(post['image_url'])}],
          "datePublished": "{post['published_iso']}",
          "author": {{"@type": "Organization", "name": "{config.SITE_NAME}"}},
          "publisher": {{"@type": "Organization", "name": "{config.SITE_NAME}"}}
        }}
        </script>
        """

        canonical = f"{config.SITE_URL}/{post['slug']}"
        header_html = render_header(
            page_title=f"{post['title']} — {config.SITE_NAME}",
            meta_desc=post["subtitle"],
            canonical_url=canonical,
            og_type="article",
            og_image=post["image_url"],
            active_nav=post["category"],
            issue_date=issue_date_str,
            json_ld=json_ld
        )
        footer_html = render_footer(current_year)

        page_html = article_tpl
        replacements = {
            "<!--{{BASE_HEADER}}-->": header_html,
            "<!--{{BASE_FOOTER}}-->": footer_html,
            "<!--{{CATEGORY_SLUG}}-->": post["category_slug"],
            "<!--{{CATEGORY_LABEL}}-->": post["category_label"],
            "<!--{{ARTICLE_TITLE}}-->": post["title"],
            "<!--{{ARTICLE_SUBTITLE}}-->": post["subtitle"],
            "<!--{{PUBLISHED_DATE}}-->": post["published_display"],
            "<!--{{HERO_IMAGE}}-->": post["image_url"],
            "<!--{{IMAGE_CREDIT}}-->": post["image_credit"],
            "<!--{{DOSSIER_LIST}}-->": dossier_html,
            "<!--{{ARTICLE_BODY}}-->": post["body_html"],
            "<!--{{NEXT_ISSUE_CARD}}-->": next_card_html,
            "<!--{{SIDEBAR_RELATED}}-->": sidebar_html,
        }
        for marker, val in replacements.items():
            page_html = page_html.replace(marker, val)

        with open(os.path.join(config.OUTPUT_DIR, post["slug"]), "w", encoding="utf-8") as f:
            f.write(page_html)

    # 2. 카테고리별 전용 서브페이지(music.html, ott.html, style.html, culture.html) 빌드
    cat_tpl = load_template("category.html")
    for cat_key, cat_info in config.CATEGORIES.items():
        cat_posts = [p for p in posts if p["category"] == cat_key]
        if not cat_posts:
            cat_posts = posts[:6]

        cards_html = "\n".join([
            f"""
            <a href="{p['slug']}" class="cat-card">
              <div class="cat-card-thumb">
                <img src="{p['image_url']}" alt="{p['title']}" loading="lazy" />
              </div>
              <div class="cat-card-body">
                <span class="cat-tag">{p['category_label']}</span>
                <h2 class="cat-card-title">{p['title']}</h2>
                <p class="cat-card-excerpt">{p['subtitle']}</p>
                <div class="cat-card-date">{p['published_display']}</div>
              </div>
            </a>
            """
            for p in cat_posts
        ])

        canonical = f"{config.SITE_URL}/{cat_info['slug']}"
        header_html = render_header(
            page_title=f"{cat_info['label']} — {config.SITE_NAME}",
            meta_desc=cat_info["description"],
            canonical_url=canonical,
            og_type="website",
            og_image=cat_posts[0]["image_url"],
            active_nav=cat_key,
            issue_date=issue_date_str
        )
        footer_html = render_footer(current_year)

        page_html = cat_tpl
        page_html = page_html.replace("<!--{{BASE_HEADER}}-->", header_html)
        page_html = page_html.replace("<!--{{BASE_FOOTER}}-->", footer_html)
        page_html = page_html.replace("<!--{{CATEGORY_TITLE}}-->", cat_info["label"])
        page_html = page_html.replace("<!--{{CATEGORY_DESCRIPTION}}-->", cat_info["description"])
        page_html = page_html.replace("<!--{{CATEGORY_ARTICLES}}-->", cards_html)

        with open(os.path.join(config.OUTPUT_DIR, cat_info["slug"]), "w", encoding="utf-8") as f:
            f.write(page_html)

    # 3. 메인 커버 페이지(index.html) 빌드
    index_tpl = load_template("index.html")
    cover_post = posts[0]
    featured_posts = posts[1:7] if len(posts) > 1 else posts[:3]
    latest_posts = posts[7:25] if len(posts) > 7 else posts

    hero_html = f"""
    <a href="{cover_post['slug']}" class="hero-cover">
      <img src="{cover_post['image_url']}" alt="{cover_post['title']}" />
      <div class="hero-overlay">
        <span class="hero-kicker">COVER STORY • {cover_post['category_label']}</span>
        <h1 class="hero-title">{cover_post['title']}</h1>
        <p class="hero-excerpt">{cover_post['subtitle']}</p>
        <div class="hero-meta">{cover_post['published_display']} • READ FEATURE &rarr;</div>
      </div>
    </a>
    """

    swipe_html = "\n".join([
        f"""
        <a href="{p['slug']}" class="swipe-card">
          <div class="card-thumb">
            <img src="{p['image_url']}" alt="{p['title']}" loading="lazy" />
          </div>
          <div class="card-body">
            <span class="cat-tag">{p['category_label']}</span>
            <h3 class="card-title">{p['title']}</h3>
            <p class="card-summary">{p['subtitle']}</p>
            <div class="card-date">{p['published_display']}</div>
          </div>
        </a>
        """
        for p in featured_posts
    ])

    latest_html = "\n".join([
        f"""
        <a href="{p['slug']}" class="news-row">
          <div class="news-row-thumb">
            <img src="{p['image_url']}" alt="{p['title']}" loading="lazy" />
          </div>
          <div>
            <span class="cat-tag">{p['category_label']}</span>
            <h3 class="news-row-title">{p['title']}</h3>
            <div class="news-row-meta">{p['published_display']}</div>
          </div>
        </a>
        """
        for p in latest_posts
    ])

    header_html = render_header(
        page_title=f"{config.SITE_NAME} — {config.SITE_TAGLINE}",
        meta_desc=config.SITE_TAGLINE,
        canonical_url=f"{config.SITE_URL}/",
        og_type="website",
        og_image=cover_post["image_url"],
        active_nav="home",
        issue_date=issue_date_str
    )
    footer_html = render_footer(current_year)

    index_html = index_tpl
    index_html = index_html.replace("<!--{{BASE_HEADER}}-->", header_html)
    index_html = index_html.replace("<!--{{BASE_FOOTER}}-->", footer_html)
    index_html = index_html.replace("<!--{{HERO_COVER}}-->", hero_html)
    index_html = index_html.replace("<!--{{FEATURED_SWIPE_CARDS}}-->", swipe_html)
    index_html = index_html.replace("<!--{{LATEST_FEED}}-->", latest_html)

    with open(os.path.join(config.OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    # 4. SEO용 sitemap.xml 및 robots.txt 자동 생성
    urls = [f"{config.SITE_URL}/"] + [f"{config.SITE_URL}/{c['slug']}" for c in config.CATEGORIES.values()]
    urls += [f"{config.SITE_URL}/{p['slug']}" for p in posts]

    sitemap_entries = "\n".join([
        f"  <url><loc>{u}</loc><lastmod>{now_kst.strftime('%Y-%m-%d')}</lastmod></url>"
        for u in urls
    ])
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_entries}
</urlset>
"""
    with open(os.path.join(config.OUTPUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap_xml)

    robots_txt = f"User-agent: *\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n"
    with open(os.path.join(config.OUTPUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots_txt)

    print(f"[Builder] 빌드 완료! 총 보유 기사 {len(posts)}건 / 신규 생성 {created_count}건")


if __name__ == "__main__":
    build_site()
