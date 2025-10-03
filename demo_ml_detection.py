#!/usr/bin/env python3
"""
Complete ML Pipeline Demo with Learning Curves

Shows the full workflow with proper ML metrics:
1. Generate synthetic training data
2. Train model with cross-validation
3. Generate learning curves, OOB error, and performance plots
4. Save all artifacts to gitignored directories
"""

import time
import json
import numpy as np
from pathlib import Path
from datetime import datetime

from ml_mining_detector import (
    MiningDetectorML,
    TrainingSample,
    TrainingDataCollector,
    TimeSeriesFeatures,
)

try:
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.use("Agg")
    from sklearn.model_selection import learning_curve, cross_val_score
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib/sklearn not available")
    exit(1)

print("=" * 70)
print("🚀 COMPLETE ML PIPELINE WITH LEARNING CURVES")
print("=" * 70)
print()

# Setup directories
ARTIFACTS_DIR = Path("training_artifacts")
MODELS_DIR = Path("models")
DATA_DIR = Path("data")
PLOTS_DIR = ARTIFACTS_DIR / "plots"
METRICS_DIR = ARTIFACTS_DIR / "metrics"

for d in [ARTIFACTS_DIR, MODELS_DIR, DATA_DIR, PLOTS_DIR, METRICS_DIR]:
    d.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# =============================================================================
# STEP 1: Generate Synthetic Training Data
# =============================================================================

print("📊 STEP 1: Generating Synthetic Training Data")
print("-" * 70)

training_samples = []
num_mining = 50
num_normal = 50

print(f"  Generating {num_mining} mining samples...")
for i in range(num_mining):
    features = TimeSeriesFeatures(
        cpu_mean=48.0 + np.random.uniform(-5, 5),
        cpu_std=2.0 + np.random.uniform(0, 2),
        cpu_max=55.0 + np.random.uniform(0, 10),
        cpu_min=40.0 + np.random.uniform(0, 5),
        cpu_trend=0.1 + np.random.uniform(-0.2, 0.2),
        cpu_sustained_high=0.0,
        cpu_sustained_moderate=0.95 + np.random.uniform(0, 0.05),
        mem_mean=60.0 + np.random.uniform(-10, 10),
        mem_std=2.0 + np.random.uniform(0, 2),
        mem_trend=0.05 + np.random.uniform(-0.1, 0.1),
        net_rx_rate_mean=1000 + np.random.uniform(0, 500),
        net_tx_rate_mean=500 + np.random.uniform(0, 300),
        net_total_bytes=50000 + np.random.uniform(0, 20000),
        net_variance=100 + np.random.uniform(0, 100),
        block_read_rate=1000 + np.random.uniform(0, 500),
        block_write_rate=500 + np.random.uniform(0, 300),
        execution_duration=30.0 + np.random.uniform(0, 10),
        sample_count=30,
        output_repetition_score=0.85 + np.random.uniform(0, 0.1),
    )
    training_samples.append(
        TrainingSample(
            container_id=f"mining_{i}",
            timestamp=time.time(),
            features=features,
            label="mining",
            metadata={"synthetic": True, "type": "mining"},
        )
    )

print(f"  Generating {num_normal} normal samples...")
for i in range(num_normal):
    features = TimeSeriesFeatures(
        cpu_mean=25.0 + np.random.uniform(0, 40),
        cpu_std=15.0 + np.random.uniform(0, 10),
        cpu_max=80.0 + np.random.uniform(0, 15),
        cpu_min=5.0 + np.random.uniform(0, 10),
        cpu_trend=0.0 + np.random.uniform(-0.5, 0.5),
        cpu_sustained_high=0.1 + np.random.uniform(0, 0.2),
        cpu_sustained_moderate=0.3 + np.random.uniform(0, 0.3),
        mem_mean=80.0 + np.random.uniform(-20, 20),
        mem_std=10.0 + np.random.uniform(0, 5),
        mem_trend=0.0 + np.random.uniform(-0.2, 0.2),
        net_rx_rate_mean=5000 + np.random.uniform(0, 5000),
        net_tx_rate_mean=3000 + np.random.uniform(0, 3000),
        net_total_bytes=200000 + np.random.uniform(0, 100000),
        net_variance=5000 + np.random.uniform(0, 5000),
        block_read_rate=10000 + np.random.uniform(0, 10000),
        block_write_rate=5000 + np.random.uniform(0, 5000),
        execution_duration=20.0 + np.random.uniform(0, 30),
        sample_count=25,
        output_repetition_score=0.15 + np.random.uniform(0, 0.2),
    )
    training_samples.append(
        TrainingSample(
            container_id=f"normal_{i}",
            timestamp=time.time(),
            features=features,
            label="normal",
            metadata={"synthetic": True, "type": "normal"},
        )
    )

print(f"  ✅ Generated {len(training_samples)} samples")
print()

# Prepare data
detector = MiningDetectorML()
X = np.array([detector.features_to_array(s.features) for s in training_samples])
y = np.array([1 if s.label == "mining" else 0 for s in training_samples])

print(f"  Feature matrix shape: {X.shape}")
print(f"  Label distribution: Mining={np.sum(y)}, Normal={len(y)-np.sum(y)}")
print()

# =============================================================================
# STEP 2: Generate Learning Curves
# =============================================================================

print("📈 STEP 2: Generating Learning Curves")
print("-" * 70)

# Learning curve: how accuracy changes with dataset size
print("  Computing learning curves...")
train_sizes, train_scores, val_scores = learning_curve(
    RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
    X,
    y,
    train_sizes=np.linspace(0.1, 1.0, 10),
    cv=5,
    scoring="accuracy",
    n_jobs=-1,
    random_state=42,
)

train_mean = np.mean(train_scores, axis=1)
train_std = np.std(train_scores, axis=1)
val_mean = np.mean(val_scores, axis=1)
val_std = np.std(val_scores, axis=1)

# Plot learning curve
plt.figure(figsize=(10, 6))
plt.plot(
    train_sizes, train_mean, "o-", color="#2196F3", label="Training Score", linewidth=2
)
plt.fill_between(
    train_sizes,
    train_mean - train_std,
    train_mean + train_std,
    alpha=0.2,
    color="#2196F3",
)
plt.plot(
    train_sizes, val_mean, "o-", color="#F44336", label="Validation Score", linewidth=2
)
plt.fill_between(
    train_sizes, val_mean - val_std, val_mean + val_std, alpha=0.2, color="#F44336"
)
plt.xlabel("Training Set Size", fontsize=12)
plt.ylabel("Accuracy Score", fontsize=12)
plt.title("Learning Curve - Accuracy vs Dataset Size", fontsize=14, fontweight="bold")
plt.legend(loc="lower right", fontsize=11)
plt.grid(True, alpha=0.3)
plt.ylim([0.5, 1.05])
plt.tight_layout()
plot_path = PLOTS_DIR / f"learning_curve_{timestamp}.png"
plt.savefig(plot_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Learning curve: {plot_path}")

# =============================================================================
# STEP 3: Cross-Validation Scores
# =============================================================================

print()
print("🎯 STEP 3: Cross-Validation Analysis")
print("-" * 70)

print("  Running 10-fold cross-validation...")
cv_scores = cross_val_score(
    RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
    X,
    y,
    cv=10,
    scoring="accuracy",
    n_jobs=-1,
)

print(f"  CV Accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

# Plot CV scores
plt.figure(figsize=(10, 6))
folds = np.arange(1, len(cv_scores) + 1)
plt.bar(folds, cv_scores, color="steelblue", alpha=0.7, edgecolor="black")
plt.axhline(
    cv_scores.mean(),
    color="red",
    linestyle="--",
    linewidth=2,
    label=f"Mean: {cv_scores.mean():.4f}",
)
plt.xlabel("Fold Number", fontsize=12)
plt.ylabel("Accuracy", fontsize=12)
plt.title("10-Fold Cross-Validation Scores", fontsize=14, fontweight="bold")
plt.legend(fontsize=11)
plt.ylim([0, 1.1])
plt.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
plot_path = PLOTS_DIR / f"cv_scores_{timestamp}.png"
plt.savefig(plot_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ CV scores: {plot_path}")

# =============================================================================
# STEP 4: OOB Error Evolution
# =============================================================================

print()
print("🌲 STEP 4: Out-of-Bag (OOB) Error Analysis")
print("-" * 70)

print("  Training Random Forest with OOB scoring...")
# Train with different numbers of trees to show OOB error evolution
tree_counts = [1, 5, 10, 20, 30, 40, 50, 75, 100]
oob_errors = []

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

for n_trees in tree_counts:
    rf = RandomForestClassifier(
        n_estimators=n_trees,
        max_depth=10,
        random_state=42,
        oob_score=True,
        warm_start=False,
    )
    rf.fit(X_scaled, y)
    oob_errors.append(1 - rf.oob_score_)

# Plot OOB error
plt.figure(figsize=(10, 6))
plt.plot(tree_counts, oob_errors, "o-", color="darkgreen", linewidth=2, markersize=8)
plt.xlabel("Number of Trees", fontsize=12)
plt.ylabel("OOB Error Rate", fontsize=12)
plt.title("Out-of-Bag Error vs Number of Trees", fontsize=14, fontweight="bold")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plot_path = PLOTS_DIR / f"oob_error_{timestamp}.png"
plt.savefig(plot_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ OOB error: {plot_path}")
print(f"  Final OOB Error (100 trees): {oob_errors[-1]:.4f}")

# =============================================================================
# STEP 5: Train Final Model
# =============================================================================

print()
print("🤖 STEP 5: Training Final Model")
print("-" * 70)

start_time = time.time()
detector = MiningDetectorML(
    model_path=MODELS_DIR / "mining_detector.pkl",
    scaler_path=MODELS_DIR / "scaler.pkl",
)
detector.train(training_samples)
training_time = time.time() - start_time

print(f"  ⚡ Training completed in {training_time:.2f} seconds!")

# =============================================================================
# STEP 6: Feature Importance
# =============================================================================

print()
print("📊 STEP 6: Feature Importance Analysis")
print("-" * 70)

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
sorted_idx = np.argsort(importances)

# Plot feature importance
plt.figure(figsize=(10, 8))
plt.barh(range(len(importances)), importances[sorted_idx], color="steelblue")
plt.yticks(range(len(importances)), [feature_names[i] for i in sorted_idx])
plt.xlabel("Importance", fontsize=12)
plt.title("Feature Importance for Mining Detection", fontsize=14, fontweight="bold")
plt.tight_layout()
plot_path = PLOTS_DIR / f"feature_importance_{timestamp}.png"
plt.savefig(plot_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Feature importance: {plot_path}")

# =============================================================================
# STEP 7: Combined Dashboard
# =============================================================================

print()
print("📊 STEP 7: Creating Combined Dashboard")
print("-" * 70)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Plot 1: Learning Curve
ax = axes[0, 0]
ax.plot(train_sizes, train_mean, "o-", color="#2196F3", label="Training", linewidth=2)
ax.fill_between(
    train_sizes,
    train_mean - train_std,
    train_mean + train_std,
    alpha=0.2,
    color="#2196F3",
)
ax.plot(train_sizes, val_mean, "o-", color="#F44336", label="Validation", linewidth=2)
ax.fill_between(
    train_sizes, val_mean - val_std, val_mean + val_std, alpha=0.2, color="#F44336"
)
ax.set_xlabel("Training Set Size", fontsize=11)
ax.set_ylabel("Accuracy", fontsize=11)
ax.set_title("Learning Curve", fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_ylim([0.5, 1.05])

# Plot 2: CV Scores
ax = axes[0, 1]
folds = np.arange(1, len(cv_scores) + 1)
ax.bar(folds, cv_scores, color="steelblue", alpha=0.7, edgecolor="black")
ax.axhline(
    cv_scores.mean(),
    color="red",
    linestyle="--",
    linewidth=2,
    label=f"Mean: {cv_scores.mean():.3f}",
)
ax.set_xlabel("Fold Number", fontsize=11)
ax.set_ylabel("Accuracy", fontsize=11)
ax.set_title("Cross-Validation Scores (10-Fold)", fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
ax.set_ylim([0, 1.1])
ax.grid(True, alpha=0.3, axis="y")

# Plot 3: OOB Error
ax = axes[1, 0]
ax.plot(tree_counts, oob_errors, "o-", color="darkgreen", linewidth=2, markersize=8)
ax.set_xlabel("Number of Trees", fontsize=11)
ax.set_ylabel("OOB Error Rate", fontsize=11)
ax.set_title("Out-of-Bag Error Evolution", fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3)

# Plot 4: Top Features
ax = axes[1, 1]
top_n = 10
top_idx = np.argsort(importances)[::-1][:top_n]
ax.barh(range(top_n), importances[top_idx], color="coral", edgecolor="black")
ax.set_yticks(range(top_n))
ax.set_yticklabels([feature_names[i] for i in top_idx], fontsize=9)
ax.set_xlabel("Importance", fontsize=11)
ax.set_title(f"Top {top_n} Features", fontsize=12, fontweight="bold")
ax.invert_yaxis()

plt.suptitle(
    "ML Mining Detection - Training Dashboard", fontsize=16, fontweight="bold", y=0.995
)
plt.tight_layout()
dashboard_path = PLOTS_DIR / f"training_dashboard_{timestamp}.png"
plt.savefig(dashboard_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  ✅ Combined dashboard: {dashboard_path}")

# =============================================================================
# STEP 8: Save Metrics
# =============================================================================

print()
print("💾 STEP 8: Saving Training Metrics")
print("-" * 70)

metrics = {
    "timestamp": timestamp,
    "training_time_seconds": round(training_time, 3),
    "dataset": {
        "total_samples": len(training_samples),
        "mining_samples": num_mining,
        "normal_samples": num_normal,
    },
    "performance": {
        "cv_accuracy_mean": round(float(cv_scores.mean()), 4),
        "cv_accuracy_std": round(float(cv_scores.std()), 4),
        "cv_scores_all_folds": [round(float(s), 4) for s in cv_scores],
        "final_oob_error": round(float(oob_errors[-1]), 4),
        "final_oob_accuracy": round(float(1 - oob_errors[-1]), 4),
    },
    "learning_curve": {
        "train_sizes": train_sizes.tolist(),
        "train_scores_mean": train_mean.tolist(),
        "val_scores_mean": val_mean.tolist(),
    },
    "model": {
        "type": "RandomForestClassifier",
        "n_estimators": 100,
        "max_depth": 10,
    },
    "top_5_features": [
        {
            "rank": i + 1,
            "name": feature_names[idx],
            "importance": round(float(importances[idx]), 4),
        }
        for i, idx in enumerate(np.argsort(importances)[::-1][:5])
    ],
}

metrics_path = METRICS_DIR / f"training_metrics_full_{timestamp}.json"
with open(metrics_path, "w") as f:
    json.dump(metrics, f, indent=2)
print(f"  ✅ Full metrics: {metrics_path}")

# =============================================================================
# Summary
# =============================================================================

print()
print("=" * 70)
print("✅ COMPLETE PIPELINE WITH LEARNING CURVES DONE!")
print("=" * 70)
print()
print(f"📊 Performance Summary:")
print(f"  CV Accuracy:     {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
print(f"  OOB Accuracy:    {1 - oob_errors[-1]:.4f}")
print(f"  Training Time:   {training_time:.2f}s")
print()
print(f"📁 Plots generated:")
print(f"  1. Learning Curve:      {PLOTS_DIR}/learning_curve_{timestamp}.png")
print(f"  2. CV Scores:           {PLOTS_DIR}/cv_scores_{timestamp}.png")
print(f"  3. OOB Error:           {PLOTS_DIR}/oob_error_{timestamp}.png")
print(f"  4. Feature Importance:  {PLOTS_DIR}/feature_importance_{timestamp}.png")
print(f"  5. Combined Dashboard:  {PLOTS_DIR}/training_dashboard_{timestamp}.png ⭐")
print()
print(f"🎯 Open the dashboard:")
print(f"  open {dashboard_path}")
print()
