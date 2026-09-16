/**
 * Vercel Serverless Function: Trigger GitHub Actions Workflow
 */
const { verifyRequest } = require('./_auth');

const GITHUB_OWNER = 'aymanehbich';
const GITHUB_REPO = 'gmapsscraper';
const WORKFLOW_FILE = 'scrape.yml';

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-hub-auth');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!verifyRequest(req)) {
    return res.status(401).json({ error: 'Unauthorized: invalid or missing password' });
  }

  const ghPat = process.env.GH_PAT;
  if (!ghPat) {
    return res.status(500).json({ error: 'GH_PAT environment variable is not configured on server' });
  }

  const {
    niche,
    city = '',
    depth = 20,
    enrich_emails = true,
    send_to_n8n = true,
    service = 'web_design',
    custom_subject = '',
    custom_pitch = '',
    demo_link = ''
  } = req.body || {};

  if (!niche) {
    return res.status(400).json({ error: 'Target niche is required' });
  }

  try {
    const ghRes = await fetch(
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github.v3+json',
          'Authorization': `Bearer ${ghPat.trim()}`,
          'Content-Type': 'application/json',
          'User-Agent': 'LeadLaunch-Serverless'
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: {
            niche,
            city,
            depth: String(depth),
            enrich_emails: Boolean(enrich_emails),
            send_to_n8n: Boolean(send_to_n8n),
            service,
            custom_subject,
            custom_pitch,
            demo_link
          }
        })
      }
    );

    if (ghRes.status === 204) {
      return res.status(200).json({ success: true, message: `Pipeline triggered for ${niche} in ${city || 'all'}` });
    }

    const errData = await ghRes.json().catch(() => ({}));
    return res.status(ghRes.status).json({ error: errData.message || `GitHub error status ${ghRes.status}` });
  } catch (err) {
    return res.status(500).json({ error: err.message || 'Failed to dispatch workflow' });
  }
};
