"""
키워드 조사 모듈
1. Google Trends (pytrends) 에서 한국 트렌드 수집
2. 기존 포스트와 비교해 미사용 키워드 선별
3. 경쟁이 심한 키워드는 롱테일로 우회
4. pytrends 실패 시 카테고리별 폴백 풀 사용
"""
import random
import time
import logging
from typing import Optional

from config import FALLBACK_KEYWORDS, CATEGORIES

logger = logging.getLogger(__name__)


class KeywordResearcher:
    def __init__(self, db):
        self.db = db

    # ── 메인 진입점 ────────────────────────────────────────
    def get_keyword(self, category: Optional[str], slot: int) -> tuple[str, str]:
        """
        반환: (keyword, category)
        - slot 21(trending): category=None → 트렌드 키워드 + 자동 카테고리 분류
        """
        if slot == 21:
            return self._get_trending_keyword()

        # 1차: Google Trends
        try:
            kw = self._from_trends(category)
            if kw:
                logger.info(f"Trends 키워드 선택: {kw}")
                return kw, category
        except Exception as e:
            logger.warning(f"pytrends 실패: {e}")

        # 2차: 폴백 풀
        kw = self._from_fallback(category)
        logger.info(f"폴백 키워드 선택: {kw}")
        return kw, category

    # ── Google Trends ──────────────────────────────────────
    def _from_trends(self, category: str) -> Optional[str]:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ko", tz=540, timeout=(10, 30),
                            retries=2, backoff_factor=0.5)
        time.sleep(random.uniform(1, 3))

        # 한국 실시간 트렌드
        trending_df = pytrends.trending_searches(pn="south_korea")
        trending_list = trending_df[0].tolist()[:30]

        used = set(self.db.get_used_keywords(category))

        for kw in trending_list:
            kw = kw.strip()
            if kw in used:
                continue
            if self._is_relevant(kw, category):
                # 롱테일 변환 (2음절 이하 단일 키워드면 확장)
                return self._make_longtail(kw, category) if len(kw) <= 4 else kw

        # 카테고리 관련 검색어 (related queries)
        seed_keywords = self._get_seed_keywords(category)
        pytrends.build_payload(seed_keywords[:5], geo="KR", timeframe="now 7-d")
        time.sleep(random.uniform(1, 2))
        related = pytrends.related_queries()

        candidates = []
        for seed in seed_keywords[:5]:
            try:
                top = related.get(seed, {}).get("top")
                if top is not None and not top.empty:
                    candidates.extend(top["query"].tolist()[:5])
            except Exception:
                continue

        for kw in candidates:
            if kw.strip() not in used and self._is_relevant(kw, category):
                return kw.strip()

        return None

    # ── 트렌드 슬롯 (21시) ────────────────────────────────
    def _get_trending_keyword(self) -> tuple[str, str]:
        used_all = set(self.db.get_used_keywords())

        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="ko", tz=540, timeout=(10, 30))
            time.sleep(random.uniform(1, 3))
            trending_df = pytrends.trending_searches(pn="south_korea")
            trending_list = trending_df[0].tolist()[:20]

            for kw in trending_list:
                kw = kw.strip()
                if kw in used_all:
                    continue
                cat = self._classify_category(kw)
                if cat:
                    return self._make_longtail(kw, cat) if len(kw) <= 4 else kw, cat
        except Exception as e:
            logger.warning(f"21시 trending 실패: {e}")

        # 폴백: 전 카테고리 미사용 키워드 중 랜덤
        for cat in random.sample(CATEGORIES, len(CATEGORIES)):
            kw = self._from_fallback(cat)
            return kw, cat

        return "재테크 방법 총정리", "생활경제"

    # ── 폴백 풀 ───────────────────────────────────────────
    def _from_fallback(self, category: str) -> str:
        pool = FALLBACK_KEYWORDS.get(category, [])
        used = set(self.db.get_used_keywords(category))
        available = [k for k in pool if k not in used]
        if available:
            return random.choice(available)
        # 전체 소진 시 기존 키워드 재조합 (접두어 추가)
        base = random.choice(pool)
        year = __import__("datetime").datetime.now().year
        return f"{year}년 {base}"

    # ── 카테고리 관련도 판단 ───────────────────────────────
    def _is_relevant(self, keyword: str, category: str) -> bool:
        keywords_map = {
            "생활경제": ["돈", "재테크", "대출", "금리", "적금", "주식", "세금",
                        "소득", "연금", "청약", "부동산", "투자", "절세", "월급",
                        "통장", "지원금", "수당", "혜택", "환급", "경제"],
            "생활건강": ["건강", "다이어트", "운동", "식단", "의료", "병원", "약",
                        "비타민", "영양", "체중", "혈압", "당뇨", "면역", "수면",
                        "피부", "헬스", "칼로리", "건강보험"],
            "지원정책": ["지원", "복지", "혜택", "급여", "수당", "보조금", "정책",
                        "신청", "자격", "청년", "노인", "장애", "육아", "임산부",
                        "실업", "저소득", "주거", "보육", "바우처"],
        }
        hints = keywords_map.get(category, [])
        return any(h in keyword for h in hints)

    def _classify_category(self, keyword: str) -> Optional[str]:
        for cat in CATEGORIES:
            if self._is_relevant(keyword, cat):
                return cat
        return None

    # ── 롱테일 변환 ───────────────────────────────────────
    def _make_longtail(self, keyword: str, category: str) -> str:
        year = __import__("datetime").datetime.now().year
        suffixes = {
            "생활경제": ["조건 총정리", "실제 후기", "신청 방법 단계별", "금액 계산법", f"{year} 최신"],
            "생활건강": ["효과 있는 방법", "주의사항 총정리", "전문가 추천", "증상별 대처법", "실천 가이드"],
            "지원정책": ["신청 자격 조건", "지급 금액 기준", "신청 방법 절차", f"{year} 변경사항", "대상자 확인"],
        }
        suffix_list = suffixes.get(category, ["총정리", "방법", "가이드"])
        return f"{keyword} {random.choice(suffix_list)}"

    # ── 카테고리별 시드 키워드 ────────────────────────────
    def _get_seed_keywords(self, category: str) -> list[str]:
        seeds = {
            "생활경제": ["재테크", "적금", "대출", "주식", "세금"],
            "생활건강": ["건강", "다이어트", "운동", "수면", "영양"],
            "지원정책": ["정부지원", "복지", "청년지원", "육아지원", "실업급여"],
        }
        return seeds.get(category, ["생활정보"])
