// /api/search-stock?q=Apple&market=overseas
// Vercel 서버리스 함수. 해외 종목 검색용입니다.
// 국내 종목은 공식 KRX 목록(data/krx_stocks.json)에서 브라우저가 직접 검색하므로 이 함수를 거치지 않습니다.

export default async function handler(req, res) {
  const q = (req.query.q || '').toString().trim();

  if (!q) {
    return res.status(400).json({ error: 'query(q) parameter is required' });
  }

  try {
    const results = await searchOverseas(q);
    return res.status(200).json({ results });
  } catch (e) {
    return res.status(500).json({ error: String(e && e.message || e) });
  }
}

async function searchOverseas(q) {
  // Yahoo Finance 비공식 검색 API
  const url = `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=8&newsCount=0`;
  const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (!r.ok) throw new Error(`Yahoo search failed: ${r.status}`);
  const data = await r.json();

  const quotes = data?.quotes || [];
  return quotes
    .filter(x => x.symbol && (x.quoteType === 'EQUITY' || x.quoteType === 'ETF'))
    .map(x => ({
      name: x.shortname || x.longname || x.symbol,
      code: x.symbol,
      market: 'overseas',
      extra: x.exchange || '',
    }))
    .slice(0, 8);
}
