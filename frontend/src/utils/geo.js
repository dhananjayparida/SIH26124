/**
 * Geospatial, Speed & Tile Layer Configuration Utilities (SIH26124).
 * Provides robust coordinate formatting, speed normalization, and multi-provider map tiles.
 */

/**
 * Formats speed reliably to km/h string.
 * Handles both m/s (standard GPS / Geolocation API) and pre-converted km/h values.
 *
 * @param {number|string|null} speed Speed in m/s or km/h
 * @returns {string} e.g. "24.5"
 */
export function formatSpeedKmh(speed) {
  if (speed === null || speed === undefined || speed === '') return '0.0';
  const val = Number(speed);
  if (isNaN(val) || val <= 0.05) return '0.0';

  // If val > 35, it's already transmitted in km/h (e.g. from GPS CSV 24.5 km/h)
  // City transit buses never travel > 35 m/s (126 km/h)
  // If val <= 35, it's in standard m/s, so multiply by 3.6
  const kmh = val > 35 ? val : val * 3.6;
  return kmh.toFixed(1);
}

/**
 * Formats latitude and longitude with precision.
 *
 * @param {number|string} lat
 * @param {number|string} lon
 * @param {number} precision Decimal places (default 5)
 * @returns {string} e.g. "20.29612, 85.82455"
 */
export function formatCoords(lat, lon, precision = 5) {
  if (lat === null || lat === undefined || lon === null || lon === undefined) {
    return 'Acquiring GPS...';
  }
  const latNum = Number(lat);
  const lonNum = Number(lon);
  if (isNaN(latNum) || isNaN(lonNum)) return 'Awaiting GPS Fix';
  return `${latNum.toFixed(precision)}, ${lonNum.toFixed(precision)}`;
}

/**
 * Returns Leaflet TileLayer configuration for the selected basemap and optional API key.
 *
 * Supports:
 * - Custom Mapbox Token (pk.*)
 * - Maptiler API Key
 * - Zero-Key High-Reliability Providers (CartoDB Dark, Esri Satellite, OpenStreetMap)
 *
 * @param {string} basemap 'dark' | 'satellite' | 'streets'
 * @param {string} apiKey Custom Mapbox token or Maptiler key
 * @returns {{ url: string, attribution: string, subdomains: string|string[], maxZoom: number }}
 */
export function getTileLayerConfig(basemap = 'dark', apiKey = '') {
  const cleanKey = (apiKey || '').trim();

  // 1. If user provided a Mapbox Access Token (starts with 'pk.')
  if (cleanKey && cleanKey.startsWith('pk.')) {
    if (basemap === 'satellite') {
      return {
        url: `https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{z}/{x}/{y}?access_token=${cleanKey}`,
        attribution: '&copy; Mapbox &copy; OpenStreetMap',
        subdomains: [],
        maxZoom: 20
      };
    } else if (basemap === 'streets') {
      return {
        url: `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{z}/{x}/{y}?access_token=${cleanKey}`,
        attribution: '&copy; Mapbox &copy; OpenStreetMap',
        subdomains: [],
        maxZoom: 20
      };
    } else {
      // Default: Mapbox Dark Tactical
      return {
        url: `https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/{z}/{x}/{y}?access_token=${cleanKey}`,
        attribution: '&copy; Mapbox &copy; OpenStreetMap',
        subdomains: [],
        maxZoom: 20
      };
    }
  }

  // 2. If user provided a Maptiler API Key
  if (cleanKey && cleanKey.length >= 10 && !cleanKey.startsWith('pk.')) {
    if (basemap === 'satellite') {
      return {
        url: `https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=${cleanKey}`,
        attribution: '&copy; MapTiler &copy; OpenStreetMap',
        subdomains: [],
        maxZoom: 20
      };
    } else if (basemap === 'streets') {
      return {
        url: `https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}.png?key=${cleanKey}`,
        attribution: '&copy; MapTiler &copy; OpenStreetMap',
        subdomains: [],
        maxZoom: 20
      };
    } else {
      return {
        url: `https://api.maptiler.com/maps/dataviz-dark/{z}/{x}/{y}.png?key=${cleanKey}`,
        attribution: '&copy; MapTiler &copy; OpenStreetMap',
        subdomains: [],
        maxZoom: 20
      };
    }
  }

  // 3. Zero-Key Default High-Reliability Providers
  if (basemap === 'satellite') {
    return {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS',
      subdomains: [],
      maxZoom: 19
    };
  } else if (basemap === 'streets') {
    return {
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap contributors',
      subdomains: 'abc',
      maxZoom: 19
    };
  } else {
    // Dark Tactical: Stadia Maps Alidade Smooth Dark — free, no API key required
    return {
      url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
      attribution: '&copy; Stadia Maps &copy; OpenStreetMap contributors',
      subdomains: [],
      maxZoom: 20
    };
  }
}
