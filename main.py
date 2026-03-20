"""
데일리 투자 뉴스 카카오톡 알림 봇 - 메인 실행 파일

실행 방법:
  python main.py

GitHub Actions에서도 동일하게 실행됩니다.
"""
import sys
from datetime import datetime

from kakao_sender import send_daily_briefing
from news_collector import collect_all_news
from report_collector import collect_all_reports


def main() -> int:
    start = datetime.now()
    print(f"\n{'=' * 50}")
    print(f"  데일리 투자 뉴스 봇 시작: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}\n")

    # 1단계: 뉴스 수집
    print("[1/3] 뉴스 수집 중...")
    news_data = collect_all_news()

    # 2단계: 증권사 리포트 수집
    print("\n[2/3] 증권사 리포트 수집 중...")
    report_data = collect_all_reports()

    # 3단계: 카카오톡 전송
    print("\n[3/3] 카카오톡 메시지 전송 중...")
    success = send_daily_briefing(news_data, report_data)

    elapsed = (datetime.now() - start).seconds
    if success:
        print(f"\n✅ 완료! ({elapsed}초 소요) 카카오톡을 확인하세요.")
        return 0
    else:
        print(f"\n❌ 메시지 전송 실패. 로그를 확인하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
