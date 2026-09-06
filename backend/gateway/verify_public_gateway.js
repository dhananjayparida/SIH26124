/**
 * Smoke-check the public gateway surface without exposing FastAPI.
 * Usage: GATEWAY_URL=https://your-tunnel.example node verify_public_gateway.js
 */

const baseUrl = (process.env.GATEWAY_URL || 'http://127.0.0.1:5000').replace(/\/$/, '');
const { WebSocket } = require('ws');

async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, options);
  let body = null;
  try { body = await response.json(); } catch (e) {}
  return { response, body };
}

async function main() {
  const health = await request('/healthz');
  if (!health.response.ok || health.body?.status !== 'healthy') throw new Error('Gateway health check failed');

  const unauthorized = await request('/ingest/packet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: 'VERIFY_UNREGISTERED' })
  });
  if (unauthorized.response.status !== 401) throw new Error(`Expected unauthenticated ingest to return 401, got ${unauthorized.response.status}`);

  const deviceId = `VERIFY_${Date.now()}`;
  const registration = await request('/devices/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: deviceId, source_type: 'phone_pwa' })
  });
  if (!registration.response.ok || !registration.body?.token) throw new Error('Device registration did not return a session token');

  const authenticated = await request('/ingest/packet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${registration.body.token}` },
    body: JSON.stringify({
      packet_id: `verify_${Date.now()}`,
      device_id: deviceId,
      frame_timestamp: Date.now() / 1000,
      gps: { latitude: 20.2961, longitude: 85.8245, timestamp: Date.now() / 1000 },
      frame_base64: null,
      extra_metadata: { source_type: 'phone_pwa' }
    })
  });
  if (!authenticated.response.ok) throw new Error(`Authenticated ingest failed with ${authenticated.response.status}`);

  const wsUrl = `${baseUrl.replace(/^http/, 'ws')}/ws?role=sensor&device_id=${deviceId}&token=invalid`;
  const wsResult = await new Promise((resolve, reject) => {
    const socket = new WebSocket(wsUrl);
    const timer = setTimeout(() => { socket.terminate(); reject(new Error('Invalid WebSocket token was not rejected')); }, 5000);
    socket.on('close', (code) => { clearTimeout(timer); resolve(code === 1008); });
    socket.on('error', () => {});
  });
  if (!wsResult) throw new Error('Invalid WebSocket token was not rejected with policy code 1008');

  const tunnel = await request('/tunnel-url');
  if (!tunnel.response.ok) throw new Error('Tunnel URL endpoint failed');

  console.log(JSON.stringify({
    gateway_url: baseUrl,
    health: health.body.status,
    unauthenticated_ingest: unauthorized.response.status,
    authenticated_ingest: authenticated.response.status,
    invalid_websocket: 'REJECTED',
    tunnel_url: tunnel.body.tunnel_url || null,
    public_gateway_check: 'PASS'
  }, null, 2));
}

main().catch((error) => {
  console.error(`Public gateway check failed: ${error.message}`);
  process.exitCode = 1;
});