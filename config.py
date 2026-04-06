import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (.env 없으면 .env.example 기반으로 직접 설정 필요)
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# ── Anthropic ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# ── WordPress ─────────────────────────────────────────────
WP_URL = os.getenv("WP_URL", "https://freenoma.com").rstrip("/")
WP_USER = os.getenv("WP_USER", "omok424642@gmail.com")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "nnUg 5V0u 2ACG GKJb FD27 J5VX")

# ── Gemini ────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Unsplash ──────────────────────────────────────────────
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

# ── 카테고리 설정 ─────────────────────────────────────────
CATEGORIES = ["생활경제", "생활건강", "지원정책"]

# 슬롯별 카테고리 (18시=auto 교대, 21시=trending)
SLOT_CATEGORY_MAP = {
    6:  "생활경제",
    9:  "생활건강",
    13: "지원정책",
    18: "auto",      # 생활경제 ↔ 생활건강 교대
    21: "trending",  # 트렌드 키워드 자동 분류
}

# ── 카테고리별 폴백 키워드 풀 ─────────────────────────────
# pytrends 실패 시 여기서 미사용 키워드 선택
FALLBACK_KEYWORDS = {
    "생활경제": [
        "청년 적금 금리 비교 2025",
        "주택청약 1순위 조건 정리",
        "연말정산 소득공제 항목 총정리",
        "파킹통장 금리 높은 순위",
        "ISA 계좌 개설 조건 혜택",
        "개인사업자 세금 절세 방법",
        "비상금 통장 따로 만드는 법",
        "부업 수입 세금 신고 기준",
        "대출 금리 낮추는 실질적 방법",
        "연금저축 세액공제 최대 한도",
        "실수령액 계산 월급 200만원",
        "재테크 시작 사회초년생 가이드",
        "신용점수 올리는 구체적 방법",
        "전세자금대출 조건 한도 비교",
        "주식 배당금 세금 처리 방법",
    ],
    "생활건강": [
        "40대 기초대사량 높이는 운동",
        "수면 부족 증상 해결 방법",
        "혈압 낮추는 식단 구체적 방법",
        "당뇨 전단계 혈당 관리 식품",
        "비타민D 결핍 자가진단 증상",
        "다이어트 정체기 극복하는 방법",
        "면역력 높이는 음식 순위",
        "공복 유산소 운동 효과 시간",
        "스트레스 해소 과학적 방법",
        "장 건강 유산균 고르는 기준",
        "수분 섭취 하루 권장량 계산",
        "콜레스테롤 낮추는 식습관 변화",
        "근감소증 예방 단백질 섭취법",
        "눈 건강 루테인 복용 시기",
        "갱년기 증상 완화 자연 요법",
    ],
    "지원정책": [
        "청년 월세 지원금 신청법",
        "육아휴직급여 계산 지급 기준",
        "장애인 활동지원 등급 신청",
        "기초생활수급자 조건 재산기준",
        "국민취업지원제도 참여 자격",
        "노인 장기요양등급 신청 방법",
        "임산부 정부 지원 총정리",
        "실업급여 수급 기간 금액 계산",
        "중소기업 청년 소득세 감면",
        "에너지 바우처 신청 대상 방법",
        "주거급여 신청 조건 금액",
        "다자녀 혜택 자녀 2명 이상",
        "청년도약계좌 가입 조건 혜택",
        "저소득층 의료비 지원 종류",
        "자영업자 고용보험 가입 혜택",
    ],
}

# ── 카테고리별 Unsplash 검색 키워드 (사람 없는 오브젝트 중심) ─
CATEGORY_IMAGE_KEYWORDS = {
    "생활경제": ["money", "finance", "calculator", "documents", "chart"],
    "생활건강": ["medicine", "hospital", "health", "vitamin", "exercise"],
    "지원정책": ["government", "documents", "policy", "support", "office"],
}

# ── 기타 ──────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "posts.db"
LOG_DIR = Path(__file__).parent / "logs"
TEMP_DIR = Path(__file__).parent / "temp_images"

LOG_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
