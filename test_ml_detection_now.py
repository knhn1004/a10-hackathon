#!/usr/bin/env python3
"""Test ML detection by running mining code in a fresh container."""
import asyncio
import httpx
import docker
import time


async def test_mining_detection():
    docker_client = docker.from_env()

    # Create fresh sandbox
    print("🚀 Creating fresh sandbox...")
    container = docker_client.containers.run(
        "code-sandbox:latest",
        name=f"test_mining_{int(time.time())}",
        labels={"sandbox": "1", "sandbox_lang": "python"},
        detach=True,
        ports={"8000/tcp": 0},
        mem_limit="512m",
        cpu_quota=50000,
        cpu_period=100000,
    )

    container_id = container.id[:12]
    print(f"✅ Container created: {container_id}")

    # Wait for container to be ready
    await asyncio.sleep(3)

    # Get the mapped port
    container.reload()
    port = container.attrs["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostPort"]
    print(f"📡 Container port: {port}")

    # Fetch and execute mining code
    print("⛏️  Executing mining code...")
    async with httpx.AsyncClient(timeout=120) as client:
        mining_url = "https://nextcloud-nww8sok.oliverchou.dev/s/NSkSdtweK6fj6KL/download/mining.py"
        code_response = await client.get(mining_url)
        mining_code = code_response.text

        response = await client.post(
            f"http://localhost:{port}/execute", json={"code": mining_code}
        )

    print(f"✅ Mining code started in container")
    print(f"\n⏳ Waiting 40 seconds for ML detection...")
    print(f"   (Needs 30s of data, plus processing time)")

    # Wait for ML to detect
    await asyncio.sleep(40)

    # Check alerts
    async with httpx.AsyncClient() as client:
        alerts = await client.get("http://localhost:8080/api/alerts")
        alerts_data = alerts.json()

        ml_alerts = [
            a for a in alerts_data["alerts"] if a["alert_type"] == "ml_mining_detected"
        ]

        if ml_alerts:
            print(f"\n🎉 SUCCESS! ML DETECTED MINING!")
            for alert in ml_alerts:
                print(f"\n  Container: {alert['name']}")
                print(f"  Confidence: {alert['details']['confidence']*100:.1f}%")
                print(f"  Auto-killed: {alert['auto_killed']}")
                print(f"  Message: {alert['message']}")
        else:
            print(f"\n❌ NO ML ALERTS FOUND")
            print(f"   Total alerts: {len(alerts_data['alerts'])}")

            # Check if container is still running
            try:
                container.reload()
                print(f"   Container status: {container.status}")
                stats = container.stats(stream=False)
                cpu = stats["cpu_stats"]["cpu_usage"]["total_usage"]
                print(f"   Container still exists")
            except:
                print(f"   Container was killed")


if __name__ == "__main__":
    asyncio.run(test_mining_detection())
