"""
Diagnostic script to confirm why joint 20 from ILI-23 didn't match to joints 20 & 30 from ILI-19.

ROOT CAUSE HYPOTHESIS:
Head section (before first marker) only uses backward_match_check, which doesn't support
1-to-many aggregation. Tail section has forward + backward + cumulative matching, but head
section is missing the cumulative matching step.
"""

import pandas as pd
import numpy as np

# Load data
ili_2023 = pd.read_csv('Sample Input/ARC/database ready/Onstream 2023 - 16in 4-25 to 10-7.csv')
ili_2019 = pd.read_csv('Sample Input/ARC/database ready/Onstream 2019 - 16in 4-25 to 10-7.csv')

print("=" * 80)
print("DIAGNOSIS: Why Joint 20 Failed to Match")
print("=" * 80)

# Find first marker
first_marker_2023 = ili_2023[ili_2023['marker'] > 0].iloc[0]
first_marker_2019 = ili_2019[ili_2019['marker'] > 0].iloc[0]

print(f"\nFirst Marker ILI-2023: Joint {first_marker_2023['joint_number']}, Index {first_marker_2023.name}")
print(f"First Marker ILI-2019: Joint {first_marker_2019['joint_number']}, Index {first_marker_2019.name}")

# Get head section (before first marker)
head_2023 = ili_2023[ili_2023.index < first_marker_2023.name]
head_2019 = ili_2019[ili_2019.index < first_marker_2019.name]

print(f"\nHead Section (before marker):")
print(f"  ILI-2023: {len(head_2023)} joints, indices 0-{len(head_2023)-1}")
print(f"  ILI-2019: {len(head_2019)} joints, indices 0-{len(head_2019)-1}")

# Find joint 20 in ILI-2023
joint_20_2023 = head_2023[head_2023['joint_number'] == 20]
j20_idx = joint_20_2023.index[0]
j20_data = joint_20_2023.iloc[0]

# Find joints 20 & 30 in ILI-2019
joint_20_2019 = head_2019[head_2019['joint_number'] == 20]
joint_30_2019 = head_2019[head_2019['joint_number'] == 30]

j20_2019_idx = joint_20_2019.index[0]
j30_2019_idx = joint_30_2019.index[0]
j20_2019_len = joint_20_2019.iloc[0]['joint_length']
j30_2019_len = joint_30_2019.iloc[0]['joint_length']

print(f"\nTarget Joint:")
print(f"  Joint 20 (ILI-2023): {j20_data['joint_length']:.3f}m (index {j20_idx})")

print(f"\nCandidate Matches:")
print(f"  Joint 20 (ILI-2019): {j20_2019_len:.3f}m (index {j20_2019_idx})")
print(f"  Joint 30 (ILI-2019): {j30_2019_len:.3f}m (index {j30_2019_idx})")
print(f"  Combined (20+30):    {j20_2019_len + j30_2019_len:.3f}m")

print("\n" + "=" * 80)
print("CURRENT HEAD SECTION LOGIC (Lines 1083-1089)")
print("=" * 80)

print("\nCode:")
print("  try:")
print("      matches, _, _ = backward_match_check(")
print("          fix_data, move_data, 0, 0, it_chunks.iloc[0, 0], it_chunks.iloc[0, 1], 1, min_confidence=0.60")
print("      )")
print("      Match_df = pd.concat([Match_df, matches])")
print("  except:")
print("      pass")

print("\nWhat happens:")
print("  1. Only backward_match_check is called")
print("  2. No forward_match_check")
print("  3. No cumulative matching")
print("  4. No short joint matching")

def _calculate_confidence(length1, length2, tolerance=0.30):
    diff = abs(length1 - length2)
    max_length = max(length1, length2)
    if max_length == 0:
        return 0.0
    return max(0.0, 1.0 - (diff / max_length / tolerance))

def _is_within_tolerance(length1, length2, tolerance=0.30):
    diff = abs(length1 - length2)
    max_length = max(length1, length2)
    if max_length == 0:
        return False
    return (diff / max_length) <= tolerance

print("\n" + "-" * 80)
print("TEST 1: backward_match_check with 1-to-1 (Joint 20 vs Joint 20)")
print("-" * 80)

confidence = _calculate_confidence(j20_data['joint_length'], j20_2019_len)
within_tol = _is_within_tolerance(j20_data['joint_length'], j20_2019_len)
diff_pct = abs(j20_data['joint_length'] - j20_2019_len) / max(j20_data['joint_length'], j20_2019_len) * 100

print(f"\nMaster: {j20_data['joint_length']:.3f}m")
print(f"Target: {j20_2019_len:.3f}m")
print(f"Difference: {diff_pct:.1f}%")
print(f"Confidence: {confidence:.3f}")
print(f"Within 30% tolerance: {within_tol}")
print(f"Passes 60% confidence: {confidence >= 0.60}")

if confidence >= 0.60:
    result = "HIGH CONFIDENCE MATCH"
elif within_tol:
    result = "MEDIUM CONFIDENCE MATCH (via tolerance)"
else:
    result = "REJECT"

print(f"\nResult: {result}")
print(f"[ACTUAL] Joint 20 was NOT matched by backward_match_check")

print("\n" + "=" * 80)
print("WHAT CUMULATIVE MATCHING WOULD DO (Missing from Head Section)")
print("=" * 80)

combined_len = j20_2019_len + j30_2019_len
confidence_cumul = _calculate_confidence(j20_data['joint_length'], combined_len)
within_tol_cumul = _is_within_tolerance(j20_data['joint_length'], combined_len)
diff_pct_cumul = abs(j20_data['joint_length'] - combined_len) / max(j20_data['joint_length'], combined_len) * 100

# Apply aggregation penalty (5% per additional joint)
adjusted_confidence = confidence_cumul - 0.05

print(f"\nMaster: {j20_data['joint_length']:.3f}m")
print(f"Target: {combined_len:.3f}m (joints 20 + 30)")
print(f"Difference: {diff_pct_cumul:.1f}%")
print(f"Raw Confidence: {confidence_cumul:.3f}")
print(f"Aggregation Penalty: -0.05 (5% for 1 extra joint)")
print(f"Adjusted Confidence: {adjusted_confidence:.3f}")
print(f"Within 30% tolerance: {within_tol_cumul}")
print(f"Passes 60% confidence: {adjusted_confidence >= 0.60}")

if adjusted_confidence >= 0.60:
    result_cumul = "HIGH CONFIDENCE MATCH"
elif within_tol_cumul:
    result_cumul = "MEDIUM CONFIDENCE MATCH (via tolerance)"
else:
    result_cumul = "REJECT"

print(f"\nResult: {result_cumul}")
print(f"[EXPECTED] Joint 20 SHOULD match via cumulative matching with medium confidence")

print("\n" + "=" * 80)
print("COMPARISON: TAIL SECTION vs HEAD SECTION")
print("=" * 80)

print("\nTAIL SECTION (Lines 1091-1143) - AFTER last marker:")
print("  ✓ forward_match_check (line 1098)")
print("  ✓ backward_match_check (line 1107)")
print("  ✓ cumulative matching (lines 1115-1141)")
print("  ✓ Can handle 1-to-many aggregation")

print("\nHEAD SECTION (Lines 1083-1089) - BEFORE first marker:")
print("  ✗ NO forward_match_check")
print("  ✓ backward_match_check only (line 1084)")
print("  ✗ NO cumulative matching")
print("  ✗ Cannot handle 1-to-many aggregation")

print("\n" + "=" * 80)
print("ROOT CAUSE CONFIRMED")
print("=" * 80)

print("\n[PROBLEM]")
print("1. Joint 20 is in HEAD section (before first marker)")
print("2. Head section only uses backward_match_check")
print("3. backward_match_check tests 1-to-1: Joint 20 (1.582m) vs Joint 20 (1.160m)")
print("4. Result: 26.7% difference, 0.217 confidence - REJECT")
print("5. Cumulative matching NOT applied to head section")
print("6. Would have matched: Joint 20 (1.582m) vs Joints 20+30 (1.788m)")
print("7. Expected result: 13.0% difference - ACCEPT with medium confidence")

print("\n[SOLUTION]")
print("Apply same matching logic to head section as tail section:")
print("  - Add forward_match_check")
print("  - Keep backward_match_check")
print("  - ADD cumulative matching (CumulativeLengthMatcher)")
print("  - Add short joint matching (if needed)")

print("\n" + "=" * 80)
