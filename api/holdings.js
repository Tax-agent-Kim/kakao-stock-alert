// /api/holdings
// GET  : holdings.json 내용을 반환 (인증 불필요, 읽기 전용)
// POST : 종목 추가/삭제 (서버에 등록된 GITHUB_TOKEN으로 커밋 수행, 필요시 PIN 확인)
//
// Vercel 프로젝트에 아래 환경변수를 등록해야 합니다 (Settings > Environment Variables):
//   GITHUB_TOKEN  - 이 저장소에 Contents: Read/Write 권한이 있는 Fine-grained PAT
//   GITHUB_OWNER  - 예: Tax-agent-Kim (생략 시 기본값 사용)
//   GITHUB_REPO   - 예: kakao-stock-alert (생략 시 기본값 사용)
//   DASHBOARD_PIN - (선택) 설정해두면 종목 추가/삭제 시 이 PIN이 필요합니다. 비워두면 누구나 수정 가능.

const OWNER = process.env.GITHUB_OWNER || 'Tax-agent-Kim';
const REPO = process.env.GITHUB_REPO || 'kakao-stock-alert';
const TOKEN = process.env.GITHUB_TOKEN;
const FILE_PATH = 'data/holdings.json';

export default async function handler(req, res) {
  if (!TOKEN) {
    return res.status(500).json({ error: 'GITHUB_TOKEN 환경변수가 설정되지 않았습니다. Vercel 프로젝트 Settings > Environment Variables에서 등록해 주세요.' });
  }

  if (req.method === 'GET') {
    try {
      const { data } = await ghGetFile();
      return res.status(200).json(data);
    } catch (e) {
      return res.status(500).json({ error: String(e && e.message || e) });
    }
  }

  if (req.method === 'POST') {
    const requiredPin = process.env.DASHBOARD_PIN;
    if (requiredPin) {
      const providedPin = req.headers['x-dashboard-pin'];
      if (providedPin !== requiredPin) {
        return res.status(401).json({ error: 'PIN이 올바르지 않습니다.' });
      }
    }

    const { action, item } = req.body || {};
    if (!action || !item) {
      return res.status(400).json({ error: 'action과 item이 필요합니다.' });
    }

    try {
      const { data, sha } = await ghGetFile();
      applyAction(data, action, item);
      await ghPutFile(data, sha);
      return res.status(200).json({ ok: true, data });
    } catch (e) {
      return res.status(500).json({ error: String(e && e.message || e) });
    }
  }

  return res.status(405).json({ error: 'Method not allowed' });
}

function applyAction(data, action, item) {
  data.holdings = data.holdings || [];
  data.watchlist = data.watchlist || [];
  if (action === 'add_holding') data.holdings.push(item);
  else if (action === 'remove_holding') data.holdings = data.holdings.filter(h => h.id !== item.id);
  else if (action === 'add_watch') data.watchlist.push(item);
  else if (action === 'remove_watch') data.watchlist = data.watchlist.filter(w => w.id !== item.id);
  else throw new Error(`알 수 없는 action: ${action}`);
}

async function ghGetFile() {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/contents/${FILE_PATH}`;
  const r = await fetch(url, {
    headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/vnd.github+json' },
  });
  if (!r.ok) throw new Error(`GitHub 조회 실패 (${r.status})`);
  const json = await r.json();
  const content = Buffer.from(json.content, 'base64').toString('utf-8');
  return { data: JSON.parse(content), sha: json.sha };
}

async function ghPutFile(data, sha) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/contents/${FILE_PATH}`;
  const body = {
    message: '종목 정보 업데이트 (웹 대시보드)',
    content: Buffer.from(JSON.stringify(data, null, 2), 'utf-8').toString('base64'),
    sha,
  };
  const r = await fetch(url, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`GitHub 저장 실패 (${r.status}): ${await r.text()}`);
}
