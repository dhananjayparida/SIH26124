import React, { useState } from 'react';
import { useStore } from '../state/store';
import { X, Key, Globe, Check, ShieldCheck, RefreshCw, Layers } from 'lucide-react';

export default function MapApiKeyModal() {
  const isMapKeyModalOpen = useStore((state) => state.isMapKeyModalOpen);
  const setMapKeyModalOpen = useStore((state) => state.setMapKeyModalOpen);
  const mapApiKey = useStore((state) => state.mapApiKey);
  const setMapApiKey = useStore((state) => state.setMapApiKey);

  const [inputKey, setInputKey] = useState(mapApiKey || '');
  const [savedSuccess, setSavedSuccess] = useState(false);

  if (!isMapKeyModalOpen) return null;

  const handleSave = (e) => {
    e.preventDefault();
    setMapApiKey(inputKey.trim());
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      setMapKeyModalOpen(false);
    }, 1200);
  };

  const handleResetDefault = () => {
    setInputKey('');
    setMapApiKey('');
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      setMapKeyModalOpen(false);
    }, 800);
  };

  const isMapbox = inputKey.trim().startsWith('pk.');
  const isCustomActive = !!mapApiKey.trim();

  return (
    <div className="modal-overlay" onClick={() => setMapKeyModalOpen(false)}>
      <div
        className="modal-content"
        style={{ maxWidth: '600px', background: '#090d16', border: '1px solid var(--accent-cyan)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Key size={18} color="var(--accent-cyan)" />
            <span style={{ fontSize: '15px', fontWeight: 800 }}>
              MAP API KEY & BASEMAP CONFIGURATION
            </span>
          </div>
          <button
            onClick={() => setMapKeyModalOpen(false)}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Status Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: isCustomActive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(56, 189, 248, 0.1)',
            padding: '10px 14px',
            borderRadius: '8px',
            border: `1px solid ${isCustomActive ? '#10b981' : 'var(--accent-cyan)'}`
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Globe size={16} color={isCustomActive ? '#10b981' : 'var(--accent-cyan)'} />
              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, color: isCustomActive ? '#10b981' : 'var(--accent-cyan)' }}>
                  {isCustomActive ? 'CUSTOM MAP KEY ACTIVE' : 'DEFAULT ZERO-KEY TILES ACTIVE'}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '2px' }}>
                  {isCustomActive
                    ? 'Streaming high-resolution Mapbox/Maptiler vector tiles'
                    : 'Streaming CARTO Dark Matter, Esri Satellite, and OpenStreetMap'}
                </div>
              </div>
            </div>
            <span style={{
              fontSize: '10px',
              fontWeight: 800,
              padding: '3px 8px',
              borderRadius: '4px',
              background: isCustomActive ? '#10b981' : 'rgba(56, 189, 248, 0.2)',
              color: isCustomActive ? '#000' : 'var(--accent-cyan)'
            }}>
              {isCustomActive ? 'ACTIVE' : 'NO KEY NEEDED'}
            </span>
          </div>

          <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                ENTER MAPBOX TOKEN OR MAPTILER KEY (OPTIONAL):
              </label>
              <input
                type="text"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                placeholder="e.g. pk.eyJ1IjoibXl1c2VyIiwiYSI6ImNsam53... or Maptiler Key"
                className="mono"
                style={{
                  width: '100%',
                  background: '#0a0f1d',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  color: 'white',
                  fontSize: '12px',
                  outline: 'none'
                }}
              />
              <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '4px' }}>
                {isMapbox
                  ? '✓ Detected Mapbox Public Access Token format (pk.*)'
                  : 'Leave blank to use the built-in free high-resolution Carto Dark Matter, Esri Satellite, and OpenStreetMap layers.'}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '6px' }}>
              <button
                type="submit"
                style={{
                  flex: 1,
                  background: '#0284c7',
                  border: 'none',
                  color: 'white',
                  padding: '10px 16px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                {savedSuccess ? <Check size={16} /> : <Key size={14} />}
                <span>{savedSuccess ? 'SAVED & APPLIED!' : 'SAVE & APPLY KEY'}</span>
              </button>

              <button
                type="button"
                onClick={handleResetDefault}
                style={{
                  background: '#1e293b',
                  border: '1px solid var(--border-color)',
                  color: '#94a3b8',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                title="Reset to free built-in Carto and Esri tiles"
              >
                <RefreshCw size={14} /> RESET TO FREE TILES
              </button>
            </div>
          </form>

          {/* Provider Overview Card */}
          <div style={{ background: 'var(--bg-card)', padding: '12px', borderRadius: '8px', fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontWeight: 700, color: 'var(--text-muted)' }}>SUPPORTED BASEMAP PROVIDERS:</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)' }}>
              <span>🌙 Dark Tactical Mode:</span>
              <span className="mono" style={{ color: '#38bdf8' }}>CARTO Dark Matter / Mapbox Dark</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)' }}>
              <span>🛰️ Satellite Imagery:</span>
              <span className="mono" style={{ color: '#10b981' }}>Esri World Imagery (Sub-meter)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)' }}>
              <span>🗺️ Street Navigation:</span>
              <span className="mono" style={{ color: '#f59e0b' }}>OpenStreetMap Standard (Fixed abc)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
