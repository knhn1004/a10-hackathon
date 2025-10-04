#!/usr/bin/env python3
"""
PyTorch-based Temporal Sequence Model for Container Anomaly Detection

Uses LSTM to process sequences of Docker inspect stats in real-time.
Similar to audio/video processing but for container metrics.
"""

import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    logging.warning("PyTorch not available. Install with: poetry add torch")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_temporal_detector")

# Configuration
SEQUENCE_LENGTH = 10  # Number of timesteps to look at (10 seconds of 1Hz data)
FEATURE_DIM = 32  # After embedding categorical + numerical features
HIDDEN_DIM = 64
NUM_LAYERS = 2
DROPOUT = 0.2
MODEL_PATH = Path("models/temporal_detector.pth")
SCALER_PATH = Path("models/temporal_scaler.pkl")


@dataclass
class ContainerSequenceFeatures:
    """Features extracted from a sequence of Docker inspect stats."""

    # Numerical features (continuous)
    cpu_percent: List[float]  # Sequence of CPU percentages
    memory_mb: List[float]  # Sequence of memory usage
    memory_percent: List[float]  # Sequence of memory percentage
    network_rx_bytes: List[float]  # Sequence of RX bytes
    network_tx_bytes: List[float]  # Sequence of TX bytes
    block_read_bytes: List[float]  # Sequence of block read
    block_write_bytes: List[float]  # Sequence of block write
    pids: List[int]  # Sequence of process counts

    # Categorical features (need one-hot encoding)
    status: str  # "running", "paused", "exited", etc.
    restart_policy: str  # "no", "always", "on-failure", etc.
    network_mode: str  # "bridge", "host", "none", etc.

    # Derived temporal features
    cpu_rate_of_change: List[float]  # First derivative of CPU
    memory_rate_of_change: List[float]  # First derivative of memory

    # Metadata
    container_id: str
    timestamp: float


class ContainerSequenceDataset(Dataset):
    """PyTorch Dataset for container sequences."""

    def __init__(self, sequences: List[ContainerSequenceFeatures], labels: List[int]):
        """
        Args:
            sequences: List of feature sequences
            labels: List of labels (0=normal, 1=suspicious, 2=mining)
        """
        self.sequences = sequences
        self.labels = labels

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.labels[idx]


class TemporalContainerDetector(nn.Module):
    """
    LSTM-based temporal sequence model for container anomaly detection.

    Architecture:
    1. Feature embedding layer (handles categorical + numerical)
    2. LSTM layers for temporal processing
    3. Attention mechanism for important timesteps
    4. Classification head
    """

    def __init__(
        self,
        numerical_dim: int = 15,  # Number of numerical features per timestep
        categorical_dims: Dict[
            str, int
        ] = None,  # Cardinality of each categorical feature
        embedding_dim: int = 8,
        hidden_dim: int = HIDDEN_DIM,
        num_layers: int = NUM_LAYERS,
        num_classes: int = 3,  # normal, suspicious, mining
        dropout: float = DROPOUT,
    ):
        super().__init__()

        if categorical_dims is None:
            categorical_dims = {
                "status": 5,  # running, paused, exited, dead, restarting
                "restart_policy": 4,  # no, always, on-failure, unless-stopped
                "network_mode": 4,  # bridge, host, none, container
            }

        self.numerical_dim = numerical_dim
        self.categorical_dims = categorical_dims
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # Categorical embeddings
        self.embeddings = nn.ModuleDict(
            {
                name: nn.Embedding(num_categories, embedding_dim)
                for name, num_categories in categorical_dims.items()
            }
        )

        # Feature dimension after combining numerical + embedded categorical
        self.total_feature_dim = numerical_dim + (len(categorical_dims) * embedding_dim)

        # Feature normalization
        self.batch_norm = nn.BatchNorm1d(self.total_feature_dim)

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=self.total_feature_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
            bidirectional=True,  # Use bidirectional for better context
        )

        # Attention mechanism
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 1)
        )

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, numerical_features, categorical_features):
        """
        Args:
            numerical_features: (batch, seq_len, numerical_dim)
            categorical_features: Dict of (batch, seq_len) for each categorical feature

        Returns:
            logits: (batch, num_classes)
            attention_weights: (batch, seq_len) for interpretability
        """
        batch_size, seq_len, _ = numerical_features.shape

        # Embed categorical features
        embedded_cats = []
        for name, embedding_layer in self.embeddings.items():
            # categorical_features[name] is (batch, seq_len)
            embedded = embedding_layer(
                categorical_features[name]
            )  # (batch, seq_len, embedding_dim)
            embedded_cats.append(embedded)

        # Concatenate numerical and embedded categorical features
        if embedded_cats:
            cat_features = torch.cat(
                embedded_cats, dim=-1
            )  # (batch, seq_len, total_cat_embedding_dim)
            combined_features = torch.cat([numerical_features, cat_features], dim=-1)
        else:
            combined_features = numerical_features

        # Normalize features (reshape for batch_norm)
        combined_features = combined_features.reshape(-1, self.total_feature_dim)
        combined_features = self.batch_norm(combined_features)
        combined_features = combined_features.reshape(batch_size, seq_len, -1)

        # LSTM processing
        lstm_out, (hidden, cell) = self.lstm(
            combined_features
        )  # (batch, seq_len, hidden_dim*2)

        # Attention mechanism
        attention_scores = self.attention(lstm_out)  # (batch, seq_len, 1)
        attention_weights = F.softmax(attention_scores, dim=1)  # (batch, seq_len, 1)

        # Weighted sum of LSTM outputs
        context_vector = torch.sum(
            lstm_out * attention_weights, dim=1
        )  # (batch, hidden_dim*2)

        # Classification
        logits = self.classifier(context_vector)  # (batch, num_classes)

        return logits, attention_weights.squeeze(-1)


class TemporalDetectorInference:
    """
    Real-time inference engine for temporal container detection.
    Collects sequences and makes predictions.
    """

    def __init__(self, model_path: Path = MODEL_PATH, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = None
        self.categorical_encoders = {}

        # Initialize categorical encoders
        self._init_categorical_encoders()

        # Load model if available
        if model_path.exists():
            self.load_model(model_path)
        else:
            logger.warning(f"No model found at {model_path}. Will use default model.")
            self.model = TemporalContainerDetector().to(self.device)
            self.model.eval()

    def _init_categorical_encoders(self):
        """Initialize categorical feature encoders."""
        self.categorical_encoders = {
            "status": {
                "created": 0,
                "running": 1,
                "paused": 2,
                "exited": 3,
                "dead": 4,
            },
            "restart_policy": {
                "no": 0,
                "always": 1,
                "on-failure": 2,
                "unless-stopped": 3,
            },
            "network_mode": {
                "bridge": 0,
                "host": 1,
                "none": 2,
                "container": 3,
            },
        }

    def encode_categorical(self, feature_name: str, value: str) -> int:
        """Encode categorical feature to integer."""
        encoder = self.categorical_encoders.get(feature_name, {})
        # Return 0 for unknown values
        return encoder.get(value.lower(), 0)

    def extract_features_from_stats(
        self, stats_sequence: List[Dict]
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Extract features from a sequence of Docker stats.

        Args:
            stats_sequence: List of Docker stats dicts (from container.stats())

        Returns:
            numerical_features: (1, seq_len, numerical_dim) tensor
            categorical_features: Dict of (1, seq_len) tensors
        """
        # No padding - caller must provide exactly SEQUENCE_LENGTH samples
        # Padding creates artificial data that doesn't represent real execution
        if len(stats_sequence) < SEQUENCE_LENGTH:
            raise ValueError(
                f"Insufficient samples: got {len(stats_sequence)}, need {SEQUENCE_LENGTH}. "
                f"Ensure monitor collects enough data before prediction."
            )

        # Truncate if too long (use most recent samples)
        stats_sequence = stats_sequence[-SEQUENCE_LENGTH:]

        numerical_features_list = []
        categorical_features_dict = {
            "status": [],
            "restart_policy": [],
            "network_mode": [],
        }

        prev_cpu = None
        prev_mem = None

        for stats in stats_sequence:
            # Extract numerical features
            cpu_percent = self._safe_get_cpu_percent(stats)
            memory_mb = self._safe_get_memory_mb(stats)
            memory_percent = self._safe_get_memory_percent(stats)
            network_rx, network_tx = self._safe_get_network(stats)
            block_read, block_write = self._safe_get_block_io(stats)
            pids = self._safe_get_pids(stats)

            # Calculate rate of change
            cpu_roc = (cpu_percent - prev_cpu) if prev_cpu is not None else 0.0
            mem_roc = (memory_mb - prev_mem) if prev_mem is not None else 0.0
            prev_cpu = cpu_percent
            prev_mem = memory_mb

            # Compile numerical features (15 features)
            numerical = [
                cpu_percent,
                memory_mb,
                memory_percent,
                network_rx,
                network_tx,
                block_read,
                block_write,
                float(pids),
                cpu_roc,
                mem_roc,
                # Additional derived features
                np.log1p(network_rx + network_tx),  # Log of total network
                np.log1p(block_read + block_write),  # Log of total I/O
                cpu_percent
                / 100.0
                * memory_percent
                / 100.0,  # CPU * Memory interaction
                float(pids) / 100.0,  # Normalized PID count
                1.0 if cpu_percent > 80 else 0.0,  # High CPU indicator
            ]
            numerical_features_list.append(numerical)

            # Extract categorical features (from attrs, not stats)
            # These will be the same across the sequence, but we need them per timestep
            categorical_features_dict["status"].append(
                self.encode_categorical("status", stats.get("status", "running"))
            )
            categorical_features_dict["restart_policy"].append(
                self.encode_categorical("restart_policy", "no")  # Default
            )
            categorical_features_dict["network_mode"].append(
                self.encode_categorical("network_mode", "bridge")  # Default
            )

        # Convert to tensors
        numerical_tensor = torch.FloatTensor(numerical_features_list).unsqueeze(
            0
        )  # (1, seq_len, 15)
        categorical_tensors = {
            name: torch.LongTensor(values).unsqueeze(0)  # (1, seq_len)
            for name, values in categorical_features_dict.items()
        }

        return numerical_tensor, categorical_tensors

    def _safe_get_cpu_percent(self, stats: Dict) -> float:
        """Safely extract CPU percentage from stats."""
        try:
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})

            cpu_delta = cpu_stats.get("cpu_usage", {}).get(
                "total_usage", 0
            ) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get(
                "system_cpu_usage", 0
            )

            online_cpus = cpu_stats.get("online_cpus", 1)

            if system_delta > 0 and cpu_delta > 0:
                return (cpu_delta / system_delta) * online_cpus * 100.0
            return 0.0
        except Exception:
            return 0.0

    def _safe_get_memory_mb(self, stats: Dict) -> float:
        """Safely extract memory MB from stats."""
        try:
            mem_stats = stats.get("memory_stats", {})
            usage = mem_stats.get("usage", 0)
            return usage / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0

    def _safe_get_memory_percent(self, stats: Dict) -> float:
        """Safely extract memory percentage from stats."""
        try:
            mem_stats = stats.get("memory_stats", {})
            usage = mem_stats.get("usage", 0)
            limit = mem_stats.get("limit", 1)
            return (usage / limit) * 100.0 if limit > 0 else 0.0
        except Exception:
            return 0.0

    def _safe_get_network(self, stats: Dict) -> Tuple[float, float]:
        """Safely extract network RX/TX bytes from stats."""
        try:
            networks = stats.get("networks", {})
            rx_bytes = sum(
                net.get("rx_bytes", 0)
                for net in networks.values()
                if isinstance(net, dict)
            )
            tx_bytes = sum(
                net.get("tx_bytes", 0)
                for net in networks.values()
                if isinstance(net, dict)
            )
            return float(rx_bytes), float(tx_bytes)
        except Exception:
            return 0.0, 0.0

    def _safe_get_block_io(self, stats: Dict) -> Tuple[float, float]:
        """Safely extract block I/O from stats."""
        try:
            blkio = stats.get("blkio_stats", {})
            io_bytes = blkio.get("io_service_bytes_recursive", [])
            if not isinstance(io_bytes, list):
                return 0.0, 0.0

            read_bytes = sum(
                item.get("value", 0) for item in io_bytes if item.get("op") == "Read"
            )
            write_bytes = sum(
                item.get("value", 0) for item in io_bytes if item.get("op") == "Write"
            )
            return float(read_bytes), float(write_bytes)
        except Exception:
            return 0.0, 0.0

    def _safe_get_pids(self, stats: Dict) -> int:
        """Safely extract PID count from stats."""
        try:
            return stats.get("pids_stats", {}).get("current", 0)
        except Exception:
            return 0

    def predict(self, stats_sequence: List[Dict]) -> Tuple[str, float, Dict]:
        """
        Make prediction on a sequence of Docker stats.

        Args:
            stats_sequence: List of Docker stats dicts

        Returns:
            prediction: "normal", "suspicious", or "mining"
            confidence: Mining probability (0-1) - we return mining_prob instead of predicted class confidence
            attention_weights: Dict showing which timesteps were most important
        """
        if not PYTORCH_AVAILABLE or self.model is None:
            return (
                "normal",
                0.0,
                {},
            )  # Return 0.0 for mining probability when model unavailable

        # Extract features
        numerical, categorical = self.extract_features_from_stats(stats_sequence)

        # Move to device
        numerical = numerical.to(self.device)
        categorical = {k: v.to(self.device) for k, v in categorical.items()}

        # Inference
        with torch.no_grad():
            logits, attention = self.model(numerical, categorical)
            probabilities = F.softmax(logits, dim=-1)

            predicted_class = torch.argmax(probabilities, dim=-1).item()

            # Handle both 2-class (normal/attack) and 3-class (normal/suspicious/mining) models
            num_classes = probabilities.size(1)

            if num_classes == 2:
                # Binary classification: normal (0) vs mining (1)
                normal_prob = probabilities[0, 0].item()
                mining_prob = probabilities[0, 1].item()

                # Determine prediction based on which class has higher probability
                if predicted_class == 0:
                    prediction = "normal"
                else:
                    prediction = "mining"

                # IMPORTANT: Always return mining_prob as the confidence score
                # This allows the monitor to check if mining_prob >= threshold
                confidence = mining_prob

            elif num_classes == 3:
                # Ternary classification: normal/suspicious/mining
                normal_prob = probabilities[0, 0].item()
                suspicious_prob = probabilities[0, 1].item()
                mining_prob = probabilities[0, 2].item()

                class_labels = ["normal", "suspicious", "mining"]
                prediction = class_labels[predicted_class]

                # IMPORTANT: Always return mining_prob as the confidence score
                # This allows the monitor to check if mining_prob >= threshold
                confidence = mining_prob
            else:
                # Unknown number of classes, default to normal
                prediction = "normal"
                confidence = 0.0  # No mining probability

        # Convert attention to dict
        attention_dict = {
            f"timestep_{i}": float(attention[0, i].item())
            for i in range(attention.size(1))
        }

        return prediction, confidence, attention_dict

    def load_model(self, model_path: Path):
        """Load trained model from file."""
        try:
            checkpoint = torch.load(model_path, map_location=self.device)

            # Extract architecture info from checkpoint
            num_classes = checkpoint.get(
                "num_classes", 3
            )  # Default to 3 for new models
            categorical_dims = checkpoint.get(
                "categorical_dims",
                {
                    "status": 5,
                    "restart_policy": 4,
                    "network_mode": 4,
                },
            )
            numerical_dim = checkpoint.get("numerical_dim", 15)

            # Create model with correct architecture
            self.model = TemporalContainerDetector(
                numerical_dim=numerical_dim,
                categorical_dims=categorical_dims,
                num_classes=num_classes,
            ).to(self.device)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.eval()
            logger.info(
                f"Loaded temporal model from {model_path} (classes={num_classes})"
            )
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.info("Using default initialized model instead")
            self.model = TemporalContainerDetector().to(self.device)
            self.model.eval()

    def save_model(self, model_path: Path):
        """Save model to file."""
        if self.model is None:
            return

        model_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "categorical_encoders": self.categorical_encoders,
            },
            model_path,
        )
        logger.info(f"Saved temporal model to {model_path}")


def get_temporal_detector() -> Optional[TemporalDetectorInference]:
    """Get or create the global temporal detector instance."""
    if not PYTORCH_AVAILABLE:
        logger.warning("PyTorch not available. Temporal detector disabled.")
        return None

    try:
        return TemporalDetectorInference()
    except Exception as e:
        logger.error(f"Failed to initialize temporal detector: {e}")
        return None


if __name__ == "__main__":
    # Test the model
    print("Testing Temporal Container Detector...")

    if not PYTORCH_AVAILABLE:
        print("PyTorch not installed. Install with: poetry add torch")
        exit(1)

    detector = TemporalDetectorInference()

    # Create dummy stats sequence
    dummy_stats = [
        {
            "cpu_stats": {
                "cpu_usage": {"total_usage": i * 1000000},
                "system_cpu_usage": i * 10000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": (i - 1) * 1000000},
                "system_cpu_usage": (i - 1) * 10000000,
            },
            "memory_stats": {"usage": i * 50000000, "limit": 1000000000},
            "networks": {"eth0": {"rx_bytes": i * 1000, "tx_bytes": i * 500}},
            "blkio_stats": {
                "io_service_bytes_recursive": [{"op": "Read", "value": i * 100}]
            },
            "pids_stats": {"current": 10 + i},
            "status": "running",
        }
        for i in range(1, 11)
    ]

    prediction, confidence, attention = detector.predict(dummy_stats)
    print(f"\nPrediction: {prediction}")
    print(f"Confidence: {confidence:.2%}")
    print(f"Attention weights: {list(attention.values())[:3]}...")
    print("\n✅ Temporal detector test passed!")
