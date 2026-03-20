"""
증권사 리포트 수집 모듈
- 네이버 금융 리서치 (종목분석 리포트)
- 한경 컨센서스
"""
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# =============================================
# 네이버 금융 - 증권사 리서치 리포트
# =============================================

NAVER_REPORT_URL = "https://finance.naver.com/research/company_list.naver"

# 네이버 금융에서 사용하는 종목 코드 (상장 종목만 해당)
# 테슬라(TSLA)는 해외주식이므로 네이버 리포트 검색어로 처리
NAVER_TICKER_MAP = {
    "테슬라": None,          # 해외주식 → 키워드 검색
    "PLUS 고배당": "278530", # PLUS 고배당주 ETF (코드 예시)
    "금": None,              # 원자재 → 키워드 검색
}


def fetch_naver_research_reports(keyword: str, count: int = 3) -> list[dict]:
    """
    네이버 금융 리서치 - 키워드로 종목 리포트 검색
    URL: https://finance.naver.com/research/company_list.naver
    """
    url = "https://finance.naver.com/research/company_list.naver"
    params = {"searchVal": keyword, "page": 1}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        reports = []
        rows = soup.select("table.type_1 tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 5:
                continue

            title_tag = cols[1].select_one("a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            link = "https://finance.naver.com" + href if href.startswith("/") else href
            firm = cols[2].get_text(strip=True)
            date = cols[4].get_text(strip=True)

            if title:
                reports.append(
                    {
                        "title": title,
                        "link": link,
                        "firm": firm,
                        "date": date,
                        "source": "네이버금융리서치",
                    }
                )
            if len(reports) >= count:
                break

        return reports

    except Exception as e:
        print(f"[네이버 리서치 오류] {keyword}: {e}")
        return []


# =============================================
# 한경 컨센서스 - 종목 리포트
# =============================================

def fetch_hankyung_reports(keyword: str, count: int = 3) -> list[dict]:
    """
    한경 컨센서스에서 키워드 기반 리포트 수집
    URL: https://consensus.hankyung.com/apps.analysis/analysis.list
    """
    url = "https://consensus.hankyung.com/apps.analysis/analysis.list"
    params = {
        "stype": "A",
        "search_text": keyword,
        "pagenum": 1,
        "pagesize": count,
    }

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        reports = []
        rows = soup.select("tbody tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 4:
                continue

            title_tag = row.select_one("a.subject")
            if not title_tag:
                title_tag = row.select_one("td.tit a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            link = "https://consensus.hankyung.com" + href if href.startswith("/") else href

            # 증권사명, 날짜 파싱 (컬럼 위치는 페이지 구조에 따라 조정)
            firm = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            date = cols[-1].get_text(strip=True) if cols else ""

            if title:
                reports.append(
                    {
                        "title": title,
                        "link": link,
                        "firm": firm,
                        "date": date,
                        "source": "한경컨센서스",
                    }
                )
            if len(reports) >= count:
                break

        return reports

    except Exception as e:
        print(f"[한경 컨센서스 오류] {keyword}: {e}")
        return []


# =============================================
# 통합 리포트 수집
# =============================================

def collect_all_reports() -> dict[str, list[dict]]:
    """
    전체 종목 리포트 수집
    Returns: { "테슬라": [...], "PLUS 고배당": [...], "금": [...] }
    """
    result = {}
    for stock in config.STOCKS:
        keyword = stock["keywords_ko"][0]
        reports = []

        # 네이버 금융 리서치 먼저 시도
        reports = fetch_naver_research_reports(keyword, count=config.REPORT_COUNT)

        # 부족하면 한경 컨센서스로 보충
        if len(reports) < config.REPORT_COUNT:
            extra = fetch_hankyung_reports(keyword, count=config.REPORT_COUNT)
            reports += extra

        # 중복 제거
        seen = set()
        unique = []
        for r in reports:
            if r["title"] not in seen:
                seen.add(r["title"])
                unique.append(r)

        result[stock["name"]] = unique[: config.REPORT_COUNT]
        print(f"[리포트 수집] {stock['name']}: {len(result[stock['name']])}건")

    return result


if __name__ == "__main__":
    reports = collect_all_reports()
    for name, items in reports.items():
        print(f"\n=== {name} 리포트 ===")
        for r in items:
            print(f"  [{r.get('firm','')}] {r['title']} ({r.get('date','')})")
            print(f"    {r['link']}")
