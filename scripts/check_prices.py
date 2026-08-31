"""
리밸런싱 시세 체크 + 카카오톡 알림 스크립트
GitHub Actions에서 정해진 시간에 자동 실행됩니다.

필요한 환경변수(GitHub Secrets로 등록):
  KAKAO_REST_API_KEY   : 카카오 디벨로퍼스 REST API 키
  KAKAO_REFRESH_TOKEN  : 최초 1회 발급받은 리프레시 토큰 (scripts/get_kakao_token.py로 발급)

동작:
  1. data/holdings.json 을 읽어 보유종목 목록을 가져옴
  2. 국내주식은 네이버금융 시세(비공식), 해외주식은 yfinance로 현재가 조회
  3. 사용자의 매매 원칙에 따라 신호(매수/매도/보유) 계산
  4. 조치가 필요한 종목이 있으면 카카오톡 "나에게 보내기"로 알림 발송
  5. data/status.json 에 계산 결과 저장 (GitHub Pages 대시보드가 이 파일을 읽음)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOLDINGS_PATH = os.path.join(ROOT, "data", "holdings.json")
STATUS_PATH = os.path.join(ROOT, "data", "status.json")
HISTORY_PATH = os.path.join(ROOT, "data", "price_history.json")
HISTORY_MAX_POINTS = 120  # 종목당 최대 보관 일수 (약 4~5개월치)


# ---------- 1. 매매 원칙 ----------
def get_signal(change_pct):
    """매입가 대비 등락률(%)을 받아 신호를 반환한다."""
    if change_pct is None:
        return {"type": "unknown", "label": "현재가 조회 실패", "amount": None}
    c = change_pct
    if c <= -25:
        return {"type": "buy", "label": "추가매수 25%", "amount": 25}
    if c <= -15:
        return {"type": "buy", "label": "추가매수 10%", "amount": 10}
    if c <= -5:
        return {"type": "hold", "label": "관망 (조치 없음)", "amount": None}
    if c >= 100:
        return {"type": "sellall", "label": "전량 매도", "amount": 100}
    if c >= 60:
        return {"type": "sell", "label": "40% 매도", "amount": 40}
    if c >= 45:
        return {"type": "sell", "label": "30% 매도", "amount": 30}
    if c >= 35:
        return {"type": "sell", "label": "20% 매도", "amount": 20}
    if c >= 25:
        return {"type": "sell", "label": "10% 매도", "amount": 10}
    if c >= 5:
        return {"type": "hold", "label": "보유 유지", "amount": None}
    return {"type": "hold", "label": "관망 (조치 없음)", "amount": None}


# ---------- 2. 시세 조회 ----------
def get_domestic_price(code):
    """네이버금융 비공식 API로 국내 종목 현재가를 가져온다.
    이 엔드포인트는 비공식이라 예고 없이 바뀔 수 있다.
    """
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        price = data["datas"][0]["closePrice"]
        return float(str(price).replace(",", ""))
    except Exception as e:
        print(f"[WARN] 국내 시세 조회 실패 ({code}): {e}", file=sys.stderr)
        return None


def get_overseas_price(ticker):
    """yfinance로 해외 종목 현재가(직전 종가)를 가져온다."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="1d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"[WARN] 해외 시세 조회 실패 ({ticker}): {e}", file=sys.stderr)
        return None


def get_current_price(market, code):
    if market == "domestic":
        return get_domestic_price(code)
    return get_overseas_price(code)


# ---------- 2-1. 가격 히스토리 (그래프용) ----------
def load_history():
    if not os.path.exists(HISTORY_PATH):
        return {}
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def record_history(history, holding_id, price):
    """오늘 날짜로 가격 1개를 기록한다. 같은 날 여러 번 실행돼도 그날 값은 최신으로 덮어쓴다."""
    if price is None:
        return
    today = datetime.now(KST).strftime("%Y-%m-%d")
    points = history.setdefault(holding_id, [])
    points = [p for p in points if p.get("date") != today]
    points.append({"date": today, "price": round(price, 2)})
    points.sort(key=lambda p: p["date"])
    history[holding_id] = points[-HISTORY_MAX_POINTS:]


# ---------- 3. 카카오톡 나에게 보내기 ----------
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_kakao_access_token(rest_api_key, refresh_token):
    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    access_token = payload["access_token"]
    new_refresh_token = payload.get("refresh_token")  # 카카오가 새 리프레시 토큰을 줄 때도 있음
    if new_refresh_token:
        print(
            "[INFO] 카카오가 새 refresh_token을 발급했습니다. "
            "GitHub Secrets의 KAKAO_REFRESH_TOKEN 값을 아래 값으로 갱신해 주세요:"
        )
        print(f"[INFO] {new_refresh_token}")
    return access_token


def send_kakao_message(access_token, text, link_url="https://github.com"):
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": "대시보드 열기",
    }
    resp = requests.post(
        KAKAO_SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"[WARN] 카카오 메시지 발송 실패: {resp.status_code} {resp.text}", file=sys.stderr)
    return resp.status_code == 200


# ---------- 4. 메인 로직 ----------
def main():
    with open(HOLDINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    history = load_history()

    holdings = data.get("holdings", [])
    results = []
    action_lines = []

    for h in holdings:
        cur = get_current_price(h["market"], h["code"])
        buy = h["buy_price"]
        qty = h.get("quantity")  # 수량은 선택 입력 항목 (없으면 금액 계산은 건너뜀)
        change = None
        if cur is not None and buy:
            change = (cur - buy) / buy * 100
        sig = get_signal(change)

        entry = {
            **h,
            "current_price": cur,
            "change_pct": round(change, 2) if change is not None else None,
            "signal_type": sig["type"],
            "signal_label": sig["label"],
        }

        if qty:
            buy_amount = buy * qty
            eval_amount = cur * qty if cur is not None else None
            profit_amount = (eval_amount - buy_amount) if eval_amount is not None else None
            entry.update(
                {
                    "buy_amount": round(buy_amount, 2),
                    "eval_amount": round(eval_amount, 2) if eval_amount is not None else None,
                    "profit_amount": round(profit_amount, 2) if profit_amount is not None else None,
                }
            )

        results.append(entry)
        record_history(history, h["id"], cur)

        if sig["type"] in ("buy", "sell", "sellall"):
            pct_str = f"{change:+.1f}%" if change is not None else "N/A"
            action_lines.append(f"- {h['name']} ({pct_str}) → {sig['label']}")

    # 포트폴리오 전체 합계 (수량이 입력된 종목만 집계)
    total_buy = sum(r["buy_amount"] for r in results if r.get("buy_amount") is not None)
    total_eval = sum(r["eval_amount"] for r in results if r.get("eval_amount") is not None)
    portfolio_summary = None
    if total_buy > 0:
        portfolio_summary = {
            "total_buy_amount": round(total_buy, 2),
            "total_eval_amount": round(total_eval, 2),
            "total_profit_amount": round(total_eval - total_buy, 2),
            "total_profit_pct": round((total_eval - total_buy) / total_buy * 100, 2),
        }

    # 관심종목은 매입가가 없어 매매 신호는 계산하지 않고, 현재가만 참고용으로 조회한다.
    watchlist = data.get("watchlist", [])
    watch_results = []
    for w in watchlist:
        cur = get_current_price(w["market"], w["code"])
        watch_results.append({**w, "current_price": cur})
        record_history(history, w["id"], cur)

    status = {
        "updated_at": datetime.now(KST).isoformat(),
        "holdings": results,
        "watchlist": watch_results,
        "portfolio_summary": portfolio_summary,
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(f"[INFO] status.json 저장 완료 (보유 {len(results)}개, 관심 {len(watch_results)}개)")

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[INFO] price_history.json 저장 완료 ({len(history)}개 종목)")

    if action_lines:
        rest_api_key = os.environ.get("KAKAO_REST_API_KEY")
        refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
        if not rest_api_key or not refresh_token:
            print("[WARN] KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 환경변수가 없어 알림을 건너뜁니다.")
            return
        access_token = refresh_kakao_access_token(rest_api_key, refresh_token)
        message = "📈 리밸런싱 알림\n\n" + "\n".join(action_lines)
        ok = send_kakao_message(access_token, message)
        print("[INFO] 카카오톡 알림 발송" + (" 성공" if ok else " 실패"))
    else:
        print("[INFO] 조치가 필요한 종목이 없어 알림을 보내지 않습니다.")


if __name__ == "__main__":
    main()
