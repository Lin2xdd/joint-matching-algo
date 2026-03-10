"""
Test for sequential merge issue.

Issue: When multiple unmatched joints need to merge sequentially into the same match,
the match_index is not updated between merges, causing later merges to fail.

Scenario:
- Initially: M2800 → T2790 (1-to-1)
- T2800 unmatched, should merge → M2800 → T2790,T2800 (1-to-2)
- T2810 unmatched, should merge → M2800 → T2790,T2800,T2810 (1-to-3)

Problem: match_index is built once at the start and not updated after each merge,
so T2810 can't find the updated match structure.
"""

import sys
import os
sys.path.append('Scripts')

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from short_joint_merge import merge_unmatched_joints_with_neighbors


def test_sequential_merge_scenario():
    """
    Test Case: Sequential merges of T2800 and T2810 into M2800 ↔ T2790
    
    Initial: M2800(12m) → T2790(5m) [1-to-1]
    Step 1: T2800(5m) should merge → M2800 → T2790+T2800 (1-to-2, 10m)
    Step 2: T2810(2m) should merge → M2800 → T2790+T2800+T2810 (1-to-3, 12m)
    """
    print("\n" + "="*80)
    print("TEST: Sequential Merge Issue")
    print("="*80)
    
    # Initial state: M2800 matched to ONLY T2790 (1-to-1)
    # Both T2800 and T2810 are unmatched
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '2800',
            'Master Total Length (m)': 12.0,
            'Target Joint Number': '2790',  # Only T2790, not yet merged
            'Target Total Length (m)': 5.0,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 7.0,
            'Length Ratio': 0.8235,  # Poor match: 12m vs 5m
            'Confidence Score': 0.600,  # Barely acceptable
            'Confidence Level': 'High',
            'Match Source': 'Forward',
            'Match Type': '1-to-1'
        }
    ]
    
    final_matched_master = {'2800'}
    final_matched_target = {'2790'}  # Only 2790 matched
    all_master_joints = {'2799', '2800', '2801'}
    all_target_joints = {'2789', '2790', '2800', '2810', '2811'}  # T2800 AND T2810 unmatched
    
    master_length_map = {2799: 11.5, 2800: 12.0, 2801: 11.8}
    target_length_map = {
        2789: 11.0,
        2790: 5.0,   # Part 1 of split
        2800: 5.0,   # Part 2 of split (unmatched)
        2810: 2.0,   # Part 3 of split (unmatched)
        2811: 11.2
    }
    
    print("\nInitial State:")
    print(f"  Matched: M2800(12m) ↔ T2790(5m) [1-to-1, poor conf=0.600]")
    print(f"  Unmatched Target: T2800(5m), T2810(2m)")
    print(f"\nExpected Sequential Merges:")
    print(f"  Step 1: T2800 merges → M2800 ↔ T2790,T2800 (10m total, conf improves)")
    print(f"  Step 2: T2810 merges → M2800 ↔ T2790,T2800,T2810 (12m total, perfect match!)")
    
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
    if merge_count >= 2:
        merged_match = updated_list[0]
        target_joints = merged_match['Target Joint Number']
        
        has_2800 = '2800' in target_joints
        has_2810 = '2810' in target_joints
        
        if has_2800 and has_2810:
            print("\n✓ SUCCESS: Both T2800 and T2810 were merged sequentially!")
            print(f"  Final match: M2800 → T{target_joints} ({merged_match['Target Total Length (m)']}m)")
            print(f"  Perfect match confidence: {merged_match['Confidence Score']:.3f}")
            return True
        elif has_2800 and not has_2810:
            print("\n✗ FAILED: T2800 merged but T2810 was NOT merged!")
            print(f"  Current match: M2800 → T{target_joints}")
            print("\n🔍 ROOT CAUSE:")
            print("  The match_index is built once at the start from matched_joints_list.")
            print("  After T2800 merges, the match_index is NOT updated.")
            print("  When T2810 tries to find the match containing T2800, it searches")
            print("  the OLD match_index which only knows about T2790, not T2790,T2800.")
            print("\n💡 SOLUTION:")
            print("  Update match_index after each merge OR rebuild it periodically.")
            return False
        else:
            print(f"\n✗ FAILED: Unexpected state - T2800 in match: {has_2800}, T2810 in match: {has_2810}")
            return False
    elif merge_count == 1:
        print(f"\n⚠ PARTIAL: Only 1 merge occurred (expected 2)")
        merged_match = updated_list[0]
        print(f"  Match: M2800 → T{merged_match['Target Joint Number']}")
        return False
    else:
        print("\n✗ FAILED: No merges occurred")
        return False


if __name__ == "__main__":
    print("="*80)
    print("SEQUENTIAL MERGE ISSUE - ROOT CAUSE DIAGNOSIS")
    print("="*80)
    
    result = test_sequential_merge_scenario()
    
    print("\n" + "="*80)
    if result:
        print("STATUS: ✓ Sequential merges work correctly")
    else:
        print("STATUS: ✗ BUG CONFIRMED - match_index not updated between merges")
    print("="*80)
