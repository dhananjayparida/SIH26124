import React, { useState, useEffect } from 'react';
import { useStore } from '../state/store';
import { X, ShieldAlert, CheckCircle2, Wrench, Clock, Bus, MapPin, Award, Crosshair, Navigation, Maximize2, Image as ImageIcon, Eye, Copy, Check, Camera, ScanLine, History } from 'lucide-react';
import { formatSpeedKmh } from '../utils/geo';

export default function EntityPanel() {
  const selectedEntity = useStore((state) => state.selectedEntity);
  const clearSelection = useStore((state) => state.clearSelection);
  const fetchEvents = useStore((state) => state.fetchEvents);
  const fetchEventDetail = useStore((state) => state.fetchEventDetail);
  const setQueueModalOpen = useStore((state) => state.setQueueModalOpen);
  const events = useStore((state) => state.events);
  const fleet = useStore((state) => state.fleet);
  const selectEntity = useStore((state) => state.selectEntity);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeEvidenceIndex, setActiveEvidenceIndex] = useState(0);
  const [isEvidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [copiedCoords, setCopiedCoords] = useState(false);

  useEffect(() => {
    setActiveEvidenceIndex(0);
    setImgError(false);
    setCopiedCoords(false);
  }, [selectedEntity?.id]);

  // A map/list click carries summary data. Load the existing detail endpoint once for investigation context.
  useEffect(() => {
    if (selectedEntity?.type === 'event' && selectedEntity.id) {
      fetchEventDetail(selectedEntity.id);
    }
  }, [selectedEntity?.id, selectedEntity?.type, fetchEventDetail]);

  const copyCoords = (lat, lon) => {
    if (lat && lon) {
      navigator.clipboard.writeText(`${lat.toFixed(6)}, ${lon.toFixed(6)}`);
      setCopiedCoords(true);
      setTimeout(() => setCopiedCoords(false), 1500);
    }
  };

  if (!selectedEntity) {
    return (
      <div style={{ padding: '30px 20px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '13px' }}>
        <MapPin size={24} style={{ marginBottom: '8px', opacity: 0.5 }} />
        <div>Click any urban event or vehicle on the map to investigate evidence, live camera feed, and urban memory.</div>
      </div>
    );
  }

  // Handle Vehicle Selection -> LIVE CAMERA & TELEMETRY STREAM
  if (selectedEntity.type === 'vehicle') {
    const v = selectedEntity.data || {};
    const isLive = v.status === 'LIVE';
    const sourceLabel = v.status === 'REPLAY'
      ? 'REPLAY'
      : v.source_type === 'sim'
        ? 'SIMULATED'
        : (v.status || 'OFFLINE');
    const observedEvents = events
      .filter((event) => (event.source_vehicle_ids || []).includes(selectedEntity.id))
      .sort((a, b) => Number(b.updated_at || b.created_at || 0) - Number(a.updated_at || a.created_at || 0));
    const frameSources = Object.values(fleet).filter((vehicle) => vehicle.latestFrame);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Header */}
        <div style={{ padding: '16px', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              MOBILE SENSING NODE
            </div>
            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-cyan)' }}>
              {selectedEntity.id}
            </div>
          </div>
          <button
            onClick={clearSelection}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: '16px', flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Status Pills */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <div
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '6px',
                background: isLive ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                border: isLive ? '1px solid #10b981' : '1px solid #64748b',
                textAlign: 'center'
              }}
            >
              <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>SOURCE HEALTH</div>
              <div style={{ fontSize: '12px', fontWeight: 800, color: isLive ? '#10b981' : '#94a3b8' }}>
                {sourceLabel}
              </div>
            </div>

            <div
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '6px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                textAlign: 'center'
              }}
            >
              <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>SPEED</div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: '#38bdf8' }}>
                {v.speed !== undefined && v.speed !== null ? `${formatSpeedKmh(v.speed)} km/h` : '0.0 km/h'}
              </div>
            </div>

            <div
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '6px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                textAlign: 'center'
              }}
            >
              <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>HEADING</div>
              <div style={{ fontSize: '13px', fontWeight: 800, color: '#f8fafc' }}>
                {v.heading ? `${v.heading.toFixed(0)}°` : 'N/A'}
              </div>
            </div>
          </div>

          {/* LIVE CAMERA DASHCAM STREAM VIEW */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '6px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>CAMERA FRAME</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: isLive ? '#ef4444' : '#f59e0b', fontSize: '11px', fontWeight: 700 }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: isLive ? '#ef4444' : '#f59e0b', display: 'inline-block' }} />
                {v.latestFrame ? sourceLabel : 'NO FRAME'}
              </span>
            </div>

            <div style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-color)', background: '#000', minHeight: '190px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {v.latestFrame ? (
                <div style={{ position: 'relative', width: '100%' }}>
                  <img
                    src={v.latestFrame}
                    alt="Live Camera Feed"
                    style={{ width: '100%', height: 'auto', maxHeight: '240px', objectFit: 'cover', display: 'block' }}
                  />
                  {(v.detections || []).map((d, index) => {
                    const box = d.bbox || {};
                    const left = ((box.x - box.width / 2) / 640) * 100;
                    const top = ((box.y - box.height / 2) / 480) * 100;
                    return (
                      <div key={`${d.class_name}-${index}`} style={{
                        position: 'absolute', left: `${left}%`, top: `${top}%`,
                        width: `${(box.width / 640) * 100}%`, height: `${(box.height / 480) * 100}%`,
                        border: '2px solid #10b981', pointerEvents: 'none'
                      }}>
                        <span style={{ position: 'absolute', top: '-18px', left: '-2px', background: '#10b981', color: '#052e16', padding: '2px 4px', fontSize: '9px', fontWeight: 800, whiteSpace: 'nowrap' }}>
                          {d.class_name} {Math.round((d.confidence || 0) * 100)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '20px' }}>
                  <Bus size={32} style={{ opacity: 0.3, marginBottom: '8px' }} />
                  <div>Awaiting camera stream from {selectedEntity.id}...</div>
                  <div style={{ fontSize: '11px', color: 'var(--accent-cyan)', marginTop: '4px' }}>
                    Open PWA on phone and tap "START SENSING"
                  </div>
                </div>
              )}

              {/* HUD Overlay on Video */}
              {v.latestFrame && (
                <div style={{ position: 'absolute', bottom: '8px', left: '8px', right: '8px', background: 'rgba(15, 23, 42, 0.75)', backdropFilter: 'blur(4px)', padding: '4px 8px', borderRadius: '4px', display: 'flex', justifyContent: 'space-between', fontSize: '10px', fontFamily: 'monospace', color: '#38bdf8' }}>
                  <span>{selectedEntity.id}</span>
                  <span>{v.latitude?.toFixed(4)}, {v.longitude?.toFixed(4)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Cockpit & Track Controls */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => {
                useStore.getState().setFollowedVehicle(selectedEntity.id);
                useStore.getState().setCockpitMode(true);
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                background: '#0284c7',
                border: 'none',
                color: 'white',
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
              <Crosshair size={14} /> ENTER COCKPIT
            </button>
            <button
              onClick={() => {
                const current = useStore.getState().followedVehicleId;
                useStore.getState().setFollowedVehicle(current === selectedEntity.id ? null : selectedEntity.id);
              }}
              style={{
                padding: '8px 12px',
                background: useStore.getState().followedVehicleId === selectedEntity.id ? '#f59e0b' : 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                color: useStore.getState().followedVehicleId === selectedEntity.id ? '#000' : '#cbd5e1',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              {useStore.getState().followedVehicleId === selectedEntity.id ? 'FOLLOWING' : 'FOLLOW'}
            </button>
          </div>

          {/* Telemetry Information */}
          <div style={{ background: 'var(--bg-card)', padding: '12px', borderRadius: '8px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Source Type:</span>
              <span className="mono" style={{ textTransform: 'uppercase' }}>{v.source_type || 'phone_pwa'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-dim)' }}>Current Coordinates:</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="mono">{v.latitude?.toFixed(5)}, {v.longitude?.toFixed(5)}</span>
                {v.latitude && v.longitude && (
                  <button
                    onClick={() => copyCoords(v.latitude, v.longitude)}
                    style={{ background: 'transparent', border: 'none', color: copiedCoords ? '#10b981' : 'var(--accent-cyan)', cursor: 'pointer', padding: '2px', display: 'flex', alignItems: 'center' }}
                    title="Copy Coordinates to Clipboard"
                  >
                    {copiedCoords ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Last Seen:</span>
              <span className="mono">{v.last_seen ? new Date(v.last_seen * 1000).toLocaleString() : 'Not reported'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Detections Triggered:</span>
              <span className="mono" style={{ color: '#facc15' }}>{v.detections_reported || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Events Observed:</span>
              <span className="mono">{v.events_observed_count ?? 'Not reported'}</span>
            </div>
          </div>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <Camera size={14} color="var(--accent-cyan)" /> AVAILABLE CAMERA SOURCES ({frameSources.length})
            </div>
            {frameSources.length > 1 ? (
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {frameSources.map((source) => (
                  <button key={source.device_id} onClick={() => {
                    useStore.getState().setFollowedVehicle(source.device_id);
                    selectEntity('vehicle', source.device_id, source);
                  }} style={{ padding: '5px 8px', borderRadius: '4px', border: `1px solid ${source.device_id === selectedEntity.id ? 'var(--accent-cyan)' : 'var(--border-color)'}`, background: source.device_id === selectedEntity.id ? 'rgba(56,189,248,.12)' : 'var(--bg-card)', color: 'var(--text-main)', cursor: 'pointer', fontSize: '10px', fontFamily: 'monospace' }}>
                    {source.device_id}
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--text-dim)', fontSize: '11px' }}>
                {frameSources.length === 1 ? 'Only one source has supplied a camera frame.' : 'No camera frame has been received from any source.'}
              </div>
            )}
          </div>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <ScanLine size={14} color="var(--accent-cyan)" /> LATEST AI DETECTIONS ({(v.detections || []).length})
            </div>
            {(v.detections || []).length === 0 ? (
              <div style={{ color: 'var(--text-dim)', fontSize: '11px' }}>No detections in the latest received telemetry frame.</div>
            ) : (v.detections || []).map((detection, index) => (
              <div key={`${detection.class_name || 'detection'}-${index}`} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '5px', padding: '7px 8px', marginBottom: '5px', background: 'rgba(255,255,255,.025)', border: '1px solid var(--border-color)', borderRadius: '5px', fontSize: '11px' }}>
                <strong style={{ textTransform: 'capitalize' }}>{detection.class_name || 'Unlabelled detection'}</strong>
                <span className="mono" style={{ color: '#10b981' }}>{((detection.confidence ?? 0) * 100).toFixed(0)}%</span>
                <span className="mono" style={{ color: 'var(--text-dim)', gridColumn: '1 / -1' }}>
                  {detection.bbox ? `bbox x:${Math.round(detection.bbox.x)} y:${Math.round(detection.bbox.y)} w:${Math.round(detection.bbox.width)} h:${Math.round(detection.bbox.height)}` : 'Bounding box not supplied'} · {v.last_seen ? new Date(v.last_seen * 1000).toLocaleTimeString() : 'Timestamp not supplied'}
                </span>
              </div>
            ))}
          </div>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <History size={14} color="var(--accent-cyan)" /> EVENTS OBSERVED BY THIS BUS ({observedEvents.length})
            </div>
            {observedEvents.length === 0 ? (
              <div style={{ color: 'var(--text-dim)', fontSize: '11px' }}>No fused events currently list this bus as a source.</div>
            ) : observedEvents.map((event) => (
              <button key={event.event_id} onClick={() => selectEntity('event', event.event_id, event)} style={{ width: '100%', textAlign: 'left', padding: '8px', marginBottom: '5px', background: 'rgba(255,255,255,.025)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-main)', cursor: 'pointer' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '11px', fontWeight: 700 }}><span>{String(event.type || 'EVENT').replace(/_/g, ' ')}</span><span style={{ color: 'var(--accent-cyan)' }}>{((event.event_confidence ?? 0) * 100).toFixed(0)}%</span></div>
                <div className="mono" style={{ color: 'var(--text-dim)', fontSize: '10px', marginTop: '3px' }}>{event.status || 'State not supplied'} · {event.latitude?.toFixed(5)}, {event.longitude?.toFixed(5)} · {event.updated_at ? new Date(event.updated_at * 1000).toLocaleTimeString() : 'Timestamp not supplied'}</div>
              </button>
            ))}
          </div>
        </div>

      </div>
    );
  }

  const ev = selectedEntity.data || {};
  const timeline = ev.urban_memory_timeline || [];

  const handleReportRepair = async () => {
    setActionLoading(true);
    try {
      await fetch(`/api/events/${ev.event_id}/repair-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Authority-Token': import.meta.env.VITE_AUTHORITY_TOKEN || ''
        },
        body: JSON.stringify({ authority: 'Bhubaneswar Municipal Corp', notes: 'Dispatched maintenance team' })
      });
      await fetchEventDetail(ev.event_id);
      await fetchEvents();
    } catch (e) {
      console.error(e);
    }
    setActionLoading(false);
  };

  const handleResolve = async () => {
    setActionLoading(true);
    try {
      await fetch(`/api/events/${ev.event_id}/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Authority-Token': import.meta.env.VITE_AUTHORITY_TOKEN || ''
        },
        body: JSON.stringify({ authority: 'BMC Quality Inspector' })
      });
      await fetchEventDetail(ev.event_id);
      await fetchEvents();
    } catch (e) {
      console.error(e);
    }
    setActionLoading(false);
  };

  const getStatusStyle = (status) => {
    switch (status) {
      case 'HIGH_PRIORITY': return { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '#ef4444' };
      case 'CORROBORATED': return { bg: 'rgba(249, 115, 22, 0.15)', color: '#f97316', border: '#f97316' };
      case 'REPAIR_REPORTED': return { bg: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '#38bdf8' };
      case 'RESOLVED': return { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '#10b981' };
      default: return { bg: 'rgba(250, 204, 21, 0.15)', color: '#facc15', border: '#facc15' };
    }
  };

  const statusStyle = getStatusStyle(ev.status);
  const sourceDevices = [...new Set(timeline.map((observation) => observation.device_id).filter(Boolean))];
  const reportedSourceDevices = sourceDevices.length ? sourceDevices : (ev.source_vehicle_ids || []);
  const repeatedObservations = Math.max(0, timeline.length - sourceDevices.length);
  const evidenceItems = (ev.evidence || []).filter((item) => item.status === 'AVAILABLE' && item.uri);
  const repairHistory = ev.repair_history || [];
  const lifecycleSteps = [
    { label: 'DETECTED', active: true, complete: true },
    { label: 'CORROBORATED', active: (reportedSourceDevices.length || ev.unique_sources || 0) >= 2, complete: (reportedSourceDevices.length || ev.unique_sources || 0) >= 2 },
    { label: 'PRIORITIZED', active: ev.status === 'HIGH_PRIORITY', complete: ev.status === 'HIGH_PRIORITY' },
    { label: 'REPAIR REPORTED', active: repairHistory.length > 0, complete: repairHistory.length > 0 },
    { label: 'RESOLVED', active: ev.status === 'RESOLVED', complete: ev.status === 'RESOLVED' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '16px', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Domain badge */}
          {(() => {
            const DOMAIN_META = {
              ROAD_DAMAGE:    { label: 'ROAD DAMAGE',    color: '#ef4444' },
              INFRASTRUCTURE: { label: 'INFRASTRUCTURE', color: '#f97316' },
              WATERLOGGING:   { label: 'WATERLOGGING',   color: '#06b6d4' },
              ROAD_HAZARD:    { label: 'ROAD HAZARD',    color: '#eab308' },
              TRAFFIC:        { label: 'TRAFFIC',         color: '#38bdf8' },
              SAFETY:         { label: 'SAFETY',          color: '#a855f7' },
              INCIDENT:       { label: 'INCIDENT',        color: '#dc2626' },
            };
            const domainKey = (ev.type || 'ROAD_DAMAGE').toUpperCase();
            const dm = DOMAIN_META[domainKey] || DOMAIN_META.ROAD_DAMAGE;
            return (
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                marginBottom: '4px'
              }}>
                <span style={{
                  fontSize: '10px', fontWeight: 800, letterSpacing: '0.5px',
                  color: dm.color,
                  background: `${dm.color}18`,
                  border: `1px solid ${dm.color}44`,
                  padding: '2px 8px', borderRadius: '4px',
                }}>● {dm.label}</span>
                <span style={{ fontSize: '10px', color: 'var(--text-dim)', letterSpacing: '0.4px' }}>
                  CLICK-TO-INVESTIGATE
                </span>
              </div>
            );
          })()}
          <div style={{ fontSize: '16px', fontWeight: 800, textTransform: 'capitalize', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {(ev.subtype || 'Unknown').replace(/_/g, ' ')}
          </div>
          <div className="mono" style={{ color: 'var(--text-dim)', fontSize: '10px', marginTop: '4px' }}>EVENT {ev.event_id || selectedEntity.id}</div>
        </div>
        <button
          onClick={clearSelection}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Main Details */}
      <div style={{ padding: '16px', flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Status Badge & Priority */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <div
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              background: statusStyle.bg,
              border: `1px solid ${statusStyle.border}`,
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>LIFECYCLE STATUS</div>
            <div style={{ fontSize: '12px', fontWeight: 800, color: statusStyle.color }}>
              {ev.status}
            </div>
          </div>

          <div
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>CONFIDENCE</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#38bdf8' }}>
              {((ev.event_confidence || 0) * 100).toFixed(0)}%
            </div>
          </div>

          <div
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>SOURCES</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#f8fafc' }}>
              {ev.unique_sources} VEHICLES
            </div>
          </div>
        </div>

        <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '11px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div><div style={{ color: 'var(--text-dim)' }}>SEVERITY</div><strong>{ev.severity || 'Not reported'}</strong></div>
          <div><div style={{ color: 'var(--text-dim)' }}>PRIORITY SCORE</div><strong className="mono">{ev.priority_score ?? 'Not reported'}</strong></div>
          <div><div style={{ color: 'var(--text-dim)' }}>FIRST OBSERVED</div><strong className="mono">{(ev.evidence_summary?.first_observed_at || ev.created_at) ? new Date((ev.evidence_summary?.first_observed_at || ev.created_at) * 1000).toLocaleString() : 'Not reported'}</strong></div>
          <div><div style={{ color: 'var(--text-dim)' }}>LAST OBSERVED</div><strong className="mono">{(ev.evidence_summary?.last_observed_at || ev.updated_at) ? new Date((ev.evidence_summary?.last_observed_at || ev.updated_at) * 1000).toLocaleString() : 'Not reported'}</strong></div>
        </div>

        <div style={{ background: 'rgba(56,189,248,.05)', padding: '11px 12px', borderRadius: '8px', border: '1px solid rgba(56,189,248,.2)', fontSize: '11px', display: 'grid', gap: '7px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}><span style={{ color: 'var(--text-dim)' }}>LOCATION</span><span className="mono">{ev.latitude?.toFixed(6)}, {ev.longitude?.toFixed(6)}</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}><span style={{ color: 'var(--text-dim)' }}>MAP CONTEXT</span><span style={{ color: 'var(--text-muted)' }}>OpenStreetMap roads at event location</span></div>
          <div style={{ color: 'var(--text-dim)', lineHeight: 1.4 }}>No application road-segment match is recorded for this event.</div>
        </div>

        <div style={{ background: 'var(--bg-card)', padding: '11px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 800, marginBottom: '8px' }}>WHY THIS EVENT IS TRUSTED</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '7px', fontSize: '10px' }}>
            <div><div style={{ color: 'var(--text-dim)' }}>OBSERVATIONS</div><strong className="mono">{timeline.length || ev.observation_count || 0}</strong></div>
            <div><div style={{ color: 'var(--text-dim)' }}>INDEPENDENT</div><strong className="mono">{reportedSourceDevices.length || ev.unique_sources || 0} DEVICE{(reportedSourceDevices.length || ev.unique_sources || 0) === 1 ? '' : 'S'}</strong></div>
            <div><div style={{ color: 'var(--text-dim)' }}>REPEATED</div><strong className="mono">{repeatedObservations} SAME-DEVICE</strong></div>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '10px', marginTop: '8px', lineHeight: 1.4 }}>
            Independent-device corroboration counts unique source devices. Repeated observations from one device remain recorded but do not add a source.
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-muted)' }}>PERSISTENT URBAN MEMORY</div>
          <div style={{ color: 'var(--text-dim)', fontSize: '11px', lineHeight: 1.55 }}>
            Source vehicles: <span className="mono" style={{ color: 'var(--text-main)' }}>{reportedSourceDevices.length ? reportedSourceDevices.join(', ') : 'Not reported'}</span><br />
            Current state: <strong style={{ color: statusStyle.color }}>{ev.status || 'Not reported'}</strong> · Repair records: <strong>{repairHistory.length}</strong>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-muted)' }}>EVIDENCE LEDGER ({evidenceItems.length} AVAILABLE)</div>
          {evidenceItems.length === 0 ? (
            <div style={{ color: 'var(--text-dim)', fontSize: '11px' }}>No evidence frame is available for inspection.</div>
          ) : evidenceItems.map((item) => (
            <div key={item.observation_id} style={{ fontSize: '11px', display: 'flex', justifyContent: 'space-between', gap: '8px', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,.05)' }}>
              <span className="mono">{item.device_id}</span>
              <span style={{ color: 'var(--text-dim)' }}>{item.timestamp ? new Date(item.timestamp * 1000).toLocaleTimeString() : 'Timestamp not supplied'}</span>
              <span style={{ color: '#10b981' }}>{((item.model_confidence ?? 0) * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>

        {/* Evidence Visual Snapshot */}
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '6px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ImageIcon size={13} color="var(--accent-cyan)" />
              VISUAL EVIDENCE
              {ev.evidence_uris && ev.evidence_uris.length > 1 && (
                <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', background: 'rgba(56, 189, 248, 0.15)', padding: '1px 5px', borderRadius: '4px' }}>
                  {activeEvidenceIndex + 1}/{ev.evidence_uris.length}
                </span>
              )}
            </span>
            {ev.evidence_uris && ev.evidence_uris.length > 0 && !imgError && (
              <button
                onClick={() => setEvidenceModalOpen(true)}
                style={{
                  background: 'rgba(56, 189, 248, 0.1)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  color: 'var(--accent-cyan)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
                title="Inspect High-Resolution Evidence Frame"
              >
                <Maximize2 size={11} /> Expand
              </button>
            )}
          </div>

          {ev.evidence_uris && ev.evidence_uris.length > 0 && !imgError ? (
            <div style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-color)', background: '#0a0f1d' }}>
              <img
                src={ev.evidence_uris[activeEvidenceIndex] || ev.evidence_uris[0]}
                alt="Defect Evidence"
                style={{
                  width: '100%',
                  height: '180px',
                  objectFit: 'cover',
                  display: 'block',
                  cursor: 'pointer',
                  transition: 'transform 0.2s'
                }}
                onClick={() => setEvidenceModalOpen(true)}
                onError={() => {
                  setImgError(true);
                }}
              />

              {/* Defect Type Pill Overlay */}
              <div style={{
                position: 'absolute',
                top: '8px',
                left: '8px',
                background: ev.subtype === 'pothole' ? 'rgba(239, 68, 68, 0.9)' : ev.subtype === 'no_zebracrossing' ? 'rgba(245, 158, 11, 0.9)' : 'rgba(2, 132, 199, 0.9)',
                backdropFilter: 'blur(4px)',
                color: 'white',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '10px',
                fontWeight: 800,
                letterSpacing: '0.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                textTransform: 'uppercase'
              }}>
                <span>{ev.subtype || 'DEFECT'}</span>
                <span>•</span>
                <span>{((ev.model_confidence ?? ev.event_confidence ?? 0) * 100).toFixed(0)}% CONF</span>
              </div>

              {/* Multi-Photo Carousel Selector */}
              {ev.evidence_uris.length > 1 && (
                <div style={{
                  position: 'absolute',
                  bottom: '8px',
                  left: '8px',
                  display: 'flex',
                  gap: '4px',
                  background: 'rgba(0, 0, 0, 0.65)',
                  backdropFilter: 'blur(4px)',
                  padding: '3px 6px',
                  borderRadius: '12px'
                }}>
                  {ev.evidence_uris.slice(0, 5).map((uri, idx) => (
                    <button
                      key={idx}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveEvidenceIndex(idx);
                        setImgError(false);
                      }}
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '50%',
                        border: 'none',
                        background: activeEvidenceIndex === idx ? 'var(--accent-cyan)' : 'rgba(255, 255, 255, 0.3)',
                        color: activeEvidenceIndex === idx ? '#0a0f1d' : '#fff',
                        fontSize: '9px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      {idx + 1}
                    </button>
                  ))}
                </div>
              )}

              {/* Click to inspect watermark */}
              <div
                onClick={() => setEvidenceModalOpen(true)}
                style={{
                  position: 'absolute',
                  bottom: '8px',
                  right: '8px',
                  background: 'rgba(15, 23, 42, 0.85)',
                  backdropFilter: 'blur(4px)',
                  color: '#94a3b8',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  cursor: 'pointer'
                }}
              >
                <Eye size={11} color="var(--accent-cyan)" />
                <span>Click to zoom</span>
              </div>
            </div>
          ) : (
            <div style={{
              height: '120px',
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: '8px',
              border: '1px dashed var(--border-color)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              color: 'var(--text-dim)',
              fontSize: '12px',
              padding: '16px',
              textAlign: 'center'
            }}>
              <ShieldAlert size={24} color="var(--text-dim)" style={{ opacity: 0.6 }} />
              <div>
                <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>No visual evidence attached</span>
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
                Evidence availability is reported in the event timeline when present
              </span>
            </div>
          )}
        </div>

        {/* Metadata Details */}
        <div style={{ background: 'var(--bg-card)', padding: '12px', borderRadius: '8px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-dim)' }}>Event ID:</span>
            <span className="mono">{ev.event_id?.substring(0, 12)}...</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-dim)' }}>Coordinates:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="mono">{ev.latitude?.toFixed(5)}, {ev.longitude?.toFixed(5)}</span>
              {ev.latitude && ev.longitude && (
                <button
                  onClick={() => copyCoords(ev.latitude, ev.longitude)}
                  style={{ background: 'transparent', border: 'none', color: copiedCoords ? '#10b981' : 'var(--accent-cyan)', cursor: 'pointer', padding: '2px', display: 'flex', alignItems: 'center' }}
                  title="Copy Coordinates to Clipboard"
                >
                  {copiedCoords ? <Check size={12} /> : <Copy size={12} />}
                </button>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-dim)' }}>Severity Rating:</span>
            <span style={{ fontWeight: 700, color: ev.severity === 'HIGH' ? '#ef4444' : '#f59e0b' }}>
              {ev.severity}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-dim)' }}>Priority Score:</span>
            <span className="mono" style={{ fontWeight: 700 }}>{ev.priority_score}</span>
          </div>
        </div>

        {/* Urban Memory Timeline (§12) */}
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Clock size={14} color="var(--accent-cyan)" />
            <span>URBAN MEMORY TIMELINE ({timeline.length})</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderLeft: '2px solid rgba(56, 189, 248, 0.3)', paddingLeft: '12px' }}>
            {timeline.map((obs, idx) => {
              const isSameDeviceRepeat = timeline.slice(0, idx).some((prior) => prior.device_id === obs.device_id);
              return (
              <div key={obs.observation_id || idx} style={{ fontSize: '11px', background: 'rgba(255,255,255,0.02)', padding: '7px 8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,.04)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                  <span style={{ color: 'var(--accent-cyan)' }}>#{idx + 1} {obs.device_id}</span>
                  <span className="mono" style={{ color: '#10b981' }}>{((obs.model_confidence ?? 0) * 100).toFixed(0)}% conf</span>
                </div>
                <div style={{ color: 'var(--text-dim)', fontSize: '10px', marginTop: '2px' }}>
                  {obs.timestamp ? new Date(obs.timestamp * 1000).toLocaleTimeString() : 'Timestamp not supplied'} · {obs.latitude?.toFixed(5)}, {obs.longitude?.toFixed(5)}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '5px' }}>
                  <span style={{ color: isSameDeviceRepeat ? '#facc15' : '#10b981', fontSize: '9px', fontWeight: 700 }}>{isSameDeviceRepeat ? 'REPEATED SAME DEVICE' : 'INDEPENDENT SOURCE'}</span>
                  {obs.source_type === 'replay' && <span style={{ color: '#f59e0b', fontSize: '9px', fontWeight: 700 }}>REPLAY SOURCE</span>}
                  <span style={{ color: obs.evidence_status === 'AVAILABLE' ? '#10b981' : 'var(--text-dim)', fontSize: '9px' }}>EVIDENCE: {obs.evidence_status || 'Not reported'}</span>
                </div>
              </div>
              );
            })}
          </div>
        </div>

        {repairHistory.length > 0 && (
          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}><Wrench size={14} color="var(--accent-cyan)" /> REPAIR HISTORY ({repairHistory.length})</div>
            {repairHistory.map((repair) => (
              <div key={repair.id} style={{ fontSize: '11px', padding: '7px 8px', marginBottom: '5px', background: 'rgba(56,189,248,.04)', border: '1px solid rgba(56,189,248,.15)', borderRadius: '5px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}><strong>{repair.status || 'Repair update'}</strong><span className="mono">{repair.reported_at ? new Date(repair.reported_at * 1000).toLocaleString() : 'Timestamp not supplied'}</span></div>
                <div style={{ color: 'var(--text-dim)', marginTop: '3px' }}>{repair.reported_by || 'Reporter not supplied'}{repair.notes ? ` · ${repair.notes}` : ''}</div>
              </div>
            ))}
          </div>
        )}

        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-muted)' }}>CLOSED-LOOP LIFECYCLE</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
            {lifecycleSteps.map((step) => (
              <span key={step.label} style={{ padding: '4px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: 800, color: step.active ? (step.complete ? '#10b981' : '#facc15') : 'var(--text-dim)', background: step.active ? (step.complete ? 'rgba(16,185,129,.1)' : 'rgba(250,204,21,.08)') : 'rgba(255,255,255,.025)', border: `1px solid ${step.active ? (step.complete ? 'rgba(16,185,129,.35)' : 'rgba(250,204,21,.3)') : 'var(--border-color)'}` }}>
                {step.complete ? '✓ ' : ''}{step.label}
              </span>
            ))}
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '10px', lineHeight: 1.45, marginTop: '8px' }}>
            Steps are shown only from current persisted fields: distinct sources, current priority state, repair records, and current resolution state. Re-check/verification is not an automatic backend state; no persistence assessment is inferred here.
          </div>
        </div>

        {/* Municipal Workflow Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: 'auto', paddingTop: '12px' }}>
          <button
            onClick={() => setQueueModalOpen(true)}
            style={{ padding: '9px', borderRadius: '6px', border: '1px solid rgba(56,189,248,.45)', background: 'rgba(56,189,248,.08)', color: 'var(--accent-cyan)', fontWeight: 700, fontSize: '12px', cursor: 'pointer' }}
          >
            OPEN MAINTENANCE QUEUE
          </button>
          {ev.status !== 'REPAIR_REPORTED' && ev.status !== 'RESOLVED' && (
            <button
              onClick={handleReportRepair}
              disabled={actionLoading}
              style={{
                padding: '10px',
                borderRadius: '6px',
                border: 'none',
                background: '#0284c7',
                color: 'white',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <Wrench size={16} />
              DISPATCH REPAIR CREW
            </button>
          )}

          {ev.status !== 'RESOLVED' && (
            <button
              onClick={handleResolve}
              disabled={actionLoading}
              style={{
                padding: '10px',
                borderRadius: '6px',
                border: 'none',
                background: '#15803d',
                color: 'white',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <CheckCircle2 size={16} />
              MARK AS RESOLVED
            </button>
          )}
        </div>
      </div>

      {/* Lightbox / High-Resolution Visual Evidence Inspection Modal */}
      {isEvidenceModalOpen && ev.evidence_uris && ev.evidence_uris.length > 0 && (
        <div
          className="modal-overlay"
          onClick={() => setEvidenceModalOpen(false)}
          style={{ zIndex: 9999 }}
        >
          <div
            className="modal-content"
            style={{ maxWidth: '820px', background: '#090d16', border: '1px solid var(--accent-cyan)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ImageIcon size={18} color="var(--accent-cyan)" />
                <span style={{ fontSize: '15px', fontWeight: 800 }}>
                  HIGH-RESOLUTION VISUAL EVIDENCE AUDIT — {ev.subtype?.toUpperCase() || 'DEFECT'}
                </span>
              </div>
              <button
                onClick={() => setEvidenceModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{
                position: 'relative',
                borderRadius: '8px',
                overflow: 'hidden',
                background: '#000',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '300px',
                maxHeight: '520px'
              }}>
                <img
                  src={ev.evidence_uris[activeEvidenceIndex] || ev.evidence_uris[0]}
                  alt="Defect Evidence Full"
                  style={{ maxWidth: '100%', maxHeight: '520px', objectFit: 'contain' }}
                />
              </div>

              {/* Evidence Telemetry Stamp */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '10px',
                background: 'var(--bg-card)',
                padding: '12px',
                borderRadius: '8px',
                fontSize: '11px'
              }}>
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>EVENT IDENTIFIER</div>
                  <div className="mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '2px' }}>
                    {ev.event_id}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>GEO-COORDINATES</div>
                  <div className="mono" style={{ fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
                    {ev.latitude?.toFixed(6)}, {ev.longitude?.toFixed(6)}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>DETECTION CONFIDENCE</div>
                  <div className="mono" style={{ fontWeight: 700, color: '#10b981', marginTop: '2px' }}>
                    {((ev.model_confidence ?? ev.event_confidence ?? 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>CORROBORATION</div>
                  <div className="mono" style={{ fontWeight: 700, color: '#f59e0b', marginTop: '2px' }}>
                    {ev.unique_sources || 1} Independent Vehicle{ev.unique_sources > 1 ? 's' : ''}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
