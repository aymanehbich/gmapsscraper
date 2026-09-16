/**
 * Vercel Serverless Function: Fetch Brevo Daily Email Balance
 */
const { verifyRequest } = require('./_auth');

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-hub-auth');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (!verifyRequest(req)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const brevoKey = process.env.BREVO_API_KEY;
  if (!brevoKey) {
    return res.status(200).json({
      configured: false,
      remaining: 300,
      sent: 0,
      percentUsed: 0
    });
  }

  try {
    const brevoRes = await fetch('https://api.brevo.com/v3/account', {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'api-key': brevoKey.trim()
      }
    });

    if (!brevoRes.ok) {
      return res.status(brevoRes.status).json({ error: 'Brevo API authentication error' });
    }

    const data = await brevoRes.json();
    const plans = data.plan || [];
    const sendPlan = plans.find(p => p.creditsType === 'sendLimit') || plans.find(p => p.type === 'free') || { credits: 300 };
    const remainingCredits = typeof sendPlan.credits === 'number' ? Math.round(sendPlan.credits) : 300;
    const totalDaily = 300;
    const estimatedSent = Math.max(0, totalDaily - remainingCredits);
    const percentUsed = Math.min(100, Math.round((estimatedSent / totalDaily) * 100));

    return res.status(200).json({
      configured: true,
      remaining: remainingCredits,
      sent: estimatedSent,
      percentUsed: percentUsed
    });
  } catch (err) {
    return res.status(500).json({ error: err.message || 'Brevo fetch failed' });
  }
};
