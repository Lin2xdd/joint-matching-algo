"""
Debug script to investigate why joint 4480 from ILI-23 didn't match to 4510 from ILI-19.
"""

import pandas as pd
import json

# Load the CSV files
ili_23_path = "Sample Input/ARC/database ready/Onstream 2023 - 16in 4-25 to 10-7.csv"
ili_19_path = "Sample Input/ARC/database ready/Onstream 2019 - 16in 4-25 to 10-7.csv"

print("=" * 80)
print("INVESTIGATING JOINT 4480 MATCHING ISSUE")
print("=" * 80)
print()

# Read the data
ili_23 = pd.read_csv(ili_23_path)
ili_19 = pd.read_csv(ili_19_path)

# Focus on the region around joint 4480
print("ILI-23 DATA (joints 4470-4530):")
print("-" * 80)
ili_23_region = ili_23[(ili_23['joint_number'] >= 4470) & (ili_23['joint_number'] <= 4530)]
print(ili_23_region[['joint_number', 'distance ', 'joint_length']].to_string(index=False))
print()

print("ILI-19 DATA (joints 4470-4530):")
print("-" * 80)
ili_19_region = ili_19[(ili_19['joint_number'] >= 4470) & (ili_19['joint_number'] <= 4530)]
print(ili_19_region[['joint_number', 'distance ', 'joint_length']].to_string(index=False))
print()

# Calculate cumulative lengths
print("CUMULATIVE LENGTH ANALYSIS:")
print("-" * 80)

# ILI-23 joint 4480
ili_23_4480 = ili_23[ili_23['joint_number'] == 4480].iloc[0]
print(f"ILI-23 Joint 4480:")
print(f"  Distance: {ili_23_4480['distance ']}")
print(f"  Length: {ili_23_4480['joint_length']}")
print()

# ILI-19 joints around 4480
print("ILI-19 Joint Lengths:")
ili_19_4470 = ili_19[ili_19['joint_number'] == 4470].iloc[0]
ili_19_4480 = ili_19[ili_19['joint_number'] == 4480].iloc[0]
ili_19_4490 = ili_19[ili_19['joint_number'] == 4490].iloc[0]
ili_19_4500 = ili_19[ili_19['joint_number'] == 4500].iloc[0]
ili_19_4510 = ili_19[ili_19['joint_number'] == 4510].iloc[0]
ili_19_4520 = ili_19[ili_19['joint_number'] == 4520].iloc[0]

print(f"  4470: {ili_19_4470['joint_length']}")
print(f"  4480: {ili_19_4480['joint_length']}")
print(f"  4490: {ili_19_4490['joint_length']}")
print(f"  4500: {ili_19_4500['joint_length']}")
print(f"  4510: {ili_19_4510['joint_length']}")
print(f"  4520: {ili_19_4520['joint_length']}")
print()

# Calculate possible combinations
combinations = [
    ("4480", [ili_19_4480['joint_length']]),
    ("4480+4490", [ili_19_4480['joint_length'], ili_19_4490['joint_length']]),
    ("4480+4490+4500", [ili_19_4480['joint_length'], ili_19_4490['joint_length'], ili_19_4500['joint_length']]),
    ("4480+4490+4510", [ili_19_4480['joint_length'], ili_19_4490['joint_length'], ili_19_4510['joint_length']]),
    ("4480+4490+4500+4510", [ili_19_4480['joint_length'], ili_19_4490['joint_length'], 
                              ili_19_4500['joint_length'], ili_19_4510['joint_length']]),
]

print("POSSIBLE CUMULATIVE MATCHES:")
print("-" * 80)
target_length = ili_23_4480['joint_length']
print(f"Target length (ILI-23 4480): {target_length}")
print()

for combo_name, lengths in combinations:
    total = sum(lengths)
    diff = abs(total - target_length)
    pct_diff = (diff / target_length) * 100 if target_length > 0 else 0
    print(f"{combo_name}:")
    print(f"  Total: {total:.3f}")
    print(f"  Difference: {diff:.3f} ({pct_diff:.1f}%)")
    print(f"  Within 30% tolerance: {'YES' if pct_diff <= 30 else 'NO'}")
    print()

# Check the matching results
print("CHECKING ACTUAL MATCHING RESULTS:")
print("-" * 80)
try:
    with open('joint_matching_results.json', 'r') as f:
        results = json.load(f)
    
    # The results show ILI-19 as master, ILI-17 as target, which is different
    print(f"Results file shows:")
    print(f"  Master: {results['run_summary']['Master_ili_id']}")
    print(f"  Target: {results['run_summary']['Target_ili_id']}")
    print()
    print("NOTE: This doesn't match the ILI-23 vs ILI-19 comparison you're asking about.")
    print("The actual matching run appears to be different from what you're referring to.")
except Exception as e:
    print(f"Could not load matching results: {e}")

print()
print("=" * 80)
print("ANALYSIS SUMMARY")
print("=" * 80)
print()
print("Key observations:")
print(f"1. ILI-23 joint 4480 has length: {ili_23_4480['joint_length']}")
print(f"2. ILI-19 joints 4480+4490 total: {ili_19_4480['joint_length'] + ili_19_4490['joint_length']:.3f}")
print(f"3. ILI-19 joints 4480+4490+4510 total: {ili_19_4480['joint_length'] + ili_19_4490['joint_length'] + ili_19_4510['joint_length']:.3f}")
print()

# Note about 4500
print("IMPORTANT: Joint 4500 is BETWEEN 4490 and 4510!")
print(f"ILI-19 joint 4500 length: {ili_19_4500['joint_length']}")
print(f"Distance 4490: {ili_19_4490['distance ']}")
print(f"Distance 4500: {ili_19_4500['distance ']}")
print(f"Distance 4510: {ili_19_4510['distance ']}")
print()
print("The cumulative matching algorithm requires CONSECUTIVE joints.")
print("To include 4510, we would need to include 4500 as well.")
print(f"That would give: 4480+4490+4500+4510 = {sum([ili_19_4480['joint_length'], ili_19_4490['joint_length'], ili_19_4500['joint_length'], ili_19_4510['joint_length']]):.3f}")
print()
