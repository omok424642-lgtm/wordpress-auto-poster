"""
WordPress REST API 래퍼
- 카테고리 조회
- 이미지 미디어 업로드
- 포스트 임시저장(draft) 생성
- Yoast SEO 메타 설정
"""
import base64
import logging
import mimetypes
from pathlib import Path
from urllib.parse import quote

import requests

from config import WP_URL, WP_USER, WP_APP_PASSWORD

logger = logging.getLogger(__name__)

API_BASE = f"{WP_URL}/wp-json/wp/v2"


class WordPressAPI:
    def __init__(self):
        # 앱 비밀번호 공백 제거 후 Base64 인코딩
        password = WP_APP_PASSWORD.replace(" ", "")
        cred = f"{WP_USER}:{password}"
        encoded = base64.b64encode(cred.encode()).decode()
        self.auth_headers = {"Authorization": f"Basic {encoded}"}
        self._category_cache: dict[str, int] = {}

    # ── 카테고리 ──────────────────────────────────────────
    def get_category_id(self, name: str) -> int | None:
        if name in self._category_cache:
            return self._category_cache[name]

        try:
            resp = requests.get(
                f"{API_BASE}/categories",
                headers=self.auth_headers,
                params={"search": name, "per_page": 50},
                timeout=15,
            )
            resp.raise_for_status()
            cats = resp.json()
            for cat in cats:
                if cat["name"] == name:
                    self._category_cache[name] = cat["id"]
                    logger.info(f"카테고리 ID: {name} → {cat['id']}")
                    return cat["id"]

            # 없으면 생성
            cat_id = self._create_category(name)
            self._category_cache[name] = cat_id
            return cat_id

        except Exception as e:
            logger.error(f"카테고리 조회 실패: {e}")
            return None

    def _create_category(self, name: str) -> int:
        resp = requests.post(
            f"{API_BASE}/categories",
            headers={**self.auth_headers, "Content-Type": "application/json"},
            json={"name": name},
            timeout=15,
        )
        resp.raise_for_status()
        cat_id = resp.json()["id"]
        logger.info(f"카테고리 생성: {name} → ID {cat_id}")
        return cat_id

    # ── 미디어 업로드 ──────────────────────────────────────
    def upload_image(self, image_path: Path, alt_text: str = "") -> dict:
        """
        반환: {"id": int, "url": str, "alt_text": str}
        """
        filename = image_path.name
        mime = "image/webp"

        with open(image_path, "rb") as f:
            image_data = f.read()

        # 한글 등 비ASCII 파일명: RFC 5987 인코딩
        encoded_name = quote(filename, safe="")
        headers = {
            **self.auth_headers,
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "Content-Type": mime,
        }

        resp = requests.post(
            f"{API_BASE}/media",
            headers=headers,
            data=image_data,
            timeout=60,
        )
        resp.raise_for_status()
        media = resp.json()

        # alt 텍스트 업데이트
        if alt_text:
            requests.post(
                f"{API_BASE}/media/{media['id']}",
                headers={**self.auth_headers, "Content-Type": "application/json"},
                json={"alt_text": alt_text},
                timeout=10,
            )

        logger.info(f"미디어 업로드 완료: ID {media['id']} → {media['source_url']}")
        return {
            "id": media["id"],
            "url": media["source_url"],
            "alt_text": alt_text,
        }

    def upload_images(self, images: list[dict]) -> list[dict]:
        """image_handler.get_images() 결과를 WordPress에 일괄 업로드"""
        uploaded = []
        for img in images:
            try:
                alt = img.get("alt_suffix", "")
                result = self.upload_image(img["path"], alt_text=alt)
                result["alt_suffix"] = alt
                uploaded.append(result)
            except Exception as e:
                logger.error(f"이미지 업로드 실패: {e}")
        return uploaded

    # ── 포스트 생성 (임시저장) ─────────────────────────────
    def create_draft(
        self,
        title: str,
        content: str,
        category_id: int | None,
        seo_title: str = "",
        meta_description: str = "",
        tags: list[str] = None,
    ) -> int:
        """
        WordPress draft 포스트 생성
        반환: post_id
        """
        # 태그 ID 조회/생성
        tag_ids = self._get_or_create_tags(tags or [])

        payload = {
            "title": title,
            "content": content,
            "status": "draft",
            "comment_status": "open",
            "ping_status": "closed",
        }

        if category_id:
            payload["categories"] = [category_id]
        if tag_ids:
            payload["tags"] = tag_ids

        # 메타설명: 표준 WordPress excerpt + Yoast SEO 동시 설정
        if meta_description:
            payload["excerpt"] = meta_description
            payload["meta"] = {
                "_yoast_wpseo_title": seo_title or title,
                "_yoast_wpseo_metadesc": meta_description,
            }
        elif seo_title:
            payload["meta"] = {"_yoast_wpseo_title": seo_title}

        resp = requests.post(
            f"{API_BASE}/posts",
            headers={**self.auth_headers, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        post = resp.json()
        post_id = post["id"]

        logger.info(f"포스트 임시저장 완료: ID {post_id} | {title}")
        logger.info(f"관리자 편집 URL: {WP_URL}/wp-admin/post.php?post={post_id}&action=edit")
        return post_id

    # ── 태그 ──────────────────────────────────────────────
    def _get_or_create_tags(self, tag_names: list[str]) -> list[int]:
        ids = []
        for name in tag_names:
            try:
                # 검색
                resp = requests.get(
                    f"{API_BASE}/tags",
                    headers=self.auth_headers,
                    params={"search": name, "per_page": 10},
                    timeout=10,
                )
                resp.raise_for_status()
                existing = resp.json()
                found = next((t for t in existing if t["name"] == name), None)

                if found:
                    ids.append(found["id"])
                else:
                    # 생성
                    cr = requests.post(
                        f"{API_BASE}/tags",
                        headers={**self.auth_headers, "Content-Type": "application/json"},
                        json={"name": name},
                        timeout=10,
                    )
                    cr.raise_for_status()
                    ids.append(cr.json()["id"])
            except Exception as e:
                logger.warning(f"태그 처리 실패 [{name}]: {e}")
        return ids

    # ── 발행된 글 목록 조회 ───────────────────────────────
    def get_published_posts_by_category(
        self, category_id: int, limit: int = 10
    ) -> list[dict]:
        """같은 카테고리의 발행글(status=publish)만 반환"""
        try:
            resp = requests.get(
                f"{API_BASE}/posts",
                headers=self.auth_headers,
                params={
                    "categories": category_id,
                    "status": "publish",
                    "per_page": limit,
                    "orderby": "date",
                    "order": "desc",
                    "_fields": "id,title,link",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"발행글 조회 실패: {e}")
            return []

    # ── 포스트 permalink 조회 ──────────────────────────────
    def get_post_link(self, post_id: int) -> str | None:
        """WP 포스트 ID로 permalink 반환 (draft 포함)"""
        try:
            resp = requests.get(
                f"{API_BASE}/posts/{post_id}",
                headers=self.auth_headers,
                params={"context": "edit"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                # 발행된 글은 link, draft는 permalink_template 활용
                link = data.get("link") or data.get("guid", {}).get("rendered", "")
                return link or None
            return None
        except Exception as e:
            logger.warning(f"permalink 조회 실패 (ID {post_id}): {e}")
            return None

    # ── 연결 테스트 ────────────────────────────────────────
    def test_connection(self) -> bool:
        try:
            resp = requests.get(
                f"{API_BASE}/users/me",
                headers=self.auth_headers,
                timeout=10,
            )
            if resp.status_code == 200:
                user = resp.json()
                logger.info(f"WordPress 연결 성공: {user.get('name', '')} ({user.get('email', '')})")
                return True
            logger.error(f"WordPress 인증 실패: {resp.status_code} {resp.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"WordPress 연결 오류: {e}")
            return False
