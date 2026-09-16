/**
 * Vercel Serverless Function: Fetch Recent Workflow Runs
 */
const { verifyRequest } = require('./_auth');

const GITHUB_OWNER = 'aymanehbich';
const GITHUB_REPO = 'gmapsscraper';
const WORKFLOW_FILE = 'scrape.yml';

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-hub-auth');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (!verifyRequest(req)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const ghPat = process.env.GH_PAT;
  const headers = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'LeadLaunch-Serverless'
  };
  if (ghPat) {
    headers['Authorization'] = `Bearer ${ghPat.trim()}`;
  }

  try {
    const ghRes = await fetch(
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=5`,
      { headers }
    );

    if (!ghRes.ok) {
      const errData = await ghRes.json().catch(() => ({}));
      return res.status(ghRes.status).json({ error: errData.message || `GitHub returned ${ghRes.status}` });
    }

    const data = await ghRes.json();
    return res.status(200).json({ runs: data.workflow_runs || [] });
  } catch (err) {
    return res.status(500).json({ error: err.message || 'Failed to fetch runs' });
  }
};
