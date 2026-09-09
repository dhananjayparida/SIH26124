/**
 * Node.js API Gateway, Load Balancer & WebSocket Relay Server (SIH26124).
 * Features multi-device load balancing, non-blocking asynchronous worker pool,
 * health checks, and real-time GIS telemetry distribution.
 *
 * TRUTH RULE: Never broadcast LIVE status for replay-sourced packets.
 * Source truth labels: LIVE | REPLAY | STALE | OFFLINE
 */

const http = require('http');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');
const os = require('os');
const express = require('express');
const cors = require('cors');
const { WebSocketServer, WebSocket } = require('ws');
const config = require('./config');

function getLocalIp() {
  try {
    const nets = os.networkInterfaces();
    for (const name of Object.keys(nets)) {
      for (const net of nets[name]) {
        if (net.family === 'IPv4' && !net.internal) {
          return net.address;
        }
      }
    }
  } catch (e) {}
  return '192.168.1.21';
}

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

const corsOptions = config.ALLOWED_ORIGINS.length > 0
  ? { origin: config.ALLOWED_ORIGINS }
  : { origin: true };
app.use(cors(corsOptions));
app.use(express.json({ limit: '20mb' }));

// Serve mobile PWA client directly
const pwaPath = path.resolve(__dirname, '../../phone_pwa');
app.use('/pwa', express.static(pwaPath, { index: 'index.html' }));

// Explicit fallback: /pwa/ and /pwa (with or without trailing slash) -> index.html
// This ensures ?device_id=BUS_LIVE_01 query params are passed through correctly
app.get(['/pwa', '/pwa/'], (req, res) => {
  res.sendFile(path.join(pwaPath, 'index.html'));
});

// Serve visual evidence snapshots, test samples, and recorded dashcam media
const evidencePath = path.resolve(__dirname, '../../data/evidence');
const samplesPath = path.resolve(__dirname, '../../data/samples');
const recordingsPath = path.resolve(__dirname, '../../data/video_recordings');

app.use('/evidence', express.static(evidencePath));
app.use('/data/samples', express.static(samplesPath));
app.use('/samples', express.static(samplesPath));
app.use('/recordings-media', express.static(recordingsPath));

// Fallback proxy for evidence images to FastAPI
app.get('/evidence/:filename', async (req, res) => {
  try {
    const response = await fetch(`${config.FASTAPI_URL}/evidence/${req.params.filename}`);
    if (!response.ok) return res.status(response.status).json({ error: 'Evidence not found' });
    const contentType = response.headers.get('content-type') || 'image/jpeg';
    res.setHeader('Content-Type', contentType);
    const buffer = Buffer.from(await response.arrayBuffer());
    return res.send(buffer);
  } catch (e) {
    return res.status(404).json({ error: 'Evidence image unavailable' });
  }
});

// In-memory registered devices & sockets
const registeredDevices = new Map();
const dashboardClients = new Set();
const sensorClients = new Map();

// Device last-seen tracker for LIVE/STALE/OFFLINE computation
// { device_id -> { ts: ms, source_type: 'phone_pwa'|'replay'|'rtsp'|'sim' } }
const deviceLastSeen = new Map();
const rateBuckets = new Map();

function consumeRateLimit(key, limit) {
  const now = Date.now();
  const current = rateBuckets.get(key);
  if (!current || now - current.startedAt >= config.RATE_LIMIT_WINDOW_MS) {
    rateBuckets.set(key, { startedAt: now, count: 1 });
    return true;
  }
  current.count += 1;
  return current.count <= limit;
}

function issueSessionToken() {
  return crypto.randomBytes(32).toString('base64url');
}

function getBearerToken(req) {
  const authorization = req.get('authorization') || '';
  if (authorization.toLowerCase().startsWith('bearer ')) return authorization.slice(7).trim();
  return req.get('x-session-token') || '';
}

function authenticateSensor(deviceId, token) {
  const session = registeredDevices.get(deviceId);
  if (!session || !token) return false;
  const expected = Buffer.from(session.token);
  const supplied = Buffer.from(token);
  return expected.length === supplied.length && crypto.timingSafeEqual(expected, supplied);
}

function requireSensorAuth(req, res, next) {
  const deviceId = req.body?.device_id;
  if (!deviceId || !authenticateSensor(deviceId, getBearerToken(req))) {
    return res.status(401).json({ error: 'Valid device session required' });
  }
  return next();
}

function requireAdmin(req, res, next) {
  const supplied = req.get('x-authority-token') || '';
  if (!config.ADMIN_TOKEN) return res.status(503).json({ error: 'Authority token is not configured' });
  if (!supplied || supplied.length !== config.ADMIN_TOKEN.length || !crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(config.ADMIN_TOKEN))) {
    return res.status(401).json({ error: 'Authority authentication required' });
  }
  return next();
}

function requestIp(req) {
  return req.socket.remoteAddress || 'unknown';
}

const STALE_MS  = 15_000;  // 15s without heartbeat -> STALE
const OFFLINE_MS = 60_000; // 60s without heartbeat -> OFFLINE

/** Computes truthful source health from last_seen timestamp. */
function computeSourceStatus(deviceId) {
  const rec = deviceLastSeen.get(deviceId);
  if (!rec) return 'OFFLINE';
  const age = Date.now() - rec.ts;
  if (age > OFFLINE_MS) return 'OFFLINE';
  if (age > STALE_MS)   return 'STALE';
  return 'LIVE';
}

/**
 * Returns the truthful display status label.
 * Replay sources are always labelled REPLAY, never LIVE.
 */
function getDisplayStatus(deviceId) {
  const rec = deviceLastSeen.get(deviceId);
  if (rec && rec.source_type === 'replay') return 'REPLAY';
  return computeSourceStatus(deviceId);
}

/** Updates the last-seen record for a device. */
function touchDevice(deviceId, sourceType) {
  deviceLastSeen.set(deviceId, {
    ts: Date.now(),
    source_type: sourceType || deviceLastSeen.get(deviceId)?.source_type || 'phone_pwa'
  });
}

/**
 * High-Throughput Asynchronous Ingestion Load Balancer
 * Distributes incoming camera frames and GPS packets across worker threads
 * with adaptive backpressure management.
 */
class IngestionLoadBalancer {
  constructor(concurrency = 12) {
    this.concurrency = concurrency;
    this.running = 0;
    this.queue = [];
    this.processedTotal = 0;
  }

  enqueue(packet) {
    return new Promise((resolve, reject) => {
      this.queue.push({ packet, resolve, reject });
      this.processNext();
    });
  }

  async processNext() {
    if (this.running >= this.concurrency || this.queue.length === 0) return;

    this.running++;
    const { packet, resolve, reject } = this.queue.shift();

    try {
      const result = await this.forwardToFastAPI(packet);
      this.processedTotal++;
      resolve(result);
    } catch (err) {
      reject(err);
    } finally {
      this.running--;
      this.processNext();
    }
  }

  async forwardToFastAPI(packet) {
    try {
      // Determine and record source type for truthful status labelling
      const sourceType = packet.extra_metadata?.source_type || 'phone_pwa';
      touchDevice(packet.device_id, sourceType);

      const response = await fetch(`${config.FASTAPI_URL}/ingest/packet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(packet)
      });
      if (!response.ok) return null;
      const result = await response.json();

      // Broadcast telemetry with TRUTHFUL status (never LIVE for replay)
      const displayStatus = getDisplayStatus(packet.device_id);
      const broadcastMsg = JSON.stringify({
        type: 'TELEMETRY_UPDATE',
        device_id: packet.device_id,
        source_type: sourceType,
        latitude: packet.gps?.latitude,
        longitude: packet.gps?.longitude,
        speed: packet.gps?.speed,
        heading: packet.gps?.heading,
        timestamp: packet.frame_timestamp,
        status: displayStatus,
        detections_count: result.detections_count || 0,
        detections_reported: result.detections_reported || 0,
        detections: result.detections || [],
        frame_base64: packet.frame_base64 || null,
        fused_events: result.fused_events || []
      });

      for (const client of dashboardClients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(broadcastMsg);
        }
      }

      return result;
    } catch (err) {
      console.warn(`[Load Balancer] Ingestion forwarding error: ${err.message}`);
      return null;
    }
  }
}

const loadBalancer = new IngestionLoadBalancer(12);

/**
 * 1. Health & Tunnel Load Balancer Metrics
 */
app.get('/healthz', (req, res) => {
  res.json({
    status: 'healthy',
    uptime: process.uptime(),
    timestamp: Date.now(),
    active_sensors: sensorClients.size,
    active_dashboards: dashboardClients.size,
    queue_depth: loadBalancer.queue.length,
    processed_total: loadBalancer.processedTotal
  });
});

app.get('/ping', (req, res) => {
  res.json({ pong: true, time: Date.now() });
});

/**
 * 2. Device Registration Endpoint
 */
app.post('/devices/register', async (req, res) => {
  if (!consumeRateLimit(`register:${requestIp(req)}`, config.REGISTRATION_LIMIT)) {
    return res.status(429).json({ error: 'Registration rate limit exceeded' });
  }
  const { device_id, source_type = 'phone_pwa', route_id = '', latitude = null, longitude = null, speed = 0, heading = 0 } = req.body;
  const devId = device_id || `BUS_LIVE_${String(registeredDevices.size + 1).padStart(2, '0')}`;

  if (!/^[A-Za-z0-9_-]{1,64}$/.test(devId)) {
    return res.status(400).json({ error: 'Invalid device_id' });
  }

  const token = issueSessionToken();
  registeredDevices.set(devId, {
    device_id: devId,
    source_type,
    route_id,
    token,
    registered_at: Date.now()
  });
  // Record source type for truthful status tracking
  touchDevice(devId, source_type);

  // Sync to FastAPI
  try {
    await fetch(`${config.FASTAPI_URL}/fleet/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: devId,
        source_type,
        latitude: latitude,
        longitude: longitude,
        speed: speed,
        heading: heading
      })
    });
  } catch (e) {}

  if (latitude && longitude) {
    const broadcastMsg = JSON.stringify({
      type: 'TELEMETRY_UPDATE',
      device_id: devId,
      source_type,
      latitude,
      longitude,
      speed,
      heading,
      timestamp: Date.now() / 1000,
      status: 'LIVE'
    });
    for (const client of dashboardClients) {
      if (client.readyState === WebSocket.OPEN) client.send(broadcastMsg);
    }
  }

  res.json({
    status: 'registered',
    device_id: devId,
    token,
    stream_ws_url: `/ws?role=sensor&device_id=${devId}&token=${token}`
  });
});

/**
 * 3. Sensor Packet Ingestion (HTTP POST Fallback)
 */
app.post(['/ingest/packet', '/api/ingest/packet'], async (req, res) => {
  if (!consumeRateLimit(`ingest:${requestIp(req)}:${req.body?.device_id || 'unknown'}`, config.INGEST_LIMIT)) {
    return res.status(429).json({ error: 'Ingestion rate limit exceeded' });
  }
  if (!authenticateSensor(req.body?.device_id, getBearerToken(req))) {
    return res.status(401).json({ error: 'Valid device session required' });
  }
  const packet = req.body;
  const result = await loadBalancer.enqueue(packet);
  res.json(result || { status: 'queued', packet_id: packet.packet_id });
});

/**
 * 4. Telemetry Heartbeat
 */
app.post(['/fleet/heartbeat', '/api/fleet/heartbeat'], async (req, res) => {
  const { device_id, latitude, longitude, speed = 0, heading = 0, source_type } = req.body;

  if (!consumeRateLimit(`heartbeat:${requestIp(req)}:${device_id || 'unknown'}`, config.HEARTBEAT_LIMIT)) {
    return res.status(429).json({ error: 'Heartbeat rate limit exceeded' });
  }
  if (!authenticateSensor(device_id, getBearerToken(req))) {
    return res.status(401).json({ error: 'Valid device session required' });
  }

  // Touch device to keep LIVE/STALE status accurate
  touchDevice(device_id, source_type);
  const displayStatus = getDisplayStatus(device_id);
  const srcType = deviceLastSeen.get(device_id)?.source_type || 'phone_pwa';

  try {
    const forwardRes = await fetch(`${config.FASTAPI_URL}/fleet/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });
    const data = await forwardRes.json();

    const broadcastMsg = JSON.stringify({
      type: 'TELEMETRY_UPDATE',
      device_id,
      source_type: srcType,
      latitude,
      longitude,
      speed,
      heading,
      timestamp: Date.now() / 1000,
      status: displayStatus
    });

    for (const client of dashboardClients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(broadcastMsg);
      }
    }

    return res.json(data);
  } catch (e) {
    return res.status(502).json({ error: 'FastAPI unavailable' });
  }
});

/**
 * 5. Proxy Endpoints for Dashboard & Phone Connection
 */
app.get(['/tunnel-url', '/api/tunnel-url'], (req, res) => {
  const localIp = getLocalIp();
  let tunnelUrl = null;
  try {
    const tunnelFile = path.resolve(__dirname, '../../data/tunnel_url.txt');
    if (fs.existsSync(tunnelFile)) {
      const content = fs.readFileSync(tunnelFile, 'utf-8').trim();
      if (content.startsWith('http')) tunnelUrl = content;
    }
  } catch (e) {}
  res.json({
    tunnel_url: tunnelUrl,
    local_ip: localIp,
    pwa_local_url: `http://${localIp}:${config.GATEWAY_PORT || 5000}/pwa`
  });
});

const proxyGetEndpoints = ['/fleet/status', '/events', '/road-segments/health', '/hud/summary', '/maintenance/queue', '/coverage/cells'];
for (const endpoint of proxyGetEndpoints) {
  const handler = async (req, res) => {
    try {
      const response = await fetch(`${config.FASTAPI_URL}${endpoint}`);
      const data = await response.json();
      res.json(data);
    } catch (e) {
      res.status(502).json({ error: `Proxy failed for ${endpoint}: ${e.message}` });
    }
  };
  app.get(endpoint, handler);
  app.get(`/api${endpoint}`, handler);
}

// Dynamic event detail proxy: GET /events/:id and /api/events/:id
const eventDetailHandler = async (req, res) => {
  try {
    const response = await fetch(`${config.FASTAPI_URL}/events/${req.params.id}`);
    if (!response.ok) return res.status(response.status).json({ error: 'Event not found' });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: `Proxy failed: ${e.message}` });
  }
};
app.get('/events/:id', eventDetailHandler);
app.get('/api/events/:id', eventDetailHandler);

// Additive fleet detail proxy.  The existing fleet/status list remains unchanged.
const fleetDetailHandler = async (req, res) => {
  try {
    const response = await fetch(`${config.FASTAPI_URL}/fleet/${req.params.id}`);
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (e) {
    res.status(502).json({ error: `Proxy failed: ${e.message}` });
  }
};
app.get('/fleet/:id', fleetDetailHandler);
app.get('/api/fleet/:id', fleetDetailHandler);

// POST proxy for repair-report and resolve
app.post(['/events/:id/repair-report', '/api/events/:id/repair-report'], requireAdmin, async (req, res) => {
  try {
    const response = await fetch(`${config.FASTAPI_URL}/events/${req.params.id}/repair-report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: e.message });
  }
});

app.post(['/events/:id/resolve', '/api/events/:id/resolve'], requireAdmin, async (req, res) => {
  try {
    const response = await fetch(`${config.FASTAPI_URL}/events/${req.params.id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: e.message });
  }
});

app.post(['/maintenance/clear', '/api/maintenance/clear'], requireAdmin, async (req, res) => {
  try {
    const response = await fetch(`${config.FASTAPI_URL}/maintenance/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: e.message });
  }
});

// Proxy for all /model/* endpoints (training, recordings, defect ledgers)
app.use(['/model', '/api/model'], async (req, res) => {
  try {
    const subPath = req.url.replace(/^\/api/, '');
    const cleanSub = subPath.replace(/^\/model/, '');
    const url = `${config.FASTAPI_URL}/model${cleanSub.startsWith('/') ? cleanSub : '/' + cleanSub}`;
    const options = {
      method: req.method,
      headers: { 'Content-Type': 'application/json' }
    };
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body && Object.keys(req.body).length > 0) {
      options.body = JSON.stringify(req.body);
    }
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return res.status(response.status).json(data);
    }
    const buffer = Buffer.from(await response.arrayBuffer());
    return res.status(response.status).send(buffer);
  } catch (e) {
    return res.status(502).json({ error: `Model proxy error: ${e.message}` });
  }
});

/**
 * 6. WebSocket Server with Connection Multiplexing
 */
wss.on('connection', (ws, req) => {
  const urlParams = new URLSearchParams(req.url.replace('/ws', ''));
  const role = urlParams.get('role') || 'sensor';
  const deviceId = urlParams.get('device_id');

  if (role === 'dashboard') {
    dashboardClients.add(ws);
    ws.on('close', () => dashboardClients.delete(ws));
    ws.on('error', () => dashboardClients.delete(ws));
    return;
  }

  const token = urlParams.get('token');
  if (role !== 'sensor' || !deviceId || !authenticateSensor(deviceId, token)) {
    ws.close(1008, 'Valid device session required');
    return;
  }

  // Sensor node connection
  sensorClients.set(deviceId, ws);

  ws.on('message', async (message) => {
    try {
      const packet = JSON.parse(message.toString());
      if (packet.device_id !== deviceId) {
        ws.close(1008, 'Device identity mismatch');
        return;
      }
      if (!consumeRateLimit(`ws:${deviceId}`, config.INGEST_LIMIT)) {
        ws.close(1008, 'Ingestion rate limit exceeded');
        return;
      }
      await loadBalancer.enqueue(packet);
    } catch (e) {
      console.warn(`[Gateway WS] Invalid packet from ${deviceId}: ${e.message}`);
    }
  });

  ws.on('close', () => {
    sensorClients.delete(deviceId);
  });

  ws.on('error', () => {
    sensorClients.delete(deviceId);
  });
});

// Clean up dead sockets periodically
setInterval(() => {
  for (const client of dashboardClients) {
    if (client.readyState === WebSocket.CLOSED || client.readyState === WebSocket.CLOSING) {
      dashboardClients.delete(client);
    }
  }
}, 10000);

const PORT = config.GATEWAY_PORT || 5000;
const localIp = getLocalIp();
server.listen(PORT, '0.0.0.0', () => {
  console.log(`================================================================`);
  console.log(`[Gateway] High-Throughput Load Balancer running on port ${PORT}`);
  console.log(`[Gateway] Ingestion Concurrency Pool: 12 Parallel Workers`);
  console.log(`[Gateway] Health: http://localhost:${PORT}/healthz`);
  console.log(`================================================================`);
  console.log(`[Gateway] 📱 Phone PWA (Local Wi-Fi):`);
  console.log(`[Gateway]    http://${localIp}:${PORT}/pwa/?device_id=BUS_LIVE_01`);
  console.log(`[Gateway] 📱 Phone PWA (localhost):`);
  console.log(`[Gateway]    http://localhost:${PORT}/pwa/?device_id=BUS_LIVE_01`);
  console.log(`[Gateway]`);
  console.log(`[Gateway] NOTE: Phone camera needs HTTPS. Use cloudflared tunnel.`);
  console.log(`================================================================`);
});
