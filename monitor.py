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
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Deque
from datetime import datetime

import docker
from docker.models.containers import Container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monitor")

# Configuration
METRICS_HISTORY_SIZE = 300  # Keep 5 minutes of data (1 sample per second)
COLLECTION_INTERVAL = 1.0  # Collect metrics every second

# Network monitoring thresholds
NETWORK_RATE_WARNING_MBPS = 10  # Warn if > 10 MB/s
NETWORK_RATE_CRITICAL_MBPS = 50  # Critical if > 50 MB/s
NETWORK_TOTAL_WARNING_MB = 100  # Warn if total > 100 MB
NETWORK_TOTAL_CRITICAL_MB = 500  # Critical if total > 500 MB
NETWORK_ANOMALY_THRESHOLD = 5.0  # Flag if rate is 5x above average

# CPU mining detection thresholds
CPU_MINING_THRESHOLD = 85  # Consider mining if CPU > 85% sustained
CPU_MINING_DURATION = 10  # Kill if sustained high CPU for > 10 seconds
CPU_MINING_AUTO_KILL = True  # Automatically kill suspected mining containers


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
    alert_type: str  # "high_rate", "high_total", "anomaly", "crypto_mining_pattern", "cpu_mining"
    severity: str  # "warning", "critical"
    timestamp: float
    details: Dict[str, any]
    message: str
    auto_killed: bool = False  # Whether container was automatically terminated


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
        self.tracked_containers: Dict[str, Dict] = {}  # Container tracking data
        self.high_cpu_start_times: Dict[str, float] = {}  # Track when high CPU started

    async def collect_container_metrics(
        self, container: Container
    ) -> Optional[ContainerMetrics]:
        """Collect metrics from a single container."""
        try:
            # Get container info
            await asyncio.to_thread(container.reload)

            # Get container stats (non-streaming)
            stats = await asyncio.to_thread(container.stats, stream=False)

            # Parse CPU usage
            cpu_percent = self._calculate_cpu_percent(container.id, stats)

            # Parse memory usage
            memory_stats = stats.get("memory_stats", {})
            memory_usage = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 1)
            memory_percent = (
                (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            )

            # Parse network I/O
            networks = stats.get("networks", {})
            network_rx = sum(net.get("rx_bytes", 0) for net in networks.values())
            network_tx = sum(net.get("tx_bytes", 0) for net in networks.values())

            # Parse block I/O
            blkio_stats = stats.get("blkio_stats", {})
            io_service_bytes = blkio_stats.get("io_service_bytes_recursive", [])
            block_read = sum(
                entry.get("value", 0)
                for entry in io_service_bytes
                if entry.get("op") == "Read"
            )
            block_write = sum(
                entry.get("value", 0)
                for entry in io_service_bytes
                if entry.get("op") == "Write"
            )

            # Get container metadata
            attrs = container.attrs
            config = attrs.get("Config", {})
            network_settings = attrs.get("NetworkSettings", {})

            # Parse ports
            ports = {}
            port_bindings = network_settings.get("Ports", {})
            for container_port, host_bindings in port_bindings.items():
                if host_bindings:
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
                labels=config.get("Labels", {}),
                ports=ports,
                timestamp=current_time,
            )

        except Exception as e:
            logger.error(f"Error collecting metrics for {container.id[:12]}: {e}")
            return None

    def _calculate_cpu_percent(self, container_id: str, stats: Dict) -> float:
        """Calculate CPU percentage using Docker stats formula."""
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})

        cpu_usage = cpu_stats.get("cpu_usage", {})
        precpu_usage = precpu_stats.get("cpu_usage", {})

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
            # Get all containers (including stopped ones)
            containers = await asyncio.to_thread(
                self.docker_client.containers.list,
                all=True,
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
