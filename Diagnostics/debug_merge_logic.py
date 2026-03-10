"""
Debug the merge logic to understand why merges aren't happening.
"""

import sys
sys.path.append('Scripts')

from short_joint_merge import (
    _calculate_confidence,
    _is_length_within_tolerance,
    _evaluate_merge_quality
)


def debug_t2800_merge():
    """Debug why T2800 doesn't merge into M2800 ↔ T2790"""
    print("\n" + "="*80)
    print("DEBUG: T2800 Merge Logic")
    print("="*80)
    
    # Original match: M2800(12m) ↔ T2790(5m)
    master_total = 12.0
    target_total_before = 5.0
    original_confidence = _calculate_confidence(master_total, target_total_before, 0.30)
    
    print(f"\nOriginal Match: M2800({master_total}m) <-> T2790({target_total_before}m)")
    print(f"  Calculated confidence: {original_confidence:.3f}")
    print(f"  Passes tolerance: {_is_length_within_tolerance(master_total, target_total_before, 0.30)}")
    
    # Proposed merge: Add T2800(5m)
    t2800_length = 5.0
    target_total_after = target_total_before + t2800_length
    merged_confidence = _calculate_confidence(master_total, target_total_after, 0.30)
    passes_tolerance = _is_length_within_tolerance(master_total, target_total_after, 0.30)
    passes_absolute = abs(master_total - target_total_after) < 1.5
    
    print(f"\nProposed Merge: M2800({master_total}m) <-> T2790+T2800({target_total_after}m)")
    print(f"  Merged confidence: {merged_confidence:.3f}")
    print(f"  Passes tolerance (30%): {passes_tolerance}")
    print(f"  Passes absolute distance (<1.5m): {passes_absolute}")
    
    # Acceptance criteria
    min_confidence = 0.60
    accept_high = merged_confidence >= min_confidence
    accept_medium = merged_confidence < min_confidence and passes_tolerance
    accept_low = merged_confidence < min_confidence and not passes_tolerance and passes_absolute
    
    print(f"\nAcceptance Criteria:")
    print(f"  High (conf >= {min_confidence}): {accept_high}")
    print(f"  Medium (conf < {min_confidence} AND within tolerance): {accept_medium}")
    print(f"  Low (conf < {min_confidence} AND NOT tolerance BUT abs < 1.5m): {accept_low}")
    print(f"  Any accepted: {accept_high or accept_medium or accept_low}")
    
    # Quality evaluation
    quality_ok = _evaluate_merge_quality(original_confidence, merged_confidence, 0.05)
    print(f"\nQuality Evaluation:")
    print(f"  Original confidence: {original_confidence:.3f}")
    print(f"  Merged confidence: {merged_confidence:.3f}")
    print(f"  Improvement threshold: 0.05 (5%)")
    print(f"  Passes quality check (merged >= original - 0.05): {quality_ok}")
    print(f"  Details: {merged_confidence:.3f} >= {original_confidence:.3f} - 0.05 = {original_confidence - 0.05:.3f}")
    
    # Final verdict
    final_accept = (accept_high or accept_medium or accept_low) and quality_ok
    print(f"\n{'OK' if final_accept else 'X'} FINAL VERDICT: {'MERGE' if final_accept else 'REJECT'}")
    
    if not final_accept:
        print(f"\nREASON FOR REJECTION:")
        if not (accept_high or accept_medium or accept_low):
            print(f"  Failed acceptance criteria")
        if not quality_ok:
            print(f"  Failed quality check: merged conf ({merged_confidence:.3f}) < original ({original_confidence:.3f}) - threshold (0.05)")


def debug_t2810_merge():
    """Debug why T2810 doesn't merge into M2800 ↔ T2790,T2800"""
    print("\n" + "="*80)
    print("DEBUG: T2810 Merge Logic (assuming T2800 already merged)")
    print("="*80)
    
    # Current match after T2800 merged: M2800(12m) ↔ T2790+T2800(10m)
    master_total = 12.0
    target_total_before = 10.0
    original_confidence = _calculate_confidence(master_total, target_total_before, 0.30)
    
    print(f"\nCurrent Match: M2800({master_total}m) <-> T2790,T2800({target_total_before}m)")
    print(f"  Calculated confidence: {original_confidence:.3f}")
    
    # Proposed merge: Add T2810(2m)
    t2810_length = 2.0
    target_total_after = target_total_before + t2810_length
    merged_confidence = _calculate_confidence(master_total, target_total_after, 0.30)
    passes_tolerance = _is_length_within_tolerance(master_total, target_total_after, 0.30)
    passes_absolute = abs(master_total - target_total_after) < 1.5
    
    print(f"\nProposed Merge: M2800({master_total}m) <-> T2790+T2800+T2810({target_total_after}m)")
    print(f"  Merged confidence: {merged_confidence:.3f}")
    print(f"  Passes tolerance (30%): {passes_tolerance}")
    print(f"  Passes absolute distance (<1.5m): {passes_absolute}")
    
    # Quality evaluation
    quality_ok = _evaluate_merge_quality(original_confidence, merged_confidence, 0.05)
    print(f"\nQuality Evaluation:")
    print(f"  Passes quality check: {quality_ok}")
    
    print(f"\n{'OK' if quality_ok else 'X'} This merge should {'SUCCEED' if quality_ok else 'FAIL'}")


if __name__ == "__main__":
    debug_t2800_merge()
    debug_t2810_merge()
