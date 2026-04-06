"""
Claude API를 사용해 SEO 최적화 HTML 블로그 콘텐츠 생성
반환: dict {title, seo_title, meta_description, tags, content,
           image_count, image_keywords_en}
"""
import json
import logging
import re
from datetime import datetime

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

# 카테고리별 계산기 힌트
CALCULATOR_HINTS = {
    "생활경제": "이자계산기, 대출상환계산기, 세금계산기, 연금계산기, 절세효과계산기 중 주제에 맞는 것",
    "생활건강": "BMI계산기, 기초대사량계산기, 칼로리계산기, 체지방률계산기, 수분섭취량계산기 중 주제에 맞는 것",
    "지원정책": "지원금계산기, 실업급여계산기, 육아휴직급여계산기, 소득분위계산기 중 주제에 맞는 것",
}

SYSTEM_PROMPT = """당신은 한국 생활정보 블로그(freenoma.com)의 전문 콘텐츠 작가입니다.
SEO에 최적화된 고품질 한국어 블로그 포스트를 HTML 형식으로 작성합니다.

## 핵심 원칙
- 독자가 실제로 행동할 수 있는 구체적인 정보 제공
- 최신 수치, 조건, 금액을 정확하게 기술 (모르면 "확인 필요" 표시)
- 날씨 인사, 안녕하세요, 오늘은~ 같은 진부한 도입부 절대 금지
- 반드시 순수 JSON만 반환 (마크다운 코드블록 없이)"""


def build_user_prompt(keyword: str, category: str, search_results: str) -> str:
    calc_hint = CALCULATOR_HINTS.get(category, "주제에 맞는 실용 계산기")
    today = datetime.now().strftime("%Y년 %m월")

    search_section = f"""
## 최신 참고 정보 ({today} 기준 검색 결과)
{search_results if search_results else "검색 결과 없음 - 최신 지식 기반으로 작성"}
""" if search_results else ""

    return f"""다음 조건으로 블로그 포스트를 작성해주세요.

## 기본 정보
- 카테고리: {category}
- 메인 키워드: {keyword}
- 작성 기준일: {today}
{search_section}

## 작성 조건
1. 제목: 클릭을 유도하는 SEO 제목 (55~60자, 숫자/연도/구체적 표현 포함)
2. 본문: 3,000자 이상 (HTML 태그 제외 순수 텍스트 기준)
3. 도입부: 날씨·계절 인사 금지. 독자의 문제/궁금증을 찌르는 3~4문장의 강렬한 훅
4. 문단: 최대 3~4문장, 짧고 읽기 쉽게
5. 최소 소제목(H2) 5개 이상

## 필수 HTML 구조 (반드시 이 순서)

### 1. 도입부 (훅 2~3 문단)
강렬한 훅 → 독자 공감 → 이 글에서 얻을 것

### 2. 핵심 요약 박스
<blockquote style="background:#f0f4ff;border-left:5px solid #002366;padding:20px 24px;margin:24px 0;border-radius:0 8px 8px 0;">
<h2 style="color:#002366;margin-top:0;">✅ 핵심 요약</h2>
<ul>
<li>핵심 포인트 1</li>
<li>핵심 포인트 2</li>
<li>핵심 포인트 3~5개</li>
</ul>
</blockquote>

### 3. 목차
<h2 style="color:#002366;">📋 목차</h2>
<ul>
<li><a href="#section1" style="color:#002366;">1. 소제목명</a></li>
...각 H2 섹션 링크...
</ul>

### 4. 구분선 (목차 뒤)
<hr style="border:0;border-top:2px solid #002366;margin:32px 0;">

### 5. 소제목 섹션 (최소 5개)
⚠️ 이미지 플레이스홀더(<!--IMAGE_PLACEHOLDER_N-->)는 절대 삽입하지 마세요. 이미지 배치는 별도 처리됩니다.
각 섹션 형식:
<h2 id="section번호" style="color:#002366;">소제목</h2>
<p>내용...</p>
[표가 있으면: div overflow-x:auto 감싼 table]
<hr style="border:0;border-top:1px solid #e0e0e0;margin:28px 0;">  ← 섹션 사이

### 6. 계산기 위젯 (반드시 1개 포함, 아코디언 방식)
위치: 본문 중간 소제목 중 하나 아래
기본 접힘 상태, 클릭 시 펼쳐지는 구조:
<div style="margin:28px 0;">
<button onclick="(function(b){{var p=b.nextElementSibling;var a=b.querySelector('.acc-arrow');if(p.style.display==='block'){{p.style.display='none';a.textContent='▼';}}else{{p.style.display='block';a.textContent='▲';}}}})(this)" style="width:100%;background:#002366;color:#fff;border:none;padding:16px 20px;border-radius:10px;cursor:pointer;font-size:1em;font-weight:bold;text-align:left;display:flex;justify-content:space-between;align-items:center;">
<span>🧮 {calc_hint}</span><span class="acc-arrow">▼</span>
</button>
<div style="display:none;background:#f8f9ff;border:2px solid #002366;border-top:none;padding:28px;border-radius:0 0 10px 10px;">
[실제로 작동하는 HTML + JavaScript 계산기 코드]
<p style="font-size:0.85em;color:#666;margin-top:12px;">※ 참고용 계산기입니다. 정확한 금액은 공식 기관에서 확인하세요.</p>
</div>
</div>

### 7. CTA 박스
<blockquote style="background:#fff3cd;border-left:5px solid #ff9900;padding:20px 24px;margin:28px 0;border-radius:0 8px 8px 0;">
<strong>📌 관련 공식 링크</strong><br>
<ul>
<li><a href="공식URL" target="_blank" rel="noopener">공식 사이트명 바로가기 →</a></li>
<li><a href="https://freenoma.com/관련글/" style="color:#002366;">관련 글: 제목</a></li>
</ul>
</blockquote>

### 8. 마무리 blockquote + 해시태그
<blockquote style="background:#f0f4ff;border-left:5px solid #002366;padding:20px 24px;margin:28px 0;border-radius:0 8px 8px 0;">
<p>마무리 2~3 문장 (독자 행동 유도)</p>
<p style="margin-top:12px;color:#555;font-size:0.9em;">#해시태그1 #해시태그2 #해시태그3 #해시태그4 #해시태그5</p>
</blockquote>

## 외부 링크 규칙
- 통계·수치·법령·기관명 언급 시 해당 공식 사이트 링크를 본문에 자연스럽게 삽입 (2~3개)
- 반드시 target="_blank" rel="noopener" 적용
- 예: 고용노동부 → <a href="https://www.moel.go.kr" target="_blank" rel="noopener">고용노동부</a>
- 예: 국민연금공단 → <a href="https://www.nps.or.kr" target="_blank" rel="noopener">국민연금공단</a>
- 예: 질병관리청 → <a href="https://www.kdca.go.kr" target="_blank" rel="noopener">질병관리청</a>

## 표 형식
<div style="overflow-x:auto;margin:20px 0;">
<table style="width:100%;border-collapse:collapse;font-size:0.95em;">
<thead><tr style="background:#002366;color:#fff;">
<th style="padding:12px;text-align:left;">항목</th>...
</tr></thead>
<tbody>
<tr style="border-bottom:1px solid #ddd;"><td style="padding:10px;">...</td>...</tr>
...
</tbody>
</table>
</div>

## 반환 형식 (반드시 순수 JSON, 마크다운 없이)
{{
  "title": "SEO 최적화 제목 (55~60자)",
  "seo_title": "메타 SEO 제목 (55자 이내)",
  "meta_description": "검색결과 클릭을 유도하는 설명 (반드시 150~160자, 메인 키워드 포함, '지금 확인하세요'류 CTA 포함)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "content": "완전한 HTML 콘텐츠 (위 구조 전체 포함, <!--IMAGE_PLACEHOLDER_1--> 등 포함)",
  "image_count": 2,
  "images": [
    {{
      "filename": "키워드기반-SEO슬러그-대표이미지.webp",
      "prompt": "Gemini 이미지 생성용 영어 프롬프트 (대표이미지 1200x630, 장면 구체적으로)",
      "alt": "SEO 최적화 ALT 태그 (한국어, 키워드 포함)",
      "caption": "이미지 캡션 (한국어, 1문장)"
    }},
    {{
      "filename": "키워드기반-SEO슬러그-이미지2.webp",
      "prompt": "Gemini 이미지 생성용 영어 프롬프트 (본문이미지 800x450, 대표이미지와 다른 장면)",
      "alt": "SEO 최적화 ALT 태그 2 (한국어, 키워드 포함)",
      "caption": "이미지 캡션 2 (한국어, 1문장)"
    }}
  ]
}}

images 배열 규칙:
- filename: 한국어 키워드 기반 하이픈 슬러그 (예: 실업급여-수급기간-대표이미지.webp)
- prompt: Gemini Imagen 생성용 영어 프롬프트. 대표이미지와 본문이미지는 반드시 서로 다른 장면
- alt/caption: 한국어, SEO 키워드 자연스럽게 포함"""


class ContentGenerator:
    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def generate(self, keyword: str, category: str, search_results: str) -> dict:
        logger.info(f"콘텐츠 생성 시작: [{category}] {keyword}")

        user_prompt = build_user_prompt(keyword, category, search_results)

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        logger.debug(f"Claude 응답 길이: {len(raw)}자")

        # JSON 파싱
        data = self._parse_json(raw)

        # 이미지 수 보정 (1~3 범위)
        data["image_count"] = max(1, min(3, int(data.get("image_count", 2))))

        # images 배열 정규화
        images = data.get("images", [])
        data["images"] = images if isinstance(images, list) else []

        # 메타설명 길이 보정 (160자 초과 시 트리밍)
        meta = data.get("meta_description", "")
        if len(meta) > 160:
            meta = meta[:157] + "..."
        data["meta_description"] = meta

        # ⚠️ IMAGE_PLACEHOLDER 배치는 main.py에서 처리
        # Claude가 실수로 삽입한 경우 제거
        content = data.get("content", "")
        content = re.sub(r'\s*<!--IMAGE_PLACEHOLDER_\d+-->\s*', '\n', content)
        data["content"] = content

        logger.info(f"콘텐츠 생성 완료: {data.get('title', '제목없음')}")
        return data

    def _parse_json(self, raw: str) -> dict:
        # 마크다운 코드블록 제거
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # JSON 시작/끝 추출 시도
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            # 디버그용 raw 응답 저장
            from pathlib import Path
            raw_path = Path(__file__).parent / "logs" / f"raw_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            raw_path.write_text(raw, encoding="utf-8")
            logger.error(f"JSON 파싱 실패. 원시 응답 저장: {raw_path}")
            return {
                "title": "콘텐츠 생성 오류",
                "seo_title": "",
                "meta_description": "",
                "tags": [],
                "content": f"<p>콘텐츠 생성 중 오류가 발생했습니다.</p><pre>{raw[:500]}</pre>",
                "image_count": 0,
                "images": [],
            }

    def _inject_placeholder(self, content: str, index: int) -> str:
        """H2 태그 뒤에 이미지 플레이스홀더 삽입"""
        placeholder = f"<!--IMAGE_PLACEHOLDER_{index}-->"
        # index번째 h2 태그 뒤에 삽입
        pattern = r'(<h2[^>]*>.*?</h2>)'
        matches = list(re.finditer(pattern, content, re.DOTALL | re.IGNORECASE))
        # 목차 H2 제외 (index+1번째 H2 뒤에 삽입)
        target_idx = index  # 1-based → 인덱스 offset
        if len(matches) > target_idx:
            m = matches[target_idx]
            insert_pos = m.end()
            content = content[:insert_pos] + f"\n{placeholder}\n" + content[insert_pos:]
        return content
