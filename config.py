"""
설정 파일: 환경변수 로드 및 검색 키워드 정의
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================
# 카카오 API
# =============================================
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8000/oauth")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
KAKAO_ACCESS_TOKEN = os.getenv("KAKAO_ACCESS_TOKEN", "")
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "")

# =============================================
# 네이버 API
# =============================================
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# =============================================
# 수집 설정
# =============================================
NEWS_COUNT = int(os.getenv("NEWS_COUNT", "5"))
REPORT_COUNT = int(os.getenv("REPORT_COUNT", "3"))

# =============================================
# 종목별 검색 키워드
# =============================================
STOCKS = [
    {
        "name": "테슬라",
        "icon": "🚗",
        "keywords_ko": ["테슬라", "Tesla TSLA"],
        "keywords_en": "Tesla TSLA stock",
        "ticker": "TSLA",
    },
    {
        "name": "PLUS 고배당",
        "icon": "💰",
        "keywords_ko": ["PLUS 고배당", "한국 고배당 ETF", "KODEX 고배당"],
        "keywords_en": "Korea high dividend ETF",
        "ticker": "PLUS고배당",
    },
    {
        "name": "금",
        "icon": "🥇",
        "keywords_ko": ["금 시세", "국제 금값", "Gold 선물"],
        "keywords_en": "Gold price XAU forecast",
        "ticker": "GOLD",
    },
]
