"""
Debug script to investigate why joint 20 from ILI-23 didn't match to 20 & 30 from ILI-19.
"""

import pandas as pd

# Load the CSV files
ili_23_path = "Sample Input/ARC/database ready/Onstream 2023 - 16in 4-25 to 10-7.csv"
ili_19_path = "Sample Input/ARC/database ready/Onstream 2019 - 16in 4-25 to 10-7.csv"

print("=" * 80)
print("INVESTIGATING JOINT 20 MATCHING ISSUE")
print("=" * 80)
print()

# Read the data
ili_23 = pd.read_csv(ili_23_path)
ili_19 = pd.read_csv(ili_19_path)

# Focus on the region around joint 20
print("ILI-23 DATA (joints 10-50):")
print("-" * 80)
ili_23_region = ili_23[(ili_23['joint_number'] >= 10) & (ili_23['joint_number'] <= 50)]
print(ili_23_region[['joint_number', 'distance ', 'joint_length']].to_string(index=False))
print()

print("ILI-19 DATA (joints 10-50):")
print("-" * 80)
ili_19_region = ili_19[(ili_19['joint_number'] >= 10) & (ili_19['joint_number'] <= 50)]
print(ili_19_region[['joint_number', 'distance ', 'joint_length']].to_string(index=False))
print()

# Get specific joints
ili_23_20 = ili_23[ili_23['joint_number'] == 20].iloc[0]
ili_19_20 = ili_19[ili_19['joint_number'] == 20].iloc[0]
ili_19_30 = ili_19[ili_19['joint_number'] == 30].iloc[0]

print("SPECIFIC JOINT DATA:")
print("-" * 80)
print(f"ILI-23 Joint 20: {ili_23_20['joint_length']}m")
print(f"ILI-19 Joint 20: {ili_19_20['joint_length']}m")
print(f"ILI-19 Joint 30: {ili_19_30['joint_length']}m")
print(f"ILI-19 Joints 20+30: {ili_19_20['joint_length'] + ili_19_30['joint_length']}m")
print()

target = ili_23_20['joint_length']
combo = ili_19_20['joint_length'] + ili_19_30['joint_length']
diff = abs(target - combo)
diff_pct = (diff / target) * 100 if target > 0 else 0

print("MATCH ANALYSIS:")
print("-" * 80)
print(f"Target length (ILI-23 joint 20): {target}m")
print(f"Combination 20+30 length: {combo}m")
print(f"Difference: {diff}m ({diff_pct:.1f}%)")
print(f"Within 30% tolerance: {'YES' if diff_pct <= 30 else 'NO'}")
print()

# Calculate confidence
if target > 0:
    diff_ratio = diff / max(target, combo)
    confidence = 1.0 - (diff_ratio / 0.30)  # 30% tolerance
    confidence = max(0.0, min(1.0, confidence))
    # Apply penalty for 2-joint combination
    penalty = 0.05 * 1  # One additional joint beyond first
    final_confidence = max(confidence - penalty, 0.0)
    
    print(f"Base confidence: {confidence:.3f}")
    print(f"Penalty (5% for 1 extra joint): -{penalty:.3f}")
    print(f"Final confidence: {final_confidence:.3f}")
    print(f"Passes 60% confidence threshold: {'YES' if final_confidence > 0.60 else 'NO'}")
    print()

# Check for markers
print("CHECKING FOR MARKERS:")
print("-" * 80)
ili_23_markers = ili_23[ili_23['joint_number'].isin([10, 20, 30, 40, 50])]
ili_19_markers = ili_19[ili_19['joint_number'].isin([10, 20, 30, 40, 50])]

print("ILI-23 joints 10-50 (checking for markers in feature_type):")
if 'feature_ type' in ili_23.columns:
    for _, row in ili_23_markers.iterrows():
        if pd.notna(row['feature_ type']):
            print(f"  Joint {row['joint_number']}: {row['feature_ type']}")

print()
print("ILI-19 joints 10-50 (checking for markers in feature_type):")
if 'feature_ type' in ili_19.columns:
    for _, row in ili_19_markers.iterrows():
        if pd.notna(row['feature_ type']):
            print(f"  Joint {row['joint_number']}: {row['feature_ type']}")

print()
print("=" * 80)
print("POSSIBLE REASONS:")
print("=" * 80)
print("1. Joint 20 may have been matched in the marker alignment phase")
print("2. Joint 20 may have been matched in the forward/backward phase")
print("3. Joint 20 may be part of an earlier chunk that matched differently")
print("4. The confidence might not pass the threshold")
print()
print("Check the matching log to see when/how joint 20 was processed.")
