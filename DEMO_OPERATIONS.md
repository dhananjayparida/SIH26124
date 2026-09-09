# Demo operations

## Start

1. Start the local stack with `python run_demo.py`.
2. Open the command center at `http://localhost:3000`.
3. Open the displayed phone PWA URL on a device. An HTTPS tunnel is required by many mobile browsers for camera and GPS permissions; otherwise use localhost or a configured secure origin.
4. In the command center, use the transport badge: `WS` means live WebSocket updates; `HTTP FALLBACK` means polling remains active but WebSocket delivery is unavailable.

## Judge flow

1. Begin at the Bhubaneswar OSM city view.
2. Run `r` in `run_demo.py` for a replay-labelled multi-device demonstration, or connect real phone sources.
3. Select a bus to show its actual source state, latest transmitted frame (if any), GPS, detections, and source-linked events.
4. Select an event to show persisted evidence, observations, independent source count, same-device repeats, and repair history.
5. Open the maintenance queue, then use the existing repair report and resolve actions from an event.
6. Return to Bhubaneswar with the map recenter control.

## Data truth

- Phone camera frames and GPS are real only when the PWA has permissions and is transmitting.
- Replay and simulation sources are labelled in the command center.
- The system persists events, observations, vehicles, repairs, and evidence references in SQLite.
- OSM provides map context; no road-segment ownership or automatic nearest-road matching is claimed.
- Automatic post-repair verification/re-check is not implemented.

## Backup and reset

The reset script is deliberately destructive and requires an explicit command:

```powershell
python scratch/reset_all_data.py --confirm-demo-reset
```

Before changing data it copies `data/urban_intel.db` and the evidence directory to `data/backups/`. It then clears local demo database rows, evidence files, and demo output. Do not run it against production data. To restore a demo snapshot, stop the services and manually replace `data/urban_intel.db` and evidence files with the intended backed-up copies.
