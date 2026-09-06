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
const btnSimulate = document.getElementById('btnSimulateDefect');
const tapPrompt = document.getElementById('tapToStartPrompt');

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
        source_type: 'phone_pwa',
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
        source_type: 'phone_pwa',
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

state.gpsMode = 'sim'; // 'sim' | 'real' (Defaults to Bhubaneswar Janpath Corridor)
state.hasRealGpsFix = false;
state.prevGps = null;
state.simInterval = null;
state.simWaypointIndex = 0;
state.simSubProgress = 0.0;

// High-fidelity Janpath Transit Corridor in Bhubaneswar (10 Waypoint Loop)
const BHUBANESWAR_JANPATH_ROUTE = [
  { lat: 20.29200, lon: 85.82100, speedKmh: 24.5 },  // Master Canteen Station
  { lat: 20.29360, lon: 85.82240, speedKmh: 26.0 },  // Kharvela Nagar
  { lat: 20.29615, lon: 85.82455, speedKmh: 25.0 },  // Ram Mandir Square
  { lat: 20.29760, lon: 85.82590, speedKmh: 28.0 },  // Satya Nagar
  { lat: 20.29950, lon: 85.82760, speedKmh: 27.5 },  // Janpath Flyover
  { lat: 20.30180, lon: 85.82980, speedKmh: 29.0 },  // Vani Vihar Square
  { lat: 20.30450, lon: 85.83220, speedKmh: 24.0 },  // Saheed Nagar Junction
  { lat: 20.30180, lon: 85.82980, speedKmh: 26.5 },  // Vani Vihar Return
  { lat: 20.29760, lon: 85.82590, speedKmh: 28.0 },  // Satya Nagar Return
  { lat: 20.29450, lon: 85.82320, speedKmh: 25.0 }   // Kharvela Nagar Return
];

function setGpsModeUI(mode) {
  if (btnGpsSim && btnGpsReal) {
    if (mode === 'sim') {
      btnGpsSim.style.background = '#0284c7';
      btnGpsSim.style.color = '#fff';
      btnGpsReal.style.background = '#1e293b';
      btnGpsReal.style.color = '#94a3b8';
      if (gpsStatusPill) {
        gpsStatusPill.textContent = 'JANPATH (SIM)';
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
  console.log(`[PWA] Switched to Janpath Transit Loop${reason ? ' (' + reason + ')' : ''}`);
}

function activateRealGps() {
  state.gpsMode = 'real';
  setGpsModeUI('real');
  stopSimulatedMotion();

  if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    alert('Notice: Mobile browsers (Chrome/Safari) restrict hardware GPS to secure HTTPS origins. Falling back to Bhubaneswar Janpath Corridor simulation.');
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
    const wsUrl = `${wsProto}//${window.location.host}/ws?role=sensor&device_id=${state.deviceId}&token=${state.token || 'tok'}`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
      console.log('[PWA] WebSocket connected -> LIVE');
      statusDot.classList.add('connected');
    };

    state.ws.onclose = () => {
      statusDot.classList.remove('connected');
      if (state.isStreaming) {
        setTimeout(connectWebSocket, 2000);
      }
    };

    state.ws.onerror = () => {
      statusDot.classList.remove('connected');
    };
  } catch (e) {
    console.warn('[PWA] WebSocket init error, will use HTTP fallback');
  }
}

/**
 * 4. Safe Mobile Camera Initialization (Zero-Crash Fallback)
 */
async function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.warn('[PWA] Camera API unavailable. Using synthetic road test card.');
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
    ctx.fillText(`STATUS: SENSING ACTIVE`, 40, 245);
  }, 350);
}

/**
 * 5. Frame Sampling & Packet Transmission (2.5 FPS)
 */
async function sendSensorPacket() {
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
  const extraMetadata = { source_type: 'phone_pwa' };

  if (state.pendingDefectInjection) {
    extraMetadata.mock_defect = {
      class_name: 'pothole',
      confidence: 0.91,
      x: 320,
      y: 270,
      w: 130,
      h: 90
    };
    state.pendingDefectInjection = false;
    btnSimulate.style.background = '#1e293b';
    console.log('[PWA] Injected pothole defect into packet');
  }

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
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    try {
      state.ws.send(payloadStr);
      adjustAdaptiveQuality(performance.now() - sendStart);
    } catch (e) {
      sendViaHttp(payloadStr);
    }
  } else {
    sendViaHttp(payloadStr);
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

function sendViaHttp(payloadStr) {
  const gatewayUrl = `${window.location.protocol}//${window.location.host}`;
  const start = performance.now();
  fetch(`${gatewayUrl}/ingest/packet`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${state.token || ''}` },
    body: payloadStr
  }).then(() => {
    adjustAdaptiveQuality(performance.now() - start);
  }).catch(() => {});
}

function updateBandwidth() {
  const elapsedSec = (Date.now() - state.lastByteCheck) / 1000;
  if (elapsedSec >= 1.0) {
    const kbps = ((state.bytesSent / 1024) / elapsedSec).toFixed(1);
    const qPct = Math.round((state.adaptiveQuality || 0.55) * 100);
    netHud.textContent = `BW: ${kbps} KB/s | Q:${qPct}%`;
    fpsHud.textContent = `FPS: 2.5`;
    state.bytesSent = 0;
    state.lastByteCheck = Date.now();
  }
}

/**
 * 6. Stream Toggle & Defect Trigger Controls
 */
async function toggleStreaming() {
  if (!state.isStreaming) {
    state.isStreaming = true;
    btnToggle.textContent = 'STOP SENSING';
    btnToggle.classList.remove('btn-primary');
    btnToggle.classList.add('btn-danger');
    if (tapPrompt) tapPrompt.style.display = 'none';

    // Start camera ONLY upon user tap (prevents mobile browser security crash)
    await startCamera();
    connectWebSocket();

    if (state.streamInterval) clearInterval(state.streamInterval);
    state.streamInterval = setInterval(sendSensorPacket, 400); // 2.5 FPS
  } else {
    state.isStreaming = false;
    btnToggle.textContent = 'START SENSING';
    btnToggle.classList.remove('btn-danger');
    btnToggle.classList.add('btn-primary');
    if (tapPrompt) tapPrompt.style.display = 'block';

    if (state.streamInterval) clearInterval(state.streamInterval);
    if (state.testCardInterval) clearInterval(state.testCardInterval);
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach((track) => track.stop());
      state.mediaStream = null;
    }
    videoEl.srcObject = null;
  }
}

btnToggle.addEventListener('click', toggleStreaming);
document.getElementById('viewportArea')?.addEventListener('click', toggleStreaming);

btnSimulate.addEventListener('click', () => {
  state.pendingDefectInjection = true;
  btnSimulate.style.background = '#dc2626';
  if (!state.isStreaming) {
    state.isStreaming = true;
    sendSensorPacket();
    state.isStreaming = false;
  }
});

// Clean Startup: Register device & start Janpath corridor GPS simulation
initDevice();
activateSimMode('Startup default');
