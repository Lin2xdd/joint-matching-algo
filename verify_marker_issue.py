"""
Verify that joint 390 is in a single-joint chunk between markers
"""
import pandas as pd
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
master_df = joint_list.loc[joint_list["insp_guid"] == master_guid].copy()
target_df = joint_list.loc[joint_list["insp_guid"] == target_guid].copy()

master_df['joint_number'] = master_df['joint_number'].astype(float)
target_df['joint_number'] = target_df['joint_number'].astype(float)
master_df = master_df.sort_values('joint_number').reset_index(drop=True)
target_df = target_df.sort_values('joint_number').reset_index(drop=True)

# Calculate differences (for marker detection)
master_df['difference'] = master_df.joint_length.shift(-1) - master_df.joint_length
master_df['difference'] = master_df['difference'].fillna(0)
target_df['difference'] = target_df.joint_length.shift(-1) - target_df.joint_length
target_df['difference'] = target_df['difference'].fillna(0)

large_diff = 3
master_markers = master_df[abs(master_df.difference) > large_diff]
target_markers = target_df[abs(target_df.difference) > large_diff]

print("=" * 80)
print("VERIFYING MARKER ISSUE FOR JOINT 390")
print("=" * 80)

print(f"\nMaster markers found: {len(master_markers)}")
print(f"Target markers found: {len(target_markers)}")

# Find markers around joint 390
joint_390_idx = master_df[master_df['joint_number'] == 390].index[0]
print(f"\nJoint 390 is at index {joint_390_idx}")

markers_around = master_markers[(master_markers.index >= joint_390_idx - 5) & (master_markers.index <= joint_390_idx + 5)]
print(f"\nMarkers within 5 positions of joint 390:")
print(markers_around[['joint_number', 'joint_length', 'difference']].to_string())

# Check joints 375-405
context = master_df[(master_df['joint_number'] >= 375) & (master_df['joint_number'] <= 405)]
print(f"\nMaster joints 375-405 with difference >3m highlighted:")
for idx, row in context.iterrows():
    marker_flag = " ← MARKER" if abs(row['difference']) > 3 else ""
    target_flag = " ← TARGET (390)" if row['joint_number'] == 390 else ""
    print(f"  Index {idx}: Joint {row['joint_number']:.0f}, Length {row['joint_length']:.3f}m, Diff {row['difference']:.3f}m{marker_flag}{target_flag}")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print("If joint 390 is between two markers (joints with large length differences),")
print("it forms a SINGLE-JOINT CHUNK that forward/backward matching skips.")
print("Forward/backward matching requires at least 2-3 consecutive joints to validate")
print("a match pattern, so single-joint chunks are not processed.")
print("=" * 80)
