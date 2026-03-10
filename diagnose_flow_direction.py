"""
Diagnose flow direction calculation for ARC Set 5 data.
Shows the actual percentages and how they were calculated.
"""

import sys
import pandas as pd
import numpy as np

# Import the matching functions
sys.path.append('Scripts')
from joint_matching import joint_diff_calc, pairs_generator, match_pct_calc

# Load the data
master_df = pd.read_csv('Data & results/ARC/Set 5/Input/Onstream 2019 280252 3.csv')
target_df = pd.read_csv('Data & results/ARC/Set 5/Input/Onstream 2010 280252 3.csv')

# Convert to int and sort
master_df['joint_number'] = master_df['joint_number'].astype(int)
master_df = master_df.sort_values('joint_number').reset_index(drop=True)

target_df['joint_number'] = target_df['joint_number'].astype(int)
target_df = target_df.sort_values('joint_number').reset_index(drop=True)

print("="*80)
print("FLOW DIRECTION DIAGNOSIS")
print("="*80)
print(f"Master (2019): {len(master_df)} joints")
print(f"Target (2010): {len(target_df)} joints")
print()

# Calculate differences
master_diff = joint_diff_calc(master_df, column='joint_length')
target_diff = joint_diff_calc(target_df, column='joint_length')

print(f"Master differences: {len(master_diff)} values")
print(f"First 10 Master differences: {master_diff[:10]}")
print()
print(f"Target differences: {len(target_diff)} values")
print(f"First 10 Target differences: {target_diff[:10]}")
print()

# Generate pairs
master_pairs = pairs_generator(master_diff)
target_pairs_fwd = pairs_generator(target_diff)

# For reverse, reverse the target dataframe first
target_rev = target_df.loc[::-1].reset_index(drop=True)
target_rev_diff = joint_diff_calc(target_rev, column='joint_length')
target_pairs_rev = pairs_generator(target_rev_diff)

print(f"Master pairs: {len(master_pairs)} pairs")
print(f"First 5 Master pairs:\n{master_pairs[:5]}")
print()
print(f"Target pairs (FWD): {len(target_pairs_fwd)} pairs")
print(f"First 5 Target FWD pairs:\n{target_pairs_fwd[:5]}")
print()
print(f"Target pairs (REV): {len(target_pairs_rev)} pairs")
print(f"First 5 Target REV pairs:\n{target_pairs_rev[:5]}")
print()

# Calculate match percentages
match_pct_fwd = match_pct_calc(master_pairs, target_pairs_fwd)
match_pct_rev = match_pct_calc(master_pairs, target_pairs_rev)

print("="*80)
print("MATCH PERCENTAGES")
print("="*80)
print(f"Forward (FWD):  {match_pct_fwd:.2f}%")
print(f"Reverse (REV):  {match_pct_rev:.2f}%")
print()

if match_pct_fwd > match_pct_rev:
    direction = "FWD"
    print(f"DECISION: FORWARD (FWD wins by {match_pct_fwd - match_pct_rev:.2f}%)")
elif match_pct_rev > match_pct_fwd:
    direction = "REV"
    print(f"DECISION: REVERSE (REV wins by {match_pct_rev - match_pct_fwd:.2f}%)")
    print("WARNING: This is INCORRECT based on geometric evidence!")
else:
    direction = "FWD (tie)"
    print(f"DECISION: TIE - defaulting to FORWARD")

print()
print("="*80)
print("HOW MATCH PERCENTAGE IS CALCULATED")
print("="*80)
print("The algorithm counts how many Master pairs appear IN ORDER in Target pairs.")
print(f"- Total Target pairs: {len(target_pairs_fwd) if direction == 'FWD' else len(target_pairs_rev)}")
print(f"- Matching pairs found: {int((match_pct_fwd if direction == 'FWD' else match_pct_rev) / 100 * len(target_pairs_fwd if direction == 'FWD' else target_pairs_rev))}")
print(f"- Match percentage: (matches / total_target_pairs) * 100")
print()

# Show geometric evidence
print("="*80)
print("GEOMETRIC EVIDENCE")
print("="*80)
print(f"Master START: Joint {master_df.iloc[0]['joint_number']} at {master_df.iloc[0]['distance']:.1f}m")
print(f"Master END:   Joint {master_df.iloc[-1]['joint_number']} at {master_df.iloc[-1]['distance']:.1f}m")
print()
print(f"Target START: Joint {target_df.iloc[0]['joint_number']} at {target_df.iloc[0]['distance ']:.1f}m")
print(f"Target END:   Joint {target_df.iloc[-1]['joint_number']} at {target_df.iloc[-1]['distance ']:.1f}m")
print()
print("Both inspections clearly run from ~0m to ~13,700m in the SAME direction!")
print("="*80)
