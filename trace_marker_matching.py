"""
Trace the actual marker matching logic to see what pairs are being created
"""
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:RedPlums2025.@localhost:5432/joint-matching')

master_guid = "6f69d5d6-4d0e-4c16-a66d-207d03017b12"  # ILI-23
target_guid = "d7c49f3d-7da7-49ff-9c2b-c09d388b74ba"  # ILI-19

joint_query = text("""
    SELECT DISTINCT
           joint_number,
           joint_length,
           iliyr,
           insp_guid,
           ili_id
    FROM public.joint_length
    WHERE insp_guid IN (:guid0,:guid1)
    ORDER BY insp_guid, joint_number
""")

with engine.connect() as conn:
    joint_list = pd.read_sql_query(con=conn, sql=joint_query, params={'guid0': master_guid, 'guid1': target_guid})
    joint_list = joint_list.dropna(subset=['joint_number', 'joint_length', 'insp_guid', 'ili_id']).reset_index(drop=True)
    joint_list = joint_list.drop_duplicates(subset=['insp_guid', 'joint_number'], keep='first').reset_index(drop=True)

joint_list["insp_guid"] = joint_list["insp_guid"].astype("str")
fix_df = joint_list.loc[joint_list["insp_guid"] == master_guid].copy()
move_df = joint_list.loc[joint_list["insp_guid"] == target_guid].copy()

fix_df['joint_number'] = fix_df['joint_number'].astype(float)
move_df['joint_number'] = move_df['joint_number'].astype(float)
fix_df = fix_df.sort_values('joint_number').reset_index(drop=True)
move_df = move_df.sort_values('joint_number').reset_index(drop=True)

# Calculate differences
fix_df['difference'] = fix_df.joint_length.shift(-1) - fix_df.joint_length
fix_df['difference'] = fix_df['difference'].fillna(0)
move_df['difference'] = move_df.joint_length.shift(-1) - move_df.joint_length
move_df['difference'] = move_df['difference'].fillna(0)

large_diff = 3
move_marker = move_df[abs(move_df.difference) > large_diff]
fix_marker = fix_df[abs(fix_df.difference) > large_diff]

print("=" * 80)
print("TRACING MARKER MATCHING ALGORITHM")
print("=" * 80)

print(f"\nMaster markers around 370-420:")
fix_markers_context = fix_marker[(fix_marker['joint_number'] >= 370) & (fix_marker['joint_number'] <= 420)]
for idx, row in fix_markers_context.iterrows():
    print(f"  Index {idx}: Joint {row['joint_number']:.0f}, diff={row['difference']:.3f}m")

print(f"\nTarget markers around 370-420:")
move_markers_context = move_marker[(move_marker['joint_number'] >= 370) & (move_marker['joint_number'] <= 420)]
for idx, row in move_markers_context.iterrows():
    print(f"  Index {idx}: Joint {row['joint_number']:.0f}, diff={row['difference']:.3f}m")

print("\n" + "=" * 80)
print("SIMULATING MARKER MATCHING LOGIC")
print("=" * 80)

# Simplified marker matching logic
# Starting after marker 380
j = 36  # Index of marker 380 in master
temp_move_match = 37  # Index of marker 380 in target

print(f"\nStarting from matched marker pair:")
print(f"  Master index {j}: Joint {fix_df.loc[j, 'joint_number']:.0f}")
print(f"  Target index {temp_move_match}: Joint {move_df.loc[temp_move_match, 'joint_number']:.0f}")

# Look for next marker in target starting after index 37
next_move_markers = move_marker[move_marker.index > temp_move_match].head(5)
print(f"\nNext target markers after index {temp_move_match}:")
for idx, row in next_move_markers.iterrows():
    print(f"  Index {idx}: Joint {row['joint_number']:.0f}, Length={row['joint_length']:.3f}m, Diff={row['difference']:.3f}m")
    
    # Try to find match in master markers
    print(f"    Looking for master marker with similar properties...")
    
    # Check if there's a master marker with similar joint_length and difference
    for fix_idx, fix_row in fix_marker[fix_marker.index > j].head(5).iterrows():
        length_match = abs(row['joint_length'] - fix_row['joint_length']) < 1
        diff_match = abs(row['difference'] - fix_row['difference']) < 1
        
        if length_match and diff_match:
            print(f"      POTENTIAL MATCH: Master index {fix_idx}, Joint {fix_row['joint_number']:.0f}")
            print(f"        Length: {fix_row['joint_length']:.3f}m vs {row['joint_length']:.3f}m")
            print(f"        Diff: {fix_row['difference']:.3f}m vs {row['difference']:.3f}m")
            break
    else:
        print(f"      No close match found in master markers")

print("\n" + "=" * 80)
print("EXPECTED BEHAVIOR:")
print("=" * 80)
print("The algorithm should:")
print("1. Start from matched marker 380 (both at their respective indices)")
print("2. Look at next target marker: 390 at index 38")
print("3. Try to match it with master markers starting after 380")
print("4. Not find a good match (390 in target doesn't align with 400 in master)")
print("5. Continue to next target marker: 400 at index 39")
print("6. Match it with master marker 400 at index 38")
print("7. Create chunk: Master[36 to 38] <-> Target[37 to 39]")
print("8. This chunk should include joint 390!")
print("=" * 80)
