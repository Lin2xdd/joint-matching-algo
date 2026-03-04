"""
Trace exactly how chunks are processed around joint 390
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
fix_df = fix_df.reset_index(drop=True)

move_df['difference'] = move_df.joint_length.shift(-1) - move_df.joint_length
move_df['difference'] = move_df['difference'].fillna(0)
move_df = move_df.reset_index(drop=True)

# Find markers
large_diff = 3
fix_marker = fix_df[abs(fix_df.difference) > large_diff]
move_marker = move_df[abs(move_df.difference) > large_diff]

print("=" * 80)
print("TRACING CHUNK PROCESSING AROUND JOINT 390")
print("=" * 80)

# Find marker matches (simplified version of the algorithm)
Match_df = pd.DataFrame([], columns=['FIX_ID', 'MOVE_ID', 'CONFIDENCE', 'SOURCE'])

# Simulate marker matching around joint 390
# Look for markers near joint 390
joint_390_fix_idx = fix_df[fix_df['joint_number'] == 390].index[0]
joint_390_move_idx = move_df[move_df['joint_number'] == 390].index[0]

print(f"\nJoint 390 location:")
print(f"  Master (ILI-23) index: {joint_390_fix_idx}")
print(f"  Target (ILI-19) index: {joint_390_move_idx}")

# Find markers before and after 390 in master
markers_before_390 = fix_marker[fix_marker.index < joint_390_fix_idx]
markers_after_390 = fix_marker[fix_marker.index > joint_390_fix_idx]

print(f"\nMarkers before joint 390 in master:")
if not markers_before_390.empty:
    last_before = markers_before_390.tail(3)
    print(last_before[['joint_number', 'joint_length', 'difference']].to_string())
else:
    print("  None")

print(f"\nMarkers after joint 390 in master:")
if not markers_after_390.empty:
    first_after = markers_after_390.head(3)
    print(first_after[['joint_number', 'joint_length', 'difference']].to_string())
else:
    print("  None")

# Show the chunk that contains joint 390
if not markers_before_390.empty and not markers_after_390.empty:
    chunk_start_idx = markers_before_390.index[-1]
    chunk_end_idx = markers_after_390.index[0]
    
    print(f"\nChunk containing joint 390:")
    print(f"  Start marker: index {chunk_start_idx} (joint {fix_df.loc[chunk_start_idx, 'joint_number']:.0f})")
    print(f"  End marker: index {chunk_end_idx} (joint {fix_df.loc[chunk_end_idx, 'joint_number']:.0f})")
    print(f"  Joints in chunk (indices {chunk_start_idx} to {chunk_end_idx}):")
    
    chunk_df = fix_df.loc[chunk_start_idx:chunk_end_idx]
    for idx, row in chunk_df.iterrows():
        is_marker = "MARKER" if idx in [chunk_start_idx, chunk_end_idx] else ""
        is_390 = "<<< JOINT 390" if row['joint_number'] == 390 else ""
        print(f"    Index {idx}: Joint {row['joint_number']:.0f}, Length {row['joint_length']:.3f}m {is_marker} {is_390}")
    
    # Check if forward matching would process this
    print(f"\n  Forward matching would start at index {chunk_start_idx}")
    print(f"  and end at index {chunk_end_idx}")
    print(f"  This means it processes indices from {chunk_start_idx}+1 to {chunk_end_idx}-1")
    print(f"  Which is: {list(range(chunk_start_idx+1, chunk_end_idx))}")
    
    if joint_390_fix_idx in range(chunk_start_idx+1, chunk_end_idx):
        print(f"\n  ✓ Joint 390 at index {joint_390_fix_idx} IS in the forward matching range!")
    else:
        print(f"\n  ✗ Joint 390 at index {joint_390_fix_idx} is NOT in the forward matching range.")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print("If joint 390 is in the forward matching range but still not matched,")
print("the issue must be in the matching logic itself (threshold, confidence, etc.)")
print("=" * 80)
