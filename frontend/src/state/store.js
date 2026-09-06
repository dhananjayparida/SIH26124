import { create } from 'zustand';

export const useStore = create((set, get) => ({
  // Fleet sensing vehicles
  fleet: {},
  // Fused Urban Events
  events: [],
  // Selected entity for click-to-investigate inspector
  selectedEntity: null,
  // Layer visibility toggles
  layers: {
    fleet:          true,
    roadDamage:     true,   // ROAD_DAMAGE events (potholes, cracks, surface damage)
    infrastructure: true,   // INFRASTRUCTURE events (zebra, dividers, signboards)
    traffic:        false,  // TRAFFIC events (vehicle density, bottlenecks)
    safety:         true,   // SAFETY events (vulnerable pedestrians)
    incident:       true,   // INCIDENT events (rash driving, hit-and-run)
    gridHealth:     true,
    trails:         true,
    annotations:    true,
    radar:          true,
    coverage:       false   // Coverage freshness layer
  },
  // Basemap style: 'dark' | 'satellite' | 'streets'
  basemap: 'dark',
  // Followed entity ID for tactical follow mode
  followedVehicleId: null,
  // Cockpit view overlay
  cockpitMode: false,
  // Analyst map annotations
  annotations: [
    {
      id: 'ann_1',
      latitude: 20.2985,
      longitude: 85.8262,
      category: 'ROADWORK',
      note: 'Janpath Drainage excavation in progress - lane reduction',
      created_at: Date.now() / 1000 - 3600
    }
  ],
  // AI Command Copilot modal
  isCopilotOpen: false,
  // HUD Statistics — includes mode (LIVE | REPLAY | STANDBY)
  hudMetrics: {
    active_vehicles: 0,
    live_sources: 0,
    stale_sources: 0,
    replay_sources: 0,
    open_events: 0,
    high_priority_events: 0,
    corroborated_events: 0,
    candidate_events: 0,
    total_observations: 0,
    mode: 'STANDBY'
  },
  // Grid health cells
  gridHealthCells: [],
  // Coverage freshness cells
  coverageCells: [],
  // Maintenance Queue Modal
  isQueueModalOpen: false,

  // Map API Key (Mapbox / Maptiler) & Map Settings Modal
  mapApiKey: localStorage.getItem('sih_map_api_key') || '',
  isMapKeyModalOpen: false,

  // Live Map Cursor Coordinates Inspector
  cursorCoords: { lat: 20.2961, lng: 85.8245 },

  // Actions
  setBasemap: (basemap) => set({ basemap }),
  setMapApiKey: (key) => {
    localStorage.setItem('sih_map_api_key', key || '');
    set({ mapApiKey: key || '' });
  },
  setMapKeyModalOpen: (isOpen) => set({ isMapKeyModalOpen: isOpen }),
  setCursorCoords: (coords) => set({ cursorCoords: coords }),
  setFollowedVehicle: (id) => set({ followedVehicleId: id }),
  setCockpitMode: (cockpitMode) => set({ cockpitMode }),
  setCopilotOpen: (isCopilotOpen) => set({ isCopilotOpen }),
  addAnnotation: (ann) => set((state) => ({ annotations: [...state.annotations, ann] })),
  removeAnnotation: (id) => set((state) => ({ annotations: state.annotations.filter((a) => a.id !== id) })),
  toggleLayer: (layerName) => set((state) => ({
    layers: { ...state.layers, [layerName]: !state.layers[layerName] }
  })),

  selectEntity: (type, id, data = null) => set({
    selectedEntity: { type, id, data }
  }),

  clearSelection: () => set({ selectedEntity: null }),

  setQueueModalOpen: (isOpen) => set({ isQueueModalOpen: isOpen }),

  // WebSocket Telemetry update
  handleWsMessage: (msg) => {
    if (msg.type === 'TELEMETRY_UPDATE') {
      const { device_id, latitude, longitude, speed, heading, timestamp, fused_events,
              frame_base64, source_type, status, detections_reported } = msg;

      set((state) => {
        const existing = state.fleet[device_id] || { trail: [] };
        const trail = [...(existing.trail || [])];
        if (latitude && longitude) {
          trail.push([latitude, longitude]);
          if (trail.length > 80) trail.shift();
        }

        const updatedFleet = {
          ...state.fleet,
          [device_id]: {
            ...existing,
            device_id,
            // Preserve truthful source_type from WS broadcast
            source_type: source_type || existing.source_type || 'phone_pwa',
            latitude: latitude !== null && latitude !== undefined ? Number(latitude) : existing.latitude,
            longitude: longitude !== null && longitude !== undefined ? Number(longitude) : existing.longitude,
            speed: speed !== null && speed !== undefined ? Number(speed) : (existing.speed ?? 0),
            heading: heading !== null && heading !== undefined ? Number(heading) : (existing.heading ?? 0),
            // Use status from gateway (LIVE | REPLAY | STALE | OFFLINE)
            status: status || existing.status || 'STALE',
            last_seen: timestamp || Date.now() / 1000,
            detections_reported: detections_reported !== undefined
              ? Number(detections_reported)
              : (existing.detections_reported || 0),
            // Store latest camera frame for cockpit panel
            latestFrame: frame_base64 || existing.latestFrame,
            trail
          }
        };

        let updatedSelected = state.selectedEntity;
        if (state.selectedEntity && state.selectedEntity.type === 'vehicle' && state.selectedEntity.id === device_id) {
          updatedSelected = {
            ...state.selectedEntity,
            data: updatedFleet[device_id]
          };
        }

        return { fleet: updatedFleet, selectedEntity: updatedSelected };
      });

      // If this packet triggered fused events, refresh events & HUD
      if (fused_events && fused_events.length > 0) {
        get().fetchEvents();
        get().fetchHUD();
        get().fetchGridHealth();
        if (get().layers.coverage) get().fetchCoverage();
      }
    }
  },

  // API Fetchers
  fetchFleet: async () => {
    try {
      const res = await fetch('/api/fleet/status');
      if (res.ok) {
        const list = await res.json();
        set((state) => {
          const fleetMap = { ...state.fleet };
          list.forEach((v) => {
            const current = fleetMap[v.device_id] || { trail: [] };
            const existingTrail = current.trail && current.trail.length > 0 ? current.trail : [];
            const newTrail = v.latitude && v.longitude && existingTrail.length === 0 ? [[Number(v.latitude), Number(v.longitude)]] : existingTrail;

            fleetMap[v.device_id] = {
              ...current,
              ...v,
              latitude: v.latitude !== null && v.latitude !== undefined ? Number(v.latitude) : current.latitude,
              longitude: v.longitude !== null && v.longitude !== undefined ? Number(v.longitude) : current.longitude,
              trail: newTrail
            };
          });
          const selected = state.selectedEntity;
          const selectedEntity = selected?.type === 'vehicle' && fleetMap[selected.id]
            ? { ...selected, data: fleetMap[selected.id] }
            : selected;
          return { fleet: fleetMap, selectedEntity };
        });
      }
    } catch (e) {
      console.error('Failed to fetch fleet status:', e);
    }
  },

  fetchEvents: async () => {
    try {
      const res = await fetch('/api/events');
      if (res.ok) {
        const events = await res.json();
        set({ events });

        // If an event is selected, refresh its full detail (Urban Memory)
        const currentSel = get().selectedEntity;
        if (currentSel && currentSel.type === 'event') {
          const match = events.find((e) => e.event_id === currentSel.id);
          if (match) get().fetchEventDetail(currentSel.id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch events:', e);
    }
  },

  fetchEventDetail: async (eventId) => {
    try {
      const res = await fetch(`/api/events/${eventId}`);
      if (res.ok) {
        const detail = await res.json();
        set({ selectedEntity: { type: 'event', id: eventId, data: detail } });
      }
    } catch (e) {
      console.error('Failed to fetch event detail:', e);
    }
  },

  fetchGridHealth: async () => {
    try {
      const res = await fetch('/api/road-segments/health');
      if (res.ok) {
        const gridHealthCells = await res.json();
        set({ gridHealthCells });
      }
    } catch (e) {
      console.error('Failed to fetch road health:', e);
    }
  },

  fetchCoverage: async () => {
    try {
      const res = await fetch('/api/coverage/cells');
      if (res.ok) {
        const coverageCells = await res.json();
        set({ coverageCells });
      }
    } catch (e) {
      console.error('Failed to fetch coverage cells:', e);
    }
  },

  fetchHUD: async () => {
    try {
      const res = await fetch('/api/hud/summary');
      if (res.ok) {
        const hudMetrics = await res.json();
        set({ hudMetrics });
      }
    } catch (e) {
      console.error('Failed to fetch HUD summary:', e);
    }
  }
}));
