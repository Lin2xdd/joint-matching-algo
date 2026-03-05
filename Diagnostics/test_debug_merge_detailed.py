"""
Detailed debug of why merge isn't happening.
"""

import sys
import os
import logging
sys.path.append('Scripts')

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

from short_joint_merge import merge_unmatched_joints_with_neighbors


def test_with_debug():
    """Test with debug output enabled"""
    print("\n" + "="*80)
    print("DETAILED DEBUG TEST")
    print("="*80)
    
    # Start with a more realistic confidence score
    # If M2800(12m) was matched to T2790(5m), the actual confidence would be ~0.0
    # But let's test with what would be calculated
    matched_joints_list = [
        {
            'Master ILI ID': 'ILI-18',
            'Master Joint Number': '2800',
            'Master Total Length (m)': 12.0,
            'Target Joint Number': '2790',
            'Target Total Length (m)': 5.0,
            'Target ILI ID': 'ILI-15',
            'Length Difference (m)': 7.0,
            'Length Ratio': 0.8235,
            'Confidence Score': 0.0,  # Realistic: 12m vs 5m is way outside tolerance
            'Confidence Level': 'Low',  # Should be Low given the poor match
            'Match Source': 'Absolute Distance',  # Maybe matched by absolute distance
            'Match Type': '1-to-1'
        }
    ]
    
    final_matched_master = {'2800'}
    final_matched_target = {'2790'}
    all_master_joints = {'2799', '2800', '2801'}
    all_target_joints = {'2789', '2790', '2800', '2810', '2811'}
    
    master_length_map = {2799: 11.5, 2800: 12.0, 2801: 11.8}
    target_length_map = {2789: 11.0, 2790: 5.0, 2800: 5.0, 2810: 2.0, 2811: 11.2}
    
    print("\nInput State:")
    print(f"  M2800(12m) <-> T2790(5m) [conf=0.0, clearly a split joint scenario]")
    print(f"  Unmatched: T2800(5m), T2810(2m)")
    print(f"\nExpected: Both should merge to create M2800 <-> T2790+T2800+T2810 (12m)")
    
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
    
    print(f"\nResult: {merge_count} merges")
    for match in updated_list:
        print(f"  M{match['Master Joint Number']} <-> T{match['Target Joint Number']}")
        print(f"    Lengths: {match['Master Total Length (m)']}m vs {match['Target Total Length (m)']}m")
        print(f"    Confidence: {match['Confidence Score']:.3f} ({match['Confidence Level']})")


if __name__ == "__main__":
    test_with_debug()
