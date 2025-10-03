#!/usr/bin/env python3
"""
Test the trained mining detection model on live containers.

Usage:
    # Test on a specific container
    python test_mining_model.py --container-id abc123

    # Test on all running containers
    python test_mining_model.py --all
"""

import argparse
import asyncio
import logging

from monitor import get_monitor
from ml_mining_detector import MiningDetectorML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_model")


async def test_container(container_id: str, duration: int = 30):
    """Test model prediction on a container."""
    monitor = get_monitor()
    detector = MiningDetectorML()

    if detector.model is None:
        logger.error("No trained model found!")
        logger.error("Train a model first: python train_mining_model.py")
        return

    logger.info(f"Testing on container {container_id}")
    logger.info(f"Collecting {duration} seconds of metrics...")

    await asyncio.sleep(duration)

    # Get metrics
    metrics_history = monitor.get_container_metrics(container_id, limit=duration)

    if not metrics_history:
        logger.error(f"No metrics found for container {container_id}")
        return

    # Get logs
    logs = monitor.get_container_logs(container_id, tail=100)
    log_text = (
        logs if isinstance(logs, str) else logs.get("combined", "") if logs else ""
    )

    # Extract features
    features = detector.extract_features(metrics_history, log_text)

    # Predict
    prediction, confidence = detector.predict(features)

    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("PREDICTION RESULTS")
    logger.info("=" * 60)
    logger.info(f"Container: {container_id}")
    logger.info(f"Prediction: {prediction.upper()}")
    logger.info(f"Confidence: {confidence*100:.1f}%")
    logger.info("")
    logger.info("Key Metrics:")
    logger.info(f"  CPU Mean: {features.cpu_mean:.2f}%")
    logger.info(f"  CPU Sustained High: {features.cpu_sustained_high*100:.1f}%")
    logger.info(f"  CPU Sustained Moderate: {features.cpu_sustained_moderate*100:.1f}%")
    logger.info(f"  Memory Mean: {features.mem_mean:.2f} MB")
    logger.info(f"  Network Activity: {features.net_total_bytes:.0f} bytes")
    logger.info(f"  Output Repetition: {features.output_repetition_score:.3f}")
    logger.info("=" * 60 + "\n")

    if prediction == "mining" and confidence > 0.8:
        logger.warning("🚨 HIGH CONFIDENCE MINING DETECTED!")
    elif prediction == "suspicious":
        logger.warning("⚠️  Suspicious activity detected (anomaly)")


async def test_all_containers(duration: int = 30):
    """Test all running containers."""
    monitor = get_monitor()
    all_metrics = monitor.get_all_container_metrics()

    if not all_metrics:
        logger.info("No containers currently running")
        return

    logger.info(f"Found {len(all_metrics)} containers")

    for container_id in all_metrics.keys():
        await test_container(container_id, duration)


def main():
    parser = argparse.ArgumentParser(description="Test mining detection model")
    parser.add_argument("--container-id", type=str, help="Container ID to test")
    parser.add_argument(
        "--all", action="store_true", help="Test all running containers"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Collection duration in seconds"
    )

    args = parser.parse_args()

    if args.all:
        asyncio.run(test_all_containers(args.duration))
    elif args.container_id:
        asyncio.run(test_container(args.container_id, args.duration))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
