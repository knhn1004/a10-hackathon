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


@dataclass
class SystemMetrics:
    """System-wide metrics."""
    total_containers: int
    running_containers: int
    total_cpu_percent: float
    total_memory_mb: float
    timestamp: float


class ContainerMonitor:
    """Monitors Docker containers and collects metrics."""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.metrics_history: Dict[str, Deque[ContainerMetrics]] = defaultdict(
            lambda: deque(maxlen=METRICS_HISTORY_SIZE)
        )
        self.system_history: Deque[SystemMetrics] = deque(maxlen=METRICS_HISTORY_SIZE)
        self.previous_stats: Dict[str, Dict] = {}
        
    async def collect_container_metrics(self, container: Container) -> Optional[ContainerMetrics]:
        """Collect metrics from a single container."""
        try:
            # Get container info
            await asyncio.to_thread(container.reload)
            
            # Get container stats (non-streaming)
            stats = await asyncio.to_thread(container.stats, stream=False)
            
            # Parse CPU usage
            cpu_percent = self._calculate_cpu_percent(container.id, stats)
            
            # Parse memory usage
            memory_stats = stats.get('memory_stats', {})
            memory_usage = memory_stats.get('usage', 0)
            memory_limit = memory_stats.get('limit', 1)
            memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            
            # Parse network I/O
            networks = stats.get('networks', {})
            network_rx = sum(net.get('rx_bytes', 0) for net in networks.values())
            network_tx = sum(net.get('tx_bytes', 0) for net in networks.values())
            
            # Parse block I/O
            blkio_stats = stats.get('blkio_stats', {})
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
            block_read = sum(
                entry.get('value', 0) 
                for entry in io_service_bytes 
                if entry.get('op') == 'Read'
            )
            block_write = sum(
                entry.get('value', 0) 
                for entry in io_service_bytes 
                if entry.get('op') == 'Write'
            )
            
            # Get container metadata
            attrs = container.attrs
            config = attrs.get('Config', {})
            network_settings = attrs.get('NetworkSettings', {})
            
            # Parse ports
            ports = {}
            port_bindings = network_settings.get('Ports', {})
            for container_port, host_bindings in port_bindings.items():
                if host_bindings:
                    host_port = host_bindings[0].get('HostPort', '')
                    ports[container_port] = host_port
            
            # Parse creation time
            created_str = attrs.get('Created', '')
            try:
                created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                created_at = created_dt.timestamp()
            except:
                created_at = time.time()
            
            return ContainerMetrics(
                container_id=container.id[:12],
                name=container.name,
                status=container.status,
                created_at=created_at,
                cpu_percent=cpu_percent,
                memory_usage_mb=memory_usage / (1024 * 1024),
                memory_limit_mb=memory_limit / (1024 * 1024),
                memory_percent=memory_percent,
                network_rx_bytes=network_rx,
                network_tx_bytes=network_tx,
                block_read_bytes=block_read,
                block_write_bytes=block_write,
                image=config.get('Image', 'unknown'),
                labels=config.get('Labels', {}),
                ports=ports,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Error collecting metrics for {container.id[:12]}: {e}")
            return None
    
    def _calculate_cpu_percent(self, container_id: str, stats: Dict) -> float:
        """Calculate CPU percentage using Docker stats formula."""
        cpu_stats = stats.get('cpu_stats', {})
        precpu_stats = stats.get('precpu_stats', {})
        
        cpu_usage = cpu_stats.get('cpu_usage', {})
        precpu_usage = precpu_stats.get('cpu_usage', {})
        
        cpu_total = cpu_usage.get('total_usage', 0)
        precpu_total = precpu_usage.get('total_usage', 0)
        
        system_cpu = cpu_stats.get('system_cpu_usage', 0)
        presystem_cpu = precpu_stats.get('system_cpu_usage', 0)
        
        online_cpus = cpu_stats.get('online_cpus', 1)
        
        cpu_delta = cpu_total - precpu_total
        system_delta = system_cpu - presystem_cpu
        
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
            return round(cpu_percent, 2)
        
        return 0.0
    
    async def collect_all_metrics(self) -> SystemMetrics:
        """Collect metrics from all containers."""
        try:
            # Get all containers (including stopped ones)
            containers = await asyncio.to_thread(
                self.docker_client.containers.list,
                all=True,
                filters={'label': 'sandbox=1'}  # Only monitor sandbox containers
            )
            
            # Collect metrics from each container
            tasks = [
                self.collect_container_metrics(container) 
                for container in containers
            ]
            metrics_list = await asyncio.gather(*tasks)
            
            # Store in history
            total_cpu = 0.0
            total_memory = 0.0
            running_count = 0
            
            for metrics in metrics_list:
                if metrics:
                    self.metrics_history[metrics.container_id].append(metrics)
                    total_cpu += metrics.cpu_percent
                    total_memory += metrics.memory_usage_mb
                    if metrics.status == 'running':
                        running_count += 1
            
            # Create system metrics
            system_metrics = SystemMetrics(
                total_containers=len(containers),
                running_containers=running_count,
                total_cpu_percent=round(total_cpu, 2),
                total_memory_mb=round(total_memory, 2),
                timestamp=time.time()
            )
            
            self.system_history.append(system_metrics)
            
            return system_metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return SystemMetrics(0, 0, 0.0, 0.0, time.time())
    
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
            state = inspect_data.get('State', {})
            config = inspect_data.get('Config', {})
            host_config = inspect_data.get('HostConfig', {})
            network_settings = inspect_data.get('NetworkSettings', {})
            
            return {
                'id': container.id[:12],
                'name': container.name,
                'image': config.get('Image', ''),
                'status': state.get('Status', ''),
                'created': inspect_data.get('Created', ''),
                'started_at': state.get('StartedAt', ''),
                'finished_at': state.get('FinishedAt', ''),
                'exit_code': state.get('ExitCode', 0),
                'error': state.get('Error', ''),
                'pid': state.get('Pid', 0),
                
                # Resource limits
                'memory_limit': host_config.get('Memory', 0),
                'cpu_quota': host_config.get('CpuQuota', 0),
                'cpu_period': host_config.get('CpuPeriod', 0),
                
                # Network
                'ip_address': network_settings.get('IPAddress', ''),
                'ports': network_settings.get('Ports', {}),
                'networks': list(network_settings.get('Networks', {}).keys()),
                
                # Labels and env
                'labels': config.get('Labels', {}),
                'env': config.get('Env', []),
                
                # Full inspect (for advanced users)
                'full_inspect': inspect_data
            }
            
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container details: {e}")
            return None


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


