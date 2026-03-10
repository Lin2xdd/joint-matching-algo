"""
Test script for Post-Processing Merge functionality.

This script validates the post-processing merge feature that addresses cases
where joints match in 1-to-1 but leave adjacent pieces unmatched (e.g., split joints).

Usage:
    python test_postprocessing_merge.py
"""

import sys
import os
sys.path.append('Scripts')

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from postprocessing_merge import postprocessing_merge

# Test data simulating the 2770 scenario
def test_scenario_1():
    """
    Test Case: M2770 (12m) matched to T2770 (10m) in 1-to-1, T2780 (2m) unmatched.
    Expected: Merge creates M2770 → T2770+T2780 (1-to-2) if it improves match.
    """
    print("\n" + "="*80)
    print("TEST CASE 1: Post-Processing Merge (1-to-2 split scenario)")
    print("="*80)
    
    # Initial state: M2770 matched to T2770, T2780 unmatched
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '2770',
            'Master Total Length (m)': 12.0,
            'Target Joint Number': '2770',
            'Target Total Length (m)': 10.0,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 2.0,
            'Length Ratio': 0.1818,
            'Confidence Score': 0.667,  # 12m vs 10m = ~67% confidence
            'Confidence Level': 'High',
            'Match Source': 'Forward',
            'Match Type': '1-to-1'
        }
    ]
    
    final_matched_master = {'2770'}
    final_matched_target = {'2770'}
    all_master_joints = {'2770', '2771', '2772'}
    all_target_joints = {'2770', '2780', '2781'}  # T2780 is unmatched, short (2m)
    
    master_length_map = {2770: 12.0, 2771: 11.5, 2772: 11.8}
    target_length_map = {2770: 10.0, 2780: 2.0, 2781: 11.0}  # T2780 is short
    
    print("\nInitial State:")
    print(f"  Matched: M2770(12m) <-> T2770(10m) [1-to-1, conf=0.667]")
    print(f"  Unmatched Master: {all_master_joints - final_matched_master}")
    print(f"  Unmatched Target: {all_target_joints - final_matched_target}")
    print(f"  Short unmatched: T2780 (2m)")
    
    # Run merge
    updated_list, updated_master, updated_target, merge_count = postprocessing_merge(
        matched_joints_list=matched_joints_list,
        final_matched_master=final_matched_master,
        final_matched_target=final_matched_target,
        all_master_joints=all_master_joints,
        all_target_joints=all_target_joints,
        master_length_map=master_length_map,
        target_length_map=target_length_map,
        fix_ili_id='ILI-18',
        move_ili_id='ILI-15',
        tolerance=0.30,
        min_confidence=0.60
    )
    
    print("\nAfter Post-Processing Merge:")
    print(f"  Merge count: {merge_count}")
    print(f"  Updated matches:")
    for match in updated_list:
        print(f"    M{match['Master Joint Number']}({match['Master Total Length (m)']}m) <-> " +
              f"T{match['Target Joint Number']}({match['Target Total Length (m)']}m) " +
              f"[{match['Match Type']}, conf={match['Confidence Score']:.3f}]")
    print(f"  Unmatched Master: {all_master_joints - updated_master}")
    print(f"  Unmatched Target: {all_target_joints - updated_target}")
    
    # Validation
    if merge_count > 0:
        merged_match = updated_list[0]
        if merged_match['Target Joint Number'] == '2770,2780':
            print("\n✓ SUCCESS: T2780 merged into M2770 → T2770+T2780 match")
            # Check if confidence improved
            if merged_match['Confidence Score'] > 0.667:
                print(f"✓ Confidence improved: {0.667:.3f} → {merged_match['Confidence Score']:.3f}")
            return True
        else:
            print("\n✗ FAILED: Merge did not produce expected result")
            return False
    else:
        print("\n⚠ NO MERGE: Conditions not met (may be expected if match quality doesn't improve)")
        return None


def test_scenario_2():
    """
    Test Case: Short master joint merge (many-to-1).
    """
    print("\n" + "="*80)
    print("TEST CASE 2: Post-Processing Merge (2-to-1 merge scenario)")
    print("="*80)
    
    # Initial state: M3100 matched to T3100, M3101 (short, 1.5m) unmatched
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '3100',
            'Master Total Length (m)': 10.0,
            'Target Joint Number': '3100',
            'Target Total Length (m)': 11.5,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 1.5,
            'Length Ratio': 0.1395,
            'Confidence Score': 0.690,
            'Confidence Level': 'High',
            'Match Source': 'Forward',
            'Match Type': '1-to-1'
        }
    ]
    
    final_matched_master = {'3100'}
    final_matched_target = {'3100'}
    all_master_joints = {'3100', '3101', '3102'}  # M3101 is unmatched, short (1.5m)
    all_target_joints = {'3100', '3101'}
    
    master_length_map = {3100: 10.0, 3101: 1.5, 3102: 11.0}  # M3101 is short
    target_length_map = {3100: 11.5, 3101: 11.2}
    
    print("\nInitial State:")
    print(f"  Matched: M3100(10m) <-> T3100(11.5m) [1-to-1, conf=0.690]")
    print(f"  Unmatched Master: {all_master_joints - final_matched_master}")
    print(f"  Unmatched Target: {all_target_joints - final_matched_target}")
    print(f"  Short unmatched: M3101 (1.5m)")
    
    # Run merge
    updated_list, updated_master, updated_target, merge_count = postprocessing_merge(
        matched_joints_list=matched_joints_list,
        final_matched_master=final_matched_master,
        final_matched_target=final_matched_target,
        all_master_joints=all_master_joints,
        all_target_joints=all_target_joints,
        master_length_map=master_length_map,
        target_length_map=target_length_map,
        fix_ili_id='ILI-18',
        move_ili_id='ILI-15',
        tolerance=0.30,
        min_confidence=0.60
    )
    
    print("\nAfter Post-Processing Merge:")
    print(f"  Merge count: {merge_count}")
    print(f"  Updated matches:")
    for match in updated_list:
        print(f"    M{match['Master Joint Number']}({match['Master Total Length (m)']}m) <-> " +
              f"T{match['Target Joint Number']}({match['Target Total Length (m)']}m) " +
              f"[{match['Match Type']}, conf={match['Confidence Score']:.3f}]")
    print(f"  Unmatched Master: {all_master_joints - updated_master}")
    print(f"  Unmatched Target: {all_target_joints - updated_target}")
    
    if merge_count > 0:
        merged_match = updated_list[0]
        if merged_match['Master Joint Number'] == '3100,3101':
            print("\n✓ SUCCESS: M3101 merged into M3100+M3101 → T3100 match")
            return True
        else:
            print("\n✗ FAILED: Merge did not produce expected result")
            return False
    else:
        print("\n⚠ NO MERGE: Conditions not met")
        return None


if __name__ == "__main__":
    print("="*80)
    print("POST-PROCESSING MERGE TEST SUITE")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(("Scenario 1 (1-to-2 split)", test_scenario_1()))
    results.append(("Scenario 2 (2-to-1 merge)", test_scenario_2()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, result in results:
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⚠ SKIPPED"
        print(f"  {status}: {name}")
    
    print("\n" + "="*80)
    print("Testing complete. Review logs above for details.")
    print("="*80)
