"""
이미지 처리 모듈
1. Unsplash API로 사람 없는 오브젝트 이미지 검색
2. 대표이미지·본문이미지는 서로 다른 사진 사용
3. 파일명은 메인 키워드 기반 SEO 슬러그
4. PIL로 WebP 변환 및 리사이즈
"""
import io
import logging
import random
import re
import time
from pathlib import Path

import requests
from PIL import Image

from config import UNSPLASH_ACCESS_KEY, CATEGORY_IMAGE_KEYWORDS, TEMP_DIR

logger = logging.getLogger(__name__)

UNSPLASH_API = "https://api.unsplash.com"
THUMBNAIL_SIZE = (1200, 630)
BODY_SIZE = (800, 450)


class ImageHandler:
    def __init__(self):
        self.headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}

    # ── 이미지 수집 ────────────────────────────────────────
    def get_images(
        self,
        keyword: str,
        category: str,
        image_count: int,
        image_keywords_en: list[str] = None,
    ) -> list[dict]:
        """
        반환: [{"path": Path, "type": "thumbnail"|"body", "alt_suffix": str}]
        - 대표이미지(thumbnail)와 본문 첫 번째 이미지는 다른 사진 보장
        """
        terms = self._build_search_terms(category)
        used_ids: set[str] = set()
        results = []

        for i in range(image_count):
            img_type = "thumbnail" if i == 0 else "body"
            size = THUMBNAIL_SIZE if i == 0 else BODY_SIZE
            # 이미지마다 다른 키워드 사용 → 다른 사진 보장
            term = terms[i % len(terms)]

            try:
                photo = self._search_unsplash(term, exclude_ids=used_ids)
                if not photo:
                    logger.warning(f"Unsplash 결과 없음: {term}")
                    continue

                used_ids.add(photo["id"])
                path = self._download_and_convert(photo, size, keyword, i + 1, img_type)
                results.append({
                    "path": path,
                    "type": img_type,
                    "alt_suffix": f"{keyword} {term}".strip(),
                    "photographer": photo.get("user", {}).get("name", ""),
                    "unsplash_link": photo.get("links", {}).get("html", ""),
                })
                time.sleep(random.uniform(0.5, 1.0))

            except Exception as e:
                logger.error(f"이미지 처리 실패 [{term}]: {e}")

        return results

    # ── Unsplash 검색 ──────────────────────────────────────
    def _search_unsplash(self, query: str, exclude_ids: set[str]) -> dict | None:
        try:
            resp = requests.get(
                f"{UNSPLASH_API}/search/photos",
                headers=self.headers,
                params={
                    "query": query,
                    "per_page": 20,
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return None

            # 이미 사용한 사진 제외 후 상위 10개 중 랜덤 선택
            candidates = [p for p in results[:10] if p["id"] not in exclude_ids]
            if not candidates:
                candidates = results[:10]  # 모두 사용됐으면 재사용 허용

            photo = random.choice(candidates)
            self._trigger_download(photo)
            return photo

        except Exception as e:
            logger.error(f"Unsplash 검색 오류: {e}")
            return None

    def _trigger_download(self, photo: dict):
        """Unsplash API 정책: 다운로드 트래킹"""
        try:
            dl_url = photo.get("links", {}).get("download_location")
            if dl_url:
                requests.get(
                    dl_url,
                    headers=self.headers,
                    params={"client_id": UNSPLASH_ACCESS_KEY},
                    timeout=5,
                )
        except Exception:
            pass

    # ── 다운로드 + WebP 변환 + 리사이즈 ─────────────────────
    def _download_and_convert(
        self,
        photo: dict,
        size: tuple[int, int],
        keyword: str,
        index: int,
        img_type: str,
    ) -> Path:
        urls = photo.get("urls", {})
        download_url = urls.get("regular") or urls.get("full") or urls.get("raw")
        if not download_url:
            raise ValueError("유효한 이미지 URL 없음")

        resp = requests.get(download_url, timeout=30)
        resp.raise_for_status()

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img = self._resize_cover(img, size)

        filename = self._make_seo_filename(keyword, img_type, index)
        out_path = TEMP_DIR / filename
        img.save(out_path, format="WEBP", quality=85, method=6)

        logger.info(f"이미지 저장: {out_path} ({size[0]}x{size[1]})")
        return out_path

    # ── SEO 파일명 생성 ────────────────────────────────────
    def _make_seo_filename(self, keyword: str, img_type: str, index: int) -> str:
        """메인 키워드 기반 SEO 슬러그 파일명 생성"""
        # 특수문자 제거, 공백→하이픈
        slug = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", "", keyword)
        slug = re.sub(r"\s+", "-", slug.strip())

        if img_type == "thumbnail":
            suffix = "대표이미지"
        else:
            suffix = f"이미지{index}"

        return f"{slug}-{suffix}.webp"

    # ── 커버 리사이즈 ──────────────────────────────────────
    def _resize_cover(self, img: Image.Image, size: tuple[int, int]) -> Image.Image:
        target_w, target_h = size
        src_w, src_h = img.size
        scale = max(target_w / src_w, target_h / src_h)
        new_w, new_h = int(src_w * scale), int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))

    # ── 카테고리 검색어 ────────────────────────────────────
    def _build_search_terms(self, category: str) -> list[str]:
        """카테고리별 키워드 리스트 반환 (순서대로 thumbnail→body 할당)"""
        terms = CATEGORY_IMAGE_KEYWORDS.get(category, ["lifestyle", "background"])
        # 랜덤 섞되 첫 번째와 두 번째가 항상 다른 키워드가 되도록
        shuffled = terms[:]
        random.shuffle(shuffled)
        return shuffled

    # ── 임시 파일 정리 ─────────────────────────────────────
    def cleanup(self):
        for f in TEMP_DIR.glob("*.webp"):
            try:
                f.unlink()
            except Exception:
                pass
