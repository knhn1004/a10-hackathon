#!/usr/bin/env python3
"""
Training Data Collection Script

Helps collect labeled examples of mining vs normal container behavior.
Run this while executing different types of code to build a training dataset.

Usage:
    # Collect normal behavior
    python collect_training_data.py --container-id abc123 --label normal --duration 60

    # Collect mining behavior
    python collect_training_data.py --container-id def456 --label mining --duration 30
"""

import argparse
import asyncio
import time
import logging
from pathlib import Path

from monitor import get_monitor
from ml_mining_detector import TrainingDataCollector, MiningDetectorML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data_collector")


async def collect_sample(
    container_id: str, label: str, duration: int, description: str = ""
):
    """
    Collect metrics for a container over a duration and save as labeled sample.

    Args:
        container_id: Container ID to monitor
        label: "mining" or "normal"
        duration: How many seconds to collect data
        description: Optional description of what the container is doing
    """
    monitor = get_monitor()
    collector = TrainingDataCollector()

    logger.info(f"Collecting {label} sample for container {container_id}")
    logger.info(f"Duration: {duration} seconds")
    logger.info(f"Description: {description}")

    # Wait for metrics to accumulate
    logger.info("Waiting for metrics to accumulate...")
    await asyncio.sleep(duration)

    # Get metrics history
    metrics_history = monitor.get_container_metrics(container_id, limit=duration)

    if not metrics_history:
        logger.error(f"No metrics found for container {container_id}")
        return

    logger.info(f"Collected {len(metrics_history)} metric samples")

    # Get logs for pattern analysis
    logs = monitor.get_container_logs(container_id, tail=100)
    log_text = (
        logs if isinstance(logs, str) else logs.get("combined", "") if logs else ""
    )

    # Extract features and preview
    detector = MiningDetectorML()
    features = detector.extract_features(metrics_history, log_text)

    logger.info("\n=== Feature Preview ===")
    logger.info(f"CPU Mean: {features.cpu_mean:.2f}%")
    logger.info(f"CPU Sustained High (>80%): {features.cpu_sustained_high*100:.1f}%")
    logger.info(
        f"CPU Sustained Moderate (>50%): {features.cpu_sustained_moderate*100:.1f}%"
    )
    logger.info(f"Memory Mean: {features.mem_mean:.2f} MB")
    logger.info(f"Network RX Rate: {features.net_rx_rate_mean:.2f} bytes/s")
    logger.info(f"Output Repetition Score: {features.output_repetition_score:.3f}")
    logger.info("=====================\n")

    # Save sample
    metadata = {
        "description": description,
        "duration": duration,
    }

    collector.add_sample(
        container_id=container_id,
        metrics_history=metrics_history,
        label=label,
        log_text=log_text,
        metadata=metadata,
    )

    logger.info(f"✅ Sample saved successfully!")


async def collect_interactive():
    """Interactive mode - guide user through collection."""
    print("\n" + "=" * 60)
    print("Training Data Collection - Interactive Mode")
    print("=" * 60 + "\n")

    monitor = get_monitor()

    # Show available containers
    print("Available containers:")
    all_metrics = monitor.get_all_container_metrics()

    if not all_metrics:
        print("No containers currently running.")
        print("Create a sandbox and run some code first.")
        return

    for container_id, metrics in all_metrics.items():
        if metrics:
            m = metrics[0]
            print(f"  - {container_id}: {m['name']} (CPU: {m['cpu_percent']:.1f}%)")

    print()
    container_id = input("Enter container ID: ").strip()

    if container_id not in all_metrics:
        print(f"Container {container_id} not found!")
        return

    print("\nLabel options:")
    print("  1. mining   - Container is running crypto mining code")
    print("  2. normal   - Container is running legitimate computation")

    label_choice = input("Enter label (1 or 2): ").strip()
    label = "mining" if label_choice == "1" else "normal"

    duration = int(
        input("Collection duration in seconds (recommended 30-60): ").strip() or "30"
    )
    description = input("Description of what code is running (optional): ").strip()

    await collect_sample(container_id, label, duration, description)


def main():
    parser = argparse.ArgumentParser(
        description="Collect labeled training data for mining detection"
    )
    parser.add_argument("--container-id", type=str, help="Container ID to monitor")
    parser.add_argument(
        "--label", choices=["mining", "normal"], help="Label for this sample"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Collection duration in seconds"
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Description of the container activity",
    )
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    if args.interactive or not (args.container_id and args.label):
        asyncio.run(collect_interactive())
    else:
        asyncio.run(
            collect_sample(
                args.container_id, args.label, args.duration, args.description
            )
        )


if __name__ == "__main__":
    main()
