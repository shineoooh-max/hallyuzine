"""
builder.py - HALLYUZINE 영문 브로드시트 매거진 생성 및 정적 HTML 조립 엔진
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


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    clean = re.sub(r"[\s-]+", "-", clean).strip("-")
    return clean[:65] if clean else f"issue-{int(time.time())}"


def get_balanced_category_order(posts: list[dict]) -> list[str]:
    counts = {cat: 0 for cat in config.CATEGORIES.keys()}
    for p in posts:
        cat = p.get("category")
        if cat in counts:
            counts[cat] += 1
    return sorted(counts.keys(), key=lambda c: counts[c])


def generate_editorial_article(client: genai.Client, candidate: dict) -> dict | None:
    prompt = f"""
You are a senior editor at HALLYUZINE, a global digital broadsheet covering K-Pop, K-Drama, Korean cinema, fashion, and Seoul lifestyle for international English-speaking readers.

First, evaluate if this news topic is genuinely positive, cultural, or exciting to international K-Culture fans (music releases, tours, dramas, films, actors, fashion, Seoul trends).
If it is domestic Korean broadcasting regulation, politics, crime/police reports, fan-security disputes, or sports news with zero K-Culture appeal, return ONLY:
{{"skip": true}}

Otherwise, transform it into an original, authoritative, magazine-grade English feature article and return ONLY a valid JSON object with these exact keys:
{{
  "skip": false,
  "category": "Choose strictly one of: music, ott, style, culture",
  "title": "Punchy, sophisticated broadsheet headline in English (max 85 chars)",
  "subtitle": "Compelling 1-sentence editorial deck summarizing why this matters globally (max 150 chars)",
  "buzz_score": 92,
  "dossier_facts": [
    "Fact 1: Key release date, platform, or official title",
    "Fact 2: Artists, cast, directors, or luxury brands involved",
    "Fact 3: Notable milestone, chart record, or cultural significance"
  ],
  "body_html": "Well-structured English editorial body (350-500 words) formatted strictly with <h3> chapter subheadings and <p> paragraphs. Break into 3 engaging, bite-sized chapters for effortless mobile reading. Do NOT include <h1>, <h2>, <html>, or markdown."
}}

Note on buzz_score: Rate global K-culture buzz potential as an integer between 82 and 99.

[SUGGESTED CATEGORY]
{candidate['category']}

[SOURCE TITLE]
{candidate['raw_title']}

[SOURCE CONTEXT]
{candidate['raw_text']}
"""
    models_to_try = [config.GEMINI_MODEL, getattr(config, "GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")]
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.65,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW
                    ),
                ),
            )
            data = json.loads(response.text)
            if data.get("skip") is True:
                print(f"[Gemini] 해외 독자 무관 기사 스킵: {candidate['raw_title']}", flush=True)
                return None

            if data.get("category") not in config.CATEGORIES:
                data["category"] = candidate["category"]

            score = int(data.get("buzz_score", 88))
            data["buzz_score"] = max(80, min(99, score))
            print(f"[Gemini] 생성 성공 ({model_name}) [{data['category'].upper()}] (Buzz {data['buzz_score']}): {data['title']}", flush=True)
            return data
        except Exception as e:
            print(f"[Gemini] 모델 지연/전환 ({model_name}) - {candidate['raw_title']}: {e}", flush=True)
            time.sleep(10)

    return None


def update_weekly_debate(client: genai.Client, posts: list[dict], now_kst: datetime) -> dict:
    week_key = now_kst.strftime("%Y-W%W")
    debate = load_json(config.DEBATE_META_PATH, {})

    if debate.get("week_key") == week_key and debate.get("question"):
        return debate

    if len(posts) < 2:
        return {
            "week_key": week_key,
            "question": "Which K-Culture wave defines this week in Seoul?",
            "option_a_label": "4th & 5th Gen K-Pop Comebacks",
            "option_a_sub": "Chart-topping singles & world tours",
            "option_a_img": posts[0]["image_url"] if posts else "",
            "option_a_pct": 54,
            "option_b_label": "Global K-Drama & OTT Blockbusters",
            "option_b_sub": "Netflix & Disney+ weekend binge hits",
            "option_b_img": posts[1]["image_url"] if len(posts) > 1 else "",
            "option_b_pct": 46
        }

    top_a, top_b = posts[0], posts[1]
    prompt = f"""
Create a fun, engaging "Weekly K-Culture Balance Game" (A vs B fan poll) for international HALLYUZINE readers inspired by these two trending Seoul stories:
Story A: {top_a['title']} ({top_a['category_label']})
Story B: {top_b['title']} ({top_b['category_label']})

Return ONLY valid JSON:
{{
  "question": "Punchy either/or question for global K-culture fans (max 75 chars)",
  "option_a_label": "Short Option A title (max 34 chars)",
  "option_a_sub": "Short context tag (max 42 chars)",
  "option_b_label": "Short Option B title (max 34 chars)",
  "option_b_sub": "Short context tag (max 42 chars)"
}}
"""
    models_to_try = [config.GEMINI_MODEL, getattr(config, "GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")]
    for model_name in models_to_try:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.75,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW
                    ),
                ),
            )
            ai_debate = json.loads(resp.text)
            debate = {
                "week_key": week_key,
                "question": ai_debate["question"],
                "option_a_label": ai_debate["option_a_label"],
                "option_a_sub": ai_debate["option_a_sub"],
                "option_a_img": top_a["image_url"],
                "option_a_pct": 53,
                "option_b_label": ai_debate["option_b_label"],
                "option_b_sub": ai_debate["option_b_sub"],
                "option_b_img": top_b["image_url"],
                "option_b_pct": 47
            }
            save_json(config.DEBATE_META_PATH, debate)
            print(f"[Debate] 주간 밸런스 게임 갱신 완료 ({model_name}, {week_key}): {debate['question']}", flush=True)
            return debate
        except Exception as e:
            print(f"[Debate] 모델 전환 ({model_name} 실패): {e}", flush=True)
            time.sleep(5)

    return {
        "week_key": week_key,
        "question": "Which Seoul headline owns your weekend watchlist?",
        "option_a_label": top_a["title"][:34],
        "option_a_sub": top_a["category_label"],
        "option_a_img": top_a["image_url"],
        "option_a_pct": 52,
        "option_b_label": top_b["title"][:34],
        "option_b_sub": top_b["category_label"],
        "option_b_img": top_b["image_url"],
        "option_b_pct": 48
    }


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

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30000),
    )
    posts = load_json(config.POSTS_META_PATH, [])
    existing_urls = {p["source_url"] for p in posts}
    existing_titles = [p.get("raw_title", p["title"]) for p in posts]

    now_kst = datetime.now(KST)
    issue_date_str = now_kst.strftime("%A, %B %d, %Y").upper()
    current_year = str(now_kst.year)

    preferred_cats = get_balanced_category_order(posts)
    print(f"[Builder] 카테고리 우선순위 (적은 순): {preferred_cats}", flush=True)

    candidates = parser.fetch_rss_candidates(existing_urls, existing_titles, preferred_cats)
    print(f"[Builder] 수집된 유효 후보 기사 수: {len(candidates)}건", flush=True)

    created_count = 0
    for cand in candidates:
        if created_count >= config.ITEMS_PER_RUN:
            break

        print(f"[Builder] 영문 기사 변환 시도: {cand['raw_title']}", flush=True)
        ai_data = generate_editorial_article(client, cand)
        if not ai_data:
            time.sleep(2)
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
            "raw_title": cand["raw_title"],
            "title": ai_data["title"],
            "subtitle": ai_data["subtitle"],
            "buzz_score": ai_data.get("buzz_score", 90),
            "dossier_facts": ai_data.get("dossier_facts", []),
            "body_html": ai_data["body_html"],
            "image_url": cand["image_url"],
            "image_credit": cand["image_credit"],
            "source_url": cand["source_url"],
            "published_iso": now_kst.isoformat(),
            "published_display": now_kst.strftime("%b %d, %Y").upper()
        }

        posts.insert(0, post_record)
        existing_urls.add(cand["source_url"])
        created_count += 1
        time.sleep(2)

    posts = posts[:120]
    save_json(config.POSTS_META_PATH, posts)

    if os.path.exists(config.OUTPUT_DIR):
        shutil.rmtree(config.OUTPUT_DIR)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    if not posts:
        print("[Builder] 발행할 기사가 없어 빌드를 종료합니다.", flush=True)
        return

    debate = update_weekly_debate(client, posts, now_kst)

    # 1. 개별 기사 상세 페이지(article.html) 빌드
    article_tpl = load_template("article.html")
    for idx, post in enumerate(posts):
        next_post = posts[(idx + 1) % len(posts)]
        related_posts = [p for p in posts if p["slug"] != post["slug"]][:5]

        dossier_items = "\n".join([f"<li>{fact}</li>" for fact in post.get("dossier_facts", [])])
        dossier_html = f"<ul>{dossier_items}</ul>"

        next_card_html = f"""
        <a href="{next_post['slug']}" class="next-issue-block">
          <div class="next-issue-thumb">
            <img src="{next_post['image_url']}" alt="{next_post['title']}" loading="lazy" />
          </div>
          <div>
            <div class="next-issue-kicker">NEXT DISPATCH &rarr; {next_post['category_label']}</div>
            <h3 class="next-issue-title">{next_post['title']}</h3>
          </div>
        </a>
        """

        sidebar_html = "\n".join([
            f"""
            <a href="{rp['slug']}" class="sidebar-item">
              <span class="cat-tag">{rp['category_label']} • BUZZ {rp.get('buzz_score', 88)}</span>
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

    # 2. 카테고리별 전용 서브페이지 빌드
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
                <span class="cat-tag">{p['category_label']} • BUZZ {p.get('buzz_score', 88)}</span>
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

    # 3. 메인 브로드시트 커버 페이지(index.html) 빌드 (#01 ~ #20 랭킹 + 주간 밸런스 게임)
    index_tpl = load_template("index.html")
    ranked_posts = posts[:20]

    # #01 톱기사
    p1 = ranked_posts[0]
    rank_01_html = f"""
    <article class="lead-story">
      <div class="lead-meta-row">
        <span class="rank-pill">#01 TOP BUZZ</span>
        <span class="cat-tag">{p1['category_label']} • SCORE {p1.get('buzz_score', 96)}</span>
        <span class="lead-date">{p1['published_display']}</span>
      </div>
      <a href="{p1['slug']}" class="lead-link">
        <h1 class="lead-title">{p1['title']}</h1>
        <p class="lead-deck">{p1['subtitle']}</p>
        <div class="lead-media">
          <img src="{p1['image_url']}" alt="{p1['title']}" />
        </div>
      </a>
    </article>
    """

    # #02 ~ #05 2단 칼럼 랭킹
    rank_02_05_html = "\n".join([
        f"""
        <a href="{p['slug']}" class="sub-rank-card">
          <div class="sub-rank-thumb">
            <img src="{p['image_url']}" alt="{p['title']}" loading="lazy" />
          </div>
          <div class="sub-rank-body">
            <div class="sub-rank-head">
              <span class="rank-num">{idx:02d}</span>
              <span class="cat-tag">{p['category_label']} • BUZZ {p.get('buzz_score', 90)}</span>
            </div>
            <h2 class="sub-rank-title">{p['title']}</h2>
            <p class="sub-rank-deck">{p['subtitle']}</p>
          </div>
        </a>
        """
        for idx, p in enumerate(ranked_posts[1:5], start=2)
    ])

    # 주간 밸런스 게임 (딥 블랙 박스)
    debate_html = f"""
    <section class="debate-box" aria-label="Weekly K-Culture Balance Game">
      <div class="debate-top">
        <span class="debate-kicker">WEEKLY K-CULTURE BALANCE GAME</span>
        <span class="debate-week">{debate['week_key']}</span>
      </div>
      <h2 class="debate-question">{debate['question']}</h2>
      <div class="debate-grid" id="debateGrid" data-week="{debate['week_key']}" data-pct-a="{debate['option_a_pct']}" data-pct-b="{debate['option_b_pct']}">
        <button type="button" class="debate-option" data-choice="A">
          <div class="debate-thumb">
            <img src="{debate['option_a_img']}" alt="{debate['option_a_label']}" loading="lazy" />
            <span class="debate-badge">PICK A</span>
          </div>
          <div class="debate-info">
            <div class="debate-opt-title">{debate['option_a_label']}</div>
            <div class="debate-opt-sub">{debate['option_a_sub']}</div>
            <div class="debate-bar-wrap"><div class="debate-bar" id="barA" style="width: 0%"></div></div>
            <div class="debate-pct" id="pctA">VOTE TO SEE RESULT</div>
          </div>
        </button>

        <button type="button" class="debate-option" data-choice="B">
          <div class="debate-thumb">
            <img src="{debate['option_b_img']}" alt="{debate['option_b_label']}" loading="lazy" />
            <span class="debate-badge">PICK B</span>
          </div>
          <div class="debate-info">
            <div class="debate-opt-title">{debate['option_b_label']}</div>
            <div class="debate-opt-sub">{debate['option_b_sub']}</div>
            <div class="debate-bar-wrap"><div class="debate-bar" id="barB" style="width: 0%"></div></div>
            <div class="debate-pct" id="pctB">VOTE TO SEE RESULT</div>
          </div>
        </button>
      </div>
    </section>
    """

    def render_rank_row(idx: int, p: dict) -> str:
        return f"""
        <a href="{p['slug']}" class="rank-row">
          <div class="rank-row-num">{idx:02d}</div>
          <div class="rank-row-thumb">
            <img src="{p['image_url']}" alt="{p['title']}" loading="lazy" />
          </div>
          <div class="rank-row-content">
            <div class="rank-row-meta">
              <span class="cat-tag">{p['category_label']}</span>
              <span>• BUZZ {p.get('buzz_score', 86)}</span>
              <span>• {p['published_display']}</span>
            </div>
            <h3 class="rank-row-title">{p['title']}</h3>
          </div>
        </a>
        """

    rank_06_10_html = "\n".join([
        render_rank_row(idx, p) for idx, p in enumerate(ranked_posts[5:10], start=6)
    ])

    rank_11_20_items = "\n".join([
        render_rank_row(idx, p) for idx, p in enumerate(ranked_posts[10:20], start=11)
    ])

    rank_11_20_block = ""
    if rank_11_20_items:
        rank_11_20_block = f"""
        <div id="moreRanksBox" class="more-ranks-hidden">
          {rank_11_20_items}
        </div>
        <div class="load-more-wrap">
          <button type="button" id="toggleRanksBtn" class="load-more-btn">LOAD RANKS #11 &ndash; #20 &darr;</button>
        </div>
        """

    header_html = render_header(
        page_title=f"{config.SITE_NAME} — {config.SITE_TAGLINE}",
        meta_desc=config.SITE_TAGLINE,
        canonical_url=f"{config.SITE_URL}/",
        og_type="website",
        og_image=p1["image_url"],
        active_nav="home",
        issue_date=issue_date_str
    )
    footer_html = render_footer(current_year)

    index_html = index_tpl
    index_html = index_html.replace("<!--{{BASE_HEADER}}-->", header_html)
    index_html = index_html.replace("<!--{{BASE_FOOTER}}-->", footer_html)
    index_html = index_html.replace("<!--{{RANK_01_LEAD}}-->", rank_01_html)
    index_html = index_html.replace("<!--{{RANK_02_05_GRID}}-->", rank_02_05_html)
    index_html = index_html.replace("<!--{{WEEKLY_DEBATE_BOX}}-->", debate_html)
    index_html = index_html.replace("<!--{{RANK_06_10_LIST}}-->", rank_06_10_html)
    index_html = index_html.replace("<!--{{RANK_11_20_ACCORDION}}-->", rank_11_20_block)

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

    print(f"[Builder] 빌드 완료! 총 보유 기사 {len(posts)}건 / 신규 생성 {created_count}건", flush=True)


if __name__ == "__main__":
    build_site()
