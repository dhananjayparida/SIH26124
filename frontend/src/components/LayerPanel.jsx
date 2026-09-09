import React from 'react';
import { useStore } from '../state/store';
import {
  Layers, Eye, EyeOff, Bus, AlertCircle, Grid, Navigation,
  Globe, MapPin, Radar, Crosshair, Key,
  Construction, Car, ShieldAlert, Flame, Waves, CircleAlert
} from 'lucide-react';

export default function LayerPanel() {
  const layers = useStore((state) => state.layers);
  const toggleLayer = useStore((state) => state.toggleLayer);
  const basemap = useStore((state) => state.basemap);
  const setBasemap = useStore((state) => state.setBasemap);
  const cockpitMode = useStore((state) => state.cockpitMode);
  const setCockpitMode = useStore((state) => state.setCockpitMode);
  const mapApiKey = useStore((state) => state.mapApiKey);
  const setMapKeyModalOpen = useStore((state) => state.setMapKeyModalOpen);

  // Intelligence domain layers
  const domainLayers = [
    {
      key: 'roadDamage',
      label: 'Road Damage',
      icon: AlertCircle,
      color: '#ef4444',
      desc: 'Potholes · Cracks · Surface Damage'
    },
    {
      key: 'infrastructure',
      label: 'Infrastructure',
      icon: Construction,
      color: '#f97316',
      desc: 'Missing Zebra · Dividers · Signboards'
    },
    {
      key: 'traffic',
      label: 'Traffic Events',
      icon: Car,
      color: '#38bdf8',
      desc: 'Only backend-reported traffic observations'
    },
    {
      key: 'safety',
      label: 'Safety Events',
      icon: ShieldAlert,
      color: '#a855f7',
      desc: 'Vulnerable Pedestrians · Crossing Risk'
    },
    {
      key: 'incident',
      label: 'Incident Intelligence',
      icon: Flame,
      color: '#dc2626',
      desc: 'Suspected Rash Driving · Hit & Run'
    },
  ];

  // Utility / spatial layers
  const utilityLayers = [
    { key: 'fleet',       label: 'Transit Fleet',     icon: Bus,        color: 'var(--accent-cyan)', desc: 'Live buses & telemetry' },
    { key: 'highPriority',label: 'High Priority',     icon: CircleAlert,color: '#f43f5e', desc: 'Priority events needing attention' },
    { key: 'gridHealth',  label: 'Road Health Grid',  icon: Grid,       color: 'var(--accent-cyan)', desc: 'Spatial health index' },
    { key: 'trails',      label: 'GPS Breadcrumbs',   icon: Navigation, color: 'var(--accent-cyan)', desc: 'Vehicle movement trail' },
    { key: 'annotations', label: 'Analyst Notes',     icon: MapPin,     color: 'var(--accent-cyan)', desc: 'Roadwork & municipal flags' },
    { key: 'radar',       label: '500m Radar Zone',   icon: Radar,      color: 'var(--accent-cyan)', desc: 'Nearby entity proximity' },
    { key: 'coverage',    label: 'Coverage Freshness',icon: Globe,      color: 'var(--accent-cyan)', desc: 'Sensing blind spots' },
  ];

  return (
    <div style={{ padding: '14px', borderBottom: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={16} color="var(--accent-cyan)" />
          <span style={{ fontSize: '13px', fontWeight: 800, letterSpacing: '0.5px' }}>
            GEV SITUATIONAL LAYERS
          </span>
        </div>
        <button
          onClick={() => setMapKeyModalOpen(true)}
          style={{
            background: mapApiKey ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.12)',
            border: `1px solid ${mapApiKey ? '#10b981' : 'var(--accent-cyan)'}`,
            color: mapApiKey ? '#10b981' : 'var(--accent-cyan)',
            padding: '3px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
          title="Configure Mapbox / Maptiler API Key or custom map tiles"
        >
          <Key size={11} />
          <span>{mapApiKey ? 'KEY ACTIVE' : 'MAP API KEY'}</span>
        </button>
      </div>

      {/* Basemap Selector (Dark Tactical / Satellite / Streets) */}
      <div style={{ background: 'var(--bg-card)', padding: '6px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '6px', paddingLeft: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>BASEMAP IMAGERY</span>
          <span style={{ color: mapApiKey ? '#10b981' : '#64748b', fontSize: '9px' }}>
            {mapApiKey ? '● High-Res Vector' : '● OpenStreetMap / Carto'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '4px' }}>
          {[
            { id: 'dark', label: 'Dark Tactical' },
            { id: 'satellite', label: '🛰️ Satellite' },
            { id: 'streets', label: 'Streets' }
          ].map((b) => (
            <button
              key={b.id}
              onClick={() => setBasemap(b.id)}
              style={{
                flex: 1,
                padding: '6px 4px',
                borderRadius: '4px',
                border: 'none',
                background: basemap === b.id ? '#0284c7' : 'transparent',
                color: basemap === b.id ? 'white' : 'var(--text-muted)',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {/* Cockpit Mode Trigger */}
      <button
        onClick={() => setCockpitMode(!cockpitMode)}
        style={{
          background: cockpitMode ? '#dc2626' : 'rgba(56, 189, 248, 0.15)',
          border: `1px solid ${cockpitMode ? '#ef4444' : 'var(--accent-cyan)'}`,
          color: cockpitMode ? 'white' : 'var(--accent-cyan)',
          padding: '8px 12px',
          borderRadius: '6px',
          fontSize: '12px',
          fontWeight: 800,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px'
        }}
      >
        <Crosshair size={14} />
        <span>{cockpitMode ? 'EXIT COCKPIT VIEW' : 'ENTER COCKPIT SENSING'}</span>
      </button>

      {/* Intelligence Domain Layers */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '2px', letterSpacing: '0.5px' }}>
          INTELLIGENCE DOMAINS
        </div>
        {domainLayers.map((item) => {
          const Icon = item.icon;
          const active = layers[item.key];
          return (
            <div
              key={item.key}
              onClick={() => toggleLayer(item.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '7px 10px',
                borderRadius: '6px',
                background: active ? `${item.color}15` : 'rgba(255,255,255,0.02)',
                border: active ? `1px solid ${item.color}55` : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icon size={14} color={active ? item.color : 'var(--text-dim)'} />
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: active ? 'var(--text-main)' : 'var(--text-muted)' }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>{item.desc}</div>
                </div>
              </div>
              {active
                ? <Eye size={13} color={item.color} />
                : <EyeOff size={13} color="var(--text-dim)" />}
            </div>
          );
        })}
      </div>

      {/* Utility / Spatial Layers */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '2px', letterSpacing: '0.5px' }}>
          SPATIAL OVERLAYS
        </div>
        {utilityLayers.map((item) => {
          const Icon = item.icon;
          const active = layers[item.key];
          return (
            <div
              key={item.key}
              onClick={() => toggleLayer(item.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '7px 10px',
                borderRadius: '6px',
                background: active ? 'rgba(56,189,248,0.08)' : 'rgba(255,255,255,0.02)',
                border: active ? '1px solid rgba(56,189,248,0.25)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icon size={14} color={active ? 'var(--accent-cyan)' : 'var(--text-dim)'} />
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: active ? 'var(--text-main)' : 'var(--text-muted)' }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>{item.desc}</div>
                </div>
              </div>
              {active
                ? <Eye size={13} color="var(--accent-cyan)" />
                : <EyeOff size={13} color="var(--text-dim)" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
