"""
Debug why T2789 merges instead of T2800.
"""

import sys
sys.path.append('Scripts')

from short_joint_merge import (
    _calculate_confidence,
    _is_length_within_tolerance,
    _evaluate_merge_quality
)


def test_t2789_merge():
    """Why does T2789 merge with M2800 ↔ T2790?"""
    print("\nT2789 trying to merge:")
    print("-" * 60)
    
    # Original: M2800(12m) ↔ T2790(5m)
    master_total = 12.0
    target_before = 5.0
    original_conf = 0.0  # From test
    
    # Add T2789(11m) - BAD, makes it worse!
    target_after = 5.0 + 11.0  # 16m
    merged_conf = _calculate_confidence(master_total, target_after, 0.30)
    passes_tol = _is_length_within_tolerance(master_total, target_after, 0.30)
    passes_abs = abs(master_total - target_after) < 1.5
    
    print(f"Original: M2800(12m) <-> T2790(5m), conf={original_conf:.3f}")
    print(f"Proposed: M2800(12m) <-> T2789+T2790(16m), conf={merged_conf:.3f}")
    print(f"  Passes tolerance: {passes_tol}")
    print(f"  Passes absolute: {passes_abs}")
    
    accept_high = merged_conf >= 0.60
    accept_medium = merged_conf < 0.60 and passes_tol
    accept_low = merged_conf < 0.60 and not passes_tol and passes_abs
    quality_ok = _evaluate_merge_quality(original_conf, merged_conf, 0.05)
    
    print(f"  Accept high: {accept_high}")
    print(f"  Accept medium: {accept_medium}")
    print(f"  Accept low: {accept_low}")
    print(f"  Quality OK: {quality_ok}")
    print(f"  Final: {(accept_high or accept_medium or accept_low) and quality_ok}")
    
    if (accept_high or accept_medium or accept_low) and quality_ok:
        print("X BUG: T2789 merge is ACCEPTED but makes match WORSE!")


def test_t2800_merge():
    """Why doesn't T2800 merge with M2800 ↔ T2790?"""
    print("\nT2800 trying to merge:")
    print("-" * 60)
    
    # Original: M2800(12m) ↔ T2790(5m)
    master_total = 12.0
    target_before = 5.0
    original_conf = 0.0
    
    # Add T2800(5m) - GOOD, improves match!
    target_after = 5.0 + 5.0  # 10m
    merged_conf = _calculate_confidence(master_total, target_after, 0.30)
    passes_tol = _is_length_within_tolerance(master_total, target_after, 0.30)
    passes_abs = abs(master_total - target_after) < 1.5
    
    print(f"Original: M2800(12m) <-> T2790(5m), conf={original_conf:.3f}")
    print(f"Proposed: M2800(12m) <-> T2790+T2800(10m), conf={merged_conf:.3f}")
    print(f"  Passes tolerance: {passes_tol}")
    print(f"  Passes absolute: {passes_abs}")
    
    accept_high = merged_conf >= 0.60
    accept_medium = merged_conf < 0.60 and passes_tol
    accept_low = merged_conf < 0.60 and not passes_tol and passes_abs
    quality_ok = _evaluate_merge_quality(original_conf, merged_conf, 0.05)
    
    print(f"  Accept high: {accept_high}")
    print(f"  Accept medium: {accept_medium}")
    print(f"  Accept low: {accept_low}")
    print(f"  Quality OK: {quality_ok}")
    print(f"  Final: {(accept_high or accept_medium or accept_low) and quality_ok}")
    
    if (accept_high or accept_medium or accept_low) and quality_ok:
        print("OK T2800 merge should be ACCEPTED (improves match)")
    else:
        print("X BUG: T2800 merge is REJECTED but would improve match!")


if __name__ == "__main__":
    print("="*60)
    print("DIAGNOSIS: Why wrong joint merges")
    print("="*60)
    test_t2789_merge()
    test_t2800_merge()
    
    print("\n" + "="*60)
    print("CONCLUSION:")
    print("  The algorithm processes joints in order (2789 before 2800)")
    print("  It accepts T2789 merge even though it makes match WORSE")
    print("  By the time T2800 is processed, T2789 already merged")
    print("  Solution: Sort candidates by match improvement, not joint number")
    print("="*60)
