"""
CLI Training Script for Road Defect & Urban Safety Perception (SIH26124).
Usage:
    python ai_engine/training/train_model.py --epochs 5 --batch-size 8 --dataset best
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine.training.trainer import global_model_trainer
from ai_engine.training.dataset_manager import BEST_CLASSES, KAGGLE_CLASSES


def main():
    parser = argparse.ArgumentParser(description="Train / Fine-Tune Road Defect & Safety Perception Model")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs (default: 5)")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size (default: 8)")
    parser.add_argument("--img-size", type=int, default=640, help="Input image resolution (default: 640)")
    parser.add_argument("--dataset", type=str, default="best", choices=["best", "kaggle"], help="Dataset to train on")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu' or '0' for CUDA GPU)")
    args = parser.parse_args()

    print("\n==================================================================")
    print("  🚀 SIH26124 ROAD DEFECT & TRAFFIC PERCEPTION MODEL TRAINER")
    print("==================================================================")
    target_classes = KAGGLE_CLASSES if args.dataset == "kaggle" else BEST_CLASSES
    print(f"  • Target Classes: {list(target_classes.values())}")
    print(f"  • Dataset:        {args.dataset}")
    print(f"  • Epochs:         {args.epochs}")
    print(f"  • Batch Size:     {args.batch_size}")
    print(f"  • Img Resolution: {args.img_size}")
    print(f"  • Device:         {args.device}")
    print("==================================================================\n")

    result = global_model_trainer.train(
        epochs=args.epochs,
        batch_size=args.batch_size,
        img_size=args.img_size,
        dataset_type=args.dataset,
        device=args.device
    )

    if result.get("status") == "success":
        print("\n==================================================================")
        print("  ✅ MODEL TRAINING & EXPORT COMPLETE!")
        print("==================================================================")
        print(f"  📁 Model Checkpoint: {result.get('model_path')}")
        metrics = result.get("metrics", {})
        print(f"  🎯 Precision:        {metrics.get('precision', 0):.3f}")
        print(f"  🎯 Recall:           {metrics.get('recall', 0):.3f}")
        print(f"  🎯 mAP@50:           {metrics.get('mAP_50', 0):.3f}")
        print(f"  🎯 mAP@50-95:        {metrics.get('mAP_50_95', 0):.3f}")
        print(f"  🏷️  Classes:          {metrics.get('classes_trained', [])}")
        print("==================================================================\n")
    else:
        print(f"\n❌ Training failed: {result.get('message')}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
