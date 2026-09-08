from __future__ import annotations
import argparse, base64, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from ai_engine.sensor_interface.contracts import SensorPacket, GPSReading
from ai_engine.perception.detector import RoadDefectDetector

SEVERITY = {
    'pothole': 'HIGH', 'alligator_crack': 'HIGH', 'waterlogging': 'HIGH',
    'damaged_road': 'HIGH', 'longitudinal_crack': 'MEDIUM',
    'transverse_crack': 'MEDIUM', 'missing_divider': 'MEDIUM',
    'no_zebracrossing': 'MEDIUM', 'damaged_signboard': 'LOW',
    'debris': 'MEDIUM', 'vehicle': 'INFO',
}
LABEL = {
    'pothole': 'POTHOLE', 'longitudinal_crack': 'LONG-CRACK',
    'transverse_crack': 'TRANS-CRACK', 'alligator_crack': 'ALLIGATOR',
    'damaged_road': 'DAMAGED-ROAD', 'missing_divider': 'DIVIDER',
    'no_zebracrossing': 'NO-ZEBRA', 'damaged_signboard': 'SIGNBOARD',
    'waterlogging': 'WATERLOG', 'debris': 'DEBRIS', 'vehicle': 'VEHICLE',
}

def load_b64(p):
    with open(p, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def build_packet(img, idx=0, cc=False):
    return SensorPacket(
        packet_id='inf_%05d' % idx,
        device_id='standalone',
        frame_timestamp=time.time(),          # float Unix timestamp (required by schema)
        frame_base64=load_b64(img),
        gps=GPSReading(latitude=17.385, longitude=78.4867, accuracy=5.0),
        extra_metadata={'check_crossing': cc},
    )

def run_one(det, img, idx=0, cc=False):
    pkt = build_packet(img, idx, cc)
    res = det.detect(pkt)
    dets = []
    for d in res.detections:
        dets.append({
            'class': d.class_name,
            'confidence': round(d.confidence, 4),
            'severity': SEVERITY.get(d.class_name, 'LOW'),
            'bbox': {'x': round(d.bbox.x,1), 'y': round(d.bbox.y,1),
                     'w': round(d.bbox.width,1), 'h': round(d.bbox.height,1)},
            'model': d.model_version,
        })
    return {'frame': idx, 'source': str(img), 'ms': round(res.inference_time_ms,2),
            'count': len(dets), 'detections': dets}

def collect(p):
    exts = {'.jpg','.jpeg','.png','.bmp','.webp'}
    p = Path(p)
    if p.is_dir(): return sorted(x for x in p.iterdir() if x.suffix.lower() in exts)
    if p.suffix.lower() in exts: return [p]
    return []

def show(r):
    n, src = r['count'], Path(r['source']).name
    if n == 0:
        print('  [%04d] %s  CLEAN' % (r['frame'], src))
        return
    print()
    print('  [%04d] %s  %d hazard(s)' % (r['frame'], src, n))
    for d in r['detections']:
        lbl = LABEL.get(d['class'], d['class'])
        pct = int(d['confidence'] * 100)
        print('    [%-6s]  %-16s  %d%%' % (d['severity'], lbl, pct))

def main():
    ap = argparse.ArgumentParser(description='SIH26124 Standalone Road Hazard Detector')
    ap.add_argument('--input','-i',required=True,help='Image / video / directory')
    ap.add_argument('--output','-o',default=None,help='Output JSON path')
    ap.add_argument('--conf','-c',type=float,default=0.45,help='Confidence threshold (default 0.45)')
    ap.add_argument('--model','-m',default=None,help='Custom .pt weights path')
    ap.add_argument('--frame-interval',type=int,default=10,help='Video: process every Nth frame')
    ap.add_argument('--check-crossing',action='store_true',help='Enable zebra crossing morphology check')
    args = ap.parse_args()

    print('=' * 60)
    print('  SIH26124 Road Hazard Inference Engine  [STANDALONE]')
    print('  No frontend / backend / streaming required')
    print('=' * 60)
    print('  Loading model (conf >= %.2f) ...' % args.conf)
    t0 = time.perf_counter()
    det = RoadDefectDetector(confidence_threshold=args.conf, weights_path=args.model, device='cpu')
    print('  Ready in %dms' % int((time.perf_counter()-t0)*1000))
    print()

    inp = Path(args.input)
    if not inp.exists():
        print('ERROR: not found: ' + str(inp))
        sys.exit(1)

    out_dir = ROOT_DIR / 'output'
    out_dir.mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else out_dir / 'inference_results.json'

    results = []
    if inp.suffix.lower() in {'.mp4','.avi','.mov','.mkv','.webm'}:
        try:
            import cv2
        except ImportError:
            print('pip install opencv-python')
            sys.exit(1)
        cap = cv2.VideoCapture(str(inp))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        print('  Video: every %d frames' % args.frame_interval)
        tmp = out_dir / '_tmp'
        tmp.mkdir(exist_ok=True)
        fi = 0
        while True:
            ok, frame = cap.read()
            if not ok: break
            if fi % args.frame_interval == 0:
                tp = tmp / ('f%06d.jpg' % fi)
                cv2.imwrite(str(tp), frame)
                r = run_one(det, tp, fi, args.check_crossing)
                r['video_sec'] = round(fi/fps, 2)
                results.append(r)
                show(r)
                tp.unlink(missing_ok=True)
            fi += 1
        cap.release()
    else:
        imgs = collect(inp)
        if not imgs:
            print('No images at ' + str(inp))
            sys.exit(1)
        print('  Image mode: %d file(s)' % len(imgs))
        for i, p in enumerate(imgs):
            results.append(run_one(det, p, i, args.check_crossing))
            show(results[-1])

    counts = Counter()
    for r in results:
        for d in r['detections']:
            counts[d['class']] += 1

    total = sum(r['count'] for r in results)
    n_pos = sum(1 for r in results if r['count'] > 0)

    print()
    print('-' * 60)
    print('SUMMARY')
    print('-' * 60)
    print('  Frames processed  : %d' % len(results))
    print('  With hazards      : %d' % n_pos)
    print('  Total detections  : %d' % total)
    if counts:
        print()
        print('  %-26s %5s  SEVERITY' % ('CLASS', 'COUNT'))
        print('  ' + '-'*44)
        for cls, cnt in counts.most_common():
            print('  %-26s %5d  %s' % (LABEL.get(cls,cls), cnt, SEVERITY.get(cls,'LOW')))
    print()

    out = {
        'engine': 'SIH26124-RoadHazardDetector',
        'version': '1.0.0',
        'run_timestamp': datetime.now(timezone.utc).isoformat(),
        'config': {
            'confidence': args.conf,
            'input': str(inp),
            'check_crossing': args.check_crossing,
        },
        'summary': {
            'total_frames': len(results),
            'frames_with_hazards': n_pos,
            'total_detections': total,
            'by_class': dict(counts.most_common()),
        },
        'frames': results,
    }
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print('Saved -> ' + str(out_path))

if __name__ == '__main__':
    main()
