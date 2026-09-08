import React, { useState, useEffect } from 'react';
import { X, Smartphone, QrCode, Wifi, Shield, Check, Copy, ExternalLink } from 'lucide-react';

export default function PhoneConnectModal({ isOpen, onClose }) {
  const [copied, setCopied] = useState(false);
  const [deviceId, setDeviceId] = useState('BUS_LIVE_01');
  const [localIp, setLocalIp] = useState('192.168.1.21');
  const [liveTunnelUrl, setLiveTunnelUrl] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetch('/api/tunnel-url')
        .then((r) => r.json())
        .then((data) => {
          if (data.local_ip) setLocalIp(data.local_ip);
          if (data.tunnel_url) setLiveTunnelUrl(data.tunnel_url);
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Local IP and Cloudflare HTTPS Tunnel URLs
  const localUrl = `http://${localIp}:5000/pwa?device_id=${deviceId}`;
  const bestUrl = liveTunnelUrl ? `${liveTunnelUrl}/pwa?device_id=${deviceId}` : localUrl;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(bestUrl)}`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '650px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Smartphone size={20} color="var(--accent-cyan)" />
            <span style={{ fontSize: '16px', fontWeight: 800 }}>
              CONNECT SMARTPHONE CAMERA & GPS
            </span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Vehicle Device Selector */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600 }}>Simulate Vehicle Identity:</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              {['BUS_LIVE_01', 'BUS_LIVE_02', 'BUS_LIVE_03'].map((id) => (
                <button
                  key={id}
                  onClick={() => setDeviceId(id)}
                  style={{
                    background: deviceId === id ? '#0284c7' : '#1e293b',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '4px 10px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {id}
                </button>
              ))}
            </div>
          </div>

          {/* Quick QR Code & Link */}
          <div style={{ display: 'flex', gap: '20px', alignItems: 'center', background: 'rgba(56, 189, 248, 0.05)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
            <div style={{ background: 'white', padding: '6px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <img src={qrImageUrl} alt="Scan to connect" style={{ width: '140px', height: '140px', display: 'block' }} />
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                Scan QR Code with your Phone
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Opens the live mobile sensing PWA over secure HTTPS with instant camera and GPS access (Zero configuration needed).
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                <button
                  onClick={() => copyToClipboard(bestUrl)}
                  style={{
                    background: '#2563eb',
                    border: 'none',
                    color: 'white',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    cursor: 'pointer'
                  }}
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? 'Copied URL!' : 'Copy Direct Link'}
                </button>

                <button
                  onClick={() => window.open(`/pwa?device_id=${deviceId}`, '_blank')}
                  style={{
                    background: 'rgba(56, 189, 248, 0.15)',
                    border: '1px solid var(--accent-cyan)',
                    color: 'var(--accent-cyan)',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    cursor: 'pointer'
                  }}
                >
                  <ExternalLink size={14} />
                  <span>Test in Browser Tab</span>
                </button>
              </div>
            </div>
          </div>

          {/* Wi-Fi Direct Alternative */}
          <div style={{ background: 'var(--bg-card)', padding: '12px 16px', borderRadius: '8px', fontSize: '12px' }}>
            <div style={{ fontWeight: 700, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Wifi size={14} color="#10b981" /> Same Wi-Fi Direct Address
            </div>
            <div style={{ color: 'var(--text-dim)', marginBottom: '8px' }}>
              If your phone is on the same Wi-Fi network, you can also type this directly into your mobile browser:
            </div>
            <div className="mono" style={{ color: 'var(--accent-cyan)', background: '#0a0f1d', padding: '6px 10px', borderRadius: '4px', userSelect: 'all' }}>
              {localUrl}
            </div>
          </div>

          {/* Demo Usage Steps */}
          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '6px' }}>
              HOW TO DEMO IN FRONT OF JUDGES:
            </div>
            <ol style={{ fontSize: '12px', color: 'var(--text-muted)', paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li>Open the link on your smartphone and allow <b>Camera</b> and <b>Location</b> permissions.</li>
              <li>Tap <b>"START SENSING"</b> — you will see your live camera feed and your phone appear on the command center map!</li>
              <li>Point camera at road hazards or test samples for real-time live YOLO perception.</li>
              <li>Watch the command center flip the event from <b>CANDIDATE</b> → <b>CORROBORATED</b> in real time.</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
