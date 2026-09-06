import React from 'react';
import { useStore } from '../state/store';
import { Bus, Wifi, WifiOff } from 'lucide-react';
import { formatSpeedKmh } from '../utils/geo';

export default function FleetList() {
  const fleet = useStore((state) => state.fleet);
  const selectEntity = useStore((state) => state.selectEntity);
  const selectedEntity = useStore((state) => state.selectedEntity);

  const vehicleList = Object.values(fleet);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.5px' }}>
          CONNECTED VEHICLES ({vehicleList.length})
        </span>
        <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'monospace' }}>
          SOURCE HEALTH
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {vehicleList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-dim)', fontSize: '12px' }}>
            No active fleet sensing nodes.
            <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--accent-cyan)' }}>
              Open Phone PWA or run Replay to connect.
            </div>
          </div>
        ) : (
          vehicleList.map((v) => {
            const isSelected = selectedEntity?.type === 'vehicle' && selectedEntity?.id === v.device_id;
            const isLive = v.status === 'LIVE';
            const isStale = v.status === 'STALE';

            return (
              <div
                key={v.device_id}
                onClick={() => selectEntity('vehicle', v.device_id, v)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  background: isSelected ? 'rgba(56, 189, 248, 0.12)' : 'var(--bg-card)',
                  border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                  cursor: 'pointer',
                  transition: 'all 0.15s'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Bus size={14} color={isLive ? 'var(--accent-cyan)' : '#94a3b8'} />
                    <span className="mono" style={{ fontSize: '13px', fontWeight: 700 }}>
                      {v.device_id}
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: isLive ? 'rgba(16, 185, 129, 0.15)' : isStale ? 'rgba(245, 158, 11, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                      color: isLive ? '#10b981' : isStale ? '#f59e0b' : '#64748b'
                    }}
                  >
                    {v.status || 'LIVE'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                  <span>{v.latitude ? `${v.latitude.toFixed(5)}, ${v.longitude.toFixed(5)}` : 'Awaiting GPS Fix'}</span>
                  <span style={{ color: '#38bdf8', fontWeight: 600 }}>{formatSpeedKmh(v.speed)} km/h</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
