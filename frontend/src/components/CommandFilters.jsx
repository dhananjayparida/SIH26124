import React, { useMemo } from 'react';
import { Filter, RotateCcw } from 'lucide-react';
import { useStore } from '../state/store';

const label = (value) => String(value || '').replace(/_/g, ' ');

export default function CommandFilters() {
  const events = useStore((state) => state.events);
  const fleet = useStore((state) => state.fleet);
  const filters = useStore((state) => state.mapFilters);
  const setMapFilter = useStore((state) => state.setMapFilter);
  const clearMapFilters = useStore((state) => state.clearMapFilters);

  const eventTypes = useMemo(
    () => [...new Set(events.map((event) => event.type).filter(Boolean))].sort(),
    [events]
  );
  const eventStatuses = useMemo(
    () => [...new Set(events.map((event) => event.status).filter(Boolean))].sort(),
    [events]
  );
  const sourceStates = useMemo(
    () => [...new Set(Object.values(fleet).map((vehicle) => vehicle.status).filter(Boolean))].sort(),
    [fleet]
  );
  const vehicles = useMemo(
    () => Object.values(fleet).sort((a, b) => a.device_id.localeCompare(b.device_id)),
    [fleet]
  );

  const field = (key, title, options) => (
    <label className="command-filter-field">
      <span>{title}</span>
      <select value={filters[key]} onChange={(event) => setMapFilter(key, event.target.value)}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );

  return (
    <section className="command-filters" aria-label="Operational filters">
      <div className="panel-section-title">
        <span><Filter size={13} /> OPERATIONAL FILTERS</span>
        <button onClick={clearMapFilters} title="Clear operational filters" aria-label="Clear operational filters">
          <RotateCcw size={13} /> Reset
        </button>
      </div>

      <div className="command-filter-grid">
        {field('eventType', 'Event type', [{ value: 'ALL', label: 'All detected types' }, ...eventTypes.map((value) => ({ value, label: label(value) }))])}
        {field('eventStatus', 'Event state', [{ value: 'ALL', label: 'All lifecycle states' }, ...eventStatuses.map((value) => ({ value, label: label(value) }))])}
        {field('priority', 'Priority', [
          { value: 'ALL', label: 'All priorities' },
          { value: 'HIGH_PRIORITY', label: 'High priority only' }
        ])}
        {field('sourceStatus', 'Source state', [{ value: 'ALL', label: 'All source states' }, ...sourceStates.map((value) => ({ value, label: value }))])}
        {field('timeRange', 'Event recency', [
          { value: 'ALL', label: 'Any time' },
          { value: '1H', label: 'Last hour' },
          { value: '24H', label: 'Last 24 hours' },
          { value: '7D', label: 'Last 7 days' }
        ])}
        {field('vehicleId', 'Vehicle', [{ value: 'ALL', label: 'All vehicles' }, ...vehicles.map((vehicle) => ({ value: vehicle.device_id, label: vehicle.device_id }))])}
      </div>
    </section>
  );
}
