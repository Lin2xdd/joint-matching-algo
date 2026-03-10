"""
Diagnostic Script: Why M53730 from ILI-18 didn't merge to M53720

Data from ARC Set 2:
ILI-18 (Master/Move):
- M53710: distance 90450.8, length 5.436m
- M53720: distance 90456.236, length 0.63m
- M53730: distance 90456.866, length 0m (!!!)

ILI-15 (Target/Fix):
- T53710: distance 90450.8, length 5.436m
- T53720: distance 90456.236, length 0.63m
- T53730: distance 90456.866, length 0.714m

Key Question: Why didn't M53730 (length=0) merge into an existing match with M53720?
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Scripts'))

from postprocessing_merge import postprocessing_merge
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def test_53730_merge_scenario():
    """Test why M53730 doesn't merge with M53720"""
    
    print("="*80)
    print("SCENARIO: M53730 (length=0) merge attempt")
    print("="*80)
    
    # Simulate the scenario where M53720 is already matched to T53720,T53730
    # (This is likely what happened - a 1-to-2 match was already created)
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '53710',
            'Master Total Length (m)': 5.436,
            'Target Joint Number': '53710',
            'Target Total Length (m)': 5.436,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 0.0,
            'Length Ratio': 0.0,
            'Confidence Score': 1.0,
            'Confidence Level': 'High',
            'Match Source': 'Forward Matching',
            'Match Type': '1-to-1'
        },
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '53720',
            'Master Total Length (m)': 0.63,
            'Target Joint Number': '53720,53730',  # Already a 1-to-2 match
            'Target Total Length (m)': 1.344,  # 0.63 + 0.714
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 0.714,
            'Length Ratio': 0.723,  # (0.714 / 0.987) = 72.3% difference
            'Confidence Score': 0.0,  # Very poor confidence due to large difference
            'Confidence Level': 'Low',
            'Match Source': 'Cumulative Length Matching',
            'Match Type': '1-to-2'
        }
    ]
    
    # Matched sets
    final_matched_master = {'53710', '53720'}
    final_matched_target = {'53710', '53720', '53730'}
    
    # All joints
    all_master_joints = {'53710', '53720', '53730'}
    all_target_joints = {'53710', '53720', '53730'}
    
    # Length maps
    master_length_map = {
        53710: 5.436,
        53720: 0.63,
        53730: 0.0  # ZERO LENGTH - This is the problem!
    }
    
    target_length_map = {
        53710: 5.436,
        53720: 0.63,
        53730: 0.714
    }
    
    print("\nINITIAL STATE:")
    print("-" * 80)
    print(f"Unmatched Master: {all_master_joints - final_matched_master}")
    print(f"Unmatched Target: {all_target_joints - final_matched_target}")
    print(f"\nM53730 length: {master_length_map[53730]}m")
    print(f"\nExisting match M53720 <-> T53720,T53730:")
    print(f"  Master total: {matched_joints_list[1]['Master Total Length (m)']}m")
    print(f"  Target total: {matched_joints_list[1]['Target Total Length (m)']}m")
    print(f"  Confidence: {matched_joints_list[1]['Confidence Score']}")
    print(f"  Length difference: {matched_joints_list[1]['Length Difference (m)']}m")
    
    print("\n" + "="*80)
    print("ATTEMPTING MERGE: M53730 (0m) into M53720 <-> T53720,T53730")
    print("="*80)
    
    # Calculate what would happen if we merge M53730 into M53720
    merged_master_total = 0.63 + 0.0  # M53720 + M53730
    merged_target_total = 1.344  # T53720 + T53730 (unchanged)
    
    print(f"\nHypothetical merge:")
    print(f"  New master total: {merged_master_total}m (53720 + 53730)")
    print(f"  Target total: {merged_target_total}m (53720 + 53730)")
    print(f"  Length difference: {abs(merged_master_total - merged_target_total)}m")
    print(f"  Length ratio: {abs(merged_master_total - merged_target_total) / ((merged_master_total + merged_target_total) / 2):.3f}")
    
    # Check acceptance criteria
    avg_length = (merged_master_total + merged_target_total) / 2
    diff = abs(merged_master_total - merged_target_total)
    diff_ratio = diff / avg_length if avg_length > 0 else float('inf')
    
    # Calculate confidence
    tolerance = 0.30
    confidence = 1.0 - (diff_ratio / tolerance)
    confidence = max(0.0, min(1.0, confidence))
    
    print(f"\nMerge evaluation:")
    print(f"  Confidence score: {confidence:.3f}")
    print(f"  Within 30% tolerance: {diff_ratio <= tolerance}")
    print(f"  Absolute difference < 1.5m: {diff < 1.5}")
    
    # Three-tier acceptance
    accept_high = confidence >= 0.60
    accept_medium = confidence < 0.60 and diff_ratio <= tolerance
    accept_low = confidence < 0.60 and diff_ratio > tolerance and diff < 1.5
    
    print(f"\nAcceptance tiers:")
    print(f"  High tier (conf >= 60%): {accept_high}")
    print(f"  Medium tier (within 30%): {accept_medium}")
    print(f"  Low tier (abs diff < 1.5m): {accept_low}")
    
    # Quality check
    original_confidence = matched_joints_list[1]['Confidence Score']
    improvement_threshold = 0.05
    quality_ok = confidence >= original_confidence - improvement_threshold
    
    print(f"\nQuality check:")
    print(f"  Original confidence: {original_confidence:.3f}")
    print(f"  Merged confidence: {confidence:.3f}")
    print(f"  Quality improvement: {quality_ok}")
    
    # Overall decision
    passes_quality = accept_low or quality_ok
    should_merge = (accept_high or accept_medium or accept_low) and passes_quality
    
    print(f"\n{'='*80}")
    print(f"MERGE DECISION: {'ACCEPT' if should_merge else 'REJECT'}")
    print(f"{'='*80}")
    
    if not should_merge:
        print("\nREASON FOR REJECTION:")
        if not (accept_high or accept_medium or accept_low):
            print("  ❌ Does not meet any acceptance tier")
            print(f"     - Confidence {confidence:.3f} < 0.60 (High)")
            print(f"     - Diff ratio {diff_ratio:.3f} > 0.30 (Medium)")
            print(f"     - Abs diff {diff:.3f}m >= 1.5m (Low)")
        elif not passes_quality:
            print("  ❌ Quality check failed")
            print(f"     - Merged confidence {confidence:.3f} < original {original_confidence:.3f} - {improvement_threshold}")
    
    print("\n" + "="*80)
    print("RUNNING ACTUAL POSTPROCESSING MERGE")
    print("="*80)
    
    # Run actual merge
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
    
    print(f"\nMerge count: {merge_count}")
    print(f"Updated matched master: {updated_master}")
    print(f"Updated matched target: {updated_target}")
    
    # Check if M53730 was merged
    if '53730' in updated_master:
        print("\n[SUCCESS] M53730 WAS MERGED")
        for match in updated_list:
            if '53730' in str(match['Master Joint Number']):
                print(f"  Match: M{match['Master Joint Number']} <-> T{match['Target Joint Number']}")
                print(f"  Master total: {match['Master Total Length (m)']}m")
                print(f"  Target total: {match['Target Total Length (m)']}m")
                print(f"  Confidence: {match['Confidence Score']}")
    else:
        print("\n[FAILURE] M53730 WAS NOT MERGED")
        print(f"  Remains unmatched")


if __name__ == '__main__':
    test_53730_merge_scenario()
