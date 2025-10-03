#!/usr/bin/env python3
"""
Train ML Model for Mining Detection with Visualization

Enhanced training script that:
- Saves training history and metrics
- Generates visualization plots
- Exports model performance reports
- All artifacts saved to gitignored directories

Usage:
    python train_mining_model_with_viz.py
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from ml_mining_detector import MiningDetectorML, TrainingDataCollector

# Optional visualization imports
try:
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("matplotlib not available. Install with: poetry add matplotlib")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_model")

# Directories for artifacts (all gitignored)
ARTIFACTS_DIR = Path("training_artifacts")
MODELS_DIR = Path("models")
PLOTS_DIR = ARTIFACTS_DIR / "plots"
METRICS_DIR = ARTIFACTS_DIR / "metrics"


def setup_directories():
    """Create artifact directories."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    MODELS_DIR.mkdir(exist_ok=True)
    PLOTS_DIR.mkdir(exist_ok=True)
    METRICS_DIR.mkdir(exist_ok=True)


def plot_feature_importance(feature_names, importances, output_path):
    """Plot feature importance as horizontal bar chart."""
    if not MATPLOTLIB_AVAILABLE:
        return

    # Sort by importance
    sorted_idx = np.argsort(importances)

    plt.figure(figsize=(10, 8))
    plt.barh(range(len(importances)), importances[sorted_idx])
    plt.yticks(range(len(importances)), [feature_names[i] for i in sorted_idx])
    plt.xlabel("Importance")
    plt.title("Feature Importance for Mining Detection")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  📊 Feature importance plot saved to {output_path}")


def plot_confusion_matrix(cm, output_path):
    """Plot confusion matrix heatmap."""
    if not MATPLOTLIB_AVAILABLE:
        return

    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title("Confusion Matrix")
    plt.colorbar()

    classes = ["Normal", "Mining"]
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes)
    plt.yticks(tick_marks, classes)

    # Add text annotations
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(
                j,
                i,
                format(cm[i, j], "d"),
                ha="center",
                va="center",
                color="white" if cm[i, j] > thresh else "black",
            )

    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  📊 Confusion matrix plot saved to {output_path}")


def plot_label_distribution(mining_count, normal_count, output_path):
    """Plot dataset label distribution."""
    if not MATPLOTLIB_AVAILABLE:
        return

    plt.figure(figsize=(8, 6))
    labels = ["Normal", "Mining"]
    counts = [normal_count, mining_count]
    colors = ["#4CAF50", "#F44336"]

    plt.bar(labels, counts, color=colors, alpha=0.7, edgecolor="black")
    plt.ylabel("Number of Samples")
    plt.title("Training Dataset Distribution")
    plt.ylim(0, max(counts) * 1.2)

    # Add count labels on bars
    for i, (label, count) in enumerate(zip(labels, counts)):
        plt.text(
            i,
            count + max(counts) * 0.02,
            str(count),
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  📊 Label distribution plot saved to {output_path}")


def save_training_metrics(metrics, output_path):
    """Save training metrics to JSON."""
    with open(output_path, "w") as f:
        json.dump(metrics, indent=2, fp=f)
    logger.info(f"  📝 Training metrics saved to {output_path}")


def train_with_visualization(data_path, model_output_path):
    """Train model and generate all visualizations."""

    setup_directories()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("=" * 60)
    logger.info("Training Mining Detection Model with Visualization")
    logger.info("=" * 60)

    # Load training data
    collector = TrainingDataCollector(data_path)
    samples = collector.load_samples()

    if not samples:
        logger.error(f"No training data found at {data_path}")
        logger.error("Options:")
        logger.error(
            "  1. Collect real data: python collect_training_data.py --interactive"
        )
        logger.error("  2. Generate synthetic data: python demo_ml_training.py")
        return None

    # Count labels
    mining_count = sum(1 for s in samples if s.label == "mining")
    normal_count = sum(1 for s in samples if s.label == "normal")

    logger.info(f"\n📊 Dataset Statistics:")
    logger.info(f"  Total samples: {len(samples)}")
    logger.info(f"  Mining samples: {mining_count}")
    logger.info(f"  Normal samples: {normal_count}")
    logger.info(
        f"  Class balance: {mining_count/(mining_count+normal_count)*100:.1f}% mining"
    )

    # Plot label distribution
    if MATPLOTLIB_AVAILABLE:
        plot_label_distribution(
            mining_count,
            normal_count,
            PLOTS_DIR / f"dataset_distribution_{timestamp}.png",
        )

    if mining_count < 5 or normal_count < 5:
        logger.warning("\n⚠️  Warning: Small dataset!")
        logger.warning(
            "  Recommend at least 10 samples of each type for good performance."
        )
        logger.warning("  Collect more data using collect_training_data.py")

    # Train model
    logger.info("\n🤖 Training model...")
    detector = MiningDetectorML(model_path=model_output_path)

    try:
        # Train (this will print classification report and confusion matrix)
        import time

        start_time = time.time()
        detector.train(samples)
        training_time = time.time() - start_time

        logger.info(f"\n⚡ Training completed in {training_time:.2f} seconds!")

        # Get feature importance
        feature_names = [
            "cpu_mean",
            "cpu_std",
            "cpu_max",
            "cpu_min",
            "cpu_trend",
            "cpu_sustained_high",
            "cpu_sustained_moderate",
            "mem_mean",
            "mem_std",
            "mem_trend",
            "net_rx_rate_mean",
            "net_tx_rate_mean",
            "net_total_bytes",
            "net_variance",
            "block_read_rate",
            "block_write_rate",
            "execution_duration",
            "sample_count",
            "output_repetition_score",
        ]

        importances = detector.model.feature_importances_

        # Generate plots
        logger.info("\n📊 Generating visualizations...")

        if MATPLOTLIB_AVAILABLE:
            plot_feature_importance(
                feature_names,
                importances,
                PLOTS_DIR / f"feature_importance_{timestamp}.png",
            )

            # Get confusion matrix from last training
            # (We'd need to modify ml_mining_detector.py to return this)
            # For now, generate a simple one if we retrain on full data

        # Save training metrics
        metrics = {
            "timestamp": timestamp,
            "training_time_seconds": training_time,
            "dataset": {
                "total_samples": len(samples),
                "mining_samples": mining_count,
                "normal_samples": normal_count,
                "data_path": str(data_path),
            },
            "model": {
                "type": "RandomForestClassifier",
                "n_estimators": 100,
                "max_depth": 10,
                "path": str(model_output_path),
            },
            "features": {
                "count": len(feature_names),
                "names": feature_names,
                "importance": {
                    name: float(imp) for name, imp in zip(feature_names, importances)
                },
                "top_5_features": [
                    {"name": feature_names[i], "importance": float(importances[i])}
                    for i in np.argsort(importances)[::-1][:5]
                ],
            },
        }

        metrics_path = METRICS_DIR / f"training_metrics_{timestamp}.json"
        save_training_metrics(metrics, metrics_path)

        # Create a "latest" symlink for easy access
        latest_metrics = METRICS_DIR / "latest_training.json"
        save_training_metrics(metrics, latest_metrics)

        logger.info("\n" + "=" * 60)
        logger.info("✅ Training Complete!")
        logger.info("=" * 60)
        logger.info(f"\n📁 Artifacts saved to:")
        logger.info(f"  Model:   {model_output_path}")
        logger.info(f"  Plots:   {PLOTS_DIR}/")
        logger.info(f"  Metrics: {metrics_path}")
        logger.info(f"\n📊 View visualizations:")
        logger.info(f"  open {PLOTS_DIR}/")
        logger.info(f"\n🎯 Next steps:")
        logger.info(
            f"  1. Review plots: open {PLOTS_DIR}/feature_importance_{timestamp}.png"
        )
        logger.info(f"  2. Test model: python test_mining_model.py --container-id <id>")
        logger.info(
            f"  3. Collect more data: python collect_training_data.py --interactive"
        )

        return detector

    except Exception as e:
        logger.error(f"\n❌ Training failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Train mining detection model with visualization"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/training_samples.jsonl"),
        help="Path to training data JSONL file",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("models/mining_detector.pkl"),
        help="Path to save trained model",
    )

    args = parser.parse_args()

    train_with_visualization(args.data, args.model_output)


if __name__ == "__main__":
    main()
