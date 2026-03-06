"""
Debug: Why M53730 (0m length) didn't merge into M53720 <-> T53720,T53730

Actual scenario from results:
- M53720 is matched to T53720,T53730 (1-to-2)
- M53730 is unmatched
- M53730 has ZERO length

Question: Why didn't M53730 merge with its neighbor M53720?
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Scripts'))

from postprocessing_merge import (
    postprocessing_merge,
    _calculate_confidence,
    _is_length_within_tolerance,
    _evaluate_merge_quality
)
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def debug_actual_scenario():
    """Debug the actual scenario from the results"""
    
    print("="*80)
    print("ACTUAL SCENARIO FROM RESULTS")
    print("="*80)
    print("\nM53720 is matched to T53720,T53730 (1-to-2)")
    print("M53730 (0m) is unmatched")
    print("Question: Why didn't M53730 merge?")
    print("="*80)
    
    # Actual scenario - M53720 already matched to T53720,T53730
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '53710',
            'Master Total Length (m)': 5.436,
            'Target Joint Number': '53710',
            'Target Total Length (m)': 5.56,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 0.124,
            'Length Ratio': 0.0225,
            'Confidence Score': 0.925,
            'Confidence Level': 'High',
            'Match Source': 'Marker Alignment',
            'Match Type': '1-to-1'
        },
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '53720',
            'Master Total Length (m)': 0.63,
            'Target Joint Number': '53720,53730',
            'Target Total Length (m)': 0.934,  # 0.22 + 0.714
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 0.304,
            'Length Ratio': 0.3887,
            'Confidence Score': 0.6,
            'Confidence Level': 'Low',
            'Match Source': 'Absolute Distance Matching + Post-Processing Merge',
            'Match Type': '1-to-2'
        }
    ]
    
    final_matched_master = {'53710', '53720'}
    final_matched_target = {'53710', '53720', '53730'}
    
    all_master_joints = {'53710', '53720', '53730'}
    all_target_joints = {'53710', '53720', '53730'}
    
    master_length_map = {
        53710: 5.436,
        53720: 0.63,
        53730: 0.0  # ZERO LENGTH
    }
    
    target_length_map = {
        53710: 5.56,
        53720: 0.22,
        53730: 0.714
    }
    
    print("\n" + "="*80)
    print("MANUAL MERGE EVALUATION")
    print("="*80)
    
    # What would happen if M53730 merges with M53720?
    print("\nAttempting to merge M53730 (0m) into M53720 <-> T53720,T53730")
    print("-"*80)
    
    # Current match
    current_master_total = 0.63
    current_target_total = 0.934
    current_confidence = 0.6
    
    print(f"\nCurrent match M53720 <-> T53720,T53730:")
    print(f"  Master total: {current_master_total}m")
    print(f"  Target total: {current_target_total}m")
    print(f"  Confidence: {current_confidence}")
    print(f"  Length diff: {abs(current_master_total - current_target_total)}m")
    
    # Merged match
    merged_master_total = 0.63 + 0.0  # Adding M53730
    merged_target_total = 0.934  # Unchanged
    
    print(f"\nAfter merging M53730 (0m):")
    print(f"  New master total: {merged_master_total}m (53720 + 53730)")
    print(f"  Target total: {merged_target_total}m (unchanged)")
    print(f"  Length diff: {abs(merged_master_total - merged_target_total)}m")
    
    # Calculate acceptance criteria
    merged_confidence = _calculate_confidence(merged_master_total, merged_target_total, 0.30)
    passes_tolerance = _is_length_within_tolerance(merged_master_total, merged_target_total, 0.30)
    passes_absolute = abs(merged_master_total - merged_target_total) < 1.5
    
    print(f"\n  Merged confidence: {merged_confidence:.3f}")
    print(f"  Within 30% tolerance: {passes_tolerance}")
    print(f"  Abs diff < 1.5m: {passes_absolute}")
    
    # Three-tier acceptance
    accept_high = merged_confidence >= 0.60
    accept_medium = merged_confidence < 0.60 and passes_tolerance
    accept_low = merged_confidence < 0.60 and not passes_tolerance and passes_absolute
    
    print(f"\n  High tier (>=60%): {accept_high}")
    print(f"  Medium tier (within 30%): {accept_medium}")
    print(f"  Low tier (abs<1.5m): {accept_low}")
    
    # Quality check
    passes_quality = accept_low or _evaluate_merge_quality(current_confidence, merged_confidence)
    
    print(f"\n  Quality check passes: {passes_quality}")
    print(f"    - Low tier bypass: {accept_low}")
    print(f"    - Quality improvement: {_evaluate_merge_quality(current_confidence, merged_confidence)}")
    
    # Decision
    should_merge = (accept_high or accept_medium or accept_low) and passes_quality
    
    print(f"\n{'='*80}")
    print(f"EXPECTED DECISION: {'ACCEPT' if should_merge else 'REJECT'}")
    print(f"{'='*80}")
    
    if not should_merge:
        print("\nWhy rejected:")
        if not (accept_high or accept_medium or accept_low):
            print("  - Does not meet any acceptance tier")
        if not passes_quality:
            print("  - Quality check failed")
    
    print("\n" + "="*80)
    print("RUNNING ACTUAL POST-PROCESSING MERGE")
    print("="*80)
    
    # Run the actual merge
    updated_list, updated_master, updated_target, merge_count = postprocessing_merge(
        matched_joints_list=matched_joints_list.copy(),
        final_matched_master=final_matched_master.copy(),
        final_matched_target=final_matched_target.copy(),
        all_master_joints=all_master_joints,
        all_target_joints=all_target_joints,
        master_length_map=master_length_map,
        target_length_map=target_length_map,
        fix_ili_id='ILI-15',
        move_ili_id='ILI-18',
        tolerance=0.30,
        min_confidence=0.60
    )
    
    print(f"\nResult: {merge_count} joints merged")
    
    if '53730' in updated_master:
        print("\n[SUCCESS] M53730 was merged!")
        for match in updated_list:
            if '53730' in str(match['Master Joint Number']):
                print(f"\n  Updated match:")
                print(f"    Master: {match['Master Joint Number']}")
                print(f"    Target: {match['Target Joint Number']}")
                print(f"    Master total: {match['Master Total Length (m)']}m")
                print(f"    Target total: {match['Target Total Length (m)']}m")
                print(f"    Confidence: {match['Confidence Score']}")
    else:
        print("\n[FAILURE] M53730 was NOT merged")
        print("  It remains unmatched")
    
    print("\n" + "="*80)
    print("DIAGNOSIS")
    print("="*80)
    
    if '53730' in updated_master and should_merge:
        print("\n✓ Algorithm works correctly - M53730 should merge and does merge")
    elif '53730' not in updated_master and not should_merge:
        print("\n✓ Algorithm works correctly - M53730 should not merge and doesn't merge")
    elif '53730' in updated_master and not should_merge:
        print("\n⚠ Algorithm merges when it shouldn't according to criteria")
    else:
        print("\n❌ BUG FOUND: M53730 should merge but doesn't!")
        print("\nPossible causes:")
        print("  1. M53730 is being filtered out before post-processing")
        print("  2. Zero-length joints are handled differently")
        print("  3. The neighbor search fails to find M53720")
        print("  4. Match index lookup fails")
        print("\nNext steps:")
        print("  - Add debug logging for joint 53730 in postprocessing_merge.py")
        print("  - Check if zero-length joints are filtered in main algorithm")
        print("  - Verify neighbor finding logic for edge cases")


if __name__ == '__main__':
    debug_actual_scenario()
