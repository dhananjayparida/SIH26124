import React from 'react';
import { useStore } from '../state/store';
import { X, Eye, Navigation, Crosshair, Gauge, Radio, Bus, ShieldAlert } from 'lucide-react';
import { formatSpeedKmh } from '../utils/geo';

export default function CockpitOverlay() {
  const cockpitMode = useStore((state) => state.cockpitMode);
  const setCockpitMode = useStore((state) => state.setCockpitMode);
  const followedVehicleId = useStore((state) => state.followedVehicleId);
  const selectedEntity = useStore((state) => state.selectedEntity);
  const fleet = useStore((state) => state.fleet);
  const events = useStore((state) => state.events);

  if (!cockpitMode) return null;

  const selectedBusId = selectedEntity?.type === 'vehicle' ? selectedEntity.id : null;
  const bus = (selectedBusId && fleet[selectedBusId]) || (followedVehicleId && fleet[followedVehicleId]) || Object.values(fleet)[0] || {};
  const isLive = bus.status === 'LIVE';
  const feedState = bus.status === 'REPLAY'
    ? 'REPLAY'
    : bus.source_type === 'sim'
      ? 'SIMULATED'
      : isLive
        ? 'LIVE'
        : (bus.status || 'OFFLINE');
  const speedKmh = formatSpeedKmh(bus.speed);
  const heading = (bus.heading || 0).toFixed(0);

  // Find nearest upcoming defect within 500m
  let nearestDefect = null;
  let minDistance = Infinity;
  if (bus.latitude && bus.longitude) {
    events.forEach((ev) => {
      const dLat = (ev.latitude - bus.latitude) * 111000;
      const dLon = (ev.longitude - bus.longitude) * 111000 * Math.cos((bus.latitude * Math.PI) / 180);
      const dist = Math.sqrt(dLat * dLat + dLon * dLon);
      if (dist < minDistance && dist < 500) {
        minDistance = dist;
        nearestDefect = { ...ev, distance_m: Math.round(dist) };
      }
    });
  }

  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      padding: '20px'
    }}>
      {/* Top Cockpit HUD Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(10, 15, 29, 0.85)',
        backdropFilter: 'blur(8px)',
        padding: '10px 20px',
        borderRadius: '8px',
        border: '1px solid rgba(56, 189, 248, 0.4)',
        pointerEvents: 'auto',
        color: '#f8fafc'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Eye size={20} color="var(--accent-cyan)" />
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '1px' }}>GEV COCKPIT SENSING VIEW</div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--accent-cyan)' }}>
              {bus.device_id || 'NO SOURCE SELECTED'}
            </div>
          </div>
          <span style={{
            fontSize: '11px',
            fontWeight: 800,
            padding: '2px 8px',
            borderRadius: '4px',
            background: isLive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.2)',
            color: isLive ? '#10b981' : '#94a3b8',
            border: isLive ? '1px solid #10b981' : '1px solid #64748b'
          }}>
            {feedState}
          </span>
        </div>

        {/* Compass Heading Tape */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'monospace', fontSize: '14px', fontWeight: 700, color: '#38bdf8' }}>
          <Navigation size={16} style={{ transform: `rotate(${heading}deg)` }} />
          <span>HDG {heading.padStart(3, '0')}°</span>
        </div>

        <button
          onClick={() => setCockpitMode(false)}
          style={{
            background: 'rgba(239, 68, 68, 0.2)',
            border: '1px solid #ef4444',
            color: '#ef4444',
            padding: '6px 14px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <X size={16} /> EXIT COCKPIT
        </button>
      </div>

      {/* Center Target Reticle / Target Lock */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1, position: 'relative' }}>
        <div style={{
          width: '180px',
          height: '180px',
          border: '1px dashed rgba(56, 189, 248, 0.3)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative'
        }}>
          <Crosshair size={32} color="rgba(56, 189, 248, 0.5)" />

          {/* Horizon Line */}
          <div style={{ position: 'absolute', width: '220px', height: '1px', background: 'rgba(56, 189, 248, 0.25)' }} />

          {/* Defect Radar Warning if nearby */}
          {nearestDefect && (
            <div style={{
              position: 'absolute',
              top: '-40px',
              background: 'rgba(239, 68, 68, 0.9)',
              color: 'white',
              padding: '4px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 800,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              animation: 'pulse 1s infinite'
            }}>
              <ShieldAlert size={14} /> DEFECT AHEAD ({nearestDefect.distance_m}m)
            </div>
          )}
        </div>
      </div>

      {/* Bottom Cockpit Panel: Dashcam PIP + Telemetry Gauges */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', pointerEvents: 'auto' }}>
        {/* Speed & Pitch Gauges */}
        <div style={{
          background: 'rgba(10, 15, 29, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '14px 18px',
          borderRadius: '8px',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          display: 'flex',
          gap: '20px'
        }}>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>GROUND SPEED</div>
            <div style={{ fontSize: '24px', fontWeight: 900, color: 'var(--accent-cyan)', fontFamily: 'monospace' }}>
              {speedKmh} <span style={{ fontSize: '12px' }}>KM/H</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>GPS LAT / LON</div>
            <div style={{ fontSize: '12px', fontWeight: 700, color: '#f8fafc', fontFamily: 'monospace', marginTop: '6px' }}>
              {bus.latitude?.toFixed(5)}, {bus.longitude?.toFixed(5)}
            </div>
          </div>
        </div>

        {/* Live Dashcam Video Tile (Picture-in-Picture) */}
        <div style={{
          width: '260px',
          height: '160px',
          background: '#000',
          borderRadius: '8px',
          overflow: 'hidden',
          border: '2px solid var(--accent-cyan)',
          position: 'relative',
          boxShadow: '0 8px 24px rgba(0,0,0,0.6)'
        }}>
          {bus.latestFrame ? (
            <div style={{ position: 'relative', width: '100%', height: '100%' }}>
              <img src={bus.latestFrame} alt="Dashcam Stream" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              {(bus.detections || []).map((d, index) => {
                const box = d.bbox || {};
                return (
                  <div key={`${d.class_name}-${index}`} style={{
                    position: 'absolute', left: `${((box.x - box.width / 2) / 640) * 100}%`, top: `${((box.y - box.height / 2) / 480) * 100}%`,
                    width: `${(box.width / 640) * 100}%`, height: `${(box.height / 480) * 100}%`, border: '2px solid #10b981', pointerEvents: 'none'
                  }} />
                );
              })}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-dim)', fontSize: '11px', textAlign: 'center', padding: '10px' }}>
              <Bus size={28} style={{ opacity: 0.4, marginBottom: '6px' }} />
              <div>No camera frame received</div>
              <div style={{ fontSize: '10px', color: 'var(--accent-cyan)' }}>Waiting for this source's telemetry</div>
            </div>
          )}
          <div style={{
            position: 'absolute',
            bottom: '6px',
            left: '6px',
            right: '6px',
            background: 'rgba(0,0,0,0.7)',
            padding: '2px 6px',
            borderRadius: '4px',
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '9px',
            fontFamily: 'monospace',
            color: '#38bdf8'
          }}>
            <span>{bus.device_id || 'NO SOURCE'}</span>
            <span>{feedState} · {(bus.detections || []).length} DETECTIONS</span>
          </div>
        </div>
      </div>
    </div>
  );
}
