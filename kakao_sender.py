"""
카카오톡 '나에게 보내기' 메시지 전송 모듈
"""
from datetime import datetime

import requests

import config
from token_manager import get_valid_token

KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _build_messages(news_data: dict, report_data: dict) -> list[str]:
    """
    종목별로 메시지를 분리하여 리스트로 반환.
    각 메시지는 2000자 이하.
    - 메시지 1: 헤더
    - 메시지 2~N: 종목별 뉴스 + 리포트
    """
    today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    messages = []

    # 헤더 메시지
    messages.append(
        f"📊 데일리 투자 뉴스 브리핑\n"
        f"📅 {today}\n"
        f"{'━' * 20}\n"
        f"총 {len(config.STOCKS)}개 종목 브리핑을 보내드립니다."
    )

    # 종목별 메시지
    for idx, stock in enumerate(config.STOCKS, 1):
        name = stock["name"]
        icon = stock["icon"]
        lines = [f"{icon} [{name}] ({idx}/{len(config.STOCKS)})", "━" * 20]

        news_items = news_data.get(name, [])
        if news_items:
            lines.append("📰 뉴스")
            for i, item in enumerate(news_items, 1):
                title = item["title"]
                if len(title) > 50:
                    title = title[:47] + "..."
                lines.append(f"{i}. {title}")
                lines.append(f"   🔗 {item['link']}")
        else:
            lines.append("❌ 뉴스를 가져오지 못했습니다.")

        report_items = report_data.get(name, [])
        if report_items:
            lines.append("\n📋 증권사 리포트")
            for r in report_items:
                firm = f"[{r.get('firm', '')}] " if r.get("firm") else ""
                title = r["title"]
                if len(title) > 45:
                    title = title[:42] + "..."
                lines.append(f"• {firm}{title}")

        if idx == len(config.STOCKS):
            lines.append("\n⚡ 투자는 본인 판단하에 신중하게!")

        messages.append("\n".join(lines))

    return messages


def send_kakao_message(text: str, access_token: str) -> bool:
    """
    카카오톡 나에게 보내기 API 호출

    template_object 형식: text 타입
    - text: 본문 (최대 2000자)
    - link: 클릭 시 이동할 링크
    """
    import json

    template = {
        "object_type": "text",
        "text": text[:2000],  # 카카오 제한
        "link": {
            "web_url": "https://finance.naver.com",
            "mobile_web_url": "https://m.finance.naver.com",
        },
        "button_title": "네이버 금융 열기",
    }

    resp = requests.post(
        KAKAO_SEND_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=15,
    )

    if resp.status_code == 200 and resp.json().get("result_code") == 0:
        print(f"[카카오톡 전송 성공] result_code=0")
        return True
    else:
        print(f"[카카오톡 전송 실패] status={resp.status_code}, body={resp.text}")
        return False


def send_daily_briefing(news_data: dict, report_data: dict) -> bool:
    """
    데일리 브리핑 메시지 전송 - 종목별로 분할하여 순서대로 전송
    """
    import time

    print("[카카오 전송] 유효한 토큰 확인 중...")
    access_token = get_valid_token()

    messages = _build_messages(news_data, report_data)
    print(f"[카카오 전송] 총 {len(messages)}개 메시지 전송 시작")

    success_count = 0
    for i, msg in enumerate(messages, 1):
        print(f"[카카오 전송] {i}/{len(messages)} 전송 중... ({len(msg)}자)")
        ok = send_kakao_message(msg, access_token)
        if ok:
            success_count += 1
        if i < len(messages):
            time.sleep(0.5)  # 연속 전송 간격

    print(f"[카카오 전송] {success_count}/{len(messages)} 성공")
    return success_count == len(messages)


if __name__ == "__main__":
    # 테스트용 더미 데이터
    dummy_news = {
        "테슬라": [
            {"title": "테슬라, 신형 Model Y 출시 발표", "link": "https://example.com/1"},
            {"title": "머스크 CEO, AI 투자 확대 계획 공개", "link": "https://example.com/2"},
        ],
        "PLUS 고배당": [
            {"title": "국내 고배당 ETF 수익률 비교", "link": "https://example.com/3"},
        ],
        "금": [
            {"title": "국제 금값 온스당 2400달러 돌파", "link": "https://example.com/4"},
        ],
    }
    dummy_reports: dict = {"테슬라": [], "PLUS 고배당": [], "금": []}

    result = send_daily_briefing(dummy_news, dummy_reports)
    print("전송 결과:", "성공" if result else "실패")
