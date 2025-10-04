#!/usr/bin/env python3
"""
Container Monitoring Service

Collects and aggregates metrics from Docker containers including:
- Resource utilization (CPU, memory, network, disk I/O)
- Container lifecycle events
- Execution statistics
- Health status

Provides historical data storage and real-time updates.
"""

import asyncio
import docker
import httpx
import json
import logging
import math
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Deque
from datetime import datetime
from docker.models.containers import Container

# Random Forest detector DISABLED - using PyTorch LSTM only
ML_DETECTOR_AVAILABLE = False

# PyTorch temporal sequence detector (preferred)
TEMPORAL_DETECTOR_AVAILABLE = False
try:
    from ml_temporal_detector import TemporalDetectorInference, PYTORCH_AVAILABLE

    if PYTORCH_AVAILABLE:
        TEMPORAL_DETECTOR_AVAILABLE = True
        logging.info("✅ PyTorch temporal detector available")
except ImportError:
    logging.info("Temporal detector not available (install PyTorch: poetry add torch)")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monitor")

# Configuration
METRICS_HISTORY_SIZE = 300  # Keep 5 minutes of data (1 sample per second)
COLLECTION_INTERVAL = (
    0.02  # Collect metrics every 20ms (50 samples/sec for ultra-fast code)
)

# Network monitoring thresholds
NETWORK_RATE_WARNING_MBPS = 10  # Warn if > 10 MB/s
NETWORK_RATE_CRITICAL_MBPS = 50  # Critical if > 50 MB/s
NETWORK_TOTAL_WARNING_MB = 100  # Warn if total > 100 MB
NETWORK_TOTAL_CRITICAL_MB = 500  # Critical if total > 500 MB
NETWORK_ANOMALY_THRESHOLD = 5.0  # Flag if rate is 5x above average

# CPU mining detection thresholds
CPU_MINING_THRESHOLD = 85  # Consider mining if CPU > 85% sustained
CPU_MINING_DURATION = 10  # Kill if sustained high CPU for > 10 seconds
CPU_MINING_AUTO_KILL = False  # Disable auto-kill for suspected mining containers

# Moderate CPU mining detection (for stealthy mining)
CPU_MODERATE_THRESHOLD = 50  # Consider potential mining if CPU > 50% sustained
CPU_MODERATE_DURATION = 30  # Kill if sustained moderate CPU for > 30 seconds
CPU_MODERATE_AUTO_KILL = False  # Disable auto-kill for suspected moderate mining

# Pattern-based mining detection
MINING_KEYWORDS = [
    "nonce",
    "hash",
    "mining",
    "miner",
    "blockchain",
    "proof-of-work",
    "difficulty",
    "block",
    "cryptocurrency",
    "bitcoin",
    "ethereum",
    "sha256",
    "scrypt",
]
MINING_PATTERN_THRESHOLD = 3  # Number of keywords to trigger suspicion

# ML mining detection
ML_MINING_CONFIDENCE_THRESHOLD = 0.90  # High threshold to reduce false positives
ML_MINING_AUTO_KILL = False  # Disable auto-kill for ML-detected mining
ML_MINING_MIN_SAMPLES = 8  # Lower for quicker demo-classifications

# Container execution time limits
# API timeout is 30s, so containers running beyond 2 minutes are either:
# - Stuck in infinite loops
# - Doing unauthorized work (mining, etc.)
# - Failed to respond but kept running
MAX_CONTAINER_RUNTIME = 120  # Kill containers running longer than 2 minutes
RUNTIME_CHECK_ENABLED = False  # Disable auto-kill for long-running containers


@dataclass
class ContainerMetrics:
    """Metrics snapshot for a single container."""

    container_id: str
    name: str
    status: str
    created_at: float

    # Resource usage
    cpu_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float

    # Network I/O (bytes)
    network_rx_bytes: int
    network_tx_bytes: int

    # Block I/O (bytes)
    block_read_bytes: int
    block_write_bytes: int

    # Container metadata
    image: str
    labels: Dict[str, str]
    ports: Dict[str, str]

    # Timestamps
    timestamp: float

    # Network rates (bytes/sec) - calculated fields with defaults
    network_rx_rate: float = 0.0
    network_tx_rate: float = 0.0


@dataclass
class NetworkAlert:
    """Network anomaly/alert information."""

    container_id: str
    name: str
    alert_type: str  # "high_rate", "high_total", "anomaly", "crypto_mining_pattern", "cpu_mining", "long_running_container", "ml_mining_detected", "ml_suspicious_detected"
    severity: str  # "warning", "critical", "high"
    timestamp: float
    details: Dict[str, any]
    message: str
    auto_killed: bool = False  # Whether container was automatically terminated


@dataclass
class MLPrediction:
    """ML model prediction record (all predictions, not just alerts)."""

    container_id: str
    name: str
    timestamp: float
    prediction: str  # "mining", "suspicious", "normal"
    confidence: float
    features: Dict[str, float]  # CPU, memory, network metrics
    samples: int  # Number of samples analyzed
    is_final: bool = False  # True for the final prediction, False for intermediate


@dataclass
class MLTimeSeries:
    """Time series of ML predictions for live wave graph."""

    container_id: str
    name: str
    timestamps: List[float]  # Timestamp for each prediction
    predictions: List[str]  # Prediction at each timestep
    confidences: List[float]  # Confidence at each timestep
    features_history: List[Dict[str, float]] = (
        None  # Features at each timestep for tooltips
    )
    attention_weights: Optional[List[float]] = None  # Attention from final prediction


@dataclass
class SystemMetrics:
    """System-wide metrics."""

    total_containers: int
    running_containers: int
    total_cpu_percent: float
    total_memory_mb: float
    timestamp: float


@dataclass
class ContainerCrash:
    """Crash event information."""

    container_id: str
    name: str
    crash_time: float
    exit_code: int
    error: str
    oom_killed: bool
    last_logs: Dict[str, str]  # Now contains stdout, stderr, combined
    last_metrics: Optional[Dict]
    crash_reason: str


class ContainerMonitor:
    """Monitors Docker containers and collects metrics."""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.metrics_history: Dict[str, Deque[ContainerMetrics]] = defaultdict(
            lambda: deque(maxlen=METRICS_HISTORY_SIZE)
        )
        self.system_history: Deque[SystemMetrics] = deque(maxlen=METRICS_HISTORY_SIZE)
        self.previous_stats: Dict[str, Dict] = {}
        self.crash_history: Deque[ContainerCrash] = deque(
            maxlen=100
        )  # Last 100 crashes
        self.network_alerts: Deque[NetworkAlert] = deque(
            maxlen=100
        )  # Last 100 network alerts
        self.ml_predictions: Deque[MLPrediction] = deque(
            maxlen=200
        )  # Last 200 ML predictions (ALL predictions, not just alerts)
        self.ml_time_series: Dict[str, MLTimeSeries] = (
            {}
        )  # Container ID -> time series of predictions (for wave graph)
        self.tracked_containers: Dict[str, Dict] = {}  # Container tracking data
        self.high_cpu_start_times: Dict[str, float] = {}  # Track when high CPU started
        self.moderate_cpu_start_times: Dict[str, float] = (
            {}
        )  # Track when moderate CPU started
        self.container_log_cache: Dict[str, str] = (
            {}
        )  # Cache recent logs for pattern detection

        # Store raw stats sequences for temporal model
        # Need 10 seconds of data at 50Hz = 500 samples
        self.container_stats_sequences: Dict[str, Deque[Dict]] = (
            {}
        )  # Container ID -> sequence of raw stats

        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=5.0)
        self.dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:8080")

        # ML mining detector (Random Forest - optional, keeping for compatibility)
        self.ml_detector: Optional["MiningDetectorML"] = None
        if ML_DETECTOR_AVAILABLE:
            try:
                self.ml_detector = MiningDetectorML()
                if self.ml_detector.model is not None:
                    logger.info(
                        "🤖 ML mining detector (Random Forest) loaded successfully"
                    )
                else:
                    logger.info(
                        "ML mining detector available but no trained model found"
                    )
            except Exception as e:
                logger.warning(f"Failed to load ML mining detector: {e}")
                self.ml_detector = None

        # Temporal detector (PyTorch LSTM - preferred)
        self.temporal_detector: Optional["TemporalDetectorInference"] = None
        if TEMPORAL_DETECTOR_AVAILABLE:
            try:
                self.temporal_detector = TemporalDetectorInference()
                logger.info("🧠 PyTorch temporal detector initialized")
            except Exception as e:
                logger.warning(f"Failed to load temporal detector: {e}")
                self.temporal_detector = None

    async def collect_container_metrics(
        self, container: Container
    ) -> Optional[ContainerMetrics]:
        """Collect metrics from a single container."""
        try:
            # Get container info
            await asyncio.to_thread(container.reload)

            # Skip if container has stopped
            if container.status != "running":
                logger.debug(
                    f"Container {container.id[:12]} is {container.status}, skipping metrics"
                )
                return None

            # Get container stats (non-streaming)
            stats = await asyncio.to_thread(container.stats, stream=False)

            # Validate that stats is a dict
            if not isinstance(stats, dict):
                logger.error(
                    f"Container {container.id[:12]}: stats is not a dict, got {type(stats)}"
                )
                return None

            # Store raw stats for temporal model (keep last 500 = 10 seconds at 50Hz)
            container_id = container.id[:12]
            if container_id not in self.container_stats_sequences:
                self.container_stats_sequences[container_id] = deque(maxlen=500)
            self.container_stats_sequences[container_id].append(stats)

            # Parse CPU usage
            cpu_percent = self._calculate_cpu_percent(container.id, stats)

            # Parse memory usage
            memory_stats = stats.get("memory_stats", {})
            if not isinstance(memory_stats, dict):
                memory_stats = {}
            memory_usage = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 1)
            memory_percent = (
                (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            )

            # Parse network I/O
            networks = stats.get("networks", {})
            # Ensure networks is a dict (it can sometimes be a string or other type)
            if not isinstance(networks, dict):
                logger.debug(
                    f"Container {container.id[:12]}: networks is not a dict, got {type(networks)}: {networks}"
                )
                networks = {}

            network_rx = 0
            network_tx = 0
            for iface_name, iface_data in networks.items():
                if isinstance(iface_data, dict):
                    network_rx += iface_data.get("rx_bytes", 0)
                    network_tx += iface_data.get("tx_bytes", 0)
                else:
                    logger.debug(
                        f"Container {container.id[:12]}: network interface {iface_name} data is not a dict: {type(iface_data)}"
                    )

            # Parse block I/O
            blkio_stats = stats.get("blkio_stats", {})
            if not isinstance(blkio_stats, dict):
                logger.debug(
                    f"Container {container.id[:12]}: blkio_stats is not a dict, got {type(blkio_stats)}"
                )
                blkio_stats = {}
            io_service_bytes = blkio_stats.get("io_service_bytes_recursive", [])
            # Ensure io_service_bytes is iterable (it can be None)
            if io_service_bytes is None or not isinstance(io_service_bytes, list):
                if io_service_bytes is not None:
                    logger.debug(
                        f"Container {container.id[:12]}: io_service_bytes is not a list, got {type(io_service_bytes)}"
                    )
                io_service_bytes = []

            block_read = 0
            block_write = 0
            for entry in io_service_bytes:
                if isinstance(entry, dict):
                    op = entry.get("op")
                    value = entry.get("value", 0)
                    if op == "Read":
                        block_read += value
                    elif op == "Write":
                        block_write += value
                else:
                    logger.debug(
                        f"Container {container.id[:12]}: block I/O entry is not a dict: {type(entry)}"
                    )

            # Get container metadata
            attrs = container.attrs
            if not isinstance(attrs, dict):
                logger.error(
                    f"Container {container.id[:12]}: attrs is not a dict, got {type(attrs)}"
                )
                return None

            config = attrs.get("Config", {})
            if not isinstance(config, dict):
                logger.warning(
                    f"Container {container.id[:12]}: Config is not a dict, got {type(config)}"
                )
                config = {}
            network_settings = attrs.get("NetworkSettings", {})
            if not isinstance(network_settings, dict):
                logger.warning(
                    f"Container {container.id[:12]}: NetworkSettings is not a dict, got {type(network_settings)}"
                )
                network_settings = {}

            # Parse ports
            ports = {}
            port_bindings = network_settings.get("Ports", {})
            if isinstance(port_bindings, dict):
                for container_port, host_bindings in port_bindings.items():
                    if (
                        host_bindings
                        and isinstance(host_bindings, list)
                        and len(host_bindings) > 0
                    ):
                        if isinstance(host_bindings[0], dict):
                            host_port = host_bindings[0].get("HostPort", "")
                            ports[container_port] = host_port

            # Parse creation time
            created_str = attrs.get("Created", "")
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                created_at = created_dt.timestamp()
            except:
                created_at = time.time()

            # Calculate network rates
            current_time = time.time()
            network_rx_rate = 0.0
            network_tx_rate = 0.0

            container_id_short = container.id[:12]
            if container_id_short in self.tracked_containers:
                prev_data = self.tracked_containers[container_id_short]
                # Ensure prev_data is a dict (it might be a string from detect_crashes)
                if isinstance(prev_data, dict):
                    time_delta = current_time - prev_data.get("last_time", current_time)

                    if time_delta > 0:
                        prev_rx = prev_data.get("network_rx_bytes", 0)
                        prev_tx = prev_data.get("network_tx_bytes", 0)

                        network_rx_rate = (network_rx - prev_rx) / time_delta
                        network_tx_rate = (network_tx - prev_tx) / time_delta

            # Update tracked data
            self.tracked_containers[container_id_short] = {
                "last_time": current_time,
                "network_rx_bytes": network_rx,
                "network_tx_bytes": network_tx,
                "container_name": container.name,
            }

            # Ensure labels is a dict
            labels = config.get("Labels", {})
            if not isinstance(labels, dict):
                labels = {}

            return ContainerMetrics(
                container_id=container_id_short,
                name=container.name,
                status=container.status,
                created_at=created_at,
                cpu_percent=cpu_percent,
                memory_usage_mb=memory_usage / (1024 * 1024),
                memory_limit_mb=memory_limit / (1024 * 1024),
                memory_percent=memory_percent,
                network_rx_bytes=network_rx,
                network_tx_bytes=network_tx,
                network_rx_rate=network_rx_rate,
                network_tx_rate=network_tx_rate,
                block_read_bytes=block_read,
                block_write_bytes=block_write,
                image=config.get("Image", "unknown"),
                labels=labels,
                ports=ports,
                timestamp=current_time,
            )

        except json.JSONDecodeError as e:
            # Container likely stopped mid-collection, skip gracefully
            logger.debug(
                f"Container {container.id[:12]} returned invalid JSON (likely stopped): {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Error collecting metrics for {container.id[:12]}: {e}")
            return None

    def _calculate_cpu_percent(self, container_id: str, stats: Dict) -> float:
        """Calculate CPU percentage using Docker stats formula."""
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})

        # Ensure stats are dictionaries
        if not isinstance(cpu_stats, dict):
            cpu_stats = {}
        if not isinstance(precpu_stats, dict):
            precpu_stats = {}

        cpu_usage = cpu_stats.get("cpu_usage", {})
        precpu_usage = precpu_stats.get("cpu_usage", {})

        # Ensure usage stats are dictionaries
        if not isinstance(cpu_usage, dict):
            cpu_usage = {}
        if not isinstance(precpu_usage, dict):
            precpu_usage = {}

        cpu_total = cpu_usage.get("total_usage", 0)
        precpu_total = precpu_usage.get("total_usage", 0)

        system_cpu = cpu_stats.get("system_cpu_usage", 0)
        presystem_cpu = precpu_stats.get("system_cpu_usage", 0)

        online_cpus = cpu_stats.get("online_cpus", 1)

        cpu_delta = cpu_total - precpu_total
        system_delta = system_cpu - presystem_cpu

        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
            return round(cpu_percent, 2)

        return 0.0

    async def detect_crashes(self, containers: List[Container]):
        """Detect container crashes and collect crash information."""
        for container in containers:
            container_id = container.id[:12]
            current_status = container.status

            # Check if container transitioned to exited/dead
            previous_status = self.tracked_containers.get(container_id)

            if previous_status == "running" and current_status in ["exited", "dead"]:
                # Container crashed or was killed
                crash_info = await self._collect_crash_info(container)
                if crash_info:
                    self.crash_history.append(crash_info)
                    logger.error(
                        f"🔥 CONTAINER CRASH DETECTED: {container.name} "
                        f"(Exit: {crash_info.exit_code}, OOM: {crash_info.oom_killed}, "
                        f"Reason: {crash_info.crash_reason})"
                    )

            # Update tracked status
            self.tracked_containers[container_id] = current_status

    def _check_network_anomalies(self, metrics: ContainerMetrics) -> List[NetworkAlert]:
        """
        Check for network anomalies and suspicious patterns.

        Returns list of network alerts if any detected.
        """
        alerts = []

        # Convert bytes/sec to MB/sec for easier reading
        rx_mbps = metrics.network_rx_rate / (1024 * 1024)
        tx_mbps = metrics.network_tx_rate / (1024 * 1024)
        total_rate_mbps = rx_mbps + tx_mbps

        # Total network usage in MB
        total_rx_mb = metrics.network_rx_bytes / (1024 * 1024)
        total_tx_mb = metrics.network_tx_bytes / (1024 * 1024)
        total_network_mb = total_rx_mb + total_tx_mb

        # Check for high network rate (immediate spike)
        if total_rate_mbps > NETWORK_RATE_CRITICAL_MBPS:
            alerts.append(
                NetworkAlert(
                    container_id=metrics.container_id,
                    name=metrics.name,
                    alert_type="high_rate",
                    severity="critical",
                    timestamp=time.time(),
                    details={
                        "rx_mbps": round(rx_mbps, 2),
                        "tx_mbps": round(tx_mbps, 2),
                        "total_rate_mbps": round(total_rate_mbps, 2),
                        "threshold": NETWORK_RATE_CRITICAL_MBPS,
                    },
                    message=(
                        f"🚨 CRITICAL: Extremely high network rate: {total_rate_mbps:.2f} MB/s "
                        f"(RX: {rx_mbps:.2f}, TX: {tx_mbps:.2f}) - "
                        f"Possible crypto mining or data exfiltration!"
                    ),
                )
            )
        elif total_rate_mbps > NETWORK_RATE_WARNING_MBPS:
            alerts.append(
                NetworkAlert(
                    container_id=metrics.container_id,
                    name=metrics.name,
                    alert_type="high_rate",
                    severity="warning",
                    timestamp=time.time(),
                    details={
                        "rx_mbps": round(rx_mbps, 2),
                        "tx_mbps": round(tx_mbps, 2),
                        "total_rate_mbps": round(total_rate_mbps, 2),
                        "threshold": NETWORK_RATE_WARNING_MBPS,
                    },
                    message=(
                        f"⚠️  WARNING: High network rate: {total_rate_mbps:.2f} MB/s "
                        f"(RX: {rx_mbps:.2f}, TX: {tx_mbps:.2f})"
                    ),
                )
            )

        # Check for high total network usage
        if total_network_mb > NETWORK_TOTAL_CRITICAL_MB:
            alerts.append(
                NetworkAlert(
                    container_id=metrics.container_id,
                    name=metrics.name,
                    alert_type="high_total",
                    severity="critical",
                    timestamp=time.time(),
                    details={
                        "total_rx_mb": round(total_rx_mb, 2),
                        "total_tx_mb": round(total_tx_mb, 2),
                        "total_network_mb": round(total_network_mb, 2),
                        "threshold": NETWORK_TOTAL_CRITICAL_MB,
                    },
                    message=(
                        f"🚨 CRITICAL: Total network usage {total_network_mb:.2f} MB "
                        f"(RX: {total_rx_mb:.2f}, TX: {total_tx_mb:.2f}) - "
                        f"Exceeds {NETWORK_TOTAL_CRITICAL_MB} MB limit!"
                    ),
                )
            )
        elif total_network_mb > NETWORK_TOTAL_WARNING_MB:
            alerts.append(
                NetworkAlert(
                    container_id=metrics.container_id,
                    name=metrics.name,
                    alert_type="high_total",
                    severity="warning",
                    timestamp=time.time(),
                    details={
                        "total_rx_mb": round(total_rx_mb, 2),
                        "total_tx_mb": round(total_tx_mb, 2),
                        "total_network_mb": round(total_network_mb, 2),
                        "threshold": NETWORK_TOTAL_WARNING_MB,
                    },
                    message=(
                        f"⚠️  WARNING: Total network usage {total_network_mb:.2f} MB "
                        f"(RX: {total_rx_mb:.2f}, TX: {total_tx_mb:.2f})"
                    ),
                )
            )

        # Check for anomaly based on historical average
        history = self.metrics_history.get(metrics.container_id)
        if history and len(history) > 10:  # Need some history
            # Calculate average rate over last N samples
            recent_rates = [
                m.network_rx_rate + m.network_tx_rate for m in list(history)[-30:]
            ]
            avg_rate = sum(recent_rates) / len(recent_rates) if recent_rates else 0

            current_total_rate = metrics.network_rx_rate + metrics.network_tx_rate

            # Alert if current rate is significantly higher than average
            if (
                avg_rate > 0
                and current_total_rate > avg_rate * NETWORK_ANOMALY_THRESHOLD
            ):
                alerts.append(
                    NetworkAlert(
                        container_id=metrics.container_id,
                        name=metrics.name,
                        alert_type="anomaly",
                        severity="warning",
                        timestamp=time.time(),
                        details={
                            "current_rate_mbps": round(
                                current_total_rate / (1024 * 1024), 2
                            ),
                            "average_rate_mbps": round(avg_rate / (1024 * 1024), 2),
                            "spike_multiplier": round(current_total_rate / avg_rate, 1),
                        },
                        message=(
                            f"⚠️  ANOMALY: Network rate spike detected! "
                            f"Current: {current_total_rate / (1024 * 1024):.2f} MB/s, "
                            f"Average: {avg_rate / (1024 * 1024):.2f} MB/s "
                            f"({current_total_rate / avg_rate:.1f}x above normal)"
                        ),
                    )
                )

        # Crypto mining pattern detection - Network variant (high CPU + high network)
        if metrics.cpu_percent > 80 and total_rate_mbps > 5:
            alerts.append(
                NetworkAlert(
                    container_id=metrics.container_id,
                    name=metrics.name,
                    alert_type="crypto_mining_pattern",
                    severity="critical",
                    timestamp=time.time(),
                    details={
                        "cpu_percent": round(metrics.cpu_percent, 2),
                        "network_rate_mbps": round(total_rate_mbps, 2),
                    },
                    message=(
                        f"🚨 SUSPICIOUS: Potential crypto mining detected! "
                        f"High CPU ({metrics.cpu_percent:.1f}%) + High network ({total_rate_mbps:.2f} MB/s)"
                    ),
                )
            )

        return alerts

    async def _check_log_patterns(
        self, container_id: str, metrics: ContainerMetrics
    ) -> Optional[NetworkAlert]:
        """
        Check container logs for mining-related patterns.

        This detects mining activity by analyzing log output for
        common mining terminology and patterns.

        Returns alert if mining patterns detected, None otherwise.
        """
        try:
            # Get recent logs (last 50 lines)
            container = self.docker_client.containers.get(container_id)
            logs = await asyncio.to_thread(container.logs, tail=50, timestamps=False)
            log_text = logs.decode("utf-8", errors="replace").lower()

            # Cache logs for this container
            self.container_log_cache[container_id] = log_text

            # Count mining-related keywords
            keyword_matches = []
            for keyword in MINING_KEYWORDS:
                if keyword.lower() in log_text:
                    keyword_matches.append(keyword)

            # Check for repetitive patterns (like "Tried X nonces...")
            repetitive_pattern = False
            lines = log_text.split("\n")
            similar_lines = 0
            for i in range(len(lines) - 1):
                if lines[i] and lines[i + 1]:
                    # Check if consecutive lines are very similar
                    line1_words = set(lines[i].split())
                    line2_words = set(lines[i + 1].split())
                    if line1_words and line2_words:
                        similarity = len(line1_words & line2_words) / len(
                            line1_words | line2_words
                        )
                        if similarity > 0.7:  # 70% similarity
                            similar_lines += 1

            if similar_lines > 10:  # Many similar lines = repetitive output
                repetitive_pattern = True

            # If enough keywords or repetitive patterns detected
            if len(keyword_matches) >= MINING_PATTERN_THRESHOLD or repetitive_pattern:
                alert = NetworkAlert(
                    container_id=container_id,
                    name=metrics.name,
                    alert_type="mining_pattern_detected",
                    severity="critical",
                    timestamp=time.time(),
                    details={
                        "keywords_found": keyword_matches,
                        "keyword_count": len(keyword_matches),
                        "repetitive_output": repetitive_pattern,
                        "cpu_percent": round(metrics.cpu_percent, 2),
                    },
                    message=(
                        f"🚨 MINING PATTERN DETECTED: Container {metrics.name} shows mining indicators! "
                        f"Keywords found: {', '.join(keyword_matches[:5])}. "
                        f"{'Repetitive output detected. ' if repetitive_pattern else ''}"
                        f"CPU: {metrics.cpu_percent:.1f}%"
                    ),
                    auto_killed=False,
                )

                # Auto-kill if enabled
                if CPU_MINING_AUTO_KILL:
                    try:
                        await asyncio.to_thread(container.kill)
                        alert.auto_killed = True
                        alert.message += f" 🔪 Container TERMINATED automatically."
                        logger.error(
                            f"🔪 TERMINATED container {metrics.name} for suspected mining (pattern detection)"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to kill mining container {container_id}: {e}"
                        )

                return alert

        except Exception as e:
            logger.debug(f"Error checking log patterns for {container_id}: {e}")

        return None

    async def _check_cpu_mining(
        self, metrics: ContainerMetrics
    ) -> Optional[NetworkAlert]:
        """
        Check for CPU-intensive mining patterns (high sustained CPU usage).

        This detects mining activity like hash calculation loops that don't
        use much network but consume lots of CPU.

        Returns alert if mining pattern detected, None otherwise.
        """
        current_time = time.time()
        container_id = metrics.container_id

        # Check if CPU is above mining threshold
        if metrics.cpu_percent >= CPU_MINING_THRESHOLD:
            # Track start time if not already tracking
            if container_id not in self.high_cpu_start_times:
                self.high_cpu_start_times[container_id] = current_time
                logger.warning(
                    f"⚠️  Container {metrics.name} started high CPU usage: {metrics.cpu_percent:.1f}%"
                )
                return None  # Don't alert yet, just started

            # Check how long it's been running at high CPU
            high_cpu_duration = current_time - self.high_cpu_start_times[container_id]

            # If sustained for too long, it's likely mining
            if high_cpu_duration >= CPU_MINING_DURATION:
                alert = NetworkAlert(
                    container_id=container_id,
                    name=metrics.name,
                    alert_type="cpu_mining",
                    severity="critical",
                    timestamp=current_time,
                    details={
                        "cpu_percent": round(metrics.cpu_percent, 2),
                        "duration_seconds": round(high_cpu_duration, 1),
                        "threshold": CPU_MINING_THRESHOLD,
                    },
                    message=(
                        f"🚨 CRYPTO MINING DETECTED: Container {metrics.name} has sustained "
                        f"{metrics.cpu_percent:.1f}% CPU for {high_cpu_duration:.1f}s - "
                        f"Likely running hash calculations or crypto mining!"
                    ),
                    auto_killed=False,
                )

                # Auto-kill if enabled
                if CPU_MINING_AUTO_KILL:
                    try:
                        container = self.docker_client.containers.get(container_id)
                        await asyncio.to_thread(container.kill)
                        alert.auto_killed = True
                        alert.message += f" 🔪 Container TERMINATED automatically."
                        logger.error(
                            f"🔪 TERMINATED container {metrics.name} for suspected crypto mining"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to kill mining container {container_id}: {e}"
                        )

                # Reset tracking for this container
                if container_id in self.high_cpu_start_times:
                    del self.high_cpu_start_times[container_id]

                return alert
        else:
            # CPU dropped below threshold, reset tracking
            if container_id in self.high_cpu_start_times:
                duration = current_time - self.high_cpu_start_times[container_id]
                logger.info(
                    f"✅ Container {metrics.name} CPU normalized after {duration:.1f}s"
                )
                del self.high_cpu_start_times[container_id]

        return None

    async def _check_ml_mining(
        self, metrics: ContainerMetrics
    ) -> Optional[NetworkAlert]:
        """
        Use PyTorch temporal LSTM model to detect mining patterns in real-time.

        Analyzes sequences of Docker stats to detect temporal anomalies.
        Creates wave graph data showing confidence over time.

        IMPORTANT: Model trained on 10 samples @ 1Hz (10 seconds).
        Monitor collects at 50Hz, so we need 500 samples = 10 seconds.
        We downsample to 10 samples before prediction to match training data.

        Predictions:
        - Intermediate: Made every 10 seconds during execution, is_final=False
        - Final: Made once after container stops, is_final=True (aggregated)

        Returns alert if high-confidence mining detected, None otherwise.
        """
        # Only use temporal detector (Random Forest removed)
        if self.temporal_detector is None:
            logger.warning(f"⚠️ Temporal detector is None for {metrics.name}")
            return None

        logger.info(f"🔬 _check_ml_mining called for {metrics.name}")

        container_id = metrics.container_id
        current_time = time.time()

        # Initialize time series for this container if needed
        if container_id not in self.ml_time_series:
            self.ml_time_series[container_id] = MLTimeSeries(
                container_id=container_id,
                name=metrics.name,
                timestamps=[],
                predictions=[],
                confidences=[],
                features_history=[],
                attention_weights=None,
            )

        # Use stats sequence for temporal model
        stats_sequence = self.container_stats_sequences.get(container_id, deque())
        # Model expects 10 samples. We collect at 50Hz (0.02s interval).
        # Minimum: 10 samples = 0.2 seconds of execution
        MIN_SAMPLES_FOR_PREDICTION = 10
        logger.info(
            f"🔍 Checking temporal for {metrics.name}: {len(stats_sequence)}/{MIN_SAMPLES_FOR_PREDICTION} samples"
        )
        if len(stats_sequence) < MIN_SAMPLES_FOR_PREDICTION:
            logger.info(
                f"⚠️ Not enough samples for {metrics.name}: {len(stats_sequence)}/{MIN_SAMPLES_FOR_PREDICTION}"
            )
            return None

        # Downsample: Take evenly-spaced samples to get 10 samples
        # For fast execution (10-50 samples), take every N-th sample
        # For longer execution (100+ samples), downsample more aggressively
        total_samples = len(stats_sequence)
        if total_samples >= 10:
            # Calculate step size to get exactly 10 samples
            step = total_samples / 10
            downsampled_stats = []
            for i in range(10):
                idx = int(i * step)
                if idx < total_samples:
                    downsampled_stats.append(stats_sequence[idx])

            # Use downsampled stats for prediction
            stats_sequence = downsampled_stats[-10:]  # Last 10 samples
        else:
            # Should never happen (we check for MIN_SAMPLES_FOR_PREDICTION above)
            return None

        try:
            # Run temporal model inference
            logger.info(
                f"🚀 About to call temporal_detector.predict with {len(stats_sequence)} samples"
            )
            prediction, confidence, attention_dict = self.temporal_detector.predict(
                list(stats_sequence)
            )
            logger.info(f"✅ Prediction successful: {prediction} ({confidence:.2%})")

            # Extract current features for tooltip
            current_features = {
                "cpu_percent": round(metrics.cpu_percent, 2),
                "memory_mb": round(metrics.memory_usage_mb, 2),
                "memory_percent": round(metrics.memory_percent, 2),
                "network_rx_rate": round(metrics.network_rx_rate / 1024, 2),  # KB/s
                "network_tx_rate": round(metrics.network_tx_rate / 1024, 2),  # KB/s
                "block_read_mb": round(
                    metrics.block_read_bytes / (1024 * 1024), 2
                ),  # MB
                "block_write_mb": round(
                    metrics.block_write_bytes / (1024 * 1024), 2
                ),  # MB
                "sequence_length": len(stats_sequence),
            }

            # Store intermediate prediction for wave graph
            self.ml_time_series[container_id].timestamps.append(current_time)
            self.ml_time_series[container_id].predictions.append(prediction)
            self.ml_time_series[container_id].confidences.append(confidence)
            self.ml_time_series[container_id].features_history.append(current_features)

            # Log prediction (confidence now represents mining_prob, not predicted class confidence)
            logger.info(
                f"🧠 Temporal LSTM Prediction for {metrics.name}: {prediction} "
                f"(mining_prob={confidence*100:.1f}%) | "
                f"Sequence length={len(stats_sequence)}"
            )

            # Check if this is likely the final prediction (container will be deleted soon)
            # We mark it final if confidence is stable or sequence is long enough
            is_final = (
                len(stats_sequence) >= 10
                or len(self.ml_time_series[container_id].timestamps) >= 10
            )

            # Store prediction record
            ml_prediction_record = MLPrediction(
                container_id=container_id,
                name=metrics.name,
                timestamp=current_time,
                prediction=prediction,
                confidence=confidence,
                features={
                    "sequence_length": len(stats_sequence),
                    "temporal_model": True,
                    "attention_entropy": -sum(
                        w * math.log(w + 1e-10)
                        for w in attention_dict.values()
                        if w > 0
                    ),
                },
                samples=len(stats_sequence),
                is_final=is_final,
            )

            # Store attention weights in time series (for final prediction)
            if is_final:
                self.ml_time_series[container_id].attention_weights = list(
                    attention_dict.values()
                )

            self.ml_predictions.append(ml_prediction_record)

            # Also write to database via API
            asyncio.create_task(self._save_ml_prediction_to_db(ml_prediction_record))

            # Act on high mining probability (confidence now represents mining_prob)
            # Alert if mining probability exceeds threshold, regardless of predicted class
            if confidence >= ML_MINING_CONFIDENCE_THRESHOLD:
                # Determine severity based on how confident the model is about mining
                severity = "critical" if confidence >= 0.95 else "high"
                alert_type = "ml_mining_detected"

                alert = NetworkAlert(
                    container_id=container_id,
                    name=metrics.name,
                    alert_type=alert_type,
                    severity=severity,
                    timestamp=current_time,
                    details={
                        "prediction": prediction,
                        "mining_probability": round(confidence, 4),
                        "sequence_length": len(stats_sequence),
                        "model_type": "PyTorch_LSTM",
                    },
                    message=(
                        f"🧠 Temporal LSTM MINING DETECTED: {metrics.name} "
                        f"(mining_prob: {confidence*100:.1f}%, predicted_class: {prediction}) - "
                        f"Sequence: {len(stats_sequence)} samples"
                    ),
                    auto_killed=False,
                )

                if ML_MINING_AUTO_KILL:
                    try:
                        container = self.docker_client.containers.get(container_id)
                        await asyncio.to_thread(container.kill)
                        alert.auto_killed = True
                        alert.message += " 🔪 Container TERMINATED."
                        logger.error(
                            f"🔪 TERMINATED {metrics.name} - LSTM detected mining (prob: {confidence:.1%})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to kill container: {e}")

                return alert

        except Exception as e:
            logger.error(f"❌ Temporal ML error for {container_id}: {e}", exc_info=True)

        # Random Forest detector removed - temporal only
        return None

    async def _check_long_running_containers(
        self, metrics: ContainerMetrics
    ) -> Optional[NetworkAlert]:
        """
        Check for containers that have been running for too long.

        Containers shouldn't run indefinitely - API timeout is 30s, so
        anything running beyond 2 minutes is likely stuck or doing something malicious.

        Returns alert if container killed, None otherwise.
        """
        if not RUNTIME_CHECK_ENABLED:
            return None

        current_time = time.time()
        container_id = metrics.container_id

        # Calculate how long container has been running
        runtime = current_time - metrics.created_at

        # Check if it's been running too long
        if runtime > MAX_CONTAINER_RUNTIME:
            alert = NetworkAlert(
                container_id=container_id,
                name=metrics.name,
                alert_type="long_running_container",
                severity="critical",
                timestamp=current_time,
                details={
                    "runtime_seconds": round(runtime, 1),
                    "max_runtime": MAX_CONTAINER_RUNTIME,
                    "created_at": metrics.created_at,
                },
                message=(
                    f"⏰ LONG-RUNNING CONTAINER: {metrics.name} has been running for "
                    f"{runtime/60:.1f} minutes (max: {MAX_CONTAINER_RUNTIME/60:.1f} min) - "
                    f"Likely stuck or doing unauthorized work!"
                ),
                auto_killed=False,
            )

            # Auto-kill the container
            try:
                container = self.docker_client.containers.get(container_id)
                await asyncio.to_thread(container.kill)
                alert.auto_killed = True
                alert.message += f" 🔪 Container TERMINATED automatically."
                logger.error(
                    f"🔪 TERMINATED long-running container {metrics.name} "
                    f"(ran for {runtime/60:.1f} minutes)"
                )
            except Exception as e:
                logger.error(
                    f"Failed to kill long-running container {container_id}: {e}"
                )

            return alert

        return None

    async def _collect_crash_info(
        self, container: Container
    ) -> Optional[ContainerCrash]:
        """Collect detailed crash information from a container."""
        try:
            container_id = container.id[:12]

            # Get container inspect data
            inspect_data = container.attrs
            state = inspect_data.get("State", {})

            exit_code = state.get("ExitCode", 0)
            error = state.get("Error", "")
            oom_killed = state.get("OOMKilled", False)

            # Determine crash reason
            crash_reason = self._determine_crash_reason(exit_code, error, oom_killed)

            # Get last logs with separate stdout/stderr (last 100 lines)
            try:
                stdout = await asyncio.to_thread(
                    container.logs, stdout=True, stderr=False, tail=100, timestamps=True
                )
                stderr = await asyncio.to_thread(
                    container.logs, stdout=False, stderr=True, tail=100, timestamps=True
                )
                combined = await asyncio.to_thread(
                    container.logs, stdout=True, stderr=True, tail=100, timestamps=True
                )

                last_logs = {
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "combined": combined.decode("utf-8", errors="replace"),
                }
            except Exception as e:
                last_logs = {"error": f"Failed to retrieve logs: {e}"}

            # Get last metrics
            last_metrics = None
            if container_id in self.metrics_history:
                history = self.metrics_history[container_id]
                if history:
                    last_metrics = asdict(history[-1])

            return ContainerCrash(
                container_id=container_id,
                name=container.name,
                crash_time=time.time(),
                exit_code=exit_code,
                error=error,
                oom_killed=oom_killed,
                last_logs=last_logs,
                last_metrics=last_metrics,
                crash_reason=crash_reason,
            )

        except Exception as e:
            logger.error(f"Error collecting crash info: {e}")
            return None

    def _determine_crash_reason(
        self, exit_code: int, error: str, oom_killed: bool
    ) -> str:
        """Determine the reason for container crash."""
        if oom_killed:
            return "OUT_OF_MEMORY"

        if exit_code == 137:
            # Try to detect fork bomb / PID limit
            if "pids" in error.lower() or "fork" in error.lower():
                return "PROCESS_LIMIT_EXCEEDED"
            return "KILLED_BY_SIGNAL_9"  # Often OOM but not flagged

        if exit_code == 139:
            return "SEGMENTATION_FAULT"

        if exit_code == 143:
            return "TERMINATED_SIGTERM"

        if exit_code == 1:
            return "GENERAL_ERROR"

        if error:
            return f"ERROR: {error}"

        if exit_code != 0:
            return f"NON_ZERO_EXIT_{exit_code}"

        return "STOPPED_NORMALLY"

    async def collect_all_metrics(self) -> SystemMetrics:
        """Collect metrics from all containers."""
        try:
            # Get ONLY running containers (not stopped/exited ones)
            containers = await asyncio.to_thread(
                self.docker_client.containers.list,
                all=False,  # Only running containers
                filters={"label": "sandbox=1"},  # Only monitor sandbox containers
            )

            # Get current container IDs
            current_container_ids = {c.id[:12] for c in containers}

            # Clean up removed containers from history
            self._cleanup_removed_containers(current_container_ids)

            # Detect crashes first
            await self.detect_crashes(containers)

            # Collect metrics from each container
            tasks = [
                self.collect_container_metrics(container) for container in containers
            ]
            metrics_list = await asyncio.gather(*tasks)

            # Store in history and check for network anomalies
            total_cpu = 0.0
            total_memory = 0.0
            running_count = 0

            for metrics in metrics_list:
                if metrics:
                    self.metrics_history[metrics.container_id].append(metrics)
                    total_cpu += metrics.cpu_percent
                    total_memory += metrics.memory_usage_mb
                    if metrics.status == "running":
                        running_count += 1

                    # Check for network anomalies and CPU mining
                    if metrics.status == "running":
                        # DEBUG: Log that we're checking a running container
                        if metrics.cpu_percent > 45:
                            logger.info(
                                f"🔍 Checking running container: {metrics.name} CPU={metrics.cpu_percent:.1f}%"
                            )

                        # Check if container has been running too long
                        runtime_alert = await self._check_long_running_containers(
                            metrics
                        )
                        if runtime_alert:
                            self.network_alerts.append(runtime_alert)
                            logger.error(runtime_alert.message)
                            continue  # Skip other checks if we're killing it

                        # Check network anomalies
                        network_alerts = self._check_network_anomalies(metrics)
                        for alert in network_alerts:
                            # Store alert
                            self.network_alerts.append(alert)
                            # Log alert
                            if alert.severity == "critical":
                                logger.error(alert.message)
                            else:
                                logger.warning(alert.message)

                        # Check CPU mining patterns
                        cpu_mining_alert = await self._check_cpu_mining(metrics)
                        if cpu_mining_alert:
                            self.network_alerts.append(cpu_mining_alert)
                            logger.error(cpu_mining_alert.message)

                        # Collect logs for ML detection
                        await self._check_log_patterns(metrics.container_id, metrics)

                        # Check ML mining detection (PyTorch LSTM only)
                        if self.temporal_detector:
                            ml_alert = await self._check_ml_mining(metrics)
                            if ml_alert:
                                self.network_alerts.append(ml_alert)
                                logger.error(ml_alert.message)
                            elif (
                                metrics.cpu_percent > 45
                            ):  # Debug: log when we check high CPU containers
                                history_len = len(
                                    self.metrics_history.get(metrics.container_id, [])
                                )
                                logger.info(
                                    f"ML check on {metrics.name}: CPU={metrics.cpu_percent:.1f}%, history={history_len}/{ML_MINING_MIN_SAMPLES}"
                                )

            # Create system metrics
            system_metrics = SystemMetrics(
                total_containers=len(containers),
                running_containers=running_count,
                total_cpu_percent=round(total_cpu, 2),
                total_memory_mb=round(total_memory, 2),
                timestamp=time.time(),
            )

            self.system_history.append(system_metrics)

            return system_metrics

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return SystemMetrics(0, 0, 0.0, 0.0, time.time())

    def _cleanup_removed_containers(self, current_container_ids: set):
        """Remove metrics for containers that no longer exist."""
        # Find containers in history that are no longer in Docker
        removed_containers = set(self.metrics_history.keys()) - current_container_ids

        if removed_containers:
            logger.info(
                f"Cleaning up {len(removed_containers)} removed containers from metrics history"
            )
            for container_id in removed_containers:
                # Remove from metrics history
                if container_id in self.metrics_history:
                    del self.metrics_history[container_id]
                    logger.debug(f"Removed metrics for container {container_id}")

                # Remove from tracked containers
                if container_id in self.tracked_containers:
                    del self.tracked_containers[container_id]

                # Remove from ML time series (wave graph data)
                if container_id in self.ml_time_series:
                    del self.ml_time_series[container_id]
                    logger.debug(f"Removed ML time series for container {container_id}")

                # Remove from stats sequences (temporal model data)
                if container_id in self.container_stats_sequences:
                    del self.container_stats_sequences[container_id]
                    logger.debug(f"Removed stats sequence for container {container_id}")

    async def start_monitoring(self):
        """Start continuous monitoring loop."""
        logger.info("Starting container monitoring...")

        while True:
            try:
                system_metrics = await self.collect_all_metrics()
                logger.debug(
                    f"Collected metrics: {system_metrics.running_containers}/"
                    f"{system_metrics.total_containers} containers running, "
                    f"CPU: {system_metrics.total_cpu_percent}%, "
                    f"Memory: {system_metrics.total_memory_mb:.1f}MB"
                )

                await asyncio.sleep(COLLECTION_INTERVAL)

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(COLLECTION_INTERVAL)

    def get_container_metrics(self, container_id: str, limit: int = 60) -> List[Dict]:
        """Get historical metrics for a specific container."""
        history = self.metrics_history.get(container_id, deque())
        recent = list(history)[-limit:]
        return [asdict(m) for m in recent]

    def get_all_container_metrics(self) -> Dict[str, List[Dict]]:
        """Get latest metrics for all containers."""
        result = {}
        for container_id, history in self.metrics_history.items():
            if history:
                result[container_id] = [asdict(history[-1])]
        return result

    def get_system_metrics(self, limit: int = 60) -> List[Dict]:
        """Get historical system metrics."""
        recent = list(self.system_history)[-limit:]
        return [asdict(m) for m in recent]

    def get_container_details(self, container_id: str) -> Optional[Dict]:
        """Get detailed container information using docker inspect."""
        try:
            container = self.docker_client.containers.get(container_id)

            # Get full inspect data
            inspect_data = container.attrs

            # Extract key information
            state = inspect_data.get("State", {})
            config = inspect_data.get("Config", {})
            host_config = inspect_data.get("HostConfig", {})
            network_settings = inspect_data.get("NetworkSettings", {})

            return {
                "id": container.id[:12],
                "name": container.name,
                "image": config.get("Image", ""),
                "status": state.get("Status", ""),
                "created": inspect_data.get("Created", ""),
                "started_at": state.get("StartedAt", ""),
                "finished_at": state.get("FinishedAt", ""),
                "exit_code": state.get("ExitCode", 0),
                "error": state.get("Error", ""),
                "oom_killed": state.get("OOMKilled", False),
                "pid": state.get("Pid", 0),
                # Resource limits
                "memory_limit": host_config.get("Memory", 0),
                "cpu_quota": host_config.get("CpuQuota", 0),
                "cpu_period": host_config.get("CpuPeriod", 0),
                "pids_limit": host_config.get("PidsLimit", 0),
                # Network
                "ip_address": network_settings.get("IPAddress", ""),
                "ports": network_settings.get("Ports", {}),
                "networks": list(network_settings.get("Networks", {}).keys()),
                # Labels and env
                "labels": config.get("Labels", {}),
                "env": config.get("Env", []),
                # Full inspect (for advanced users)
                "full_inspect": inspect_data,
            }

        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container details: {e}")
            return None

    def get_container_logs(
        self, container_id: str, tail: int = 100, separate_streams: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Get container logs with separate stdout and stderr.

        Args:
            container_id: Container ID
            tail: Number of lines to retrieve
            separate_streams: If True, return dict with stdout/stderr separated

        Returns:
            If separate_streams=True: {"stdout": str, "stderr": str, "combined": str}
            If separate_streams=False: Combined logs string (for backward compatibility)
        """
        try:
            container = self.docker_client.containers.get(container_id)

            if separate_streams:
                # Get stdout and stderr separately
                stdout = container.logs(
                    stdout=True, stderr=False, tail=tail, timestamps=True
                )
                stderr = container.logs(
                    stdout=False, stderr=True, tail=tail, timestamps=True
                )
                combined = container.logs(
                    stdout=True, stderr=True, tail=tail, timestamps=True
                )

                return {
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "combined": combined.decode("utf-8", errors="replace"),
                }
            else:
                # Backward compatible - return combined logs
                logs = container.logs(tail=tail, timestamps=True)
                return logs.decode("utf-8", errors="replace")

        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container logs: {e}")
            return None

    def get_crash_history(self, limit: int = 20) -> List[Dict]:
        """Get recent crash history."""
        recent = list(self.crash_history)[-limit:]
        return [asdict(crash) for crash in recent]

    def get_crash_by_container(self, container_id: str) -> Optional[Dict]:
        """Get most recent crash for a specific container."""
        for crash in reversed(self.crash_history):
            if crash.container_id == container_id:
                return asdict(crash)
        return None

    def get_network_alerts(self, limit: int = 50) -> List[Dict]:
        """Get recent network/security alerts."""
        recent = list(self.network_alerts)[-limit:]
        return [asdict(alert) for alert in recent]

    def get_alerts_by_container(self, container_id: str, limit: int = 20) -> List[Dict]:
        """Get alerts for a specific container."""
        container_alerts = [
            alert for alert in self.network_alerts if alert.container_id == container_id
        ]
        recent = container_alerts[-limit:]
        return [asdict(alert) for alert in recent]

    def get_critical_alerts(self, limit: int = 20) -> List[Dict]:
        """Get recent critical alerts only."""
        critical = [
            alert for alert in self.network_alerts if alert.severity == "critical"
        ]
        recent = critical[-limit:]
        return [asdict(alert) for alert in recent]

    def get_ml_predictions(self, limit: int = 100) -> List[Dict]:
        """Get ALL recent ML predictions (not just alerts)."""
        recent = list(self.ml_predictions)[-limit:]
        return [asdict(pred) for pred in recent]

    def get_ml_time_series(self, container_id: Optional[str] = None) -> List[Dict]:
        """Get time series of predictions for wave graph visualization."""
        if container_id:
            series = self.ml_time_series.get(container_id)
            return [asdict(series)] if series else []
        else:
            # Return all active time series
            return [asdict(series) for series in self.ml_time_series.values()]

    async def create_final_ml_prediction(
        self, container_id: str, mcp_request_id: str = None
    ):
        """Create a final aggregated ML prediction for a container after execution completes.

        Args:
            container_id: Container ID to analyze
            mcp_request_id: MCP request ID to link the prediction to
        """
        logger.info(
            f"🎯 create_final_ml_prediction called for container {container_id[:12]}, request: {mcp_request_id}"
        )
        try:
            # Get all metrics for this container
            history = self.metrics_history.get(container_id, [])
            logger.info(f"   📈 Metrics history: {len(history)} samples")

            # Get container info (try from history, fallback to container ID)
            if history:
                container_name = history[-1].name
            else:
                # Try to get container name from Docker
                try:
                    container = await asyncio.to_thread(
                        self.docker_client.containers.get, container_id
                    )
                    container_name = container.name
                except:
                    container_name = container_id

            # Use the most recent prediction from time series if available
            if container_id in self.ml_time_series:
                series = self.ml_time_series[container_id]
                if series.predictions:
                    # Take the most confident prediction from the series
                    max_conf_idx = series.confidences.index(max(series.confidences))
                    prediction = series.predictions[max_conf_idx]
                    confidence = series.confidences[max_conf_idx]
                    features = (
                        series.features_history[max_conf_idx]
                        if max_conf_idx < len(series.features_history)
                        else {}
                    )
                    samples = len(series.predictions)
                else:
                    # No predictions yet, default to normal
                    prediction = "normal"
                    confidence = 0.5
                    features = {}
                    samples = len(history) if history else 0
            else:
                # No time series, default to normal (fast execution, not enough monitoring data)
                logger.info(
                    f"⚠️ No ML predictions yet for {container_id[:12]} (execution was too fast), defaulting to 'normal'"
                )
                prediction = "normal"
                confidence = 0.5
                features = {}
                samples = len(history) if history else 0

            # Calculate duration
            if history and len(history) >= 2:
                duration = history[-1].timestamp - history[0].timestamp
            else:
                duration = 0.1  # Default to 0.1s for fast execution

            features["execution_duration"] = duration
            features["total_samples"] = samples

            # Look up container owner
            logger.info(
                f"🔍 Looking up owner for final prediction: {container_id[:12]}"
            )
            response = await self.http_client.get(
                f"{self.dashboard_url}/api/containers/{container_id}/owner"
            )

            if response.status_code != 200:
                logger.warning(
                    f"❌ Container owner lookup failed: {response.status_code}"
                )
                return

            owner_data = response.json()
            if not owner_data.get("found"):
                logger.warning(f"❌ No owner for container {container_id[:12]}")
                return

            user_id = owner_data.get("user_id")
            logger.info(f"✅ Found owner: {user_id}")

            # Save final prediction to database
            logger.info(
                f"💾 Saving final ML prediction to database: {prediction} ({confidence:.0%}), is_final=True, mcp_request_id={mcp_request_id}"
            )
            save_response = await self.http_client.post(
                f"{self.dashboard_url}/api/ml/predictions/log",
                headers={"X-Monitor-Internal": "true"},
                json={
                    "container_id": container_id,
                    "container_name": container_name,
                    "mcp_request_id": mcp_request_id,
                    "prediction": prediction,
                    "confidence": confidence,
                    "samples": samples,
                    "duration": duration,
                    "features": features,
                    "is_final": True,  # Mark as final prediction
                    "user_id_override": user_id,
                },
            )

            if save_response.status_code == 200:
                logger.info(
                    f"✅ Final ML prediction saved: {prediction} ({confidence:.0%}) for request {mcp_request_id}"
                )
            else:
                logger.error(
                    f"❌ Failed to save final prediction: {save_response.status_code}"
                )

        except Exception as e:
            logger.error(f"❌ Failed to create final ML prediction: {e}", exc_info=True)

    async def _save_ml_prediction_to_db(self, prediction: MLPrediction):
        """Save ML prediction to database via dashboard API."""
        try:
            # Look up container owner
            logger.info(
                f"🔍 Looking up owner for container {prediction.container_id[:12]}"
            )
            response = await self.http_client.get(
                f"{self.dashboard_url}/api/containers/{prediction.container_id}/owner"
            )

            if response.status_code != 200:
                logger.warning(
                    f"❌ Container {prediction.container_id[:12]} owner lookup failed: {response.status_code}"
                )
                return

            owner_data = response.json()
            if not owner_data.get("found"):
                logger.warning(
                    f"❌ No owner for container {prediction.container_id[:12]}"
                )
                return

            user_id = owner_data.get("user_id")
            mcp_request_id = owner_data.get(
                "mcp_request_id"
            )  # Get MCP request ID from container
            logger.info(
                f"✅ Found owner for {prediction.container_id[:12]}: {user_id}, request: {mcp_request_id}"
            )

            # Calculate duration from features
            duration = prediction.features.get("execution_duration", 0.0)

            # Write prediction to database (monitor is trusted internal call)
            save_response = await self.http_client.post(
                f"{self.dashboard_url}/api/ml/predictions/log",
                headers={"X-Monitor-Internal": "true"},
                json={
                    "container_id": prediction.container_id,
                    "container_name": prediction.name,
                    "mcp_request_id": mcp_request_id,  # Link to MCP request
                    "prediction": prediction.prediction,
                    "confidence": prediction.confidence,
                    "samples": prediction.samples,
                    "duration": duration,
                    "features": prediction.features,
                    "is_final": prediction.is_final,  # Use actual is_final value from prediction
                    "user_id_override": user_id,
                },
            )

            if save_response.status_code == 200:
                logger.info(
                    f"📊 ML prediction saved to DB: {prediction.prediction} ({prediction.confidence:.0%}) for user {user_id}"
                )
            else:
                logger.error(
                    f"❌ Failed to save ML prediction: {save_response.status_code} - {save_response.text}"
                )

        except Exception as e:
            logger.error(f"❌ Failed to save ML prediction to DB: {e}", exc_info=True)


# Global monitor instance
_monitor_instance: Optional[ContainerMonitor] = None


def get_monitor() -> ContainerMonitor:
    """Get or create the global monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ContainerMonitor()
    return _monitor_instance


async def main():
    """Run the monitor standalone."""
    monitor = get_monitor()
    await monitor.start_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
