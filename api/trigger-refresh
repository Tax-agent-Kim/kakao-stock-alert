// /api/trigger-refresh
// POST 요청 시 GitHub Actions의 '리밸런싱 시세 체크' 워크플로우를 즉시 실행시킵니다.
// GITHUB_TOKEN에 Actions: Read and write 권한이 있어야 합니다.

const OWNER = process.env.GITHUB_OWNER || 'Tax-agent-Kim';
const REPO = process.env.GITHUB_REPO || 'kakao-stock-alert';
const TOKEN = process.env.GITHUB_TOKEN;
const WORKFLOW_FILE = 'check.yml';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }
  if (!TOKEN) {
    return res.status(500).json({ error: 'GITHUB_TOKEN 환경변수가 설정되지 않았습니다.' });
  }

  const requiredPin = process.env.DASHBOARD_PIN;
  if (requiredPin) {
    const providedPin = req.headers['x-dashboard-pin'];
    if (providedPin !== requiredPin) {
      return res.status(401).json({ error: 'PIN이 올바르지 않습니다.' });
    }
  }

  try {
    const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
    const r = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main' }),
    });
    if (r.status !== 204) {
      const text = await r.text();
      throw new Error(`GitHub 실행 요청 실패 (${r.status}): ${text}`);
    }
    return res.status(200).json({ ok: true });
  } catch (e) {
    return res.status(500).json({ error: String(e && e.message || e) });
  }
}
