"""
Test the EXACT real scenario for joint 2810.
Based on user clarification: Only T2810 is unmatched in that region.
"""

import sys
import os
sys.path.append('Scripts')

if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from short_joint_merge import merge_unmatched_joints_with_neighbors


def test_real_scenario():
    """
    Real Scenario:
    - M2800 is already matched to T2790,T2800 (1-to-2) from previous algorithm
    - T2810 is the ONLY unmatched joint in the region  
    - T2810 should merge into the existing match
    """
    print("\n" + "="*80)
    print("REAL SCENARIO TEST: M2800 -> T2790,T2800 + unmatched T2810")
    print("="*80)
    
    # M2800 already matched to T2790,T2800 (this is the state AFTER earlier matching)
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '2800',
            'Master Total Length (m)': 12.0,
            'Target Joint Number': '2790,2800',  # Already 1-to-2
            'Target Total Length (m)': 10.0,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 2.0,
            'Length Ratio': 0.1818,
            'Confidence Score': 0.667,
            'Confidence Level': 'High',
            'Match Source': 'Cumulative Length',
            'Match Type': '1-to-2'
        }
    ]
    
    final_matched_master = {'2800'}
    final_matched_target = {'2790', '2800'}  # Both already matched
    
    # All joints in the region - T2810 is unmatched
    all_master_joints = {'2799', '2800', '2801'}
    all_target_joints = {'2789', '2790', '2800', '2810', '2811'}
    
    # Real lengths
    master_length_map = {2799: 11.5, 2800: 12.0, 2801: 11.8}
    target_length_map = {
        2789: 11.0,
        2790: 5.0,   # Part of match
        2800: 5.0,   # Part of match
        2810: 2.0,   # UNMATCHED - should merge
        2811: 11.2
    }
    
    print("\nCurrent State:")
    print(f"  Matched: M2800(12m) <-> T2790,T2800(10m) [1-to-2]")
    print(f"  Unmatched Master: {sorted([int(j) for j in all_master_joints - final_matched_master])}")
    print(f"  Unmatched Target: {sorted([int(j) for j in all_target_joints - final_matched_target])}")
    print(f"\n  Target joints in order: {sorted([int(j) for j in all_target_joints])}")
    print(f"  T2810's neighbors: prev=T2800 (matched), next=T2811 (unmatched)")
    print(f"\nExpected: T2810 merges -> M2800 <-> T2790,T2800,T2810 (12m perfect match!)")
    
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
    
    print("\nResult:")
    print(f"  Merges: {merge_count}")
    for match in updated_list:
        print(f"  M{match['Master Joint Number']} <-> T{match['Target Joint Number']}")
        print(f"    {match['Master Total Length (m)']}m vs {match['Target Total Length (m)']}m")
        print(f"    Conf: {match['Confidence Score']:.3f} ({match['Confidence Level']})")
    
    print(f"\n  Unmatched Master: {sorted([int(j) for j in all_master_joints - updated_master])}")
    print(f"  Unmatched Target: {sorted([int(j) for j in all_target_joints - updated_target])}")
    
    # Check result
    if merge_count > 0:
        result_match = updated_list[0]
        target_joints = result_match['Target Joint Number']
        
        if '2810' in target_joints and '2790' in target_joints and '2800' in target_joints:
            print("\nSUCCESS: T2810 merged correctly!")
            print(f"  Final: M2800 -> T{target_joints} ({result_match['Target Total Length (m)']}m)")
            return True
        else:
            print(f"\nFAILED: T2810 NOT in result. Got: T{target_joints}")
            return False
    else:
        print("\nFAILED: No merges occurred")
        return False


if __name__ == "__main__":
    result = test_real_scenario()
    print("\n" + "="*80)
    print(f"Test {'PASSED' if result else 'FAILED'}")
    print("="*80)
