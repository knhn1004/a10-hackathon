#!/usr/bin/env python3
"""
Test script for the trained temporal detector model.
Tests various workload patterns to understand model behavior.
"""

import numpy as np
from ml_temporal_detector import get_temporal_detector

def create_stats_sequence(cpu_base, cpu_variance, mem_base, mem_variance, 
                         net_base, net_variance, pids_base, pids_variance, 
                         sequence_length=10, trend=0):
    """Create a realistic stats sequence with specified parameters."""
    stats = []
    
    for i in range(sequence_length):
        # Add some trend and noise
        cpu_usage = max(0, min(100, cpu_base + trend * i + np.random.normal(0, cpu_variance)))
        mem_usage = max(0, mem_base + trend * i * 1000000 + np.random.normal(0, mem_variance * 1000000))
        net_rx = max(0, net_base + np.random.poisson(net_variance))
        net_tx = max(0, net_base + np.random.poisson(net_variance))
        pids = max(1, int(pids_base + np.random.normal(0, pids_variance)))
        
        stats.append({
            'cpu_stats': {
                'cpu_usage': {'total_usage': int(cpu_usage * 1000000)},
                'system_cpu_usage': int((i + 1) * 10000000),
                'online_cpus': 4,
            },
            'precpu_stats': {
                'cpu_usage': {'total_usage': int(cpu_usage * 1000000) - 1000000},
                'system_cpu_usage': int(i * 10000000),
            },
            'memory_stats': {'usage': int(mem_usage), 'limit': 1000000000},
            'networks': {'eth0': {'rx_bytes': int(net_rx), 'tx_bytes': int(net_tx)}},
            'blkio_stats': {
                'io_service_bytes_recursive': [
                    {'op': 'Read', 'value': int(np.random.poisson(1000))},
                    {'op': 'Write', 'value': int(np.random.poisson(500))}
                ]
            },
            'pids_stats': {'current': pids},
            'status': 'running',
        })
    
    return stats

def test_workload_patterns():
    """Test various workload patterns."""
    print("🧪 Testing Trained Temporal Detector with Various Workload Patterns")
    print("=" * 70)
    
    detector = get_temporal_detector()
    if not detector:
        print("❌ Failed to initialize temporal detector")
        return
    
    # Test patterns
    test_cases = [
        {
            'name': 'Idle System',
            'params': {'cpu_base': 5, 'cpu_variance': 2, 'mem_base': 100000000, 
                      'mem_variance': 10000000, 'net_base': 100, 'net_variance': 50,
                      'pids_base': 50, 'pids_variance': 5, 'trend': 0}
        },
        {
            'name': 'Normal Web Server',
            'params': {'cpu_base': 25, 'cpu_variance': 10, 'mem_base': 200000000,
                      'mem_variance': 20000000, 'net_base': 1000, 'net_variance': 500,
                      'pids_base': 80, 'pids_variance': 10, 'trend': 0}
        },
        {
            'name': 'CPU Intensive Task',
            'params': {'cpu_base': 60, 'cpu_variance': 15, 'mem_base': 300000000,
                      'mem_variance': 30000000, 'net_base': 500, 'net_variance': 200,
                      'pids_base': 100, 'pids_variance': 15, 'trend': 0}
        },
        {
            'name': 'Memory Intensive Task',
            'params': {'cpu_base': 30, 'cpu_variance': 8, 'mem_base': 600000000,
                      'mem_variance': 50000000, 'net_base': 300, 'net_variance': 100,
                      'pids_base': 90, 'pids_variance': 10, 'trend': 0}
        },
        {
            'name': 'High Network Activity',
            'params': {'cpu_base': 35, 'cpu_variance': 12, 'mem_base': 250000000,
                      'mem_variance': 25000000, 'net_base': 5000, 'net_variance': 2000,
                      'pids_base': 120, 'pids_variance': 20, 'trend': 0}
        },
        {
            'name': 'Sustained High CPU (Mining-like)',
            'params': {'cpu_base': 85, 'cpu_variance': 5, 'mem_base': 400000000,
                      'mem_variance': 20000000, 'net_base': 2000, 'net_variance': 1000,
                      'pids_base': 150, 'pids_variance': 10, 'trend': 0}
        },
        {
            'name': 'Gradually Increasing Load',
            'params': {'cpu_base': 20, 'cpu_variance': 8, 'mem_base': 200000000,
                      'mem_variance': 20000000, 'net_base': 1000, 'net_variance': 500,
                      'pids_base': 80, 'pids_variance': 10, 'trend': 5}
        },
        {
            'name': 'Bursty Workload',
            'params': {'cpu_base': 40, 'cpu_variance': 25, 'mem_base': 300000000,
                      'mem_variance': 40000000, 'net_base': 2000, 'net_variance': 1500,
                      'pids_base': 100, 'pids_variance': 20, 'trend': 0}
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n📊 Testing: {test_case['name']}")
        
        # Create multiple sequences for this pattern to get average behavior
        predictions = []
        confidences = []
        
        for _ in range(5):  # Test 5 sequences per pattern
            stats = create_stats_sequence(**test_case['params'])
            prediction, confidence, attention = detector.predict(stats)
            predictions.append(prediction)
            confidences.append(confidence)
        
        # Calculate statistics
        avg_confidence = np.mean(confidences)
        prediction_counts = {p: predictions.count(p) for p in set(predictions)}
        most_common_prediction = max(prediction_counts, key=prediction_counts.get)
        
        print(f"   Most common prediction: {most_common_prediction}")
        print(f"   Average confidence: {avg_confidence:.1%}")
        print(f"   Prediction distribution: {prediction_counts}")
        
        results.append({
            'name': test_case['name'],
            'prediction': most_common_prediction,
            'confidence': avg_confidence,
            'distribution': prediction_counts
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("📈 SUMMARY")
    print("=" * 70)
    
    normal_count = sum(1 for r in results if r['prediction'] == 'normal')
    attack_count = sum(1 for r in results if r['prediction'] == 'attack')
    
    print(f"Normal predictions: {normal_count}/{len(results)}")
    print(f"Attack predictions: {attack_count}/{len(results)}")
    
    print("\nDetailed Results:")
    for result in results:
        print(f"  {result['name']:25} -> {result['prediction']:6} ({result['confidence']:.1%})")
    
    # Analysis
    print("\n🔍 ANALYSIS:")
    if attack_count > normal_count:
        print("⚠️  Model appears to be biased towards predicting 'attack'")
        print("   This could indicate:")
        print("   - Overfitting to synthetic training data")
        print("   - Need for more diverse normal workload training data")
        print("   - Threshold tuning required")
    else:
        print("✅ Model shows reasonable discrimination between normal and attack patterns")
    
    print("\n💡 RECOMMENDATIONS:")
    print("1. Train with real-world container metrics for better generalization")
    print("2. Add more diverse normal workload patterns to training data")
    print("3. Consider adjusting confidence thresholds")
    print("4. Implement ensemble methods for better robustness")

if __name__ == "__main__":
    test_workload_patterns()

