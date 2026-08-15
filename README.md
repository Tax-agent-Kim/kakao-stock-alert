# 리밸런싱 장부 + 카카오톡 알림

매입가 대비 등락률에 따라 자동으로 매매 신호를 계산하고, 조치가 필요하면 카카오톡으로 알려주는 개인용 투자 대시보드입니다.

## 구조
- `index.html` — GitHub Pages로 배포되는 대시보드 (정적 페이지)
- `data/holdings.json` — 보유종목/관심종목 목록 (직접 수정)
- `data/status.json` — 시세·신호 계산 결과 (자동 생성, 직접 수정 X)
- `scripts/check_prices.py` — 시세 조회 → 신호 계산 → 카카오톡 발송 → status.json 저장
- `scripts/get_kakao_token.py` — 카카오 리프레시 토큰 최초 발급용 (로컬 1회 실행)
- `.github/workflows/check.yml` — 정해진 시간에 자동 실행되는 GitHub Actions

## 1. 저장소 준비
1. 이 폴더 전체를 본인 GitHub 저장소로 올립니다 (새 저장소 생성 후 그대로 push, 또는 웹에서 파일 업로드).
2. 저장소 `Settings > Pages` 에서 Source를 `Deploy from a branch`, 브랜치는 `main`, 폴더는 `/root`로 설정 → 몇 분 뒤 `https://아이디.github.io/저장소이름/` 로 대시보드가 열립니다.

## 2. 카카오 앱 만들기
1. https://developers.kakao.com 접속 → 로그인 → **내 애플리케이션 > 애플리케이션 추가하기**
2. **앱 설정 > 플랫폼 > Web** 등록: 사이트 도메인 `http://localhost:8765`
3. **제품설정 > 카카오 로그인** 활성화 ON
4. **제품설정 > 카카오 로그인 > Redirect URI** 에 `http://localhost:8765/callback` 등록
5. **앱 설정 > 앱 키**에서 **REST API 키** 복사해둡니다

## 3. 리프레시 토큰 발급 (본인 컴퓨터에서 1회만)
```bash
pip install requests
python scripts/get_kakao_token.py YOUR_REST_API_KEY
```
브라우저가 열리면 카카오 로그인 → 동의. 터미널에 `refresh_token`이 출력됩니다.

## 4. GitHub Secrets 등록
저장소 `Settings > Secrets and variables > Actions > New repository secret` 에서 아래 2개 등록:
- `KAKAO_REST_API_KEY` = 2단계에서 복사한 REST API 키
- `KAKAO_REFRESH_TOKEN` = 3단계에서 발급받은 refresh_token

## 5. 보유종목 등록
`data/holdings.json` 을 GitHub 웹 화면에서 직접 열어 수정 (연필 아이콘 클릭 → 수정 → Commit):
```json
{
  "holdings": [
    { "id": "h1", "market": "domestic", "name": "삼성전자", "code": "005930", "buy_price": 70000 },
    { "id": "h2", "market": "overseas", "name": "Apple", "code": "AAPL", "buy_price": 180.0 }
  ],
  "watchlist": [
    { "id": "w1", "market": "domestic", "name": "현대건설", "code": "000720" }
  ]
}
```
- `market`: `domestic`(국내) 또는 `overseas`(해외)
- `code`: 국내는 6자리 종목코드, 해외는 티커(AAPL, TSLA 등)

## 6. 실행 확인
`Actions` 탭 > `리밸런싱 시세 체크` > `Run workflow` 로 수동 실행해 정상 동작하는지 먼저 확인하세요.
평상시에는 `.github/workflows/check.yml`에 설정된 시간(평일 KST 06:10, 15:35)에 자동 실행됩니다. 시간은 파일 상단 주석을 참고해 원하는 대로 수정 가능합니다.

## 참고 / 한계
- 국내 시세는 네이버금융의 **비공식** 엔드포인트를 사용합니다. 공식 API가 아니라 예고 없이 형식이 바뀌거나 막힐 수 있습니다. 더 안정적으로 하려면 공공데이터포털(data.go.kr)의 KRX 시세 API로 교체하는 것을 권장합니다(발급 절차가 조금 더 필요).
- 해외 시세는 `yfinance`(약 15분 지연)를 사용합니다.
- 카카오 액세스 토큰은 몇 시간이면 만료되지만, 매 실행마다 refresh_token으로 자동 갱신합니다. 다만 refresh_token 자체도 일정 기간(보통 약 2개월) 미사용 시 만료될 수 있어, Actions가 실패하면 3단계를 다시 실행해 새 토큰을 발급받아야 할 수 있습니다.
- "나에게 보내기"는 본인에게만 발송되며 카카오톡 친구에게 보내는 기능이 아닙니다. 별도 심사가 필요 없습니다.
