/**
 * Shared Password & Auth Verification for Serverless Routes
 */
function verifyRequest(req) {
  const masterPassword = process.env.HUB_PASSWORD || 'smnblil2001';
  const authHeader = req.headers['authorization'] || req.headers['x-hub-auth'] || '';
  const token = authHeader.replace(/^Bearer\s+/i, '').trim();

  if (!token || token !== masterPassword) {
    return false;
  }
  return true;
}

module.exports = { verifyRequest };
