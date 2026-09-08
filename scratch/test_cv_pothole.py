import numpy as np
from PIL import Image
from pathlib import Path

img_path = Path("data/samples/pothole_sample_frame.jpg")
frame = Image.open(img_path)
arr = np.array(frame.convert("L"))
h, w = arr.shape
road_view = arr[int(h * 0.35):, :]
mean_b = np.mean(road_view)

dark_mask = road_view < (mean_b * 0.60)
print(f"Image size: {w}x{h}, mean brightness: {mean_b:.1f}")
print(f"Dark pixels count: {np.sum(dark_mask)} ({np.sum(dark_mask) / road_view.size * 100:.2f}%)")

if np.sum(dark_mask) > 100:
    y_idx, x_idx = np.nonzero(dark_mask)
    min_x, max_x = int(np.min(x_idx)), int(np.max(x_idx))
    min_y, max_y = int(np.min(y_idx)) + int(h * 0.35), int(np.max(y_idx)) + int(h * 0.35)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    bw = max_x - min_x
    bh = max_y - min_y
    print(f"Detected Pothole Candidate! Center=({cx:.1f}, {cy:.1f}), Box={bw}x{bh}")
