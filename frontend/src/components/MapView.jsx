import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { useStore } from '../state/store';
import { formatSpeedKmh, getTileLayerConfig } from '../utils/geo';
import CockpitOverlay from './CockpitOverlay';

export default function MapView() {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const tileLayerRef = useRef(null);
  const layersRef = useRef({
    fleetGroup:          L.layerGroup(),
    trailsGroup:         L.layerGroup(),
    roadDamageGroup:     L.layerGroup(),   // ROAD_DAMAGE events
    infrastructureGroup: L.layerGroup(),   // INFRASTRUCTURE events
    trafficGroup:        L.layerGroup(),   // TRAFFIC events
    safetyGroup:         L.layerGroup(),   // SAFETY events
    incidentGroup:       L.layerGroup(),   // INCIDENT events
    gridGroup:           L.layerGroup(),
    annotationsGroup:    L.layerGroup(),
    radarGroup:          L.layerGroup()
  });

  const fleet = useStore((state) => state.fleet);
  const events = useStore((state) => state.events);
  const gridHealthCells = useStore((state) => state.gridHealthCells);
  const annotations = useStore((state) => state.annotations);
  const layers = useStore((state) => state.layers);
  const basemap = useStore((state) => state.basemap);
  const mapApiKey = useStore((state) => state.mapApiKey);
  const cursorCoords = useStore((state) => state.cursorCoords);
  const setCursorCoords = useStore((state) => state.setCursorCoords);
  const followedVehicleId = useStore((state) => state.followedVehicleId);
  const selectEntity = useStore((state) => state.selectEntity);
  const selectedEntity = useStore((state) => state.selectedEntity);

  // 1. Initialize Map
  useEffect(() => {
    if (!mapInstanceRef.current && mapContainerRef.current) {
      // Default center: Janpath, Bhubaneswar
      const map = L.map(mapContainerRef.current, {
        center: [20.2961, 85.8245],
        zoom: 14,
        zoomControl: false
      });

      // Zoom control in top right
      L.control.zoom({ position: 'topright' }).addTo(map);

      // Mousemove real-time coordinate tracking
      map.on('mousemove', (e) => {
        setCursorCoords({ lat: e.latlng.lat, lng: e.latlng.lng });
      });

      // Add feature layer groups
      layersRef.current.gridGroup.addTo(map);
      layersRef.current.trailsGroup.addTo(map);
      layersRef.current.roadDamageGroup.addTo(map);
      layersRef.current.infrastructureGroup.addTo(map);
      layersRef.current.trafficGroup.addTo(map);
      layersRef.current.safetyGroup.addTo(map);
      layersRef.current.incidentGroup.addTo(map);
      layersRef.current.annotationsGroup.addTo(map);
      layersRef.current.radarGroup.addTo(map);
      layersRef.current.fleetGroup.addTo(map);

      mapInstanceRef.current = map;
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // 2. Dynamic Basemap Tile Switcher (Mapbox / CARTO / Esri / OpenStreetMap)
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    const map = mapInstanceRef.current;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    const config = getTileLayerConfig(basemap, mapApiKey);
    const layer = L.tileLayer(config.url, {
      attribution: config.attribution,
      subdomains: config.subdomains,
      maxZoom: config.maxZoom
    });

    layer.on('tileerror', () => {
      console.warn('[MapView] Tile loading fallback active');
    });

    layer.addTo(map);
    tileLayerRef.current = layer;
  }, [basemap, mapApiKey]);

  // 3. Update Fleet Markers & Trails
  useEffect(() => {
    const { fleetGroup, trailsGroup } = layersRef.current;
    fleetGroup.clearLayers();
    trailsGroup.clearLayers();

    if (!layers.fleet) return;

    Object.values(fleet).forEach((bus) => {
      if (!bus.latitude || !bus.longitude) return;

      // Draw GPS Trail
      if (layers.trails && bus.trail && bus.trail.length > 1) {
        const polyline = L.polyline(bus.trail, {
          color: '#38bdf8',
          weight: 3,
          opacity: 0.6,
          dashArray: '4, 8'
        });
        trailsGroup.addLayer(polyline);
      }

      // Live / Stale status color
      const isLive = bus.status === 'LIVE';
      const isSelected = selectedEntity?.type === 'vehicle' && selectedEntity?.id === bus.device_id;
      const isFollowed = followedVehicleId === bus.device_id;

      const vehicleIcon = L.divIcon({
        className: 'custom-bus-marker',
        html: `
          <div style="
            position: relative;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: ${isFollowed ? '#f59e0b' : isLive ? '#0284c7' : '#475569'};
            border: 2px solid ${isFollowed ? '#fbbf24' : isSelected ? '#ffffff' : isLive ? '#38bdf8' : '#94a3b8'};
            border-radius: 50%;
            box-shadow: 0 0 ${isFollowed ? '16px #f59e0b' : isLive ? '10px rgba(56, 189, 248, 0.6)' : 'none'};
            transform: rotate(${bus.heading || 0}deg);
            transition: all 0.3s ease;
          ">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L19 21L12 17L5 21L12 2Z"/>
            </svg>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const marker = L.marker([bus.latitude, bus.longitude], { icon: vehicleIcon });

      marker.bindTooltip(
        `<b>${bus.device_id}</b> (${bus.source_type || 'phone_pwa'})<br/>Status: <b>${bus.status}</b><br/>Speed: <b>${formatSpeedKmh(bus.speed)} km/h</b><br/>GPS: ${bus.latitude.toFixed(5)}, ${bus.longitude.toFixed(5)}`,
        { direction: 'top', className: 'custom-leaflet-tooltip' }
      );

      marker.on('click', () => {
        selectEntity('vehicle', bus.device_id, bus);
      });

      fleetGroup.addLayer(marker);
    });

    // Auto Follow Vehicle in Follow Mode
    if (followedVehicleId && fleet[followedVehicleId] && mapInstanceRef.current) {
      const fb = fleet[followedVehicleId];
      if (fb.latitude && fb.longitude) {
        mapInstanceRef.current.panTo([fb.latitude, fb.longitude], { animate: true, duration: 0.5 });
      }
    }
  }, [fleet, layers.fleet, layers.trails, selectedEntity, followedVehicleId, selectEntity]);

  // 4. Update Urban Event Pins (multi-domain)
  useEffect(() => {
    const {
      roadDamageGroup, infrastructureGroup, trafficGroup, safetyGroup, incidentGroup
    } = layersRef.current;

    roadDamageGroup.clearLayers();
    infrastructureGroup.clearLayers();
    trafficGroup.clearLayers();
    safetyGroup.clearLayers();
    incidentGroup.clearLayers();

    // Domain colour palette (matches LayerPanel)
    const DOMAIN_COLORS = {
      ROAD_DAMAGE:    '#ef4444',
      INFRASTRUCTURE: '#f97316',
      WATERLOGGING:   '#06b6d4',
      ROAD_HAZARD:    '#eab308',
      TRAFFIC:        '#38bdf8',
      SAFETY:         '#a855f7',
      INCIDENT:       '#dc2626',
    };

    // Domain → layer group + store key
    const DOMAIN_META = {
      ROAD_DAMAGE:    { group: roadDamageGroup,     layerKey: 'roadDamage' },
      INFRASTRUCTURE: { group: infrastructureGroup,  layerKey: 'infrastructure' },
      WATERLOGGING:   { group: roadDamageGroup,     layerKey: 'roadDamage' },
      ROAD_HAZARD:    { group: roadDamageGroup,     layerKey: 'roadDamage' },
      TRAFFIC:        { group: trafficGroup,         layerKey: 'traffic' },
      SAFETY:         { group: safetyGroup,          layerKey: 'safety' },
      INCIDENT:       { group: incidentGroup,        layerKey: 'incident' },
    };

    events.forEach((ev) => {
      if (!ev.latitude || !ev.longitude) return;

      const evType = (ev.type || 'ROAD_DAMAGE').toUpperCase();
      const meta = DOMAIN_META[evType] || DOMAIN_META.ROAD_DAMAGE;

      // Respect layer toggle
      if (!layers[meta.layerKey]) return;

      const domainColor = DOMAIN_COLORS[evType] || '#eab308';

      // Lifecycle status → ring size (domain colour stays constant)
      let radius = 6;
      let strokeWidth = 1.5;
      if (ev.status === 'CORROBORATED')      { radius = 7; strokeWidth = 2; }
      else if (ev.status === 'HIGH_PRIORITY') { radius = 9; strokeWidth = 2.5; }
      else if (ev.status === 'REPAIR_REPORTED') { radius = 7; strokeWidth = 2; }
      else if (ev.status === 'RESOLVED')     { radius = 6; }

      const isSelected = selectedEntity?.type === 'event' && selectedEntity?.id === ev.event_id;

      const circle = L.circleMarker([ev.latitude, ev.longitude], {
        radius: isSelected ? radius + 4 : radius,
        fillColor: ev.status === 'RESOLVED' ? '#10b981' : domainColor,
        color: isSelected ? '#ffffff' : '#0f172a',
        weight: isSelected ? 3 : strokeWidth,
        opacity: 1,
        fillOpacity: ev.status === 'RESOLVED' ? 0.5 : 0.85
      });

      const domainLabel = evType.replace('_', ' ');
      circle.bindTooltip(
        `<b>${domainLabel}</b> · ${ev.subtype?.replace('_', ' ') || ''}<br/>` +
        `Status: <b>${ev.status}</b><br/>` +
        `Confidence: ${(ev.event_confidence * 100).toFixed(0)}% (${ev.unique_sources} source${ev.unique_sources !== 1 ? 's' : ''})`,
        { direction: 'top', className: 'custom-leaflet-tooltip' }
      );

      circle.on('click', () => {
        selectEntity('event', ev.event_id, ev);
      });

      meta.group.addLayer(circle);
    });
  }, [
    events,
    layers.roadDamage, layers.infrastructure, layers.traffic, layers.safety, layers.incident,
    selectedEntity, selectEntity
  ]);

  // 5. Update Analyst Annotations Layer
  useEffect(() => {
    const { annotationsGroup } = layersRef.current;
    annotationsGroup.clearLayers();

    if (!layers.annotations) return;

    annotations.forEach((ann) => {
      const annIcon = L.divIcon({
        className: 'custom-ann-marker',
        html: `
          <div style="
            background: #8b5cf6;
            color: white;
            font-size: 10px;
            font-weight: 800;
            padding: 3px 6px;
            border-radius: 4px;
            border: 1px solid #c4b5fd;
            white-space: nowrap;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
          ">
            📌 ${ann.category}
          </div>
        `,
        iconSize: [80, 24],
        iconAnchor: [40, 12]
      });

      const marker = L.marker([ann.latitude, ann.longitude], { icon: annIcon });
      marker.bindPopup(`<b>${ann.category}</b><br/>${ann.note}<br/><small style="color:#64748b">Analyst Note</small>`);
      annotationsGroup.addLayer(marker);
    });
  }, [annotations, layers.annotations]);

  // 6. Update Nearby Entities Radar Ring
  useEffect(() => {
    const { radarGroup } = layersRef.current;
    radarGroup.clearLayers();

    if (!layers.radar || !selectedEntity || !selectedEntity.data) return;

    const { latitude, longitude } = selectedEntity.data;
    if (latitude && longitude) {
      // 500m proximity radar ring
      const circle = L.circle([latitude, longitude], {
        radius: 500,
        color: 'var(--accent-cyan)',
        weight: 1.5,
        fillColor: 'var(--accent-cyan)',
        fillOpacity: 0.05,
        dashArray: '6, 6'
      });
      circle.bindTooltip('500m Proximity Radar Zone', { direction: 'center', opacity: 0.7 });
      radarGroup.addLayer(circle);
    }
  }, [selectedEntity, layers.radar]);

  // 7. Update Road Health Grid Polygons
  useEffect(() => {
    const { gridGroup } = layersRef.current;
    gridGroup.clearLayers();

    if (!layers.gridHealth) return;

    gridHealthCells.forEach((cell) => {
      const rect = L.rectangle(cell.bounds, {
        color: cell.color,
        weight: 1,
        fillColor: cell.color,
        fillOpacity: 0.15
      });

      rect.bindTooltip(
        `<b>Road Condition: ${cell.status}</b><br/>Health Index: <b>${cell.health_score}/100</b><br/>Defects: ${cell.event_count}`,
        { direction: 'center', opacity: 0.8 }
      );

      gridGroup.addLayer(rect);
    });
  }, [gridHealthCells, layers.gridHealth]);

  // 8. Fly-to selected entity
  useEffect(() => {
    if (!mapInstanceRef.current || !selectedEntity) return;

    if (selectedEntity.type === 'event' && selectedEntity.data) {
      const { latitude, longitude } = selectedEntity.data;
      if (latitude && longitude) {
        mapInstanceRef.current.flyTo([latitude, longitude], 16, { duration: 1.2 });
      }
    } else if (selectedEntity.type === 'vehicle' && selectedEntity.data) {
      const { latitude, longitude } = selectedEntity.data;
      if (latitude && longitude && !followedVehicleId) {
        mapInstanceRef.current.panTo([latitude, longitude]);
      }
    }
  }, [selectedEntity, followedVehicleId]);

  const handleLocatePhone = () => {
    if (!mapInstanceRef.current) return;
    const fleetList = Object.values(fleet);
    // Prioritize LIVE phones, then any recently active vehicle
    let target = fleetList.find((b) => b.status === 'LIVE' && b.latitude && b.longitude);
    if (!target) {
      target = fleetList.find((b) => b.latitude && b.longitude && (b.source_type === 'phone_pwa' || b.device_id.includes('LIVE')));
    }
    if (!target) {
      target = fleetList.find((b) => b.latitude && b.longitude && (b.status === 'REPLAY' || b.status === 'STALE'));
    }
    if (!target) {
      target = fleetList.find((b) => b.latitude && b.longitude);
    }
    if (target && target.latitude && target.longitude) {
      mapInstanceRef.current.flyTo([target.latitude, target.longitude], 16, { duration: 1.2 });
      selectEntity('vehicle', target.device_id, target);
    } else {
      mapInstanceRef.current.flyTo([20.2961, 85.8245], 14, { duration: 1.0 });
    }
  };

  const handleCenterBhubaneswar = () => {
    if (!mapInstanceRef.current) return;
    mapInstanceRef.current.flyTo([20.2961, 85.8245], 14, { duration: 1.2 });
  };

  // Detect if any live phone is streaming from outside the primary Bhubaneswar Janpath bounding box
  const livePhoneOutside = Object.values(fleet).find(
    (b) => b.status === 'LIVE' && b.latitude && b.longitude && (Math.abs(b.latitude - 20.2961) > 0.08 || Math.abs(b.longitude - 85.8245) > 0.08)
  );

  return (
    <div className="map-container" style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div id="map" ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Floating GPS Location Controls */}
      <div style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        zIndex: 500,
        display: 'flex',
        gap: '8px',
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(8px)',
        padding: '6px',
        borderRadius: '8px',
        border: '1px solid rgba(56, 189, 248, 0.3)'
      }}>
        <button
          onClick={handleLocatePhone}
          style={{
            background: '#0284c7',
            border: 'none',
            color: 'white',
            padding: '6px 12px',
            borderRadius: '6px',
            fontSize: '11px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '5px'
          }}
        >
          📍 LOCATE LIVE PHONE
        </button>
        <button
          onClick={handleCenterBhubaneswar}
          style={{
            background: '#1e293b',
            border: '1px solid var(--border-color)',
            color: '#94a3b8',
            padding: '6px 10px',
            borderRadius: '6px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          🏙️ BHUBANESWAR
        </button>
      </div>

      {/* Live Phone Outside Corridor Alert Banner */}
      {livePhoneOutside && (
        <div style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          zIndex: 500,
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          background: 'rgba(234, 88, 12, 0.92)',
          backdropFilter: 'blur(8px)',
          color: 'white',
          padding: '6px 14px',
          borderRadius: '8px',
          border: '1px solid rgba(251, 146, 60, 0.5)',
          fontSize: '11px',
          fontWeight: 700,
          boxShadow: '0 4px 14px rgba(0,0,0,0.5)'
        }}>
          <span>📍 LIVE GPS: {livePhoneOutside.device_id} ({livePhoneOutside.latitude.toFixed(4)}, {livePhoneOutside.longitude.toFixed(4)})</span>
          <button
            onClick={() => {
              if (mapInstanceRef.current) {
                mapInstanceRef.current.flyTo([livePhoneOutside.latitude, livePhoneOutside.longitude], 16, { duration: 1.2 });
                selectEntity('vehicle', livePhoneOutside.device_id, livePhoneOutside);
              }
            }}
            style={{
              background: 'white',
              color: '#ea580c',
              border: 'none',
              padding: '3px 8px',
              borderRadius: '4px',
              fontWeight: 800,
              fontSize: '11px',
              cursor: 'pointer'
            }}
          >
            PAN TO PHONE
          </button>
        </div>
      )}

      {/* Live Cursor Coordinate Inspector HUD */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        zIndex: 500,
        background: 'rgba(10, 15, 29, 0.85)',
        backdropFilter: 'blur(8px)',
        padding: '6px 12px',
        borderRadius: '6px',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '11px',
        color: '#cbd5e1',
        fontFamily: 'monospace',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>CURSOR:</span>
          <span>{cursorCoords.lat ? cursorCoords.lat.toFixed(5) : '20.29610'}° N, {cursorCoords.lng ? cursorCoords.lng.toFixed(5) : '85.82450'}° E</span>
        </div>
        <div style={{ width: '1px', height: '12px', background: 'var(--border-color)' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ color: '#f59e0b', fontWeight: 600 }}>JANPATH CORRIDOR</span>
        </div>
        <div style={{ width: '1px', height: '12px', background: 'var(--border-color)' }} />
        <span style={{ color: mapApiKey ? '#10b981' : '#38bdf8', fontWeight: 700, fontSize: '10px' }}>
          {mapApiKey ? 'MAPBOX HD' : 'CARTO / OSM'}
        </span>
      </div>

      <CockpitOverlay />
    </div>
  );
}
