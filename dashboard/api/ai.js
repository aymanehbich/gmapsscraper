/**
 * Vercel Serverless Function: AI Campaign Copilot (DeepSeek V3)
 */
const { verifyRequest } = require('./_auth');

const SYSTEM_AI_INSTRUCTION = `You are the LeadLaunch AI Outreach Copilot for Aymane. You generate cold email pitches, subject lines, and campaign setups for B2B local business outreach (Plumbers, Electricians, Dentists, Roofers, etc.) in English or French.
When the user asks for a pitch, campaign, or service (e.g. Local SEO, Google Review Automation, Website Redesign, Emergency Booking, etc.), craft a compelling, concise 2-sentence pitch with natural variables (like {{title}}, {{city}}, {{category}}, {{demoLink}}).
IMPORTANT: At the end of your response, output a JSON block wrapped in \`\`\`json containing the campaign parameters so the user can apply it in 1 click:
\`\`\`json
{
  "campaignConfig": {
    "niche": "Target Niche (e.g. Plumber, Dentist, Electrician)",
    "country": "United_States or France or Morocco or United_Kingdom",
    "city": "City name",
    "service": "web_design or custom",
    "custom_service": "Descriptive Service Name (e.g. Local SEO & Maps Top 3, Automated 5-Star Reviews, 24/7 Booking Portal)",
    "custom_subject": "High converting subject line with {{title}} and {{city}}",
    "custom_pitch": "Punchy 2-sentence pitch with {{category}} and {{city}}",
    "demo_link": "https://demo.aymanehbich.com/showcase",
    "depth": 20
  }
}
\`\`\``;

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-hub-auth');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!verifyRequest(req)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const deepseekKey = process.env.DEEPSEEK_API_KEY;
  if (!deepseekKey) {
    return res.status(500).json({ error: 'DEEPSEEK_API_KEY environment variable is not configured on server' });
  }

  const { prompt } = req.body || {};
  if (!prompt) {
    return res.status(400).json({ error: 'Prompt is required' });
  }

  try {
    const aiRes = await fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${deepseekKey.trim()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: [
          { role: 'system', content: SYSTEM_AI_INSTRUCTION },
          { role: 'user', content: prompt }
        ],
        temperature: 0.7
      })
    });

    if (!aiRes.ok) {
      const errData = await aiRes.json().catch(() => ({}));
      return res.status(aiRes.status).json({ error: errData.error?.message || `DeepSeek error ${aiRes.status}` });
    }

    const data = await aiRes.json();
    const text = data.choices?.[0]?.message?.content || '';
    return res.status(200).json({ text });
  } catch (err) {
    return res.status(500).json({ error: err.message || 'Failed to generate AI response' });
  }
};
