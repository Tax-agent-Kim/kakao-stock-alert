"""
한국거래소(KRX) 상장법인목록을 공식 소스에서 받아와 data/krx_stocks.json 으로 저장합니다.
GitHub Actions가 주기적으로 이 스크립트를 실행해 목록을 최신 상태로 유지합니다.

데이터 출처: KRX 상장법인목록 다운로드 (kind.krx.co.kr) — 코스피/코스닥 상장회사 정식 목록
"""

import json
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
from pykrx import stock as pkstock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "krx_stocks.json")

MARKET_TYPES = {
    "stockMkt": "KOSPI",
    "kosdaqMkt": "KOSDAQ",
}


def fetch_market(market_type_param):
    url = f"https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={market_type_param}"
    tables = pd.read_html(url, header=0, encoding="euc-kr")
    df = tables[0]
    return df


def fetch_etfs():
    """ETF는 '상장법인'이 아니라 자산운용사가 발행하는 별도 상품이라
    일반 상장법인목록에는 없음. pykrx를 통해 KRX ETF 목록을 따로 가져온다."""
    tickers = []
    used_date = None
    for delta in range(7):  # 주말/공휴일 대비 최근 영업일까지 최대 7일 역순 조회
        date = (datetime.now() - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            tickers = pkstock.get_etf_ticker_list(date)
        except Exception as e:
            print(f"[WARN] ETF 티커 목록 조회 실패 ({date}): {e}", file=sys.stderr)
            tickers = []
        if tickers:
            used_date = date
            break

    print(f"[INFO] ETF 티커 원본 {len(tickers)}개 조회됨 (기준일: {used_date})")

    etfs = []
    failed = []
    for t in tickers:
        try:
            name = pkstock.get_etf_ticker_name(t)
        except Exception as e:
            failed.append((t, str(e)))
            continue
        if name:
            etfs.append({"name": name, "code": t, "market_label": "ETF"})
        else:
            failed.append((t, "이름 조회 결과 없음"))

    if failed:
        print(f"[WARN] 이름 조회 실패한 ETF {len(failed)}개: {failed[:20]}")

    return etfs


def main():
    all_stocks = []
    for param, market_label in MARKET_TYPES.items():
        df = fetch_market(param)
        for _, row in df.iterrows():
            code = str(row["종목코드"]).zfill(6)
            name = str(row["회사명"]).strip()
            all_stocks.append({"name": name, "code": code, "market_label": market_label})

    etfs = fetch_etfs()
    all_stocks.extend(etfs)
    print(f"[INFO] ETF {len(etfs)}개 포함")

    # 특정 종목이 실제로 최종 목록에 들어갔는지 확인용 (문의 대응 진단용)
    check_codes = ["498400"]
    for code in check_codes:
        found = next((s for s in all_stocks if s["code"] == code), None)
        print(f"[CHECK] 종목코드 {code}: {'포함됨 -> ' + found['name'] if found else '목록에 없음'}")

    all_stocks.sort(key=lambda x: x["name"])

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"stocks": all_stocks, "count": len(all_stocks)}, f, ensure_ascii=False, indent=2)

    print(f"[INFO] KRX 종목 {len(all_stocks)}개 저장 완료 -> {OUT_PATH}")


if __name__ == "__main__":
    main()
