"""
한국거래소(KRX) 상장법인목록을 공식 소스에서 받아와 data/krx_stocks.json 으로 저장합니다.
GitHub Actions가 주기적으로 이 스크립트를 실행해 목록을 최신 상태로 유지합니다.

데이터 출처: KRX 상장법인목록 다운로드 (kind.krx.co.kr) — 코스피/코스닥 상장회사 정식 목록
"""

import json
import os
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
    for delta in range(7):  # 주말/공휴일 대비 최근 영업일까지 최대 7일 역순 조회
        date = (datetime.now() - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            tickers = pkstock.get_etf_ticker_list(date)
        except Exception:
            tickers = []
        if tickers:
            break

    etfs = []
    for t in tickers:
        try:
            name = pkstock.get_etf_ticker_name(t)
        except Exception:
            continue
        if name:
            etfs.append({"name": name, "code": t, "market_label": "ETF"})
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

    all_stocks.sort(key=lambda x: x["name"])

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"stocks": all_stocks, "count": len(all_stocks)}, f, ensure_ascii=False, indent=2)

    print(f"[INFO] KRX 종목 {len(all_stocks)}개 저장 완료 -> {OUT_PATH}")


if __name__ == "__main__":
    main()
