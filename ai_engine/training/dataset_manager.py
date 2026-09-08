"""
Curated Best Dataset Manager for Urban Road Defect & Traffic Perception (SIH26124).
Provides automated generation, validation, and external import for the benchmark
5-class road safety dataset:
- 0: pothole
- 1: crack (longitudinal / alligator / damaged road)
- 2: no_zebracrossing (missing/faded crosswalk in pedestrian zone)
- 3: zebra_crossing (intact pedestrian crosswalk)
- 4: vehicle (car, bus, truck, motorcycle)
"""

import os
import shutil
import random
import subprocess
import zipfile
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import cv2
except ImportError:
    cv2 = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
BEST_DATASET_DIR = DATA_DIR / "training_dataset" / "best"
SAMPLES_DIR = DATA_DIR / "samples"

BEST_CLASSES = {
    0: "pothole",
    1: "longitudinal_crack",
    2: "transverse_crack",
    3: "alligator_crack",
    4: "damaged_road",
    5: "missing_divider",
    6: "no_zebracrossing",
    7: "damaged_signboard",
    8: "waterlogging",
    9: "debris",
    10: "vehicle",
}

KAGGLE_DATASET_SLUG = "sabidrahman/pothole-cracks-and-openmanhole"
KAGGLE_DATASET_DIR = DATA_DIR / "training_dataset" / "kaggle_road_hazards"
KAGGLE_CLASSES = {
    0: "pothole",
    1: "crack",
    2: "open_manhole"
}


class BestDatasetManager:
    """
    Manages benchmark datasets conforming to YOLOv8 & D-FINE training formats.
    """

    def __init__(self, dataset_dir: Path = BEST_DATASET_DIR):
        self.dataset_dir = dataset_dir
        self.train_img = self.dataset_dir / "train" / "images"
        self.train_lbl = self.dataset_dir / "train" / "labels"
        self.val_img = self.dataset_dir / "val" / "images"
        self.val_lbl = self.dataset_dir / "val" / "labels"

    def prepare_dataset(self, min_samples_per_class: int = 4) -> Path:
        """
        Prepares the full benchmark dataset with train/val splits and creates data.yaml.
        """
        for p in [self.train_img, self.train_lbl, self.val_img, self.val_lbl]:
            p.mkdir(parents=True, exist_ok=True)

        yaml_path = self.dataset_dir / "data.yaml"
        need_regen = False
        if yaml_path.exists():
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg.get("nc") != len(BEST_CLASSES):
                        need_regen = True
            except Exception:
                need_regen = True
        else:
            need_regen = True

        # Check existing samples
        existing_train = list(self.train_img.glob("*.jpg"))
        if len(existing_train) < 10 or need_regen:
            print("[BestDatasetManager] Initializing curated SIH 10-class benchmark dataset samples...")
            self._generate_curated_benchmark_samples()

        # Write data.yaml configuration
        yaml_content = {
            "path": str(self.dataset_dir.resolve()).replace("\\", "/"),
            "train": "train/images",
            "val": "val/images",
            "nc": len(BEST_CLASSES),
            "names": BEST_CLASSES
        }

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_content, f, sort_keys=False)

        print(f"[BestDatasetManager] data.yaml created at: {yaml_path}")
        return yaml_path

    def _generate_curated_benchmark_samples(self):
        """
        Generates calibrated high-detail training and validation samples
        covering all 10 SIH defect categories plus vehicles across varied road surfaces.
        """
        if cv2 is None:
            return

        sample_frame_path = SAMPLES_DIR / "pothole_sample_frame.jpg"
        real_road_base = None
        if sample_frame_path.exists():
            real_road_base = cv2.imread(str(sample_frame_path))

        random.seed(42)

        # Generate train and val sets
        for split, count in [("train", 20), ("val", 8)]:
            img_dir = self.dataset_dir / split / "images"
            lbl_dir = self.dataset_dir / split / "labels"

            for i in range(count):
                # 1. Canvas: Realistic road asphalt
                if real_road_base is not None and random.random() > 0.4:
                    canvas = cv2.resize(real_road_base, (640, 480)).copy()
                    alpha = 0.8 + random.random() * 0.4
                    canvas = cv2.convertScaleAbs(canvas, alpha=alpha, beta=random.randint(-15, 15))
                else:
                    canvas = np.full((480, 640, 3), random.randint(55, 75), dtype=np.uint8)
                    noise = np.random.normal(0, 10, canvas.shape).astype(np.uint8)
                    canvas = cv2.add(canvas, noise)
                    cv2.line(canvas, (320, 180), (320, 480), (200, 200, 200), 4)

                labels: List[str] = []

                # Class 0: Pothole
                if i % 2 == 0:
                    px, py = random.randint(180, 420), random.randint(240, 380)
                    pr_x, pr_y = random.randint(35, 65), random.randint(22, 42)
                    cv2.ellipse(canvas, (px, py), (pr_x + 4, pr_y + 3), 0, 0, 360, (25, 25, 25), 2)
                    cv2.ellipse(canvas, (px, py), (pr_x, pr_y), 0, 0, 360, (12, 12, 12), -1)
                    labels.append(f"0 {px/640:.6f} {py/480:.6f} {(pr_x*2)/640:.6f} {(pr_y*2)/480:.6f}")

                # Class 1: Longitudinal Crack (parallel to road direction)
                if i % 3 == 0:
                    lx, ly = random.randint(200, 400), random.randint(260, 360)
                    lw, lh = random.randint(120, 180), random.randint(12, 20)
                    cv2.line(canvas, (lx - lw//2, ly), (lx + lw//2, ly + random.randint(-5, 5)), (15, 15, 15), 3)
                    labels.append(f"1 {lx/640:.6f} {ly/480:.6f} {lw/640:.6f} {lh/480:.6f}")

                # Class 2: Transverse Crack (perpendicular to road direction)
                if i % 3 == 1:
                    tx, ty = random.randint(220, 420), random.randint(250, 370)
                    tw, th = random.randint(14, 24), random.randint(100, 160)
                    cv2.line(canvas, (tx, ty - th//2), (tx + random.randint(-4, 4), ty + th//2), (18, 18, 18), 3)
                    labels.append(f"2 {tx/640:.6f} {ty/480:.6f} {tw/640:.6f} {th/480:.6f}")

                # Class 3: Alligator Crack (interconnected fatigue network)
                if i % 4 == 0:
                    ax, ay = random.randint(200, 380), random.randint(280, 390)
                    aw, ah = random.randint(110, 160), random.randint(70, 110)
                    # Draw web of cracked lines
                    for _ in range(5):
                        p1 = (ax + random.randint(-aw//2, aw//2), ay + random.randint(-ah//2, ah//2))
                        p2 = (ax + random.randint(-aw//2, aw//2), ay + random.randint(-ah//2, ah//2))
                        cv2.line(canvas, p1, p2, (20, 20, 20), 2)
                    labels.append(f"3 {ax/640:.6f} {ay/480:.6f} {aw/640:.6f} {ah/480:.6f}")

                # Class 4: Damaged Road Surface (rough degraded asphalt patch)
                if i % 4 == 1:
                    dx, dy = random.randint(160, 360), random.randint(260, 380)
                    dw, dh = random.randint(140, 200), random.randint(80, 130)
                    patch = canvas[max(0, dy-dh//2):min(480, dy+dh//2), max(0, dx-dw//2):min(640, dx+dw//2)]
                    if patch.size > 0:
                        noise_patch = np.random.normal(0, 20, patch.shape).astype(np.int16)
                        blended = np.clip(patch.astype(np.int16) + noise_patch, 0, 255).astype(np.uint8)
                        canvas[max(0, dy-dh//2):min(480, dy+dh//2), max(0, dx-dw//2):min(640, dx+dw//2)] = blended
                    labels.append(f"4 {dx/640:.6f} {dy/480:.6f} {dw/640:.6f} {dh/480:.6f}")

                # Class 5: Missing Road Divider
                if i % 4 == 2:
                    mx, my = 320, random.randint(220, 360)
                    mw, mh = 45, 120
                    cv2.rectangle(canvas, (mx - mw//2, my - mh//2), (mx + mw//2, my + mh//2), (80, 75, 70), 1)
                    labels.append(f"5 {mx/640:.6f} {my/480:.6f} {mw/640:.6f} {mh/480:.6f}")

                # Class 6: Missing / Failed Zebra Crossing
                if i % 3 == 2:
                    zx, zy = 320, 400
                    zw, zh = 260, 60
                    for s in range(4):
                        sx = zx - 90 + s * 55
                        cv2.rectangle(canvas, (sx, zy - 20), (sx + 20, zy + 20), (70, 70, 70), 1)
                    labels.append(f"6 {zx/640:.6f} {zy/480:.6f} {zw/640:.6f} {zh/480:.6f}")

                # Class 7: Damaged / Missing Traffic Signboard
                if i % 4 == 3:
                    sx, sy = random.randint(80, 140), random.randint(140, 220)
                    sw, sh = 60, 75
                    # Tilted signboard pole and board
                    cv2.line(canvas, (sx, sy + 35), (sx - 5, sy - 25), (160, 160, 160), 3)
                    cv2.circle(canvas, (sx - 5, sy - 25), 18, (40, 40, 200), -1)
                    labels.append(f"7 {sx/640:.6f} {sy/480:.6f} {sw/640:.6f} {sh/480:.6f}")

                # Class 8: Waterlogging (standing surface water)
                if i % 5 == 0:
                    wx, wy = random.randint(220, 420), random.randint(300, 410)
                    ww, wh = random.randint(160, 240), random.randint(60, 100)
                    overlay = canvas.copy()
                    cv2.ellipse(overlay, (wx, wy), (ww//2, wh//2), 0, 0, 360, (110, 80, 50), -1)
                    cv2.addWeighted(overlay, 0.45, canvas, 0.55, 0, canvas)
                    labels.append(f"8 {wx/640:.6f} {wy/480:.6f} {ww/640:.6f} {wh/480:.6f}")

                # Class 9: Debris (spilled rocks / gravel / trash)
                if i % 5 == 1:
                    bx, by = random.randint(180, 400), random.randint(320, 420)
                    bw, bh = random.randint(70, 110), random.randint(45, 75)
                    for _ in range(8):
                        rx = bx + random.randint(-bw//3, bw//3)
                        ry = by + random.randint(-bh//3, bh//3)
                        cv2.circle(canvas, (rx, ry), random.randint(3, 7), (140, 130, 120), -1)
                    labels.append(f"9 {bx/640:.6f} {by/480:.6f} {bw/640:.6f} {bh/480:.6f}")

                # Class 10: Vehicle (Car or Bus ahead)
                if i % 2 == 1:
                    vx, vy = random.randint(340, 500), random.randint(180, 250)
                    vw, vh = random.randint(70, 110), random.randint(50, 80)
                    cv2.rectangle(canvas, (vx - vw//2, vy - vh//2), (vx + vw//2, vy + vh//2), (180, 50, 50), -1)
                    cv2.rectangle(canvas, (vx - vw//3, vy - vh//2 + 5), (vx + vw//3, vy - 5), (40, 40, 40), -1)
                    cv2.circle(canvas, (vx - vw//2 + 8, vy + vh//2 - 10), 4, (0, 0, 220), -1)
                    cv2.circle(canvas, (vx + vw//2 - 8, vy + vh//2 - 10), 4, (0, 0, 220), -1)
                    labels.append(f"10 {vx/640:.6f} {vy/480:.6f} {vw/640:.6f} {vh/480:.6f}")

                # Save image and label
                sample_filename = f"curated_rdd_{split}_{i:03d}"
                img_file = img_dir / f"{sample_filename}.jpg"
                lbl_file = lbl_dir / f"{sample_filename}.txt"

                cv2.imwrite(str(img_file), canvas)
                with open(lbl_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(labels) + "\n")

        print(f"[BestDatasetManager] Generated curated multi-class benchmark dataset in {self.dataset_dir}")

    def import_rdd_dataset(self, source_path: Path) -> bool:
        """
        Imports and maps an external RDD2022 (Road Damage Dataset) folder into
        the standardized 5-class YOLO format.
        """
        if not source_path.exists():
            print(f"[BestDatasetManager] Source directory {source_path} does not exist.")
            return False

        # RDD2022 class mapping:
        # D00 -> 1 (longitudinal crack), D10 -> 1 (transverse crack), D20 -> 1 (alligator crack), D40 -> 0 (pothole)
        rdd_map = {"D00": 1, "D10": 1, "D20": 1, "D40": 0}

        count = 0
        for img_file in source_path.glob("**/*.jpg"):
            lbl_file = img_file.with_suffix(".txt")
            if not lbl_file.exists():
                continue

            target_img = self.train_img / img_file.name
            target_lbl = self.train_lbl / lbl_file.name

            shutil.copy(img_file, target_img)
            with open(lbl_file, "r") as src_f, open(target_lbl, "w") as dst_f:
                for line in src_f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        orig_cls = parts[0]
                        mapped_cls = rdd_map.get(orig_cls, 0 if "40" in orig_cls else 1)
                        dst_f.write(f"{mapped_cls} {' '.join(parts[1:])}\n")
            count += 1

        print(f"[BestDatasetManager] Successfully imported {count} samples from {source_path}")
        return True

    def download_kaggle_dataset(self, force: bool = False) -> Path:
        """Download and normalize the public Kaggle road-hazards dataset."""
        dataset_dir = KAGGLE_DATASET_DIR
        yaml_path = dataset_dir / "data.yaml"
        if yaml_path.exists() and not force:
            return yaml_path

        archive_dir = DATA_DIR / "downloads"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / "pothole-cracks-and-openmanhole.zip"
        raw_dir = archive_dir / "pothole-cracks-and-openmanhole"
        if force and dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        if not archive_path.exists() or force:
            try:
                subprocess.run(
                    ["kaggle", "datasets", "download", "-d", KAGGLE_DATASET_SLUG, "-p", str(archive_dir)],
                    check=True,
                    cwd=str(BASE_DIR)
                )
            except FileNotFoundError as exc:
                raise RuntimeError("Kaggle CLI is not installed. Install it with: pip install kaggle") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError("Kaggle download failed. Configure KAGGLE_API_TOKEN or ~/.kaggle/kaggle.json") from exc

        if not raw_dir.exists() or force:
            raw_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(raw_dir)

        for split_name, candidates in {
            "train": ("train",),
            "val": ("valid", "val", "validation")
        }.items():
            image_out = dataset_dir / split_name / "images"
            label_out = dataset_dir / split_name / "labels"
            image_out.mkdir(parents=True, exist_ok=True)
            label_out.mkdir(parents=True, exist_ok=True)
            split_root = next((raw_dir / name for name in candidates if (raw_dir / name).exists()), None)
            if split_root is None:
                raise RuntimeError(f"Kaggle archive is missing a {split_name}/valid split")
            source_images = split_root / "images"
            source_labels = split_root / "labels"
            if not source_images.exists() or not source_labels.exists():
                raise RuntimeError(f"Kaggle {split_name} split must contain images/ and labels/")
            for image_file in source_images.rglob("*"):
                if image_file.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                    continue
                label_file = source_labels / f"{image_file.stem}.txt"
                if not label_file.exists():
                    continue
                shutil.copy2(image_file, image_out / image_file.name)
                shutil.copy2(label_file, label_out / f"{image_file.stem}.txt")

        dataset_dir.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "path": str(dataset_dir.resolve()).replace("\\", "/"),
                "train": "train/images",
                "val": "val/images",
                "nc": len(KAGGLE_CLASSES),
                "names": KAGGLE_CLASSES
            }, f, sort_keys=False)
        print(f"[BestDatasetManager] Kaggle dataset prepared at {dataset_dir}")
        return yaml_path


# Global singleton instance
global_dataset_manager = BestDatasetManager()
