#!/usr/bin/env python3
"""
Direct evaluation on test set using the same data format as training.
This avoids the sequence-to-stats conversion which was corrupting the data.
"""

import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, auc
from sklearn.metrics import precision_recall_curve, average_precision_score

from train_temporal_detector import TemporalDetectorTrainer
from ml_temporal_detector import TemporalContainerDetector, MODEL_PATH

def evaluate_directly():
    """Evaluate using the actual test data loader - no conversion needed."""
    print("🧪 Direct Evaluation on Test Set")
    print("=" * 60)
    
    # Load data
    print("🔄 Loading test data...")
    trainer = TemporalDetectorTrainer()
    df = trainer.load_dataset()
    sequences, labels = trainer.preprocess_data(df)
    train_loader, val_loader, test_loader = trainer.create_data_loaders(sequences, labels)
    
    # Load trained model
    print("📦 Loading trained model...")
    device = torch.device("cpu")
    checkpoint = torch.load(MODEL_PATH, map_location=device)
    
    model = TemporalContainerDetector(
        numerical_dim=checkpoint.get("numerical_dim", 15),
        categorical_dims=checkpoint.get("categorical_dims", {}),
        num_classes=checkpoint.get("num_classes", 2),
        dropout=0.4  # Same as training
    ).to(device)
    
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print("✅ Model loaded successfully")
    
    # Evaluate
    print("🔮 Making predictions...")
    all_predictions = []
    all_labels = []
    all_probabilities = []
    
    with torch.no_grad():
        for batch_idx, (sequences, labels_batch) in enumerate(test_loader):
            if batch_idx % 50 == 0:
                print(f"   Batch {batch_idx}/{len(test_loader)}...")
            
            sequences = sequences.to(device)
            labels_batch = labels_batch.squeeze().to(device)
            
            # Forward pass
            logits, attention = model(sequences, {})
            probabilities = F.softmax(logits, dim=-1)
            _, predicted = torch.max(logits, 1)
            
            all_predictions.extend(predicted.cpu().numpy())
            all_labels.extend(labels_batch.cpu().numpy())
            all_probabilities.extend(probabilities[:, 1].cpu().numpy())  # Probability of attack class
    
    print(f"✅ Completed {len(all_predictions)} predictions")
    
    # Calculate metrics
    accuracy = sum(p == l for p, l in zip(all_predictions, all_labels)) / len(all_labels)
    
    print(f"\n📊 TEST SET RESULTS")
    print("=" * 60)
    print(f"Test Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Classification report
    class_names = ['Normal', 'Attack']
    report = classification_report(all_labels, all_predictions, target_names=class_names)
    print(f"\n📈 Classification Report:")
    print(report)
    
    # Confusion matrix
    cm = confusion_matrix(all_labels, all_predictions)
    print(f"\n🔢 Confusion Matrix:")
    print(f"                 Predicted")
    print(f"Actual    Normal  Attack")
    print(f"Normal    {cm[0,0]:6d}  {cm[0,1]:6d}")
    print(f"Attack    {cm[1,0]:6d}  {cm[1,1]:6d}")
    
    # Calculate additional metrics
    tn, fp, fn, tp = cm.ravel()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    
    print(f"\n📊 Detailed Metrics:")
    print(f"Precision (Attack): {precision:.4f}")
    print(f"Recall (Attack):    {recall:.4f}")
    print(f"F1-Score (Attack):  {f1:.4f}")
    print(f"Specificity:        {specificity:.4f}")
    
    # Plot ROC curve
    fpr, tpr, _ = roc_curve(all_labels, all_probabilities)
    roc_auc = auc(fpr, tpr)
    
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve - Direct Evaluation')
    plt.legend(loc="lower right")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('roc_curve_direct.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n📊 ROC Curve saved (AUC = {roc_auc:.3f})")
    
    # Plot Precision-Recall curve
    precision_vals, recall_vals, _ = precision_recall_curve(all_labels, all_probabilities)
    avg_precision = average_precision_score(all_labels, all_probabilities)
    
    plt.figure(figsize=(8, 6))
    plt.plot(recall_vals, precision_vals, color='darkorange', lw=2, label=f'PR curve (AP = {avg_precision:.3f})')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve - Direct Evaluation')
    plt.legend(loc="lower left")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('precision_recall_curve_direct.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"📊 Precision-Recall Curve saved (AP = {avg_precision:.3f})")
    
    # Plot confusion matrix
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
               xticklabels=class_names, yticklabels=class_names)
    plt.title('Confusion Matrix - Direct Evaluation')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.tight_layout()
    plt.savefig('test_confusion_matrix_direct.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("📊 Test Confusion Matrix saved")
    
    # Confidence analysis
    normal_probs = [prob for label, prob in zip(all_labels, all_probabilities) if label == 0]
    attack_probs = [prob for label, prob in zip(all_labels, all_probabilities) if label == 1]
    
    print(f"\n🎯 Confidence Analysis (Attack Probability):")
    print("=" * 40)
    print(f"Normal samples (n={len(normal_probs)}):")
    print(f"  Mean: {np.mean(normal_probs):.3f}")
    print(f"  Std:  {np.std(normal_probs):.3f}")
    print(f"  Min:  {np.min(normal_probs):.3f}")
    print(f"  Max:  {np.max(normal_probs):.3f}")
    
    print(f"\nAttack samples (n={len(attack_probs)}):")
    print(f"  Mean: {np.mean(attack_probs):.3f}")
    print(f"  Std:  {np.std(attack_probs):.3f}")
    print(f"  Min:  {np.min(attack_probs):.3f}")
    print(f"  Max:  {np.max(attack_probs):.3f}")
    
    # Plot confidence distributions
    plt.figure(figsize=(10, 6))
    plt.hist(normal_probs, bins=50, alpha=0.7, label='Normal', color='blue')
    plt.hist(attack_probs, bins=50, alpha=0.7, label='Attack', color='red')
    plt.xlabel('Attack Probability')
    plt.ylabel('Frequency')
    plt.title('Attack Probability Distribution by True Class')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('confidence_distribution_direct.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("📊 Confidence Distribution saved")
    
    print(f"\n🎉 Evaluation Complete!")
    print(f"Test Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"F1-Score: {f1:.4f}")
    print(f"AUC: {roc_auc:.4f}")

if __name__ == "__main__":
    evaluate_directly()

