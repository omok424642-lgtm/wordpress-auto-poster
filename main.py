"""
WordPress 자동 포스팅 메인 스크립트

사용법:
  python main.py <슬롯>
  슬롯: 6, 9, 13, 18, 21

예시:
  python main.py 6    # 06:00 생활경제
  python main.py 9    # 09:00 생활건강
  python main.py 13   # 13:00 지원정책
  python main.py 18   # 18:00 교대 (생활경제/생활건강)
  python main.py 21   # 21:00 트렌드 키워드

  python main.py --test    # WordPress 연결 테스트
  python main.py --status  # 최근 포스팅 현황
"""
import argparse
import logging
import sys
import re
import io
from datetime import datetime
from pathlib import Path

# Windows 콘솔 UTF-8 강제 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 로그 설정 (파일 + 콘솔)
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── 내부 모듈 (로그 설정 후 import) ───────────────────────
from config import SLOT_CATEGORY_MAP, WP_URL
from database import Database
from keyword_research import KeywordResearcher
from web_search import WebSearcher
from content_generator import ContentGenerator
from wordpress_api import WordPressAPI


# ── 이미지 배치 규칙 적용 (placeholder 삽입) ──────────────
def _place_image_placeholders(content: str, image_count: int) -> tuple[str, int]:
    """
    규칙:
    - IMAGE_PLACEHOLDER_1(대표이미지 1200x630): 핵심요약 blockquote 바로 앞
    - IMAGE_PLACEHOLDER_2+(본문이미지 800x450): 목차 이후 표·계산기 없는 H2 전부
    image_count 제한 없이 적격 소제목 전체에 삽입.
    반환: (수정된 content, 실제 삽입된 총 placeholder 수)
    """
    # 기존 플레이스홀더 제거
    content = re.sub(r'\n?<!--IMAGE_PLACEHOLDER_\d+-->\n?', '\n', content)

    # ── 1. 대표이미지: 첫 번째 <blockquote> 바로 앞 ──────
    bq_match = re.search(r'<blockquote', content, re.IGNORECASE)
    if bq_match:
        pos = bq_match.start()
        content = content[:pos] + "<!--IMAGE_PLACEHOLDER_1-->\n" + content[pos:]
    else:
        content = "<!--IMAGE_PLACEHOLDER_1-->\n" + content

    # ── 2. 본문이미지: 목차 이후 모든 적격 H2 바로 아래 ─
    toc_match = re.search(
        r'<h2[^>]*>(?:[^<]*)(?:📋\s*)?목차(?:[^<]*)</h2>',
        content, re.IGNORECASE | re.DOTALL
    )
    if not toc_match:
        logger.warning("목차 H2 미발견 – 본문이미지 배치 생략")
        logger.info("이미지 플레이스홀더 배치 완료: 1개")
        return content, 1

    before_toc = content[:toc_match.end()]
    after_toc  = content[toc_match.end():]

    parts = re.split(r'(<h2[^>]*>.*?</h2>)', after_toc, flags=re.IGNORECASE | re.DOTALL)

    placeholder_idx = 2
    new_parts = [parts[0]]

    i = 1
    while i < len(parts):
        h2_tag    = parts[i]
        following = parts[i + 1] if i + 1 < len(parts) else ""

        new_parts.append(h2_tag)

        # 표·계산기·Q&A 없는 소제목 전부에 이미지 삽입 (횟수 제한 없음)
        h2_text_raw = re.sub(r'<[^>]+>', '', h2_tag)
        has_table = bool(re.search(r'<table', following, re.IGNORECASE))
        has_calc  = bool(re.search(r'acc-arrow|🧮|계산기', following))
        has_qa    = bool(re.search(r'Q&A|FAQ|자주\s*묻는\s*질문|질문과\s*답변', h2_text_raw, re.IGNORECASE))
        if not has_table and not has_calc and not has_qa:
            new_parts.append(f"\n<!--IMAGE_PLACEHOLDER_{placeholder_idx}-->")
            placeholder_idx += 1

        new_parts.append(following)
        i += 2

    content = before_toc + "".join(new_parts)
    total = placeholder_idx - 1
    logger.info(f"이미지 플레이스홀더 배치 완료: {total}개")
    return content, total


# ── 이미지 placeholder → HTML 주석 + figure 태그 교체 ─────
def _inject_image_html(content: str, images: list, total_count: int, keyword: str) -> str:
    """
    <!--IMAGE_PLACEHOLDER_N-->을 HTML 주석(파일명·Gemini 프롬프트) + figure 태그로 교체.
    대표이미지(1): 1200x630 / 본문이미지(2+): 800x450
    images 배열이 부족하면 마지막 항목을 재활용하고 파일명 인덱스만 변경.
    """
    year  = datetime.now().strftime("%Y")
    month = datetime.now().strftime("%m")

    for i in range(1, total_count + 1):
        placeholder = f"<!--IMAGE_PLACEHOLDER_{i}-->"
        if placeholder not in content:
            continue

        # Claude 제공 images 범위 안이면 그대로, 벗어나면 직전 H2에서 파생
        in_range = images and i - 1 < len(images)
        img_data = images[i - 1] if in_range else {}

        if in_range:
            filename = img_data.get("filename") or _make_slug(keyword, i)
            prompt   = img_data.get("prompt", f"{keyword} related scene, Korean style, navy #002366 tone")
            alt      = img_data.get("alt", keyword)
            caption  = img_data.get("caption", keyword)
        else:
            # placeholder 앞뒤 컨텍스트에서 섹션 정보 추출
            ph_pos = content.find(placeholder)
            preceding = content[:ph_pos]
            following_text = content[ph_pos + len(placeholder):]

            # 직전 H2
            h2_hits = re.findall(r'<h2[^>]*>(.*?)</h2>', preceding, re.DOTALL | re.IGNORECASE)
            h2_text = re.sub(r'<[^>]+>', '', h2_hits[-1]).strip() if h2_hits else keyword

            # placeholder 이후 첫 번째 <p> 태그 내용을 섹션 요약으로 활용
            p_match = re.search(r'<p[^>]*>(.*?)</p>', following_text, re.DOTALL | re.IGNORECASE)
            p_text = re.sub(r'<[^>]+>', '', p_match.group(1)).strip() if p_match else ""

            # alt: 섹션 첫 문장(60자 이내), caption: 핵심 내용 요약
            if p_text:
                first_sentence = re.split(r'[.。!?！？]', p_text)[0].strip()[:60]
                alt = first_sentence if first_sentence else f"{keyword} {h2_text}"
                # caption: p_text 앞 50자 + 키워드 자연 결합
                caption_base = p_text[:50].rstrip()
                caption = f"{caption_base}{'...' if len(p_text) > 50 else ''}"
            else:
                alt     = f"{keyword} {h2_text}"
                caption = f"{h2_text} 관련 정보를 시각적으로 정리한 이미지입니다."

            # 파일명용 슬러그
            h2_slug = re.sub(r'[^\w가-힣a-zA-Z0-9]', '-', h2_text)
            h2_slug = re.sub(r'-+', '-', h2_slug).strip('-')[:30]
            filename = f"{h2_slug}-이미지{i}.webp"

            prompt  = (f"{keyword}, {h2_text}, Korean style infographic scene, "
                       f"navy #002366 tone, photorealistic, 800x450")

        # 크기: 대표이미지 vs 본문이미지
        if i == 1:
            w, h = 1200, 630
        else:
            w, h = 800, 450

        url = f"https://freenoma.com/wp-content/uploads/{year}/{month}/{filename}"

        html = (
            f"<!-- \n"
            f"📁 파일명: {filename}\n"
            f"🎨 Gemini 프롬프트: {prompt} (한국적 분위기, 네이비 #002366 톤, 16:9)\n"
            f"-->\n"
            f'<figure>'
            f'<img src="{url}" alt="{alt}" width="{w}" height="{h}" '
            f'loading="lazy" style="width:100%;height:auto;border-radius:6px;">'
            f"<figcaption>{caption}</figcaption>"
            f"</figure>"
        )

        content = content.replace(placeholder, html)

    # 남은 플레이스홀더 제거
    content = re.sub(r"<!--IMAGE_PLACEHOLDER_\d+-->", "", content)
    return content


def _make_slug(keyword: str, index: int) -> str:
    """키워드 기반 SEO 파일명 슬러그"""
    slug = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", "", keyword)
    slug = re.sub(r"\s+", "-", slug.strip())
    suffix = "대표이미지" if index == 1 else f"이미지{index}"
    return f"{slug}-{suffix}.webp"


# ── 내부 링크 삽입 (발행글만, 본문 텍스트 안에 자연 삽입) ──
def _inject_internal_links(
    content: str, category: str, category_id: int | None, wp: WordPressAPI
) -> str:
    """
    WordPress에서 같은 카테고리 발행글(status=publish)을 가져와
    본문 단락(p) 안에 자연스럽게 앵커 링크로 삽입.
    """
    if not category_id:
        logger.info("내부링크: 카테고리 ID 없음")
        return content

    published = wp.get_published_posts_by_category(category_id, limit=10)
    if not published:
        logger.info("내부링크: 발행된 관련 글 없음")
        return content

    selected = published[:3]
    logger.info(f"내부링크 발행글 {len(selected)}개 발견")

    # 불용어 (단독으로는 매칭 안 할 단어)
    stopwords = {'및', '의', '을', '를', '이', '가', '에', '로', '은', '는',
                 '에서', '으로', '와', '과', '총정리', '방법', '가이드', '완벽'}

    inserted = 0
    for post in selected:
        raw_title = post.get("title", {}).get("rendered", "")
        post_link = post.get("link", "")
        if not raw_title or not post_link:
            continue

        # HTML 엔티티 제거 후 키워드 추출
        plain_title = re.sub(r'<[^>]+>', '', raw_title)
        key_words = [
            w for w in re.split(r'[\s\-–—·\|]+', plain_title)
            if len(w) >= 3 and w not in stopwords
        ]

        # 본문 <p> 태그 목록 수집 (이미 링크 있는 단락 제외)
        para_matches = list(re.finditer(
            r'(<p(?:[^>]*)>)((?:(?!<\/p>).)+?)(</p>)',
            content, re.DOTALL | re.IGNORECASE
        ))

        best_match, best_score = None, 0
        for m in para_matches:
            body = m.group(2)
            if 'freenoma.com' in body:      # 이미 내부링크 있음
                continue
            if len(body.strip()) < 60:      # 너무 짧은 단락
                continue
            score = sum(1 for w in key_words if w in body)
            if score > best_score:
                best_score, best_match = score, m

        if best_match and best_score > 0:
            # 단락 끝에 자연스러운 링크 문장 추가
            link_sentence = (
                f' 자세한 내용은 '
                f'<a href="{post_link}" style="color:#002366;">'
                f'{plain_title}</a>을(를) 참고하세요.'
            )
            new_para = (
                best_match.group(1)
                + best_match.group(2).rstrip()
                + link_sentence
                + best_match.group(3)
            )
            content = content[:best_match.start()] + new_para + content[best_match.end():]
            inserted += 1
        else:
            # 매칭 단락 없으면 마지막 <hr> 앞에 standalone 단락으로 삽입
            last_hr = content.rfind('<hr')
            if last_hr > 0:
                fallback = (
                    f'\n<p>관련 글: '
                    f'<a href="{post_link}" style="color:#002366;">{plain_title}</a></p>\n'
                )
                content = content[:last_hr] + fallback + content[last_hr:]
                inserted += 1

    logger.info(f"내부링크 {inserted}개 삽입 완료")
    return content


# ── 포스팅 메인 플로우 ─────────────────────────────────────
def run_post(slot: int):
    logger.info("=" * 55)
    logger.info(f"  자동 포스팅 시작 | 슬롯: {slot:02d}:00")
    logger.info("=" * 55)

    db = Database()
    wp = WordPressAPI()

    # ── 1. WordPress 연결 확인 ─────────────────────────────
    if not wp.test_connection():
        logger.error("WordPress 연결 실패. 종료합니다.")
        sys.exit(1)

    # ── 2. 카테고리 결정 ───────────────────────────────────
    raw_category = SLOT_CATEGORY_MAP.get(slot)
    if raw_category == "auto":
        category = db.get_rotation_category()
        logger.info(f"18시 교대 카테고리: {category}")
    else:
        category = raw_category

    # ── 3. 키워드 선정 ─────────────────────────────────────
    researcher = KeywordResearcher(db)
    keyword, category = researcher.get_keyword(
        category if category != "trending" else None,
        slot
    )
    logger.info(f"선택 키워드: [{category}] {keyword}")

    # ── 4. 최신 정보 검색 ──────────────────────────────────
    searcher = WebSearcher()
    search_results = searcher.search(keyword, category)
    logger.info(f"검색 컨텍스트: {len(search_results)}자")

    # ── 5. 콘텐츠 생성 ─────────────────────────────────────
    generator = ContentGenerator()
    content_data = generator.generate(keyword, category, search_results)

    title       = content_data["title"]
    seo_title   = content_data.get("seo_title", title)
    meta_desc   = content_data.get("meta_description", "")
    tags        = content_data.get("tags", [])
    html_content = content_data["content"]
    image_count = content_data.get("image_count", 2)
    images      = content_data.get("images", [])

    logger.info(f"제목: {title}")
    logger.info(f"이미지 슬롯: {image_count}개")

    # ── 6. 카테고리 ID 조회 (내부링크·임시저장 공통 사용) ──
    category_id = wp.get_category_id(category)

    # ── 7. 이미지 배치 규칙 적용 → placeholder 삽입 ─────────
    placed_content, total_images = _place_image_placeholders(html_content, image_count)

    # ── 8. placeholder → HTML 주석 + figure 태그 교체 ────
    final_content = _inject_image_html(placed_content, images, total_images, keyword)

    # ── 9. 내부 링크 삽입 (발행글만, 본문 안 자연 삽입) ────
    final_content = _inject_internal_links(final_content, category, category_id, wp)

    # ── 10. WordPress 임시저장 ─────────────────────────────

    post_id = wp.create_draft(
        title=title,
        content=final_content,
        category_id=category_id,
        seo_title=seo_title,
        meta_description=meta_desc,
        tags=tags,
    )

    # ── 11. 이력 저장 ──────────────────────────────────────
    db.add_post(keyword, category, title, post_id, slot)
    if slot == 18:
        db.update_rotation(category)

    # ── 완료 리포트 ────────────────────────────────────────
    logger.info("")
    logger.info("=" * 55)
    logger.info("  ✅ 포스팅 완료!")
    logger.info(f"  카테고리  : {category}")
    logger.info(f"  키워드    : {keyword}")
    logger.info(f"  제목      : {title}")
    logger.info(f"  WP 포스트 : {WP_URL}/?p={post_id}")
    logger.info(f"  편집 링크 : {WP_URL}/wp-admin/post.php?post={post_id}&action=edit")
    logger.info("  ⚠️  검토 후 직접 발행하세요.")
    logger.info("=" * 55)


def test_connection():
    wp = WordPressAPI()
    ok = wp.test_connection()
    if ok:
        print("\n✅ WordPress 연결 성공!")
    else:
        print("\n❌ WordPress 연결 실패. 계정 정보를 확인하세요.")
    sys.exit(0 if ok else 1)


def show_status():
    db = Database()
    posts = db.get_recent_posts(20)
    print(f"\n{'=' * 60}")
    print(f"  최근 포스팅 현황 (최대 20개)")
    print(f"{'=' * 60}")
    if not posts:
        print("  포스팅 이력 없음")
    for p in posts:
        print(f"  [{p['category']}] {p['created_at'][:16]}  WP#{p['wp_post_id']}")
        print(f"    키워드: {p['keyword']}")
        print(f"    제목  : {p['title']}")
        print()
    print(f"  18시 다음 카테고리: {db.get_rotation_category()}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="WordPress 자동 포스팅",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "slot",
        nargs="?",
        type=int,
        choices=[6, 9, 13, 18, 21],
        help="발행 시간 슬롯",
    )
    parser.add_argument("--test", action="store_true", help="WordPress 연결 테스트")
    parser.add_argument("--status", action="store_true", help="포스팅 현황 확인")
    args = parser.parse_args()

    if args.test:
        test_connection()
    elif args.status:
        show_status()
    elif args.slot is not None:
        run_post(args.slot)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
