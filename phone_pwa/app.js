/**
 * Mobile Sensing Node PWA Client (SIH26124).
 * Rock-solid mobile camera streaming, GPS geolocation,
 * and dual-transport WebSocket + HTTP packet transmission.
 */

const state = {
  deviceId: 'BUS_LIVE_01',
  token: null,
  isStreaming: false,
  ws: null,
  watchId: null,
  currentGps: {
    latitude: 20.2961,
    longitude: 85.8245,
    altitude: 45.0,
    speed: 6.8, // m/s (~24.5 km/h)
    heading: 82.0,
    accuracy: 4.0,
    timestamp: Date.now() / 1000
  },
  packetsSent: 0,
  bytesSent: 0,
  lastByteCheck: Date.now(),
  streamInterval: null,
  heartbeatInterval: null,
  testCardInterval: null,
  mediaStream: null,
  pendingDefectInjection: false
};

// UI Elements
const videoEl = document.getElementById('videoElement');
const canvas = document.getElementById('captureCanvas');
const ctx = canvas.getContext('2d');
const statusDot = document.getElementById('statusDot');
const deviceBadge = document.getElementById('deviceBadge');
const fpsHud = document.getElementById('fpsHud');
const netHud = document.getElementById('netHud');
const coordsDisplay = document.getElementById('coordsDisplay');
const speedDisplay = document.getElementById('speedDisplay');
const packetDisplay = document.getElementById('packetDisplay');
const btnToggle = document.getElementById('btnToggleStream');
const btnSimulate = document.getElementById('btnSimulateDefect') || document.getElementById('aiModeIndicator');
const tapPrompt = document.getElementById('tapToStartPrompt');
const connStatusEl = document.getElementById('connStatus');

function setConnStatus(msg, color) {
  if (!connStatusEl) return;
  connStatusEl.textContent = msg;
  connStatusEl.style.color = color || '#94a3b8';
}

// A source is hardware-live only when both a real GPS fix and camera stream are active.
// Any test-card or simulated-GPS fallback is transmitted as `sim` so the dashboard can label it truthfully.
function currentSourceType() {
  const hasLiveCamera = Boolean(state.mediaStream && videoEl?.srcObject && videoEl.videoWidth > 0);
  return state.gpsMode === 'real' && hasLiveCamera ? 'phone_pwa' : 'sim';
}

// SIH26124 — Full 10 defect categories for mobile edge sensing simulation
const SIH_DEFECT_CLASSES = [
  { class_name: 'pothole', label: 'POTHOLE', confidence: 0.92, x: 320, y: 270, w: 140, h: 90 },
  { class_name: 'longitudinal_crack', label: 'LONGITUDINAL CRACK', confidence: 0.88, x: 310, y: 300, w: 220, h: 20 },
  { class_name: 'transverse_crack', label: 'TRANSVERSE CRACK', confidence: 0.86, x: 320, y: 310, w: 20, h: 180 },
  { class_name: 'alligator_crack', label: 'ALLIGATOR CRACK', confidence: 0.89, x: 300, y: 350, w: 170, h: 110 },
  { class_name: 'damaged_road', label: 'DAMAGED ROAD', confidence: 0.84, x: 280, y: 330, w: 220, h: 140 },
  { class_name: 'missing_divider', label: 'MISSING DIVIDER', confidence: 0.81, x: 320, y: 240, w: 60, h: 200 },
  { class_name: 'no_zebracrossing', label: 'MISSING ZEBRA', confidence: 0.87, x: 320, y: 340, w: 450, h: 120 },
  { class_name: 'damaged_signboard', label: 'DAMAGED SIGNBOARD', confidence: 0.83, x: 100, y: 150, w: 90, h: 110 },
  { class_name: 'waterlogging', label: 'WATERLOGGING', confidence: 0.90, x: 320, y: 360, w: 320, h: 160 },
  { class_name: 'debris', label: 'ROAD DEBRIS', confidence: 0.85, x: 250, y: 370, w: 120, h: 80 }
];
let defectCycleIndex = 0;

/**
 * 1. Initialize Device Registration & Heartbeat Keepalive
 */
async function initDevice() {
  const urlParams = new URLSearchParams(window.location.search);
  const requestedId = urlParams.get('device_id') || localStorage.getItem('sih_device_id') || 'BUS_LIVE_01';
  state.deviceId = requestedId;
  deviceBadge.textContent = state.deviceId;

  try {
    const gatewayUrl = `${window.location.protocol}//${window.location.host}`;
    const res = await fetch(`${gatewayUrl}/devices/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: requestedId,
        source_type: currentSourceType(),
        latitude: state.currentGps?.latitude || null,
        longitude: state.currentGps?.longitude || null,
        speed: state.currentGps?.speed || 0,
        heading: state.currentGps?.heading || 0
      })
    });
    const data = await res.json();
    state.deviceId = data.device_id;
    state.token = data.token;
    localStorage.setItem('sih_device_id', state.deviceId);
    deviceBadge.textContent = state.deviceId;
  } catch (e) {
    console.warn(`[PWA] Offline registration fallback for ${requestedId}`);
  }

  // Pre-connect WebSocket
  connectWebSocket();

  // Send keepalive heartbeat every 2.5s
  if (!state.heartbeatInterval) {
    state.heartbeatInterval = setInterval(sendHeartbeat, 2500);
  }
}

async function sendHeartbeat() {
  const gatewayUrl = `${window.location.protocol}//${window.location.host}`;
  try {
    await fetch(`${gatewayUrl}/fleet/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${state.token || ''}` },
      body: JSON.stringify({
        device_id: state.deviceId,
        source_type: currentSourceType(),
        latitude: state.currentGps.latitude,
        longitude: state.currentGps.longitude,
        speed: state.currentGps.speed,
        heading: state.currentGps.heading
      })
    });
  } catch (e) {}
}

const btnGpsReal = document.getElementById('btnGpsReal');
const btnGpsSim = document.getElementById('btnGpsSim');
const gpsStatusPill = document.getElementById('gpsStatusPill');

state.gpsMode = 'sim'; // 'sim' | 'real' (Defaults to GITA College area, Bhubaneswar)
state.hasRealGpsFix = false;
state.prevGps = null;
state.simInterval = null;
state.simWaypointIndex = 0;
state.simSubProgress = 0.0;

// GITA Autonomous College Transit Route, Janla, Bhubaneswar (10 Waypoint Loop)
const BHUBANESWAR_JANPATH_ROUTE = [
  { lat: 20.18000, lon: 85.73800, speedKmh: 22.0 },  // GITA College Main Gate
  { lat: 20.18120, lon: 85.73950, speedKmh: 24.0 },  // NH-16 Service Road
  { lat: 20.18280, lon: 85.74100, speedKmh: 25.5 },  // Janla Square
  { lat: 20.18450, lon: 85.74280, speedKmh: 27.0 },  // Khandagiri Link
  { lat: 20.18600, lon: 85.74450, speedKmh: 28.0 },  // AIIMS Odisha Junction
  { lat: 20.18450, lon: 85.74280, speedKmh: 26.0 },  // Khandagiri Return
  { lat: 20.18280, lon: 85.74100, speedKmh: 25.0 },  // Janla Square Return
  { lat: 20.18120, lon: 85.73950, speedKmh: 24.0 },  // NH-16 Return
  { lat: 20.18000, lon: 85.73800, speedKmh: 23.0 },  // GITA Gate Return
  { lat: 20.17880, lon: 85.73680, speedKmh: 22.0 }   // Campus Loop End
];

function setGpsModeUI(mode) {
  if (btnGpsSim && btnGpsReal) {
    if (mode === 'sim') {
      btnGpsSim.style.background = '#0284c7';
      btnGpsSim.style.color = '#fff';
      btnGpsReal.style.background = '#1e293b';
      btnGpsReal.style.color = '#94a3b8';
      if (gpsStatusPill) {
        gpsStatusPill.textContent = 'GITA ROUTE (SIM)';
        gpsStatusPill.style.background = 'rgba(56,189,248,0.2)';
        gpsStatusPill.style.color = '#38bdf8';
      }
    } else {
      btnGpsReal.style.background = '#0284c7';
      btnGpsReal.style.color = '#fff';
      btnGpsSim.style.background = '#1e293b';
      btnGpsSim.style.color = '#94a3b8';
      if (gpsStatusPill) {
        gpsStatusPill.textContent = 'HARDWARE GPS';
        gpsStatusPill.style.background = 'rgba(16,185,129,0.2)';
        gpsStatusPill.style.color = '#10b981';
      }
    }
  }
}

function activateSimMode(reason = '') {
  state.gpsMode = 'sim';
  setGpsModeUI('sim');
  if (state.watchId && 'geolocation' in navigator) {
    navigator.geolocation.clearWatch(state.watchId);
    state.watchId = null;
  }
  startSimulatedMotion();
  console.log(`[PWA] Switched to GITA College Transit Loop${reason ? ' (' + reason + ')' : ''}`);
}

function activateRealGps() {
  state.gpsMode = 'real';
  setGpsModeUI('real');
  stopSimulatedMotion();

  if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    alert('Notice: Mobile browsers (Chrome/Safari) restrict hardware GPS to secure HTTPS origins. Falling back to GITA College area simulation.');
    activateSimMode('HTTP origin blocked');
    return;
  }

  startHardwareGps();
}

if (btnGpsReal && btnGpsSim) {
  btnGpsReal.addEventListener('click', activateRealGps);
  btnGpsSim.addEventListener('click', () => activateSimMode('User selected'));
}

// Click to copy coordinates
if (coordsDisplay) {
  coordsDisplay.style.cursor = 'pointer';
  coordsDisplay.title = 'Tap to copy GPS coordinates';
  coordsDisplay.addEventListener('click', () => {
    const text = `${state.currentGps.latitude.toFixed(6)}, ${state.currentGps.longitude.toFixed(6)}`;
    navigator.clipboard.writeText(text).then(() => {
      const orig = coordsDisplay.textContent;
      coordsDisplay.textContent = 'COPIED TO CLIPBOARD!';
      setTimeout(() => { coordsDisplay.textContent = orig; }, 1200);
    }).catch(() => {});
  });
}

/**
 * 2. Geolocation Tracking with Delta-Speed Precision & Automatic Fallback
 */
function startHardwareGps() {
  if ('geolocation' in navigator) {
    navigator.geolocation.getCurrentPosition(
      (pos) => handleGpsUpdate(pos),
      (err) => {
        console.warn('[PWA] Immediate hardware GPS fix query error:', err.message);
        if (!state.hasRealGpsFix) {
          activateSimMode('GPS fix unavailable');
        }
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 0 }
    );

    if (state.watchId) navigator.geolocation.clearWatch(state.watchId);
    state.watchId = navigator.geolocation.watchPosition(
      (pos) => handleGpsUpdate(pos),
      (err) => {
        console.warn('[PWA] Real GPS fix error:', err.message);
        if (!state.hasRealGpsFix && state.gpsMode === 'real') {
          activateSimMode('Hardware GPS lost');
        }
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 8000 }
    );
  } else {
    activateSimMode('Geolocation API unsupported');
  }
}

function handleGpsUpdate(pos) {
  if (state.gpsMode !== 'real') return;
  state.hasRealGpsFix = true;

  let speedVal = pos.coords.speed;
  let headingVal = pos.coords.heading;
  const nowSec = pos.timestamp / 1000;

  // Compute speed & heading from consecutive GPS updates when browser returns null or 0
  if (state.prevGps) {
    const dt = nowSec - state.prevGps.timestamp;
    if (dt > 0.4 && dt < 20) {
      const dLat = (pos.coords.latitude - state.prevGps.latitude) * 111139;
      const dLon = (pos.coords.longitude - state.prevGps.longitude) * 111139 * Math.cos(pos.coords.latitude * Math.PI / 180);
      const distMeters = Math.sqrt(dLat * dLat + dLon * dLon);
      const calcSpeed = distMeters / dt; // in m/s

      if (speedVal === null || isNaN(speedVal) || (speedVal === 0 && distMeters > 0.5)) {
        speedVal = calcSpeed;
      }
      if (distMeters > 0.8) {
        headingVal = (Math.atan2(dLon, dLat) * 180 / Math.PI + 360) % 360;
      }
    }
  }

  state.prevGps = {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
    timestamp: nowSec
  };

  state.currentGps = {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
    altitude: pos.coords.altitude || 45.0,
    speed: speedVal !== null && !isNaN(speedVal) && speedVal >= 0 ? speedVal : 0.0,
    heading: headingVal !== null && !isNaN(headingVal) ? headingVal : (state.currentGps?.heading || 0.0),
    accuracy: pos.coords.accuracy || 3.0,
    timestamp: nowSec
  };

  setGpsModeUI('real');
  updateTelemetryUI();
  sendHeartbeat();
}

function stepSimulatedMotion() {
  // Advance smoothly along Janpath waypoints
  state.simSubProgress += 0.15;
  if (state.simSubProgress >= 1.0) {
    state.simSubProgress = 0.0;
    state.simWaypointIndex = (state.simWaypointIndex + 1) % BHUBANESWAR_JANPATH_ROUTE.length;
  }

  const currWp = BHUBANESWAR_JANPATH_ROUTE[state.simWaypointIndex];
  const nextWp = BHUBANESWAR_JANPATH_ROUTE[(state.simWaypointIndex + 1) % BHUBANESWAR_JANPATH_ROUTE.length];
  const t = state.simSubProgress;

  // Linear interpolation between waypoints
  const lat = currWp.lat + (nextWp.lat - currWp.lat) * t;
  const lon = currWp.lon + (nextWp.lon - currWp.lon) * t;

  // True spherical bearing calculation
  const dLon = (nextWp.lon - currWp.lon) * Math.PI / 180;
  const lat1 = currWp.lat * Math.PI / 180;
  const lat2 = nextWp.lat * Math.PI / 180;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  const heading = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;

  // Realistic transit speed (km/h -> m/s)
  const baseKmh = currWp.speedKmh + (Math.sin(Date.now() / 2000) * 1.5);
  const speedMs = baseKmh / 3.6;

  state.currentGps = {
    latitude: lat,
    longitude: lon,
    altitude: 45.0,
    speed: speedMs,
    heading: heading,
    accuracy: 3.5,
    timestamp: Date.now() / 1000
  };

  updateTelemetryUI();
  sendHeartbeat();
}

function startSimulatedMotion() {
  stopSimulatedMotion();
  stepSimulatedMotion(); // Immediate first tick
  state.simInterval = setInterval(() => {
    if (state.gpsMode === 'sim') {
      stepSimulatedMotion();
    }
  }, 800);
}

function stopSimulatedMotion() {
  if (state.simInterval) {
    clearInterval(state.simInterval);
    state.simInterval = null;
  }
}

function updateTelemetryUI() {
  coordsDisplay.textContent = `${state.currentGps.latitude.toFixed(5)}, ${state.currentGps.longitude.toFixed(5)}`;
  const kmh = ((state.currentGps.speed || 0) * 3.6).toFixed(1);
  const acc = state.currentGps.accuracy ? `±${state.currentGps.accuracy.toFixed(1)}m` : '±3m';
  speedDisplay.textContent = `${kmh} km/h | ${acc}`;
  packetDisplay.textContent = `${state.packetsSent} sent`;
}

/**
 * 3. WebSocket Connection
 */
function connectWebSocket() {
  if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = state.token || '';
    const wsUrl = `${wsProto}//${window.location.host}/ws?role=sensor&device_id=${encodeURIComponent(state.deviceId)}&token=${encodeURIComponent(token)}`;

    setConnStatus('⬤ CONNECTING...', '#f59e0b');
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
      console.log('[PWA] WebSocket connected -> LIVE');
      statusDot.classList.add('connected');
      setConnStatus('⬤ LIVE WS', '#10b981');
    };

    state.ws.onclose = (ev) => {
      statusDot.classList.remove('connected');
      setConnStatus('⬤ HTTP FALLBACK', '#f59e0b');
      console.log(`[PWA] WebSocket closed (${ev.code}). Using HTTP fallback.`);
      if (state.isStreaming) {
        setTimeout(connectWebSocket, 3000);
      }
    };

    state.ws.onerror = (err) => {
      statusDot.classList.remove('connected');
      setConnStatus('⬤ WS ERROR', '#ef4444');
    };
  } catch (e) {
    console.warn('[PWA] WebSocket init error, will use HTTP fallback:', e.message);
    setConnStatus('⬤ HTTP ONLY', '#f59e0b');
  }
}

async function checkTunnelStatus() {
  // Always try to get tunnel URL; banner only shown on HTTP
  try {
    const res = await fetch('/tunnel-url');
    if (res.ok) {
      const data = await res.json();
      if (data.tunnel_url && window.location.protocol === 'http:') {
        const banner = document.getElementById('httpsBanner');
        const btn = document.getElementById('httpsSwitchBtn');
        if (banner && btn) {
          btn.href = `${data.tunnel_url}/pwa/?device_id=${encodeURIComponent(state.deviceId)}`;
          banner.classList.add('visible');
        }
      }
    }
  } catch (e) {}
}

/**
 * 4. Safe Mobile Camera Initialization (Zero-Crash Fallback)
 */
async function startCamera() {
  // Check if camera API is available
  // On HTTP (non-localhost), mobile browsers block camera
  const isSecure = window.isSecureContext ||
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1';

  if (!isSecure || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.warn('[PWA] Camera API unavailable — not a secure context (HTTP on mobile).');

    // Try to offer the HTTPS tunnel link
    try {
      const res = await fetch('/tunnel-url');
      if (res.ok) {
        const data = await res.json();
        if (data.tunnel_url) {
          const targetUrl = `${data.tunnel_url}/pwa/?device_id=${encodeURIComponent(state.deviceId)}`;
          // Show banner
          const banner = document.getElementById('httpsBanner');
          const btn = document.getElementById('httpsSwitchBtn');
          if (banner && btn) { btn.href = targetUrl; banner.classList.add('visible'); }

          const doSwitch = confirm(
            'Mobile Chrome/Safari blocks live camera over plain HTTP.\n\n' +
            'A secure HTTPS tunnel is available!\n\n' +
            'Tap OK to switch to HTTPS and enable live camera.'
          );
          if (doSwitch) { window.location.href = targetUrl; return; }
        }
      }
    } catch (e) {}

    // Fallback: inform user and use simulated test card
    const origin = window.location.origin;
    const flagUrl = 'chrome://flags/#unsafely-treat-insecure-origin-as-secure';
    alert(
      'Camera blocked on HTTP.\n\n' +
      'To enable live camera:\n' +
      '  1. Use the HTTPS tunnel URL shown in start.bat output, OR\n' +
      '  2. On Chrome Android: ' + flagUrl + '\n' +
      '     Add: ' + origin + '\n\n' +
      'Using simulated sensor stream for now.'
    );
    startTestCardStream();
    return;
  }

  let stream = null;

  // Try 1: Back camera with ideal 640x480 resolution
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
  } catch (e1) {
    // Try 2: Simple back camera
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false
      });
    } catch (e2) {
      // Try 3: Any available video device
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      } catch (e3) {
        console.warn('[PWA] Camera permission denied or device busy:', e3.message);
      }
    }
  }

  if (stream) {
    state.mediaStream = stream;
    videoEl.srcObject = stream;
    try {
      await videoEl.play();
      console.log('[PWA] Mobile Camera stream active!');
    } catch (playErr) {
      console.warn('[PWA] Video play warning:', playErr);
    }
  } else {
    startTestCardStream();
  }
}

function startTestCardStream() {
  if (state.testCardInterval) clearInterval(state.testCardInterval);
  state.testCardInterval = setInterval(() => {
    if (videoEl.srcObject && videoEl.videoWidth > 0) return;
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#38bdf8';
    ctx.font = 'bold 22px monospace';
    ctx.fillText(`SENSOR NODE: ${state.deviceId}`, 40, 100);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '15px monospace';
    ctx.fillText(`GPS: ${state.currentGps.latitude.toFixed(5)}, ${state.currentGps.longitude.toFixed(5)}`, 40, 140);
    ctx.fillText(`SPEED: ${(state.currentGps.speed * 3.6).toFixed(1)} KM/H | HDG: ${(state.currentGps.heading).toFixed(0)}°`, 40, 175);
    ctx.fillText(`TIME: ${new Date().toLocaleTimeString()}`, 40, 210);
    ctx.fillStyle = '#10b981';
    ctx.fillText(`STATUS: SIMULATED TEST FRAME`, 40, 245);
  }, 350);
}

/**
 * 5. Frame Sampling & Packet Transmission (4 FPS)
 */
async function sendSensorPacket(forceHttp = false) {
  if (!state.isStreaming) return;

  try {
    // Ensure canvas dimensions
    if (canvas.width !== 640) canvas.width = 640;
    if (canvas.height !== 480) canvas.height = 480;

    // Capture frame from live video element if ready
    if (videoEl.videoWidth > 0 && videoEl.readyState >= 2) {
      ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    }
  } catch (e) {}

  let frameBase64 = null;
  const quality = state.adaptiveQuality || 0.55;
  try {
    frameBase64 = canvas.toDataURL('image/jpeg', quality);
  } catch (e) {}

  const now = Date.now() / 1000;
  const extraMetadata = { source_type: currentSourceType() };

  const packet = {
    packet_id: `pkt_${state.deviceId}_${Date.now()}`,
    device_id: state.deviceId,
    frame_timestamp: now,
    gps: state.currentGps,
    is_stale_gps: false,
    frame_base64: frameBase64,
    extra_metadata: extraMetadata
  };

  const payloadStr = JSON.stringify(packet);
  const sendStart = performance.now();

  // Send over WebSocket if connected, otherwise fallback to HTTP POST
  if (!forceHttp && state.ws && state.ws.readyState === WebSocket.OPEN) {
    try {
      state.ws.send(payloadStr);
      adjustAdaptiveQuality(performance.now() - sendStart);
    } catch (e) {
      await sendViaHttp(payloadStr);
    }
  } else {
    await sendViaHttp(payloadStr);
  }

  state.packetsSent++;
  state.bytesSent += payloadStr.length;
  updateBandwidth();
}

function adjustAdaptiveQuality(rttMs) {
  if (rttMs > 250) {
    state.adaptiveQuality = Math.max(0.35, (state.adaptiveQuality || 0.55) - 0.05);
  } else if (rttMs < 80) {
    state.adaptiveQuality = Math.min(0.65, (state.adaptiveQuality || 0.55) + 0.02);
  }
}

async function sendViaHttp(payloadStr) {
  const gatewayUrl = `${window.location.protocol}//${window.location.host}`;
  const start = performance.now();
  try {
    const response = await fetch(`${gatewayUrl}/ingest/packet`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${state.token || ''}` },
      body: payloadStr
    });
    adjustAdaptiveQuality(performance.now() - start);
    if (!response.ok) {
      const details = await response.text();
      throw new Error(`HTTP ${response.status}: ${details}`);
    }
    const data = await response.json();
    if (data && data.detections && data.detections.length > 0) {
      renderLiveDetections(data.detections);
    }
    return data;
  } catch (error) {
    console.error('[PWA] Sensor packet failed:', error);
    throw error;
  }
}

/**
 * Render genuine YOLO/D-FINE model predictions directly on phone camera HUD
 */
function renderLiveDetections(detections) {
  if (!detections || detections.length === 0) return;
  try {
    ctx.save();
    for (const d of detections) {
      const bbox = d.bbox || {};
      const x = bbox.x || 320;
      const y = bbox.y || 240;
      const w = bbox.width || 120;
      const h = bbox.height || 80;
      const rx = Math.max(10, x - w / 2);
      const ry = Math.max(10, y - h / 2);
      const confPct = Math.round((d.confidence || 0) * 100);
      const modelName = d.model_version || 'YOLOv8';
      const label = `[${modelName}] ${d.class_name.toUpperCase()} (${confPct}%)`;

      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 3;
      ctx.strokeRect(rx, ry, w, h);

      ctx.fillStyle = 'rgba(16, 185, 129, 0.9)';
      const textWidth = Math.max(200, label.length * 7.5 + 20);
      ctx.fillRect(rx, Math.max(0, ry - 22), textWidth, 22);

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(label, rx + 6, Math.max(15, ry - 6));
    }
    ctx.restore();
  } catch (err) {
    console.warn('[PWA] Canvas HUD render error:', err);
  }
}

function updateBandwidth() {
  const elapsedSec = (Date.now() - state.lastByteCheck) / 1000;
  if (elapsedSec >= 1.0) {
    const kbps = ((state.bytesSent / 1024) / elapsedSec).toFixed(1);
    const qPct = Math.round((state.adaptiveQuality || 0.55) * 100);
    netHud.textContent = `BW: ${kbps} KB/s | Q:${qPct}%`;
    fpsHud.textContent = `FPS: 4`;
    state.bytesSent = 0;
    state.lastByteCheck = Date.now();
  }
}

/**
 * 6. Stream Toggle & Live AI Perception Controls
 */
async function toggleStreaming() {
  if (!state.isStreaming) {
    state.isStreaming = true;
    btnToggle.textContent = '⏹ STOP SENSING';
    btnToggle.classList.remove('btn-primary');
    btnToggle.classList.add('btn-danger');
    if (tapPrompt) tapPrompt.style.display = 'none';

    // Start camera ONLY upon user gesture (required by mobile browsers)
    await startCamera();
    connectWebSocket();

    if (state.streamInterval) clearInterval(state.streamInterval);
    state.streamInterval = setInterval(sendSensorPacket, 250); // 4 FPS
  } else {
    state.isStreaming = false;
    btnToggle.textContent = '▶ START SENSING';
    btnToggle.classList.remove('btn-danger');
    btnToggle.classList.add('btn-primary');
    if (tapPrompt) tapPrompt.style.display = 'block';

    if (state.streamInterval) { clearInterval(state.streamInterval); state.streamInterval = null; }
    if (state.testCardInterval) { clearInterval(state.testCardInterval); state.testCardInterval = null; }
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach((track) => track.stop());
      state.mediaStream = null;
    }
    videoEl.srcObject = null;
    setConnStatus('⬤ IDLE', '#94a3b8');
  }
}

btnToggle.addEventListener('click', toggleStreaming);
document.getElementById('viewportArea')?.addEventListener('click', toggleStreaming);

if (btnSimulate) {
  btnSimulate.addEventListener('click', () => {
    console.log('[PWA] Live AI Mode: Point camera at road hazards for genuine neural detection.');
  });
}

// Clean Startup: Register device & start Janpath corridor GPS simulation
initDevice();
activateSimMode('Startup default');
checkTunnelStatus();
