"""
뉴스 수집 모듈
- 네이버 경제 '많이 본 뉴스': 실제 조회수 랭킹 기반, 키워드 필터링
- 네이버 검색 API: 키워드 관련성 순 (보완용)
- Google 뉴스 RSS: 영문 뉴스 (보완용)
"""
import re
import urllib.parse

import feedparser
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

# 네이버 뉴스 섹션 ID
# 100=정치, 101=경제, 102=사회, 104=생활/문화, 105=IT/과학, 106=세계
NAVER_SECTION_ECONOMY = "101"
NAVER_SECTION_WORLD = "106"  # 테슬라 등 해외주식용


def _clean_html(text: str) -> str:
    """HTML 태그 및 특수문자 제거"""
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
    )
    return text.strip()


def fetch_naver_popular_by_keyword(
    keywords: list[str], section_id: str = NAVER_SECTION_ECONOMY, count: int = 5
) -> list[dict]:
    """
    네이버 뉴스 '많이 본 뉴스' 랭킹 페이지에서 키워드 관련 기사 수집.
    실제 조회수 순위 기준이므로 가장 인기 있는 뉴스가 먼저 옴.
    """
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    params = {"rankingType": "popular", "sectionId": section_id}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        results = []
        # 랭킹 기사 목록 파싱 (순위대로 처리 → 자연스럽게 인기순 정렬)
        for item in soup.select("ul.rankingnews_list li, .ranking_section li"):
            title_tag = item.select_one("a.list_title, a.ranking_headline, a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            if not href:
                continue
            link = href if href.startswith("http") else "https://news.naver.com" + href

            # 키워드 포함 여부 확인 (대소문자 무시)
            title_lower = title.lower()
            if any(kw.lower() in title_lower for kw in keywords):
                results.append(
                    {
                        "title": title,
                        "link": link,
                        "source": "네이버많이본뉴스",
                        "popularity": len(results) + 1,  # 랭킹 순위
                    }
                )

            if len(results) >= count:
                break

        return results

    except Exception as e:
        print(f"[네이버 많이 본 뉴스 오류] {keywords}: {e}")
        return []


def fetch_naver_search_by_sim(keyword: str, display: int = 20) -> list[dict]:
    """
    네이버 검색 API - 관련도순(sim) 정렬.
    네이버가 클릭수/반응을 반영한 관련도 점수로 정렬하므로
    인기 기사가 상위에 오는 경향이 있음.
    """
    if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
        return []

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }
    params = {
        "query": keyword,
        "display": display,
        "sort": "sim",  # 관련도순 (클릭/반응 기반)
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "title": _clean_html(item["title"]),
                "link": item["originallink"] or item["link"],
                "source": "네이버검색",
                "popularity": idx + 1,
            }
            for idx, item in enumerate(items)
        ]
    except Exception as e:
        print(f"[네이버 검색 오류] {keyword}: {e}")
        return []


def fetch_google_rss_news(keyword: str, display: int = 5) -> list[dict]:
    """Google 뉴스 RSS - 구글 트렌딩 기사 수집"""
    encoded = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        feed = feedparser.parse(url)
        return [
            {
                "title": _clean_html(entry.get("title", "")),
                "link": entry.get("link", ""),
                "source": "Google뉴스",
                "popularity": idx + 1,
            }
            for idx, entry in enumerate(feed.entries[:display])
        ]
    except Exception as e:
        print(f"[Google RSS 오류] {keyword}: {e}")
        return []


def _merge_and_rank(lists: list[list[dict]], final_count: int) -> list[dict]:
    """
    여러 소스의 뉴스를 합쳐 중복 제거 후 인기순으로 반환.
    먼저 추가된 소스(많이 본 뉴스)가 우선순위를 가짐.
    """
    seen = set()
    merged = []
    for items in lists:
        for item in items:
            title_key = re.sub(r"\s+", "", item["title"])[:30]  # 유사 제목 중복 방지
            if title_key not in seen and item["title"]:
                seen.add(title_key)
                merged.append(item)
    return merged[:final_count]


def collect_all_news() -> dict[str, list[dict]]:
    """
    전체 종목 뉴스 수집 - 인기순 정렬
    우선순위: 네이버 많이본뉴스 > 네이버 검색(관련도순) > Google RSS
    """
    result = {}
    for stock in config.STOCKS:
        name = stock["name"]
        keywords_ko = stock["keywords_ko"]
        keyword_main = keywords_ko[0]

        # 1) 네이버 경제 '많이 본 뉴스'에서 키워드 필터링 (진짜 인기순)
        section = NAVER_SECTION_WORLD if name == "테슬라" else NAVER_SECTION_ECONOMY
        popular = fetch_naver_popular_by_keyword(
            keywords_ko, section_id=section, count=config.NEWS_COUNT
        )

        # 2) 네이버 검색 관련도순 (보완)
        search = fetch_naver_search_by_sim(keyword_main, display=20)

        # 3) Google RSS (보완)
        google = fetch_google_rss_news(stock["keywords_en"], display=config.NEWS_COUNT)

        # 소스 우선순위: 많이본뉴스 → 검색결과 → Google
        merged = _merge_and_rank([popular, search, google], config.NEWS_COUNT)

        result[name] = merged
        sources = [item["source"] for item in merged]
        print(f"[뉴스 수집] {name}: {len(merged)}건 (출처: {', '.join(set(sources))})")

    return result


if __name__ == "__main__":
    news = collect_all_news()
    for name, items in news.items():
        print(f"\n=== {name} ===")
        for i, item in enumerate(items, 1):
            print(f"  {i}. [{item['source']}] {item['title']}")
            print(f"     {item['link']}")
