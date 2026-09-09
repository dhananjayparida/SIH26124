# SIH26124 — AI-Powered Mobile Urban Intelligence Platform
### Using Public Transport Fleet as a Distributed Sensing Layer

> **Core Innovation Statement**:  
> *Fleet-Sourced Urban Evidence Fusion* — repeated, independent observations from distributed public transit vehicles are merged into persistent, confidence-scored urban events with a complete lifecycle (Candidate → Corroborated → High-Priority → Resolved), rather than treating each noisy detection as a disposable alert.

---

## Architecture Overview

```
                          [ INGESTION CHANNELS ]
       Mobile Phone PWA (LIVE WebSocket)      Replay Engine (Virtual Clock)
             (2.5 FPS @ 480p, High-Acc GPS)        (Janpath Bhubaneswar fixtures)
                            \                     /
                             \___________________/
                                       |
                   Node.js API Gateway (Port 5000)
             (Auth, Device Registry, WS Ingest, WS Live Push)
                                       |
                   FastAPI AI & Fusion Service (Port 8000)
  ┌────────────────────────────────────┴────────────────────────────────────┐
  │                                                                         │
  │  1. AI-01 Sensor Interface: Temporal Sync & GPS Interpolation           │
  │  2. AI-02 Perception: YOLOv8n Road Defect Detector (potholes/damage)    │
  │  3. AI-05 Spatio-Temporal Fusion: Spatial radius, unique device dedupe  │
  │  4. AI-06 Event Intelligence: Lifecycle state machine & photo evidence  │
  │  5. AI-07 Urban Intelligence: Grid road health, priority rank, queue    │
  │                                                                         │
  └────────────────────────────────────┬────────────────────────────────────┘
                                       |
                                  SQLite
             (events, observations, vehicles, repairs, evidence)
                                       |
          React 18 + Leaflet GIS Command Center (Port 3000)
    (Live fleet trails, Defect pins, Urban Memory timeline, Health Grid)
```

---

## Key Differentiators

1. **Independent-Source Corroboration**: An observation from a single bus creates a `CANDIDATE` event. Only when a 2nd independent vehicle confirms the defect within spatial radius ($R \approx 25\text{m}$) does it promote to `CORROBORATED` with confidence bonuses. A 3rd vehicle pushes it to `HIGH_PRIORITY`.
2. **Duplicate Prevention**: The *same* vehicle reporting the same defect on multiple passes increases observation count but does NOT inflate the unique source count.
3. **Urban Memory**: Complete chronological trail of every contributing vehicle observation (timestamp, confidence, device ID, snapshot) preserved in an immutable inspection timeline.
4. **Zero-Friction Live Mobile Sensing**: Install-free browser PWA with camera sampling (2-3 FPS) and throttled high-accuracy GPS, reducing cellular bandwidth by 10-15x over raw video.
5. **Deterministic Replay Fallback**: virtual-clock replay engine simulating buses on Bhubaneswar Janpath road for rehearsed demo stability.

---

## Quick Start Guide

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Launch the FastAPI AI Service (Port 8000)
```bash
python -m uvicorn backend.ai_service.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Launch the Node.js API Gateway (Port 5000)
```bash
cd backend/gateway
npm install
$env:ADMIN_TOKEN = "use-a-long-random-demo-token"
npm start
```
*The mobile sensing PWA is automatically served at `http://localhost:5000/pwa`.*

### Public mobile demo (Cloudflare Tunnel)

FastAPI stays private on `127.0.0.1:8000`; expose only the Node gateway:

```bash
cloudflared tunnel --url http://127.0.0.1:5000
```

Put the assigned HTTPS URL in `data/tunnel_url.txt` when using the command center's phone-connect panel. The phone URL is:
`https://<tunnel-host>/pwa?device_id=BUS_LIVE_01`.

The PWA derives HTTPS/WSS from its current origin. Registration returns a random session token, and the PWA sends it as a bearer token for WebSocket, heartbeat, and HTTP fallback ingestion. Do not expose port 8000 through the tunnel. Set `ALLOWED_ORIGINS` to the dashboard origin(s) when the gateway is accessed cross-origin; same-origin tunnel access needs no CORS exception.

Verify the public gateway from a second network after starting Node and the tunnel:

```bash
cd backend/gateway
$env:GATEWAY_URL = "https://<tunnel-host>"
npm run verify:public
```

The check confirms the public gateway is healthy, unauthenticated ingest returns `401`, and the tunnel URL endpoint is reachable. The physical phone test must additionally verify camera permission, real GPS mode, WSS connection, a moving marker, and a received evidence frame.

Authority actions (`repair-report`, `resolve`, and maintenance clearing) require the `X-Authority-Token` header. For the Vite dashboard, provide the same value as `VITE_AUTHORITY_TOKEN` in the frontend environment before starting it. Keep both demo tokens in local environment variables; never commit them.

### Kaggle road-hazards dataset

The public [Potholes, Cracks and Open Manholes](https://www.kaggle.com/datasets/sabidrahman/pothole-cracks-and-openmanhole) dataset is supported as a separate three-class training source: `pothole`, `crack`, and `open_manhole`. Its license is CC BY-NC-SA 4.0; review that license before redistribution or commercial use.

Configure Kaggle credentials locally, then download and normalize the dataset into `data/training_dataset/kaggle_road_hazards`:

```bash
pip install kaggle
# Set KAGGLE_API_TOKEN, or place the Kaggle credentials file in its standard user location.
python -c "from ai_engine.training.dataset_manager import global_dataset_manager; print(global_dataset_manager.download_kaggle_dataset())"
python ai_engine/training/train_model.py --dataset kaggle --epochs 5
```

The existing five-class benchmark remains the default. The Kaggle import is never mixed into it automatically, and `open_manhole` is not silently relabeled as a pothole or generic crack.

### 3. Launch the React GIS Command Center (Port 3000)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 5-Minute Rehearsed Demo Script for Judges

1. **Command Center Overview**: Open `http://localhost:3000`. Show the dark GIS map of Bhubaneswar, the bottom HUD bar showing live metrics, and the left layer panel.
2. **Deterministic Replay Corroboration**:
   Run the automated multi-bus demonstration from your terminal:
   ```bash
   python replay_engine/player.py --multi --speed 2.0
   ```
3. **Observe State Transitions Live**:
   - `BUS_01` traverses Janpath Road and detects a pothole → pin appears on map as **CANDIDATE** (Yellow) with 80% confidence.
   - `BUS_02` traverses the same road 5 seconds later → pin flips live to **CORROBORATED** (Orange) with 91% confidence.
   - `BUS_03` traverses the same spot → pin promotes to **HIGH_PRIORITY** (Red) with 98% confidence.
4. **Click-to-Investigate & Urban Memory**:
   - Click the defect marker on the map.
   - Show the right inspection panel: captured visual snapshot, confidence breakdown, and the **Urban Memory Timeline** showing each bus fix chronologically.
5. **Municipal Workflows**:
   - Click **"DISPATCH REPAIR CREW"** → Status flips to `REPAIR_REPORTED`.
   - Click **"MARK AS RESOLVED"** → Status transitions to `RESOLVED`.
6. **Road Health & Maintenance Queue**:
   - Toggle the **Road Health Grid** layer to display green/yellow/red spatial degradation cells.
   - Click **"MAINTENANCE QUEUE"** in the top bar to inspect prioritized work orders and click **"EXPORT CSV"**.
7. **Live Phone Demonstration (Optional)**:
   - On your phone (connected to same Wi-Fi), open `http://<your-laptop-ip>:5000/pwa?device_id=BUS_LIVE_01`.
   - Tap **"START SENSING"** → see your live phone marker and camera stream appear in the command center. Tap **"TRIGGER DEFECT"** to inject a defect and watch the fusion engine update in real time.

---

## Automated Test Suite

Run the full suite of unit and integration tests:
```bash
python -m unittest discover -s tests
```
- `test_contracts.py`: Schema boundary and coordinate validation
- `test_sync.py`: Clock skew validation and GPS linear interpolation
- `test_fusion.py`: Spatio-temporal clustering, duplicate prevention, and corroboration lifecycle
- `test_state_machine.py`: Lifecycle state machine transition checks
