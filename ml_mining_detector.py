#!/usr/bin/env python3
"""
Machine Learning-based Crypto Mining Detector

Uses time series classification to detect mining behavior based on
container resource usage patterns (CPU, memory, network, I/O).

Features:
- Time series feature extraction
- Random Forest classifier (can be upgraded to LSTM/Transformer)
- Real-time inference
- Continuous learning from labeled examples
"""

import json
import logging
import pickle
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
from collections import deque

# Optional imports for ML (install if needed)
try:
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, confusion_matrix

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available. Install with: poetry add scikit-learn")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_mining_detector")

# Configuration
WINDOW_SIZE = 30  # Use last 30 seconds of metrics
FEATURE_HISTORY_SIZE = 300  # Keep 5 minutes of history
MODEL_PATH = Path("models/mining_detector.pkl")
SCALER_PATH = Path("models/scaler.pkl")
TRAINING_DATA_PATH = Path("data/training_samples.jsonl")


@dataclass
class TimeSeriesFeatures:
    """Extracted features from time series metrics."""

    # CPU features
    cpu_mean: float
    cpu_std: float
    cpu_max: float
    cpu_min: float
    cpu_trend: float  # Linear trend coefficient
    cpu_sustained_high: float  # Percentage of time > 80%
    cpu_sustained_moderate: float  # Percentage of time > 50%

    # Memory features
    mem_mean: float
    mem_std: float
    mem_trend: float

    # Network features
    net_rx_rate_mean: float
    net_tx_rate_mean: float
    net_total_bytes: float
    net_variance: float

    # Block I/O features
    block_read_rate: float
    block_write_rate: float

    # Temporal features
    execution_duration: float
    sample_count: int

    # Pattern features
    output_repetition_score: float  # How repetitive is the output

    # Label (for training)
    label: Optional[str] = None  # "mining", "normal", "suspicious"


@dataclass
class TrainingSample:
    """A labeled training sample."""

    container_id: str
    timestamp: float
    features: TimeSeriesFeatures
    label: str  # "mining" or "normal"
    metadata: Dict  # Additional info (container name, etc.)


class MiningDetectorML:
    """ML-based mining detector using time series classification."""

    def __init__(self, model_path: Path = MODEL_PATH, scaler_path: Path = SCALER_PATH):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.anomaly_detector: Optional[IsolationForest] = None

        # Load model if exists
        self.load_model()

    def extract_features(
        self, metrics_history: List[Dict], log_text: Optional[str] = None
    ) -> TimeSeriesFeatures:
        """
        Extract features from time series metrics.

        Args:
            metrics_history: List of metric dicts (last N seconds)
            log_text: Optional container log text for pattern analysis

        Returns:
            TimeSeriesFeatures object
        """
        if not metrics_history:
            raise ValueError("Metrics history is empty")

        # Extract CPU time series
        cpu_series = [m["cpu_percent"] for m in metrics_history]
        mem_series = [m["memory_usage_mb"] for m in metrics_history]
        net_rx_series = [m.get("network_rx_rate", 0) for m in metrics_history]
        net_tx_series = [m.get("network_tx_rate", 0) for m in metrics_history]

        # CPU features
        cpu_mean = np.mean(cpu_series)
        cpu_std = np.std(cpu_series)
        cpu_max = np.max(cpu_series)
        cpu_min = np.min(cpu_series)
        cpu_trend = self._calculate_trend(cpu_series)
        cpu_sustained_high = sum(1 for x in cpu_series if x > 80) / len(cpu_series)
        cpu_sustained_moderate = sum(1 for x in cpu_series if x > 50) / len(cpu_series)

        # Memory features
        mem_mean = np.mean(mem_series)
        mem_std = np.std(mem_series)
        mem_trend = self._calculate_trend(mem_series)

        # Network features
        net_rx_mean = np.mean(net_rx_series)
        net_tx_mean = np.mean(net_tx_series)
        total_net = sum(net_rx_series) + sum(net_tx_series)
        net_variance = np.var(net_rx_series) + np.var(net_tx_series)

        # Block I/O features
        block_reads = [m.get("block_read_bytes", 0) for m in metrics_history]
        block_writes = [m.get("block_write_bytes", 0) for m in metrics_history]
        block_read_rate = (
            (block_reads[-1] - block_reads[0]) / len(metrics_history)
            if len(block_reads) > 1
            else 0
        )
        block_write_rate = (
            (block_writes[-1] - block_writes[0]) / len(metrics_history)
            if len(block_writes) > 1
            else 0
        )

        # Temporal features
        execution_duration = (
            metrics_history[-1]["timestamp"] - metrics_history[0]["timestamp"]
        )
        sample_count = len(metrics_history)

        # Pattern features from logs
        output_repetition = 0.0
        if log_text:
            output_repetition = self._calculate_repetition_score(log_text)

        return TimeSeriesFeatures(
            cpu_mean=cpu_mean,
            cpu_std=cpu_std,
            cpu_max=cpu_max,
            cpu_min=cpu_min,
            cpu_trend=cpu_trend,
            cpu_sustained_high=cpu_sustained_high,
            cpu_sustained_moderate=cpu_sustained_moderate,
            mem_mean=mem_mean,
            mem_std=mem_std,
            mem_trend=mem_trend,
            net_rx_rate_mean=net_rx_mean,
            net_tx_rate_mean=net_tx_mean,
            net_total_bytes=total_net,
            net_variance=net_variance,
            block_read_rate=block_read_rate,
            block_write_rate=block_write_rate,
            execution_duration=execution_duration,
            sample_count=sample_count,
            output_repetition_score=output_repetition,
        )

    def _calculate_trend(self, series: List[float]) -> float:
        """Calculate linear trend coefficient."""
        if len(series) < 2:
            return 0.0
        x = np.arange(len(series))
        coeffs = np.polyfit(x, series, 1)
        return coeffs[0]  # Slope

    def _calculate_repetition_score(self, log_text: str) -> float:
        """
        Calculate how repetitive the log output is.
        Higher score = more repetitive (typical of mining).
        """
        lines = [l.strip() for l in log_text.split("\n") if l.strip()]
        if len(lines) < 2:
            return 0.0

        # Count similar consecutive lines
        similar_count = 0
        for i in range(len(lines) - 1):
            words1 = set(lines[i].split())
            words2 = set(lines[i + 1].split())
            if words1 and words2:
                similarity = len(words1 & words2) / len(words1 | words2)
                if similarity > 0.7:
                    similar_count += 1

        return similar_count / len(lines)

    def features_to_array(self, features: TimeSeriesFeatures) -> np.ndarray:
        """Convert features to numpy array for model input."""
        return np.array(
            [
                features.cpu_mean,
                features.cpu_std,
                features.cpu_max,
                features.cpu_min,
                features.cpu_trend,
                features.cpu_sustained_high,
                features.cpu_sustained_moderate,
                features.mem_mean,
                features.mem_std,
                features.mem_trend,
                features.net_rx_rate_mean,
                features.net_tx_rate_mean,
                features.net_total_bytes,
                features.net_variance,
                features.block_read_rate,
                features.block_write_rate,
                features.execution_duration,
                features.sample_count,
                features.output_repetition_score,
            ]
        )

    def predict(self, features: TimeSeriesFeatures) -> Tuple[str, float]:
        """
        Predict if behavior is mining or normal.

        Returns:
            (prediction, confidence) tuple
            prediction: "mining" or "normal"
            confidence: 0.0 to 1.0
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn not installed")

        if self.model is None:
            raise RuntimeError("Model not loaded. Train or load a model first.")

        # Convert to array and scale
        X = self.features_to_array(features).reshape(1, -1)
        if self.scaler:
            X = self.scaler.transform(X)

        # Get prediction and probability
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        confidence = np.max(probabilities)

        label = "mining" if prediction == 1 else "normal"

        # Also check with anomaly detector if available
        if self.anomaly_detector:
            anomaly_score = self.anomaly_detector.predict(X)[0]
            if anomaly_score == -1:  # Anomaly detected
                label = "suspicious"

        return label, confidence

    def train(self, training_data: List[TrainingSample]):
        """
        Train the model on labeled data.

        Args:
            training_data: List of labeled training samples
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn not installed")

        logger.info(f"Training on {len(training_data)} samples...")

        # Convert to arrays
        X = []
        y = []
        for sample in training_data:
            X.append(self.features_to_array(sample.features))
            y.append(1 if sample.label == "mining" else 0)

        X = np.array(X)
        y = np.array(y)

        logger.info(f"Feature matrix shape: {X.shape}")
        logger.info(f"Label distribution: {np.bincount(y)}")

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train Random Forest classifier
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight="balanced",  # Handle imbalanced data
        )
        self.model.fit(X_train_scaled, y_train)

        # Train anomaly detector (unsupervised)
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.anomaly_detector.fit(X_train_scaled)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        logger.info("\nClassification Report:")
        logger.info(
            classification_report(y_test, y_pred, target_names=["normal", "mining"])
        )
        logger.info("\nConfusion Matrix:")
        logger.info(confusion_matrix(y_test, y_pred))

        # Feature importance
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
        importances = self.model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]

        logger.info("\nTop 10 Important Features:")
        for i in sorted_idx[:10]:
            logger.info(f"  {feature_names[i]}: {importances[i]:.4f}")

        # Save model
        self.save_model()

    def save_model(self):
        """Save trained model and scaler to disk."""
        if self.model is None:
            raise RuntimeError("No model to save")

        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.model_path, "wb") as f:
            pickle.dump(
                {"model": self.model, "anomaly_detector": self.anomaly_detector}, f
            )

        with open(self.scaler_path, "wb") as f:
            pickle.dump(self.scaler, f)

        logger.info(f"Model saved to {self.model_path}")

    def load_model(self):
        """Load trained model from disk."""
        if not self.model_path.exists():
            logger.info("No trained model found. Train a model first.")
            return

        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.anomaly_detector = data.get("anomaly_detector")

            with open(self.scaler_path, "rb") as f:
                self.scaler = pickle.load(f)

            logger.info(f"Model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")


class TrainingDataCollector:
    """Collects and stores labeled training data."""

    def __init__(self, data_path: Path = TRAINING_DATA_PATH):
        self.data_path = data_path
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

    def add_sample(
        self,
        container_id: str,
        metrics_history: List[Dict],
        label: str,
        log_text: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Add a labeled training sample.

        Args:
            container_id: Container ID
            metrics_history: List of metrics over time
            label: "mining" or "normal"
            log_text: Optional container logs
            metadata: Additional metadata
        """
        detector = MiningDetectorML()
        features = detector.extract_features(metrics_history, log_text)

        sample = TrainingSample(
            container_id=container_id,
            timestamp=datetime.now().timestamp(),
            features=features,
            label=label,
            metadata=metadata or {},
        )

        # Append to JSONL file
        with open(self.data_path, "a") as f:
            sample_dict = {
                "container_id": sample.container_id,
                "timestamp": sample.timestamp,
                "features": asdict(sample.features),
                "label": sample.label,
                "metadata": sample.metadata,
            }
            f.write(json.dumps(sample_dict) + "\n")

        logger.info(f"Added {label} sample for container {container_id}")

    def load_samples(self) -> List[TrainingSample]:
        """Load all training samples from disk."""
        if not self.data_path.exists():
            return []

        samples = []
        with open(self.data_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)

                # Reconstruct TimeSeriesFeatures
                features_dict = data["features"]
                features_dict.pop("label", None)  # Remove if present
                features = TimeSeriesFeatures(**features_dict)

                sample = TrainingSample(
                    container_id=data["container_id"],
                    timestamp=data["timestamp"],
                    features=features,
                    label=data["label"],
                    metadata=data["metadata"],
                )
                samples.append(sample)

        logger.info(f"Loaded {len(samples)} training samples")
        return samples


if __name__ == "__main__":
    # Example usage
    if not SKLEARN_AVAILABLE:
        print("Please install scikit-learn: poetry add scikit-learn")
        exit(1)

    print("ML Mining Detector")
    print("==================")
    print()
    print("This module provides ML-based mining detection.")
    print("Use training_data_collector.py to collect labeled data,")
    print("then train_mining_model.py to train the model.")
