import React, { useEffect, useState } from 'react';
import { useStore } from '../state/store';
import { X, Download, AlertTriangle, Clock, Trash2, Camera, ZoomIn } from 'lucide-react';

/* ── Snapshot lightbox ──────────────────────────────────────────────────── */
function SnapshotLightbox({ url, onClose }) {
  if (!url) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.88)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(6px)',
      }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ position: 'relative' }}>
        <img
          src={url}
          alt="Defect snapshot"
          style={{
            maxWidth: '90vw', maxHeight: '85vh',
            borderRadius: '12px',
            border: '2px solid rgba(239,68,68,0.6)',
            boxShadow: '0 0 60px rgba(239,68,68,0.25)',
          }}
        />
        <button
          onClick={onClose}
          style={{
            position: 'absolute', top: -16, right: -16,
            background: '#dc2626', border: 'none', borderRadius: '50%',
            width: 32, height: 32, cursor: 'pointer', color: 'white',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        ><X size={16} /></button>
      </div>
    </div>
  );
}

/* ── Severity colour helper ─────────────────────────────────────────────── */
const SEV_COLOR = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e', INFO: '#38bdf8' };

/* ── Main component ─────────────────────────────────────────────────────── */
export default function MaintenanceQueue() {
  const isQueueModalOpen   = useStore((s) => s.isQueueModalOpen);
  const setQueueModalOpen  = useStore((s) => s.setQueueModalOpen);
  const selectEntity       = useStore((s) => s.selectEntity);

  const [queue,      setQueue]      = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [lightboxUrl, setLightbox]  = useState(null);

  useEffect(() => {
    if (isQueueModalOpen) {
      setLoading(true);
      fetch('/api/maintenance/queue')
        .then((r) => r.json())
        .then((data) => { setQueue(data); setLoading(false); })
        .catch(() => setLoading(false));
    }
  }, [isQueueModalOpen]);

  if (!isQueueModalOpen) return null;

  const handleExportCSV = () => window.open('/api/maintenance/export-csv', '_blank');

  const handleClearQueue = async () => {
    if (!window.confirm('Clear all defects from the maintenance queue?')) return;
    try {
      await fetch('/api/maintenance/clear', {
        method: 'POST',
        headers: { 'X-Authority-Token': import.meta.env.VITE_AUTHORITY_TOKEN || '' },
      });
      setQueue([]);
    } catch (err) {
      console.error('Failed to clear queue', err);
    }
  };

  const handleRowClick = (item) => {
    setQueueModalOpen(false);
    selectEntity('event', item.event_id, item);
  };

  const openSnapshot = (e, url) => {
    e.stopPropagation(); // don't trigger row click
    setLightbox(url);
  };

  return (
    <>
      {lightboxUrl && <SnapshotLightbox url={lightboxUrl} onClose={() => setLightbox(null)} />}

      <div className="modal-overlay" onClick={() => setQueueModalOpen(false)}>
        <div
          className="modal-content"
          style={{ maxWidth: '960px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* ── Header ──────────────────────────────────────────────────── */}
          <div className="modal-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={20} color="#f59e0b" />
              <span style={{ fontSize: '15px', fontWeight: 800, letterSpacing: '0.05em' }}>
                PRIORITIZED MAINTENANCE WORKFLOW
              </span>
              {queue.length > 0 && (
                <span style={{
                  background: 'rgba(239,68,68,0.18)', color: '#ef4444',
                  borderRadius: '12px', padding: '1px 10px', fontSize: '12px', fontWeight: 700,
                }}>
                  {queue.length} defects
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button onClick={handleClearQueue} style={btnStyle('#dc2626')} title="Clear all defects">
                <Trash2 size={13} /> CLEAR
              </button>
              <button onClick={handleExportCSV} style={btnStyle('#2563eb')}>
                <Download size={13} /> EXPORT CSV
              </button>
              <button
                onClick={() => setQueueModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              ><X size={20} /></button>
            </div>
          </div>

          {/* ── Body ────────────────────────────────────────────────────── */}
          <div className="modal-body" style={{ overflowY: 'auto', flex: 1 }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-dim)' }}>
                Calculating optimal road repair priority ranking...
              </div>
            ) : queue.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 40px', color: 'var(--text-dim)' }}>
                <AlertTriangle size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
              <div>No open events are currently queued for maintenance.</div>
              <div style={{ marginTop: 8, fontSize: 11 }}>Resolved events and their repair/observation history remain available through event investigation.</div>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-dim)', textAlign: 'left' }}>
                    <th style={th}>#</th>
                    <th style={th}>Snapshot</th>
                    <th style={th}>Type</th>
                    <th style={th}>Severity</th>
                    <th style={th}>Status</th>
                    <th style={th}>Reported</th>
                    <th style={th}>Sources</th>
                    <th style={th}>Priority</th>
                    <th style={th}>GPS</th>
                    <th style={th}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((item) => (
                    <tr
                      key={item.event_id}
                      onClick={() => handleRowClick(item)}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer', transition: 'background 0.15s' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(56,189,248,0.06)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      {/* Rank */}
                      <td style={{ ...td, fontWeight: 700 }}>{item.rank}</td>

                      {/* Snapshot thumbnail */}
                      <td style={{ ...td, width: 72 }}>
                        {item.evidence_url ? (
                          <div
                            onClick={(e) => openSnapshot(e, item.evidence_url)}
                            style={{
                              width: 64, height: 48, borderRadius: 6, overflow: 'hidden',
                              border: `2px solid ${SEV_COLOR[item.severity] || '#64748b'}`,
                              position: 'relative', cursor: 'zoom-in', flexShrink: 0,
                              display: 'inline-block',
                            }}
                            title="Click to enlarge snapshot"
                          >
                            <img
                              src={item.evidence_url}
                              alt="defect"
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
                            />
                            {/* fallback icon */}
                            <div style={{
                              display: 'none', position: 'absolute', inset: 0,
                              alignItems: 'center', justifyContent: 'center',
                              background: 'rgba(30,41,59,0.8)',
                            }}>
                              <Camera size={18} color="#64748b" />
                            </div>
                            {/* zoom overlay */}
                            <div style={{
                              position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              opacity: 0, transition: 'opacity 0.2s',
                            }}
                              onMouseEnter={(e) => (e.currentTarget.style.opacity = 1)}
                              onMouseLeave={(e) => (e.currentTarget.style.opacity = 0)}
                            >
                              <ZoomIn size={16} color="white" />
                            </div>
                          </div>
                        ) : (
                          <div style={{
                            width: 64, height: 48, borderRadius: 6,
                            background: 'rgba(255,255,255,0.04)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>
                            <Camera size={16} color="#334155" />
                          </div>
                        )}
                      </td>

                      {/* Type */}
                      <td style={{ ...td, textTransform: 'capitalize', fontWeight: 600 }}>
                        {(item.type || '').replace(/_/g, ' ')}
                      </td>

                      {/* Severity */}
                      <td style={{ ...td, fontWeight: 700, color: SEV_COLOR[item.severity] || '#94a3b8' }}>
                        {item.severity}
                      </td>

                      {/* Status badge */}
                      <td style={td}>
                        <span style={{
                          fontSize: '10px', fontWeight: 700, padding: '2px 7px', borderRadius: 4,
                          background: item.status === 'HIGH_PRIORITY' ? 'rgba(239,68,68,0.15)' : 'rgba(249,115,22,0.15)',
                          color: item.status === 'HIGH_PRIORITY' ? '#ef4444' : '#f97316',
                        }}>
                          {item.status}
                        </span>
                      </td>

                      {/* Reported time */}
                      <td style={td}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#cbd5e1', fontSize: 12 }}>
                          <Clock size={11} color="var(--accent-cyan)" />
                          <span>{item.reported_time || 'N/A'}</span>
                          {item.age_str && (
                            <span style={{ fontSize: 10, color: '#94a3b8', background: '#1e293b', padding: '1px 5px', borderRadius: 3 }}>
                              {item.age_str}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Sources */}
                      <td style={{ ...td, color: 'var(--text-dim)' }}>{item.unique_sources} bus{item.unique_sources !== 1 ? 'es' : ''}</td>

                      {/* Priority score */}
                      <td style={{ ...td, fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'monospace' }}>
                        {item.priority_score}
                      </td>

                      {/* GPS */}
                      <td style={{ ...td, color: 'var(--text-dim)', fontFamily: 'monospace', fontSize: 11 }}>
                        {item.latitude?.toFixed(4)}, {item.longitude?.toFixed(4)}
                      </td>
                      <td style={td}>
                        <span style={{ color: 'var(--accent-cyan)', fontSize: 11, fontWeight: 700 }}>INVESTIGATE →</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/* ── Style helpers ────────────────────────────────────────────────────────── */
const th = { padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap' };
const td = { padding: '10px 10px', verticalAlign: 'middle' };
const btnStyle = (bg) => ({
  background: bg, border: 'none', color: 'white',
  padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 700,
  display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer',
});
