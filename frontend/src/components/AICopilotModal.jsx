import React, { useState } from 'react';
import { useStore } from '../state/store';
import { X, Sparkles, MessageSquare, Play, Check, Send, AlertTriangle, Bus, Layers } from 'lucide-react';

export default function AICopilotModal() {
  const isCopilotOpen = useStore((state) => state.isCopilotOpen);
  const setCopilotOpen = useStore((state) => state.setCopilotOpen);
  const setQueueModalOpen = useStore((state) => state.setQueueModalOpen);
  const setCockpitMode = useStore((state) => state.setCockpitMode);
  const hudMetrics = useStore((state) => state.hudMetrics);
  const events = useStore((state) => state.events);
  const selectEntity = useStore((state) => state.selectEntity);

  const [inputQuery, setInputQuery] = useState('');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Command shortcuts ready. Use the listed commands to navigate current fleet, event, cockpit, and maintenance data.'
    }
  ]);
  const [executing, setExecuting] = useState(false);

  if (!isCopilotOpen) return null;

  const quickPrompts = [
    'Show highest priority road defect',
    'How many sensing buses are active?',
    'Enter Cockpit Sensing View',
    'Open Municipal Maintenance Queue',
    'What is the current defect corroboration count?'
  ];

  const handleExecute = async (queryText) => {
    const q = (queryText || inputQuery).trim();
    if (!q) return;

    const userMsg = { role: 'user', text: q };
    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setExecuting(true);

    const qLower = q.toLowerCase();
    let reply = '';

    // Tool calling logic against live store & APIs
    if (qLower.includes('highest priority') || qLower.includes('worst pothole') || qLower.includes('priority defect')) {
      const highSev = events.find((e) => e.status === 'HIGH_PRIORITY') || events[0];
      if (highSev) {
        selectEntity('event', highSev.event_id, highSev);
        reply = `Selected High-Priority Defect (${highSev.event_id}) at ${highSev.latitude?.toFixed(4)}, ${highSev.longitude?.toFixed(4)}. Severity is ${highSev.severity} with ${highSev.unique_sources} corroborating buses.`;
      } else {
        reply = 'No open high-priority defects currently found.';
      }
    } else if (qLower.includes('buses') || qLower.includes('active') || qLower.includes('fleet')) {
      reply = `Fleet Status: ${hudMetrics.active_vehicles} connected vehicles registered, with ${hudMetrics.live_sources} currently marked LIVE by the backend.`;
    } else if (qLower.includes('cockpit') || qLower.includes('follow') || qLower.includes('dashcam')) {
      setCockpitMode(true);
      setCopilotOpen(false);
      reply = 'Opened cockpit view. Select a bus to inspect its current telemetry and latest received frame.';
    } else if (qLower.includes('maintenance') || qLower.includes('queue') || qLower.includes('work order') || qLower.includes('export')) {
      setQueueModalOpen(true);
      setCopilotOpen(false);
      reply = 'Opened Prioritized Municipal Maintenance Queue.';
    } else if (qLower.includes('corroborat') || qLower.includes('count') || qLower.includes('summary')) {
      reply = `Urban Memory Summary: ${hudMetrics.open_events} total defects recorded. ${hudMetrics.corroborated_events} corroborated by 2+ buses, and ${hudMetrics.high_priority_events} elevated to High-Priority.`;
    } else {
      reply = `That command is not available. Use one of the listed shortcuts; this panel does not use a generative AI service.`;
    }

    setTimeout(() => {
      setMessages((prev) => [...prev, { role: 'assistant', text: reply }]);
      setExecuting(false);
    }, 400);
  };

  return (
    <div className="modal-overlay" onClick={() => setCopilotOpen(false)}>
      <div className="modal-content" style={{ maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={18} color="var(--accent-cyan)" />
            <span style={{ fontSize: '15px', fontWeight: 800 }}>
              OPERATIONAL COMMAND SHORTCUTS
            </span>
          </div>
          <button
            onClick={() => setCopilotOpen(false)}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px', minHeight: '320px' }}>
          {/* Quick Prompts */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {quickPrompts.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleExecute(p)}
                style={{
                  background: 'rgba(56, 189, 248, 0.08)',
                  border: '1px solid rgba(56, 189, 248, 0.2)',
                  color: 'var(--accent-cyan)',
                  padding: '4px 10px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Messages History */}
          <div style={{
            flex: 1,
            maxHeight: '220px',
            overflowY: 'auto',
            background: 'var(--bg-card)',
            padding: '12px',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  background: m.role === 'user' ? '#0284c7' : '#1e293b',
                  color: 'white',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  maxWidth: '85%'
                }}
              >
                {m.text}
              </div>
            ))}
            {executing && (
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontStyle: 'italic' }}>
                Executing urban tool call...
              </div>
            )}
          </div>

          {/* Input Box */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleExecute();
            }}
            style={{ display: 'flex', gap: '8px' }}
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Enter a supported shortcut, e.g. 'Show highest priority road defect'"
              style={{
                flex: 1,
                background: '#0a0f1d',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '10px 14px',
                color: 'white',
                fontSize: '13px',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              style={{
                background: '#2563eb',
                border: 'none',
                color: 'white',
                padding: '0 16px',
                borderRadius: '6px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontWeight: 700
              }}
            >
              <Send size={15} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
