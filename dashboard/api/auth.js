/**
 * Vercel Serverless Function: Validate Master Password
 */
module.exports = async (req, res) => {
  // CORS Headers
  res.setHeader('Access-Control-Allow-Credentials', true);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, Authorization, x-hub-auth'
  );

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { password } = req.body || {};
  const masterPassword = process.env.HUB_PASSWORD || 'smnblil2001';

  if (!password || password.trim() !== masterPassword) {
    return res.status(401).json({ success: false, error: 'Invalid workspace password' });
  }

  return res.status(200).json({
    success: true,
    message: 'Authenticated successfully'
  });
};
