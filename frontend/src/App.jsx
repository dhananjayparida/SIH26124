import React, { useEffect, useState } from 'react';
import { useStore } from './state/store';
import MapView from './components/MapView';
import LayerPanel from './components/LayerPanel';
import CommandFilters from './components/CommandFilters';
import FleetList from './components/FleetList';
import EntityPanel from './components/EntityPanel';
import HUDBar from './components/HUDBar';
import MaintenanceQueue from './components/MaintenanceQueue';
import PhoneConnectModal from './components/PhoneConnectModal';
import AICopilotModal from './components/AICopilotModal';
import MapApiKeyModal from './components/MapApiKeyModal';
import { ListOrdered, Radio, Smartphone, Sparkles, Clock3 } from 'lucide-react';

export default function App() {
  const fetchFleet = useStore((state) => state.fetchFleet);
  const fetchEvents = useStore((state) => state.fetchEvents);
  const fetchGridHealth = useStore((state) => state.fetchGridHealth);
  const fetchHUD = useStore((state) => state.fetchHUD);
  const handleWsMessage = useStore((state) => state.handleWsMessage);
  const setTransportStatus = useStore((state) => state.setTransportStatus);
  const transportStatus = useStore((state) => state.transportStatus);
  const setQueueModalOpen = useStore((state) => state.setQueueModalOpen);
  const hudMetrics = useStore((state) => state.hudMetrics);
  const fleet = useStore((state) => state.fleet);
  const events = useStore((state) => state.events);
  const [isPhoneModalOpen, setPhoneModalOpen] = useState(false);
  const lastUpdate = Math.max(
    0,
    ...Object.values(fleet).map((vehicle) => Number(vehicle.last_seen) || 0),
    ...events.map((event) => Number(event.updated_at || event.created_at) || 0)
  );
  const sourceMode = hudMetrics.mode || 'STANDBY';

  // Setup WebSocket connection and initial polling
  useEffect(() => {
    // Initial fetch
    fetchFleet();
    fetchEvents();
    fetchGridHealth();
    fetchHUD();

    // 3s interval polling fallback
    const interval = setInterval(() => {
      fetchFleet();
      fetchEvents();
      fetchGridHealth();
      fetchHUD();
    }, 3000);

    // WebSocket real-time updates
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws?role=dashboard`;
    let ws = null;

    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleWsMessage(msg);
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };
      ws.onopen = () => {
        setTransportStatus('WEBSOCKET');
        console.log('[Command Center] WS live link connected');
      };
      ws.onerror = () => setTransportStatus('HTTP_FALLBACK');
      ws.onclose = () => setTransportStatus('HTTP_FALLBACK');
    } catch (e) {
      setTransportStatus('HTTP_FALLBACK');
      console.warn('WS not reachable, using HTTP polling');
    }

    return () => {
      clearInterval(interval);
      if (ws) ws.close();
    };
  }, [fetchFleet, fetchEvents, fetchGridHealth, fetchHUD, handleWsMessage, setTransportStatus]);

  return (
    <div className="app-container">
      {/* Top Header Bar */}
      <header className="top-header">
        <div className="logo-section">
          <div className="logo-badge">SIH26124</div>
          <div className="logo-title">
            URBAN INTELLIGENCE COMMAND CENTER
            <span className="logo-sub">— BHUBANESWAR FLEET FUSION</span>
          </div>
        </div>

        <div className="top-actions">
          <div className="top-hud-metrics" aria-label="Live operational summary">
            <div className={`system-state state-${sourceMode.toLowerCase()}`}>
              <Radio size={13} />
              <span>{sourceMode}</span>
            </div>
            <div className={`system-state ${transportStatus === 'WEBSOCKET' ? 'state-live' : transportStatus === 'HTTP_FALLBACK' ? 'state-replay' : ''}`} title="Dashboard transport state">
              <span>{transportStatus === 'WEBSOCKET' ? 'WS' : transportStatus === 'HTTP_FALLBACK' ? 'HTTP FALLBACK' : 'CONNECTING'}</span>
            </div>
            <div><span>ACTIVE</span><strong>{hudMetrics.active_vehicles}</strong></div>
            <div><span>OPEN</span><strong>{hudMetrics.open_events}</strong></div>
            <div><span>HIGH</span><strong className="danger-value">{hudMetrics.high_priority_events}</strong></div>
            <div><span>CORROBORATED</span><strong className="warm-value">{hudMetrics.corroborated_events}</strong></div>
            <div className="last-update"><Clock3 size={12} /><span>{lastUpdate ? new Date(lastUpdate * 1000).toLocaleTimeString() : 'Awaiting data'}</span></div>
          </div>

          <button
            className="btn-queue"
            onClick={() => useStore.getState().setCopilotOpen(true)}
            style={{ borderColor: '#8b5cf6', background: 'rgba(139, 92, 246, 0.15)', color: '#c4b5fd' }}
          >
            <Sparkles size={15} color="#c4b5fd" />
            <span>COMMAND SHORTCUTS</span>
          </button>

          <button
            className="btn-queue"
            onClick={() => setPhoneModalOpen(true)}
            style={{ borderColor: 'var(--accent-cyan)', background: 'rgba(56, 189, 248, 0.1)' }}
          >
            <Smartphone size={15} color="var(--accent-cyan)" />
            <span>CONNECT PHONE SENSOR</span>
          </button>

          <button className="btn-queue" onClick={() => setQueueModalOpen(true)}>
            <ListOrdered size={15} color="var(--accent-cyan)" />
            <span>MAINTENANCE QUEUE</span>
          </button>
        </div>
      </header>

      {/* Main Workspace: Left Sidebar + Map + Right Sidebar */}
      <div className="main-workspace">
        <aside className="left-sidebar">
          <CommandFilters />
          <LayerPanel />
          <FleetList />
        </aside>

        <main className="map-workspace">
          <MapView />
        </main>

        <aside className="right-sidebar">
          <EntityPanel />
        </aside>
      </div>

      {/* Bottom HUD Bar */}
      <HUDBar />

      {/* Maintenance Queue Modal */}
      <MaintenanceQueue />

      {/* Phone Camera Connect QR Modal */}
      <PhoneConnectModal isOpen={isPhoneModalOpen} onClose={() => setPhoneModalOpen(false)} />

      {/* AI Command Copilot Modal */}
      <AICopilotModal />

      {/* Map API Key & Basemap Credentials Modal */}
      <MapApiKeyModal />
    </div>
  );
}
