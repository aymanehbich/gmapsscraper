/**
 * Shared Password & Auth Verification for Serverless Routes
 */
function verifyRequest(req) {
  const masterPassword = process.env.HUB_PASSWORD;
  if (!masterPassword) {
    // If HUB_PASSWORD is not set on Vercel, refuse requests for security
    return false;
  }
  const authHeader = req.headers['authorization'] || req.headers['x-hub-auth'] || '';
  const token = authHeader.replace(/^Bearer\s+/i, '').trim();

  if (!token || token !== masterPassword.trim()) {
    return false;
  }
  return true;
}

module.exports = { verifyRequest };
