"""
DuckDuckGo 검색으로 최신 정보 수집
콘텐츠 생성 시 Claude API에 컨텍스트로 제공
"""
import logging
import time
import random

logger = logging.getLogger(__name__)

MAX_RESULTS = 6
SEARCH_TIMEOUT = 15


class WebSearcher:
    def search(self, keyword: str, category: str) -> str:
        """
        키워드 관련 최신 정보를 검색해 문자열로 반환
        실패 시 빈 문자열 반환 (Claude가 자체 지식으로 작성)
        """
        queries = self._build_queries(keyword, category)
        results = []

        for query in queries[:2]:
            try:
                hits = self._ddg_search(query)
                results.extend(hits)
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.warning(f"검색 실패 [{query}]: {e}")

        if not results:
            return ""

        # 중복 제거 후 컨텍스트 문자열 구성
        seen = set()
        context_lines = []
        for r in results:
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            if title and title not in seen:
                seen.add(title)
                context_lines.append(f"- {title}: {body[:200]}")

        context = "\n".join(context_lines[:MAX_RESULTS])
        logger.info(f"검색 결과 {len(context_lines)}건 수집")
        return context

    def _ddg_search(self, query: str) -> list[dict]:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                region="kr-kr",
                safesearch="moderate",
                max_results=MAX_RESULTS,
            ))
        return results

    def _build_queries(self, keyword: str, category: str) -> list[str]:
        import datetime
        year = datetime.datetime.now().year
        queries = [
            f"{keyword} {year}",
            f"{keyword} 방법 조건",
        ]
        if category == "지원정책":
            queries.insert(0, f"{keyword} 신청 {year}")
        elif category == "생활경제":
            queries.insert(0, f"{keyword} 금리 혜택 {year}")
        elif category == "생활건강":
            queries.insert(0, f"{keyword} 효과 방법 {year}")
        return queries
