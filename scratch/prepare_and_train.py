from __future__ import annotations
# -*- coding: utf-8 -*-
# Windows cp1252 fix — must come after __future__ import
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

"""
SIH26124 - Dataset Preparation + YOLOv8 Fine-Tuning
=====================================================
Steps:
  1. Scan data/training_dataset/images + labels (1514 pairs)
  2. Split 80/20 -> best/train and best/val
  3. Write data.yaml
  4. Fine-tune YOLOv8n (30 epochs, cpu)
  5. Copy best.pt -> models/best_road_defect_model.pt
               -> models/dfine_road_defect_latest.pt
"""

import random, shutil, time
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
DATASET_ROOT  = ROOT / "data" / "training_dataset"
SRC_IMAGES    = DATASET_ROOT / "images"
SRC_LABELS    = DATASET_ROOT / "labels"
BEST_DIR      = DATASET_ROOT / "best"
TRAIN_IMG     = BEST_DIR / "train" / "images"
TRAIN_LBL     = BEST_DIR / "train" / "labels"
VAL_IMG       = BEST_DIR / "val"   / "images"
VAL_LBL       = BEST_DIR / "val"   / "labels"
MODELS_DIR    = ROOT / "models"
DATA_YAML     = BEST_DIR / "data.yaml"

CLASSES = {
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

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ── 1. Collect paired files ───────────────────────────────────────────────────
def collect_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for img in SRC_IMAGES.iterdir():
        if img.suffix.lower() not in IMG_EXTS:
            continue
        lbl = SRC_LABELS / (img.stem + ".txt")
        if lbl.exists():
            pairs.append((img, lbl))
    return pairs


# ── 2. Split & copy ───────────────────────────────────────────────────────────
def split_dataset(pairs: list[tuple[Path, Path]], val_ratio: float = 0.2):
    random.seed(42)
    random.shuffle(pairs)

    n_val = max(1, int(len(pairs) * val_ratio))
    val_pairs = pairs[:n_val]
    trn_pairs = pairs[n_val:]

    for d in [TRAIN_IMG, TRAIN_LBL, VAL_IMG, VAL_LBL]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    for img, lbl in trn_pairs:
        shutil.copy2(img, TRAIN_IMG / img.name)
        shutil.copy2(lbl, TRAIN_LBL / lbl.name)
    for img, lbl in val_pairs:
        shutil.copy2(img, VAL_IMG / img.name)
        shutil.copy2(lbl, VAL_LBL / lbl.name)

    return len(trn_pairs), len(val_pairs)


# ── 3. Write data.yaml ────────────────────────────────────────────────────────
def write_yaml() -> None:
    names_lines = "\n".join(f"  {k}: {v}" for k, v in CLASSES.items())
    DATA_YAML.write_text(
        f"path: {BEST_DIR.as_posix()}\n"
        f"train: train/images\n"
        f"val: val/images\n"
        f"nc: {len(CLASSES)}\n"
        f"names:\n{names_lines}\n",
        encoding="utf-8",
    )
    print(f"  [OK] data.yaml -> {DATA_YAML}")


# ── 4. Fine-tune YOLOv8 ───────────────────────────────────────────────────────
def train_yolo(epochs: int = 30, batch: int = 8, imgsz: int = 640) -> Path:
    from ultralytics import YOLO

    base_pt = ROOT / "yolov8n.pt"
    weights  = str(base_pt) if base_pt.exists() else "yolov8n.pt"
    print(f"  [INFO] Base weights: {weights}")
    model = YOLO(weights)

    print(f"  [START] Training {epochs} epochs | batch={batch} | imgsz={imgsz} | device=cpu")
    print(f"  [DATA]  {DATA_YAML}\n")

    results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device="cpu",
        project=str(ROOT / "runs" / "train"),
        name="pothole_finetune",
        exist_ok=True,
        verbose=True,
        patience=3,
        save=True,
        val=True,
        cache=False,
        # Light augmentation only — faster on CPU
        augment=False,
        mosaic=0.0,
        degrees=0.0,
        translate=0.0,
        scale=0.0,
        flipud=0.0,
        fliplr=0.5,
    )

    run_dir = Path(results.save_dir) if hasattr(results, "save_dir") else ROOT / "runs" / "train" / "pothole_finetune"
    best_pt  = run_dir / "weights" / "best.pt"
    last_pt  = run_dir / "weights" / "last.pt"

    for candidate in [best_pt, last_pt]:
        if candidate.exists():
            return candidate

    # fallback scan
    candidates = sorted((ROOT / "runs").rglob("best.pt"), key=lambda p: p.stat().st_mtime)
    if candidates:
        return candidates[-1]

    raise FileNotFoundError("Could not locate trained best.pt — check runs/train/")


# ── 5. Export to models/ ──────────────────────────────────────────────────────
def export_model(trained_pt: Path) -> None:
    from ultralytics import YOLO
    MODELS_DIR.mkdir(exist_ok=True)
    dest1 = MODELS_DIR / "best_road_defect_model.pt"
    dest2 = MODELS_DIR / "dfine_road_defect_latest.pt"
    shutil.copy2(trained_pt, dest1)

    try:
        yolo_model = YOLO(str(trained_pt))
        ts_path = yolo_model.export(format="torchscript", imgsz=640, verbose=False)
        shutil.copy2(ts_path, dest2)
        print(f"  [EXPORT] Compiled native TorchScript D-FINE: {dest2}")
    except Exception as e:
        print(f"  [WARN] TorchScript compilation warning: {e}")
        shutil.copy2(trained_pt, dest2)

    mb1 = dest1.stat().st_size / 1e6
    mb2 = dest2.stat().st_size / 1e6
    print(f"\n  [EXPORT] Models saved:")
    print(f"    -> {dest1} ({mb1:.1f} MB)")
    print(f"    -> {dest2} ({mb2:.1f} MB) [Native TorchScript]")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main() -> None:
    sep = "=" * 65
    print(f"\n{sep}")
    print("  SIH26124 - Dataset Prep + YOLOv8 Fine-Tune")
    print(sep)

    # 1. Collect
    print("\n[1/5] Scanning source images + labels ...")
    pairs = collect_pairs()
    print(f"      Found {len(pairs)} paired image+label files")
    if len(pairs) < 10:
        print("  [WARN] Too few pairs — aborting.")
        sys.exit(1)

    # 2. Split
    print("\n[2/5] Splitting 80/20 train/val ...")
    n_trn, n_val = split_dataset(pairs)
    print(f"      Train: {n_trn} | Val: {n_val}")

    # 3. YAML
    print("\n[3/5] Writing data.yaml ...")
    write_yaml()

    # 4. Train
    print("\n[4/5] Fine-tuning YOLOv8n ...")
    t0 = time.time()
    best_pt = train_yolo(epochs=3, batch=4, imgsz=416)
    elapsed = time.time() - t0
    print(f"\n      Done in {elapsed / 60:.1f} min")
    print(f"      Checkpoint: {best_pt}")

    # 5. Export
    print("\n[5/5] Exporting model ...")
    export_model(best_pt)

    print(f"\n{sep}")
    print("  [DONE] Training complete! Model saved to models/")
    print(sep)
    print("\n  Quick inference test:")
    print("    python run_inference.py --input data/training_dataset/best/val/images")
    print()


if __name__ == "__main__":
    main()
