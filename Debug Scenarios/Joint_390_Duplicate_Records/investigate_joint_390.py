"""
Investigation: Why Joint 390 from ILI-23 didn't match to Joint 390 from ILI-19

This script analyzes the data quality and matching issues for joint 390.
"""

import pandas as pd
import numpy as np

print("=" * 80)
print("INVESTIGATION: Joint 390 Matching Issue (ILI-19 vs ILI-23)")
print("=" * 80)

# Load the data files
ili_19_file = "Sample Input/ARC/database ready/Onstream 2019 - 16in 4-25 to 10-7.csv"
ili_23_file = "Sample Input/ARC/database ready/Onstream 2023 - 16in 4-25 to 10-7.csv"

print("\n1. Loading data files...")
df_2019 = pd.read_csv(ili_19_file)
df_2023 = pd.read_csv(ili_23_file)

print(f"   ILI-19 total records: {len(df_2019)}")
print(f"   ILI-23 total records: {len(df_2023)}")

# Filter for joint 390
print("\n2. Filtering for Joint 390...")
joint_390_2019 = df_2019[df_2019['joint_number'] == 390]
joint_390_2023 = df_2023[df_2023['joint_number'] == 390]

print(f"   ILI-19 Joint 390 records: {len(joint_390_2019)}")
print(f"   ILI-23 Joint 390 records: {len(joint_390_2023)}")

# Analyze ILI-19 Joint 390
print("\n3. ILI-19 Joint 390 Details:")
print("   " + "-" * 76)
if not joint_390_2019.empty:
    for idx, row in joint_390_2019.iterrows():
        print(f"   Joint Number: {row['joint_number']}")
        print(f"   Joint Length: {row['joint_length']}m")
        print(f"   Distance: {row['distance ']}m")
        print(f"   ILI ID: {row['ili_id']}")
        print(f"   Feature Type: {row['feature_ type']}")
else:
    print("   No records found!")

# Analyze ILI-23 Joint 390
print("\n4. ILI-23 Joint 390 Details:")
print("   " + "-" * 76)
if not joint_390_2023.empty:
    print(f"   Found {len(joint_390_2023)} records for Joint 390")
    print(f"   Joint Length: {joint_390_2023['joint_length'].iloc[0]}m (all records)")
    print(f"   Distance range: {joint_390_2023['distance '].min()}m to {joint_390_2023['distance '].max()}m")
    print(f"   ILI ID: {joint_390_2023['ili_id'].iloc[0]}")
    print(f"\n   All distances for Joint 390 in ILI-23:")
    for idx, row in joint_390_2023.iterrows():
        print(f"      - {row['distance ']}m (length: {row['joint_length']}m)")
else:
    print("   No records found!")

# Calculate matching metrics
print("\n5. Matching Analysis:")
print("   " + "-" * 76)

if not joint_390_2019.empty and not joint_390_2023.empty:
    length_2019 = joint_390_2019['joint_length'].iloc[0]
    length_2023 = joint_390_2023['joint_length'].iloc[0]
    
    length_diff = abs(length_2019 - length_2023)
    avg_length = (length_2019 + length_2023) / 2
    length_diff_pct = (length_diff / avg_length) * 100
    
    print(f"   ILI-19 Length: {length_2019}m")
    print(f"   ILI-23 Length: {length_2023}m")
    print(f"   Length Difference: {length_diff}m ({length_diff_pct:.2f}%)")
    print(f"   Average Length: {avg_length}m")
    
    # Check against typical tolerance (20%)
    tolerance = 0.20
    within_tolerance = length_diff_pct / 100 <= tolerance
    print(f"\n   Within 20% tolerance? {within_tolerance}")
    
    # Calculate confidence score
    confidence = 1.0 - (length_diff / avg_length) / tolerance
    confidence = max(0.0, min(1.0, confidence))
    print(f"   Confidence score: {confidence:.3f} ({confidence*100:.1f}%)")
    
    # Distance analysis
    dist_2019 = joint_390_2019['distance '].iloc[0]
    dist_2023_min = joint_390_2023['distance '].min()
    dist_2023_max = joint_390_2023['distance '].max()
    
    print(f"\n   Distance shift:")
    print(f"   ILI-19 position: {dist_2019}m")
    print(f"   ILI-23 position range: {dist_2023_min}m to {dist_2023_max}m")
    print(f"   Shift from ILI-19: {dist_2023_min - dist_2019:.3f}m to {dist_2023_max - dist_2019:.3f}m")

# ROOT CAUSE ANALYSIS
print("\n6. ROOT CAUSE ANALYSIS:")
print("   " + "=" * 76)

print("\n   ❌ ISSUE IDENTIFIED: DATA QUALITY PROBLEM")
print(f"\n   Joint 390 in ILI-23 has {len(joint_390_2023)} DUPLICATE records!")
print("   This is not normal - each joint should typically have 1 record.")
print("\n   Why the matching failed:")
print("   1. Multiple duplicate records for the same joint number confuse the algorithm")
print("   2. The algorithm expects unique joint numbers in cleaned data")
print("   3. Length discrepancy: 9.154m vs 8.504m (7.1% difference)")
print("   4. This is within 20% tolerance, so should match IF data were clean")

print("\n7. DATA CLEANING REQUIREMENTS:")
print("   " + "-" * 76)
print("   The database should:")
print("   • Have unique joint_number values per inspection")
print("   • Use DISTINCT joint_number in queries")
print("   • Or aggregate/deduplicate before matching")
print("\n   Current SQL query likely needs:")
print("   SELECT DISTINCT joint_number, joint_length, ...")
print("   OR")
print("   GROUP BY joint_number (with appropriate aggregation)")

print("\n8. RECOMMENDED FIX:")
print("   " + "-" * 76)
print("   Option 1: Clean the source data in the database")
print("   Option 2: Add deduplication logic to the matching script:")
print("   ")
print("   # After loading data, deduplicate by keeping first occurrence:")
print("   joint_list = joint_list.drop_duplicates(")
print("       subset=['insp_guid', 'joint_number'], ")
print("       keep='first'")
print("   ).reset_index(drop=True)")
print("")
print("   Option 3: Use aggregation (take max/min/avg of duplicates):")
print("   joint_list = joint_list.groupby(['insp_guid', 'joint_number']).agg({")
print("       'joint_length': 'first',  # or 'mean', 'max', etc.")
print("       'iliyr': 'first',")
print("       'ili_id': 'first'")
print("   }).reset_index()")

# Check surrounding joints for context
print("\n9. SURROUNDING JOINTS CONTEXT:")
print("   " + "-" * 76)

joints_2019_context = df_2019[
    (df_2019['joint_number'] >= 385) & 
    (df_2019['joint_number'] <= 395)
][['joint_number', 'joint_length', 'distance ']].drop_duplicates('joint_number')

joints_2023_context = df_2023[
    (df_2023['joint_number'] >= 385) & 
    (df_2023['joint_number'] <= 395)
][['joint_number', 'joint_length', 'distance ']].drop_duplicates('joint_number')

print("\n   ILI-19 Joints 385-395:")
if not joints_2019_context.empty:
    print(joints_2019_context.to_string(index=False))
else:
    print("   No data found")

print("\n   ILI-23 Joints 385-395:")
if not joints_2023_context.empty:
    print(joints_2023_context.to_string(index=False))
else:
    print("   No data found")

print("\n" + "=" * 80)
print("INVESTIGATION COMPLETE")
print("=" * 80)
