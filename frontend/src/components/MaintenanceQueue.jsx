import React, { useEffect, useState } from 'react';
import { useStore } from '../state/store';
import { X, Download, AlertTriangle, ArrowUpDown, Clock, Trash2 } from 'lucide-react';

export default function MaintenanceQueue() {
  const isQueueModalOpen = useStore((state) => state.isQueueModalOpen);
  const setQueueModalOpen = useStore((state) => state.setQueueModalOpen);
  const selectEntity = useStore((state) => state.selectEntity);
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isQueueModalOpen) {
      setLoading(true);
      fetch('/api/maintenance/queue')
        .then((res) => res.json())
        .then((data) => {
          setQueue(data);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [isQueueModalOpen]);

  if (!isQueueModalOpen) return null;

  const handleExportCSV = () => {
    window.open('/api/maintenance/export-csv', '_blank');
  };

  const handleClearQueue = async () => {
    if (window.confirm('Are you sure you want to clear all defects from the maintenance queue?')) {
      try {
        await fetch('/api/maintenance/clear', {
          method: 'POST',
          headers: { 'X-Authority-Token': import.meta.env.VITE_AUTHORITY_TOKEN || '' }
        });
        setQueue([]);
      } catch (err) {
        console.error('Failed to clear queue', err);
      }
    }
  };

  const handleRowClick = (item) => {
    setQueueModalOpen(false);
    selectEntity('event', item.event_id, item);
  };

  return (
    <div className="modal-overlay" onClick={() => setQueueModalOpen(false)}>
      <div className="modal-content" style={{ maxWidth: '850px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={20} color="#f59e0b" />
            <span style={{ fontSize: '16px', fontWeight: 800 }}>
              PRIORITIZED MUNICIPAL MAINTENANCE QUEUE
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              onClick={handleClearQueue}
              style={{
                background: '#dc2626',
                border: 'none',
                color: 'white',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer'
              }}
              title="Clear all defects from maintenance queue"
            >
              <Trash2 size={14} /> CLEAR QUEUE
            </button>
            <button
              onClick={handleExportCSV}
              style={{
                background: '#2563eb',
                border: 'none',
                color: 'white',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer'
              }}
            >
              <Download size={14} /> EXPORT CSV
            </button>
            <button
              onClick={() => setQueueModalOpen(false)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="modal-body">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
              Calculating optimal road repair priority ranking...
            </div>
          ) : queue.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
              No open road defects currently queued for repair.
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-dim)', textAlign: 'left' }}>
                  <th style={{ padding: '8px' }}>#</th>
                  <th style={{ padding: '8px' }}>Type</th>
                  <th style={{ padding: '8px' }}>Status</th>
                  <th style={{ padding: '8px' }}>Severity</th>
                  <th style={{ padding: '8px' }}>Reported Timing</th>
                  <th style={{ padding: '8px' }}>Sources</th>
                  <th style={{ padding: '8px' }}>Priority</th>
                  <th style={{ padding: '8px' }}>Location</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((item) => (
                  <tr
                    key={item.event_id}
                    onClick={() => handleRowClick(item)}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      cursor: 'pointer',
                      transition: 'background 0.15s'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(56, 189, 248, 0.06)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ padding: '10px 8px', fontWeight: 700 }}>{item.rank}</td>
                    <td style={{ padding: '10px 8px', textTransform: 'capitalize' }}>{item.type}</td>
                    <td style={{ padding: '10px 8px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: item.status === 'HIGH_PRIORITY' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(249, 115, 22, 0.2)',
                          color: item.status === 'HIGH_PRIORITY' ? '#ef4444' : '#f97316'
                        }}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td style={{ padding: '10px 8px', fontWeight: 600, color: item.severity === 'HIGH' ? '#ef4444' : '#f59e0b' }}>
                      {item.severity}
                    </td>
                    <td style={{ padding: '10px 8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#cbd5e1', fontSize: '12px' }}>
                        <Clock size={12} color="var(--accent-cyan)" />
                        <span>{item.reported_time || (item.created_at ? new Date(item.created_at * 1000).toLocaleTimeString() : 'N/A')}</span>
                        {item.age_str && (
                          <span style={{ fontSize: '10px', color: '#94a3b8', background: '#1e293b', padding: '1px 5px', borderRadius: '3px' }}>
                            {item.age_str}
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '10px 8px' }}>{item.unique_sources} buses</td>
                    <td style={{ padding: '10px 8px', fontWeight: 700, color: 'var(--accent-cyan)' }} className="mono">
                      {item.priority_score}
                    </td>
                    <td style={{ padding: '10px 8px', color: 'var(--text-dim)' }} className="mono">
                      {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
