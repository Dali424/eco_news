"""
카카오 액세스 토큰 관리 모듈

최초 1회 실행:
  python token_manager.py

이후 자동으로 리프레시 토큰으로 갱신됨.
토큰은 .env 파일에 저장됩니다.
"""
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import dotenv_values, set_key

import config

ENV_FILE = Path(__file__).parent / ".env"
KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
LOCAL_PORT = 8000  # Redirect URI의 포트와 일치해야 함

_auth_code: list[str] = []  # 로컬 서버가 캡처한 인가 코드 저장


class _OAuthHandler(BaseHTTPRequestHandler):
    """카카오 리다이렉트를 받아 인가 코드를 캡처하는 임시 HTTP 서버"""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        code = params.get("code", [""])[0]

        if code:
            _auth_code.append(code)
            body = "<h2>인증 완료! 창을 닫아도 됩니다.</h2>".encode("utf-8")
            self.send_response(200)
        else:
            body = "<h2>code 파라미터를 찾지 못했습니다.</h2>".encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 서버 로그 숨김


def _wait_for_code(timeout: int = 120) -> str:
    """로컬 서버를 띄워 카카오 리다이렉트에서 인가 코드를 자동 수신"""
    server = HTTPServer(("localhost", LOCAL_PORT), _OAuthHandler)
    server.timeout = timeout

    print(f"[로컬 서버 시작] http://localhost:{LOCAL_PORT} 에서 인가 코드 대기 중...")

    def _serve():
        server.handle_request()  # 요청 1개만 처리 후 종료

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    t.join(timeout=timeout + 2)

    if _auth_code:
        return _auth_code[0]
    raise TimeoutError("인가 코드를 받지 못했습니다. 브라우저에서 로그인했는지 확인하세요.")


def _update_github_secret(secret_name: str, secret_value: str) -> bool:
    """
    GitHub Actions 환경에서 Repository Secret을 자동 갱신.
    GH_TOKEN, GH_REPO 환경변수가 있을 때만 동작.
    """
    gh_token = os.getenv("GH_TOKEN", "")
    gh_repo = os.getenv("GH_REPO", "")  # "username/repo_name" 형식

    if not gh_token or not gh_repo:
        return False

    try:
        import base64
        from nacl import encoding, public

        # 1) 리포지토리 공개키 가져오기
        pub_resp = requests.get(
            f"https://api.github.com/repos/{gh_repo}/actions/secrets/public-key",
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        pub_resp.raise_for_status()
        pub_data = pub_resp.json()
        key_id = pub_data["key_id"]
        pub_key_b64 = pub_data["key"]

        # 2) 값 암호화 (libsodium SealedBox)
        pub_key_obj = public.PublicKey(pub_key_b64.encode(), encoding.Base64Encoder())
        sealed_box = public.SealedBox(pub_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

        # 3) Secret 업데이트
        put_resp = requests.put(
            f"https://api.github.com/repos/{gh_repo}/actions/secrets/{secret_name}",
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/vnd.github+json",
            },
            json={"encrypted_value": encrypted_b64, "key_id": key_id},
            timeout=10,
        )
        put_resp.raise_for_status()
        print(f"[GitHub Secrets 자동 갱신] {secret_name} 업데이트 완료")
        return True

    except Exception as e:
        print(f"[GitHub Secrets 갱신 실패] {secret_name}: {e}")
        return False


def _save_tokens(access_token: str, refresh_token: str = "") -> None:
    """토큰을 .env 파일에 저장하고, GitHub Actions 환경이면 Secrets도 갱신"""
    # 로컬: .env 파일에 저장
    if not ENV_FILE.exists():
        ENV_FILE.write_text("")

    set_key(str(ENV_FILE), "KAKAO_ACCESS_TOKEN", access_token)
    if refresh_token:
        set_key(str(ENV_FILE), "KAKAO_REFRESH_TOKEN", refresh_token)
    print("[토큰 저장 완료] .env 파일에 저장되었습니다.")

    # GitHub Actions 환경: Secrets 자동 갱신
    _update_github_secret("KAKAO_ACCESS_TOKEN", access_token)
    if refresh_token:
        _update_github_secret("KAKAO_REFRESH_TOKEN", refresh_token)


def get_initial_token() -> dict:
    """
    최초 인증: 브라우저로 카카오 로그인 후 인가코드를 입력받아 토큰 발급

    단계:
    1. 브라우저에서 카카오 로그인
    2. 리다이렉트된 URL에서 code 파라미터 복사
    3. 입력하면 액세스 토큰 발급 완료
    """
    if not config.KAKAO_REST_API_KEY:
        print("[오류] KAKAO_REST_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    auth_url = (
        f"{KAKAO_AUTH_URL}"
        f"?client_id={config.KAKAO_REST_API_KEY}"
        f"&redirect_uri={config.KAKAO_REDIRECT_URI}"
        f"&response_type=code"
    )

    print("\n" + "=" * 60)
    print("카카오 인증을 시작합니다.")
    print("=" * 60)
    print(f"\n브라우저에서 카카오 로그인 후 자동으로 인가 코드를 받습니다.\n")
    print(f"인증 URL:\n{auth_url}\n")

    try:
        webbrowser.open(auth_url)
        print("(브라우저가 자동으로 열렸습니다. 카카오 로그인을 완료해주세요.)")
    except Exception:
        print(f"(브라우저를 직접 열어주세요:\n{auth_url})")

    try:
        code = _wait_for_code(timeout=120)
        print(f"[인가 코드 수신 완료]")
    except TimeoutError as e:
        print(f"[오류] {e}")
        sys.exit(1)

    data = {
        "grant_type": "authorization_code",
        "client_id": config.KAKAO_REST_API_KEY,
        "redirect_uri": config.KAKAO_REDIRECT_URI,
        "code": code,
    }
    if config.KAKAO_CLIENT_SECRET:
        data["client_secret"] = config.KAKAO_CLIENT_SECRET

    resp = requests.post(KAKAO_TOKEN_URL, data=data, timeout=10)
    resp.raise_for_status()
    token_data = resp.json()

    if "access_token" not in token_data:
        print(f"[오류] 토큰 발급 실패: {token_data}")
        sys.exit(1)

    _save_tokens(token_data["access_token"], token_data.get("refresh_token", ""))
    print(f"\n[성공] 액세스 토큰 발급 완료!")
    return token_data


def refresh_access_token(refresh_token: str) -> str | None:
    """
    리프레시 토큰으로 액세스 토큰 갱신
    카카오 액세스 토큰 유효기간: 6시간
    리프레시 토큰 유효기간: 60일 (만료 1개월 전부터 자동 갱신)
    """
    data = {
        "grant_type": "refresh_token",
        "client_id": config.KAKAO_REST_API_KEY,
        "refresh_token": refresh_token,
    }
    if config.KAKAO_CLIENT_SECRET:
        data["client_secret"] = config.KAKAO_CLIENT_SECRET

    resp = requests.post(KAKAO_TOKEN_URL, data=data, timeout=10)

    if resp.status_code != 200:
        print(f"[토큰 갱신 실패] status={resp.status_code}: {resp.text}")
        return None

    data = resp.json()
    new_access = data.get("access_token", "")
    new_refresh = data.get("refresh_token", "")  # 갱신된 경우에만 반환됨

    _save_tokens(new_access, new_refresh if new_refresh else refresh_token)
    print("[토큰 갱신 완료]")
    return new_access


def get_valid_token() -> str:
    """
    유효한 액세스 토큰 반환
    - 환경변수에 있으면 그대로 사용 (GitHub Actions용)
    - 없거나 만료 시 리프레시 토큰으로 갱신
    - 리프레시 토큰도 없으면 초기 인증 안내
    """
    # GitHub Actions 환경: 시크릿에서 직접 주입
    access_token = os.getenv("KAKAO_ACCESS_TOKEN", "")
    refresh_token = os.getenv("KAKAO_REFRESH_TOKEN", "")

    if access_token:
        # 토큰 유효성 검사
        resp = requests.get(
            "https://kapi.kakao.com/v1/user/access_token_info",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return access_token
        print("[토큰 만료] 리프레시 토큰으로 갱신 시도...")

    if refresh_token:
        new_token = refresh_access_token(refresh_token)
        if new_token:
            return new_token

    # 토큰이 없거나 갱신 실패 → 최초 인증 필요
    print("\n[안내] 카카오 토큰이 없습니다. 최초 인증을 진행합니다.")
    data = get_initial_token()
    return data["access_token"]


if __name__ == "__main__":
    print("카카오 토큰 초기 발급을 시작합니다...")
    get_initial_token()
