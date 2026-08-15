"""
카카오 리프레시 토큰 최초 발급용 스크립트.
*** 이 스크립트는 GitHub Actions가 아니라, 세무사님 컴퓨터에서 딱 한 번만 실행합니다. ***

사전 준비 (카카오 디벨로퍼스, https://developers.kakao.com):
  1. [내 애플리케이션] > 애플리케이션 추가하기 로 앱 생성
  2. [앱 설정 > 플랫폼] > Web 플랫폼 등록 → 사이트 도메인: http://localhost:8765
  3. [제품설정 > 카카오 로그인] 활성화 ON
  4. [제품설정 > 카카오 로그인 > Redirect URI] 에 http://localhost:8765/callback 등록
  5. [제품설정 > 카카오 로그인 > 동의항목] 에서 "카카오톡 메시지 전송" 항목을 켜기
     (심사 없이 "나에게 보내기"는 바로 사용 가능한 경우가 많지만, 화면에 안내가 뜨면 안내대로 진행)
  6. [앱 설정 > 앱 키] 에서 REST API 키 복사

실행 방법:
  pip install requests
  python get_kakao_token.py  YOUR_REST_API_KEY

브라우저가 열리면 카카오 로그인 후 동의하면 됩니다.
터미널에 refresh_token이 출력되면, 이 값을 GitHub 저장소의
Settings > Secrets and variables > Actions 에 KAKAO_REFRESH_TOKEN 이름으로 등록하세요.
REST API 키는 KAKAO_REST_API_KEY 이름으로 함께 등록하세요.
"""

import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import requests

REDIRECT_URI = "http://localhost:8765/callback"
AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"

auth_code_holder = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if "code" in qs:
            auth_code_holder["code"] = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>인증 완료! 이 창은 닫으셔도 됩니다.</h2>".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 콘솔 로그 억제


def main():
    if len(sys.argv) < 2:
        print("사용법: python get_kakao_token.py YOUR_REST_API_KEY")
        sys.exit(1)

    rest_api_key = sys.argv[1]

    auth_url = (
        f"{AUTH_URL}?client_id={rest_api_key}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    print("브라우저에서 카카오 로그인 창을 엽니다...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8765), CallbackHandler)
    while "code" not in auth_code_holder:
        server.handle_request()

    code = auth_code_holder["code"]
    print("인증 코드 수신 완료. 토큰 교환 중...")

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": rest_api_key,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    resp.raise_for_status()
    payload = resp.json()

    print("\n=== 발급 완료 ===")
    print(f"access_token  (약 몇 시간만 유효, 저장 불필요): {payload['access_token']}")
    print(f"refresh_token (GitHub Secrets에 저장할 값)    : {payload['refresh_token']}")
    print("\nGitHub 저장소 > Settings > Secrets and variables > Actions 에서")
    print("  KAKAO_REST_API_KEY  =", rest_api_key)
    print("  KAKAO_REFRESH_TOKEN =", payload["refresh_token"])
    print("두 개의 Repository secret으로 등록하세요.")


if __name__ == "__main__":
    main()
