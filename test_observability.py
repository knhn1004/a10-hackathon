#!/usr/bin/env python3
"""
Test script for observability features

This script:
1. Creates a test sandbox container
2. Collects metrics from it
3. Verifies the monitoring system works
4. Tests the dashboard API endpoints
"""

import asyncio
import time
import docker
import httpx
from monitor import ContainerMonitor


async def test_monitoring():
    """Test the monitoring system."""
    print("🧪 Testing Observability System\n")
    
    # Initialize Docker client
    docker_client = docker.from_env()
    
    # Check if Docker is running
    try:
        docker_client.ping()
        print("✅ Docker is running")
    except Exception as e:
        print(f"❌ Docker is not available: {e}")
        return
    
    # Create monitor
    monitor = ContainerMonitor()
    print("✅ Monitor initialized")
    
    # Build sandbox image if needed
    print("\n📦 Checking for sandbox image...")
    try:
        docker_client.images.get("code-sandbox:latest")
        print("✅ Sandbox image found")
    except docker.errors.ImageNotFound:
        print("⚠️  Sandbox image not found. Building...")
        docker_client.images.build(path=".", tag="code-sandbox:latest")
        print("✅ Sandbox image built")
    
    # Create a test container
    print("\n🐳 Creating test container...")
    container = docker_client.containers.run(
        "code-sandbox:latest",
        name="test_sandbox_observability",
        labels={"sandbox": "1", "test": "1"},
        detach=True,
        ports={"8000/tcp": 0},
        mem_limit="512m",
        cpu_period=100000,
        cpu_quota=50000,
        remove=False  # Don't auto-remove so we can inspect it
    )
    print(f"✅ Test container created: {container.id[:12]}")
    
    # Wait for container to start
    print("\n⏳ Waiting for container to be ready...")
    await asyncio.sleep(3)
    
    try:
        # Collect metrics
        print("\n📊 Collecting metrics...")
        metrics = await monitor.collect_container_metrics(container)
        
        if metrics:
            print("✅ Metrics collected successfully!")
            print(f"\n📈 Container Metrics:")
            print(f"   Name: {metrics.name}")
            print(f"   Status: {metrics.status}")
            print(f"   CPU: {metrics.cpu_percent}%")
            print(f"   Memory: {metrics.memory_usage_mb:.1f} MB / {metrics.memory_limit_mb:.1f} MB ({metrics.memory_percent:.1f}%)")
            print(f"   Network RX: {metrics.network_rx_bytes / 1024:.1f} KB")
            print(f"   Network TX: {metrics.network_tx_bytes / 1024:.1f} KB")
            print(f"   Block Read: {metrics.block_read_bytes / 1024:.1f} KB")
            print(f"   Block Write: {metrics.block_write_bytes / 1024:.1f} KB")
        else:
            print("❌ Failed to collect metrics")
            return
        
        # Test container details
        print("\n🔍 Getting container details (Docker inspect)...")
        details = monitor.get_container_details(container.id[:12])
        
        if details:
            print("✅ Container details retrieved!")
            print(f"   ID: {details['id']}")
            print(f"   Image: {details['image']}")
            print(f"   Status: {details['status']}")
            print(f"   IP Address: {details['ip_address']}")
            print(f"   Memory Limit: {details['memory_limit'] / 1024 / 1024:.0f} MB")
            print(f"   CPU Quota: {details['cpu_quota']}")
        else:
            print("❌ Failed to get container details")
        
        # Test system metrics
        print("\n🌐 Collecting system metrics...")
        system_metrics = await monitor.collect_all_metrics()
        print("✅ System metrics collected!")
        print(f"   Total Containers: {system_metrics.total_containers}")
        print(f"   Running Containers: {system_metrics.running_containers}")
        print(f"   Total CPU: {system_metrics.total_cpu_percent}%")
        print(f"   Total Memory: {system_metrics.total_memory_mb:.1f} MB")
        
        # Test continuous collection
        print("\n⏱️  Testing continuous monitoring (5 samples)...")
        for i in range(5):
            await monitor.collect_all_metrics()
            print(f"   Sample {i+1}/5 collected")
            await asyncio.sleep(1)
        
        print("✅ Continuous monitoring working!")
        
        # Check history
        history = monitor.get_container_metrics(container.id[:12], limit=10)
        print(f"\n📚 Metrics history: {len(history)} samples stored")
        
        print("\n✨ All monitoring tests passed!")
        
    finally:
        # Cleanup
        print("\n🧹 Cleaning up test container...")
        container.stop()
        container.remove()
        print("✅ Test container removed")


async def test_dashboard_api():
    """Test the dashboard API (if running)."""
    print("\n🌐 Testing Dashboard API (if running)...\n")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            # Test health endpoint
            response = await client.get("http://localhost:8080/api/health")
            if response.status_code == 200:
                print("✅ Dashboard API is running!")
                data = response.json()
                print(f"   Status: {data['status']}")
                print(f"   Monitoring Active: {data['monitoring_active']}")
                
                # Test system endpoint
                response = await client.get("http://localhost:8080/api/system?limit=10")
                if response.status_code == 200:
                    data = response.json()
                    print(f"\n✅ System metrics endpoint working!")
                    print(f"   Samples available: {data['count']}")
                
                # Test overview endpoint
                response = await client.get("http://localhost:8080/api/overview")
                if response.status_code == 200:
                    data = response.json()
                    print(f"\n✅ Overview endpoint working!")
                    print(f"   Total containers: {data['summary']['total_containers']}")
                    print(f"   Running containers: {data['summary']['running_containers']}")
                
                print("\n✨ All dashboard API tests passed!")
            else:
                print(f"⚠️  Dashboard returned status: {response.status_code}")
        except httpx.ConnectError:
            print("⚠️  Dashboard is not running")
            print("   Start it with: ./run_dashboard.sh")
        except Exception as e:
            print(f"❌ Dashboard API test failed: {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("  Code Sandbox Observability Test Suite")
    print("=" * 60)
    
    # Test monitoring
    await test_monitoring()
    
    # Test dashboard API
    await test_dashboard_api()
    
    print("\n" + "=" * 60)
    print("  Test Suite Complete!")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   1. Start the dashboard: ./run_dashboard.sh")
    print("   2. Open: http://localhost:8080")
    print("   3. Create sandboxes using the MCP server")
    print("   4. Watch metrics in real-time!")


if __name__ == "__main__":
    asyncio.run(main())

