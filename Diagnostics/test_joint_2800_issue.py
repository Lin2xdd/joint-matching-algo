"""
Diagnostic test for joint 2800 merge issue.

Issue: Joint 2800 from ILI-18 should be matched to 2790, 2800, and 2810,
but 2810 was not matched in the merge.

This test reproduces the exact scenario to identify the bug.
"""

import sys
import os
sys.path.append('Scripts')

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from short_joint_merge import merge_unmatched_joints_with_neighbors


def test_joint_2800_scenario():
    """
    Test Case: M2800 should match to T2790+T2800+T2810 (1-to-3)
    
    Scenario:
    - M2800 (12m) is matched to T2790+T2800 (1-to-2)
    - T2810 (2m) is unmatched and should be merged
    - Expected: M2800 → T2790+T2800+T2810 (1-to-3)
    """
    print("\n" + "="*80)
    print("DIAGNOSTIC TEST: Joint 2800 Issue")
    print("="*80)
    
    # Initial state: M2800 already matched to T2790,T2800 (1-to-2)
    # T2810 is unmatched
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '2800',
            'Master Total Length (m)': 12.0,
            'Target Joint Number': '2790,2800',  # Already merged 2790 and 2800
            'Target Total Length (m)': 10.0,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 2.0,
            'Length Ratio': 0.1818,
            'Confidence Score': 0.667,
            'Confidence Level': 'High',
            'Match Source': 'Forward + Unmatched Joint Merge',
            'Match Type': '1-to-2'
        }
    ]
    
    final_matched_master = {'2800'}
    final_matched_target = {'2790', '2800'}  # Both 2790 and 2800 are matched
    all_master_joints = {'2799', '2800', '2801'}
    all_target_joints = {'2789', '2790', '2800', '2810', '2811'}  # T2810 unmatched
    
    master_length_map = {2799: 11.5, 2800: 12.0, 2801: 11.8}
    target_length_map = {2789: 11.0, 2790: 5.0, 2800: 5.0, 2810: 2.0, 2811: 11.2}
    
    print("\nInitial State:")
    print(f"  Matched: M2800(12m) ↔ T2790,T2800(10m) [1-to-2]")
    print(f"  Unmatched Master: {sorted([int(j) for j in all_master_joints - final_matched_master])}")
    print(f"  Unmatched Target: {sorted([int(j) for j in all_target_joints - final_matched_target])}")
    print(f"\nProblem: T2810 (2m) should be merged into M2800 ↔ T2790,T2800,T2810")
    print(f"Expected Result: M2800 → T2790+T2800+T2810 (1-to-3, total 12m target)")
    
    # Run merge
    updated_list, updated_master, updated_target, merge_count = merge_unmatched_joints_with_neighbors(
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
    
    print("\nAfter Short Joint Merge:")
    print(f"  Merge count: {merge_count}")
    print(f"  Updated matches:")
    for match in updated_list:
        print(f"    M{match['Master Joint Number']}({match['Master Total Length (m)']}m) ↔ " +
              f"T{match['Target Joint Number']}({match['Target Total Length (m)']}m) " +
              f"[{match['Match Type']}, conf={match['Confidence Score']:.3f}, level={match['Confidence Level']}]")
    print(f"  Unmatched Master: {sorted([int(j) for j in all_master_joints - updated_master])}")
    print(f"  Unmatched Target: {sorted([int(j) for j in all_target_joints - updated_target])}")
    
    # Validation
    if merge_count > 0:
        merged_match = updated_list[0]
        target_joints = merged_match['Target Joint Number']
        if '2810' in target_joints:
            print("\n✓ SUCCESS: T2810 was merged as expected!")
            print(f"  Final match: M2800 → T{target_joints}")
            return True
        else:
            print("\n✗ FAILED: T2810 was NOT merged!")
            print(f"  Current match: M2800 → T{target_joints}")
            print("\n🔍 ROOT CAUSE ANALYSIS:")
            print("  The match_index is not updated after each merge.")
            print("  When T2810 tries to find the match containing T2800,")
            print("  it finds the OLD match structure before T2790 was merged.")
            return False
    else:
        print("\n✗ FAILED: No merge occurred")
        return False


if __name__ == "__main__":
    print("="*80)
    print("JOINT 2800 MERGE ISSUE - DIAGNOSTIC TEST")
    print("="*80)
    
    result = test_joint_2800_scenario()
    
    print("\n" + "="*80)
    if result:
        print("STATUS: ✓ Issue is FIXED")
    else:
        print("STATUS: ✗ Issue REPRODUCED - Fix needed")
    print("="*80)
