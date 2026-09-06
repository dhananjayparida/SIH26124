import React from 'react';
import { useStore } from '../state/store';
import { Bus, AlertTriangle, ShieldCheck, Activity, Layers, Radio, RefreshCw, Power } from 'lucide-react';

const MODE_STYLES = {
  LIVE:    { color: '#10b981', bg: 'rgba(16,185,129,0.15)', border: '#10b981', icon: Radio,      label: 'LIVE' },
  REPLAY:  { color: '#f59e0b', bg: 'rgba(245,158,11,0.15)', border: '#f59e0b', icon: RefreshCw,  label: 'REPLAY' },
  STANDBY: { color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: '#64748b', icon: Power,      label: 'STANDBY' },
};

export default function HUDBar() {
  const hudMetrics = useStore((state) => state.hudMetrics);
  const mode = hudMetrics.mode || 'STANDBY';
  const modeStyle = MODE_STYLES[mode] || MODE_STYLES.STANDBY;
  const ModeIcon = modeStyle.icon;

  return (
    <footer className="bottom-hud">

      {/* System MODE badge — most important truth indicator */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 10px',
        borderRadius: '6px',
        background: modeStyle.bg,
        border: `1px solid ${modeStyle.border}`,
        marginRight: '4px'
      }}>
        <ModeIcon size={13} color={modeStyle.color}
          style={mode === 'LIVE' ? { animation: 'pulse 2s infinite' } : {}} />
        <span style={{ fontSize: '11px', fontWeight: 800, color: modeStyle.color, letterSpacing: '0.5px' }}>
          MODE: {modeStyle.label}
        </span>
      </div>

      <div style={{ width: '1px', height: '20px', background: 'var(--border-color)' }} />

      <div className="hud-stat">
        <Bus size={15} color="#38bdf8" />
        <span>FLEET:</span>
        <span className="hud-stat-value mono">{hudMetrics.active_vehicles}</span>
        <span style={{ color: '#10b981', fontSize: '11px' }}>
          {hudMetrics.live_sources > 0 && <span>{hudMetrics.live_sources}L </span>}
          {hudMetrics.replay_sources > 0 && <span style={{ color: '#f59e0b' }}>{hudMetrics.replay_sources}R </span>}
          {hudMetrics.stale_sources > 0 && <span style={{ color: '#94a3b8' }}>{hudMetrics.stale_sources}S</span>}
        </span>
      </div>

      <div style={{ width: '1px', height: '20px', background: 'var(--border-color)' }} />

      <div className="hud-stat">
        <Activity size={15} color="#facc15" />
        <span>OPEN:</span>
        <span className="hud-stat-value mono">{hudMetrics.open_events}</span>
        <span style={{ color: '#64748b', fontSize: '10px' }}>
          ({hudMetrics.candidate_events || 0} cand)
        </span>
      </div>

      <div style={{ width: '1px', height: '20px', background: 'var(--border-color)' }} />

      <div className="hud-stat">
        <AlertTriangle size={15} color="#ef4444" />
        <span>HIGH PRIORITY:</span>
        <span className="hud-stat-value mono" style={{ color: '#ef4444' }}>
          {hudMetrics.high_priority_events}
        </span>
      </div>

      <div style={{ width: '1px', height: '20px', background: 'var(--border-color)' }} />

      <div className="hud-stat">
        <ShieldCheck size={15} color="#f97316" />
        <span>CORROBORATED:</span>
        <span className="hud-stat-value mono" style={{ color: '#f97316' }}>
          {hudMetrics.corroborated_events}
        </span>
      </div>

      <div style={{ width: '1px', height: '20px', background: 'var(--border-color)' }} />

      <div className="hud-stat">
        <Layers size={15} color="#a855f7" />
        <span>OBSERVATIONS:</span>
        <span className="hud-stat-value mono">{hudMetrics.total_observations}</span>
      </div>

    </footer>
  );
}
