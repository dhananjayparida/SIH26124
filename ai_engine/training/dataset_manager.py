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
    1: "crack",
    2: "no_zebracrossing",
    3: "zebra_crossing",
    4: "vehicle"
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

        # Check existing samples
        existing_train = list(self.train_img.glob("*.jpg"))
        if len(existing_train) < 10:
            print("[BestDatasetManager] Initializing benchmark dataset samples...")
            self._generate_curated_benchmark_samples()

        # Write data.yaml configuration
        yaml_path = self.dataset_dir / "data.yaml"
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
        covering all 5 classes across varied road surfaces.
        """
        if cv2 is None:
            return

        sample_frame_path = SAMPLES_DIR / "pothole_sample_frame.jpg"
        real_road_base = None
        if sample_frame_path.exists():
            real_road_base = cv2.imread(str(sample_frame_path))

        random.seed(42)

        # Generate train and val sets
        for split, count in [("train", 16), ("val", 6)]:
            img_dir = self.dataset_dir / split / "images"
            lbl_dir = self.dataset_dir / split / "labels"

            for i in range(count):
                # 1. Canvas: Realistic road asphalt
                if real_road_base is not None and random.random() > 0.4:
                    canvas = cv2.resize(real_road_base, (640, 480)).copy()
                    # Apply slight brightness/contrast variations
                    alpha = 0.8 + random.random() * 0.4
                    canvas = cv2.convertScaleAbs(canvas, alpha=alpha, beta=random.randint(-15, 15))
                else:
                    # Synthetic asphalt texture
                    canvas = np.full((480, 640, 3), random.randint(55, 75), dtype=np.uint8)
                    noise = np.random.normal(0, 10, canvas.shape).astype(np.uint8)
                    canvas = cv2.add(canvas, noise)
                    # Add lane markings
                    cv2.line(canvas, (320, 180), (320, 480), (200, 200, 200), 4)

                labels: List[str] = []

                # Add Class 0: Pothole
                px, py = random.randint(180, 420), random.randint(240, 380)
                pr_x, pr_y = random.randint(35, 65), random.randint(22, 42)
                # Outer rim & dark crater
                cv2.ellipse(canvas, (px, py), (pr_x + 4, pr_y + 3), 0, 0, 360, (25, 25, 25), 2)
                cv2.ellipse(canvas, (px, py), (pr_x, pr_y), 0, 0, 360, (12, 12, 12), -1)
                # Normalize bbox: x_center, y_center, w, h
                labels.append(f"0 {px/640:.6f} {py/480:.6f} {(pr_x*2)/640:.6f} {(pr_y*2)/480:.6f}")

                # Add Class 1: Crack (RDD2022 Longitudinal / Transverse Crack)
                if i % 2 == 0:
                    cx1, cy1 = random.randint(80, 260), random.randint(200, 340)
                    cx2, cy2 = cx1 + random.randint(40, 90), cy1 + random.randint(20, 60)
                    cv2.line(canvas, (cx1, cy1), (cx2, cy2), (18, 18, 18), 3)
                    cw = abs(cx2 - cx1) + 12
                    ch = abs(cy2 - cy1) + 12
                    c_center_x = (cx1 + cx2) / 2.0
                    c_center_y = (cy1 + cy2) / 2.0
                    labels.append(f"1 {c_center_x/640:.6f} {c_center_y/480:.6f} {cw/640:.6f} {ch/480:.6f}")

                # Add Class 2 & 3: Zebra Crossing (3) vs Missing Zebra Crossing (2)
                if i % 3 == 0:
                    # Intact Zebra Crossing: alternating white stripes
                    zx, zy = 320, 400
                    zw, zh = 260, 60
                    for s in range(5):
                        sx = zx - 110 + s * 50
                        cv2.rectangle(canvas, (sx, zy - 25), (sx + 28, zy + 25), (230, 230, 230), -1)
                    labels.append(f"3 {zx/640:.6f} {zy/480:.6f} {zw/640:.6f} {zh/480:.6f}")
                elif i % 3 == 1:
                    # Missing Zebra Crossing: pedestrian zone with faded / absent stripes
                    zx, zy = 320, 400
                    zw, zh = 250, 60
                    # Faded worn out marking traces
                    for s in range(4):
                        sx = zx - 90 + s * 55
                        cv2.rectangle(canvas, (sx, zy - 20), (sx + 20, zy + 20), (70, 70, 70), 1)
                    # Hazard box warning for missing crosswalk
                    labels.append(f"2 {zx/640:.6f} {zy/480:.6f} {zw/640:.6f} {zh/480:.6f}")

                # Add Class 4: Vehicle (Car or Bus ahead)
                if i % 2 == 1:
                    vx, vy = random.randint(340, 520), random.randint(180, 260)
                    vw, vh = random.randint(70, 110), random.randint(50, 80)
                    # Simplified vehicle silhouette
                    cv2.rectangle(canvas, (vx - vw//2, vy - vh//2), (vx + vw//2, vy + vh//2), (180, 50, 50), -1)
                    # Vehicle windshield / roof
                    cv2.rectangle(canvas, (vx - vw//3, vy - vh//2 + 5), (vx + vw//3, vy - 5), (40, 40, 40), -1)
                    # Tail lights
                    cv2.circle(canvas, (vx - vw//2 + 8, vy + vh//2 - 10), 4, (0, 0, 220), -1)
                    cv2.circle(canvas, (vx + vw//2 - 8, vy + vh//2 - 10), 4, (0, 0, 220), -1)
                    labels.append(f"4 {vx/640:.6f} {vy/480:.6f} {vw/640:.6f} {vh/480:.6f}")

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
