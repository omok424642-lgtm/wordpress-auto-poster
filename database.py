"""
SQLite 데이터베이스 관리
- 발행된 포스트 및 키워드 이력 저장
- 18시 슬롯 카테고리 교대 상태 관리
"""
import sqlite3
import logging
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword     TEXT    NOT NULL,
                    category    TEXT    NOT NULL,
                    title       TEXT,
                    wp_post_id  INTEGER,
                    slot        INTEGER,
                    created_at  TEXT    DEFAULT (datetime('now','localtime'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            # 18시 교대 초기값
            conn.execute("""
                INSERT OR IGNORE INTO state (key, value)
                VALUES ('slot18_last_category', '생활건강')
            """)
            conn.commit()
        logger.debug("DB 초기화 완료")

    # ── 포스트 기록 ────────────────────────────────────────
    def add_post(self, keyword: str, category: str, title: str,
                 wp_post_id: int, slot: int):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO posts (keyword, category, title, wp_post_id, slot) "
                "VALUES (?, ?, ?, ?, ?)",
                (keyword, category, title, wp_post_id, slot)
            )
            conn.commit()
        logger.info(f"DB 저장: [{category}] {keyword} → WP ID {wp_post_id}")

    # ── 사용된 키워드 목록 ─────────────────────────────────
    def get_used_keywords(self, category: str = None) -> list[str]:
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT keyword FROM posts WHERE category=?", (category,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT keyword FROM posts").fetchall()
        return [r[0] for r in rows]

    def is_keyword_used(self, keyword: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM posts WHERE keyword=?", (keyword,)
            ).fetchone()
        return row is not None

    # ── 18시 교대 관리 ─────────────────────────────────────
    def get_rotation_category(self) -> str:
        """마지막으로 사용한 카테고리의 반대를 반환"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM state WHERE key='slot18_last_category'"
            ).fetchone()
        last = row[0] if row else "생활건강"
        return "생활경제" if last == "생활건강" else "생활건강"

    def update_rotation(self, used_category: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE state SET value=? WHERE key='slot18_last_category'",
                (used_category,)
            )
            conn.commit()

    # ── 통계 ──────────────────────────────────────────────
    def get_recent_posts(self, limit: int = 10) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT keyword, category, title, wp_post_id, created_at "
                "FROM posts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"keyword": r[0], "category": r[1], "title": r[2],
             "wp_post_id": r[3], "created_at": r[4]}
            for r in rows
        ]
