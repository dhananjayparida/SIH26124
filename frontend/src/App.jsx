import React, { useEffect, useState } from 'react';
import { useStore } from './state/store';
import MapView from './components/MapView';
import LayerPanel from './components/LayerPanel';
import FleetList from './components/FleetList';
import EntityPanel from './components/EntityPanel';
import HUDBar from './components/HUDBar';
import MaintenanceQueue from './components/MaintenanceQueue';
import PhoneConnectModal from './components/PhoneConnectModal';
import AICopilotModal from './components/AICopilotModal';
import MapApiKeyModal from './components/MapApiKeyModal';
import { Shield, ListOrdered, Radio, Smartphone, Sparkles } from 'lucide-react';

export default function App() {
  const fetchFleet = useStore((state) => state.fetchFleet);
  const fetchEvents = useStore((state) => state.fetchEvents);
  const fetchGridHealth = useStore((state) => state.fetchGridHealth);
  const fetchHUD = useStore((state) => state.fetchHUD);
  const handleWsMessage = useStore((state) => state.handleWsMessage);
  const setQueueModalOpen = useStore((state) => state.setQueueModalOpen);
  const [isPhoneModalOpen, setPhoneModalOpen] = useState(false);

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
      ws.onopen = () => console.log('[Command Center] WS live link connected');
    } catch (e) {
      console.warn('WS not reachable, using HTTP polling');
    }

    return () => {
      clearInterval(interval);
      if (ws) ws.close();
    };
  }, [fetchFleet, fetchEvents, fetchGridHealth, fetchHUD, handleWsMessage]);

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
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#10b981', marginRight: '8px' }}>
            <Radio size={14} className="animate-pulse" />
            <span className="mono" style={{ fontWeight: 700 }}>LIVE FUSION ACTIVE</span>
          </div>

          <button
            className="btn-queue"
            onClick={() => useStore.getState().setCopilotOpen(true)}
            style={{ borderColor: '#8b5cf6', background: 'rgba(139, 92, 246, 0.15)', color: '#c4b5fd' }}
          >
            <Sparkles size={15} color="#c4b5fd" />
            <span>AI COPILOT</span>
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
          <LayerPanel />
          <FleetList />
        </aside>

        <main style={{ flex: 1, position: 'relative' }}>
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
