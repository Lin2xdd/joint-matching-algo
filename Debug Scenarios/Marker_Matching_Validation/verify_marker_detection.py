"""
Verify exactly which joints are detected as markers
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
fix_markers = fix_df[abs(fix_df.difference) > large_diff]
move_markers = move_df[abs(move_df.difference) > large_diff]

print("=" * 80)
print("MARKER DETECTION ANALYSIS")
print("=" * 80)

print(f"\nILI-23 (Master) - Markers detected (|diff| > {large_diff}m):")
print(f"Total markers: {len(fix_markers)}")
markers_around_390 = fix_markers[(fix_markers['joint_number'] >= 370) & (fix_markers['joint_number'] <= 420)]
print(f"\nMarkers between joints 370-420:")
print(markers_around_390[['joint_number', 'joint_length', 'difference']].to_string())

print(f"\n\nILI-19 (Target) - Markers detected (|diff| > {large_diff}m):")
print(f"Total markers: {len(move_markers)}")
markers_around_390_target = move_markers[(move_markers['joint_number'] >= 370) & (move_markers['joint_number'] <= 420)]
print(f"\nMarkers between joints 370-420:")
print(markers_around_390_target[['joint_number', 'joint_length', 'difference']].to_string())

print("\n" + "=" * 80)
print("JOINT 400 STATUS:")
print("=" * 80)

fix_400 = fix_df[fix_df['joint_number'] == 400]
if not fix_400.empty:
    diff_400 = fix_400['difference'].iloc[0]
    print(f"\nILI-23 Joint 400:")
    print(f"  Index: {fix_400.index[0]}")
    print(f"  Length: {fix_400['joint_length'].iloc[0]}m")
    print(f"  Difference to next joint: {diff_400}m")
    print(f"  Absolute difference: {abs(diff_400)}m")
    print(f"  Is marker (|diff| > 3): {abs(diff_400) > 3}")

move_400 = move_df[move_df['joint_number'] == 400]
if not move_400.empty:
    diff_400_target = move_400['difference'].iloc[0]
    print(f"\nILI-19 Joint 400:")
    print(f"  Index: {move_400.index[0]}")
    print(f"  Length: {move_400['joint_length'].iloc[0]}m")
    print(f"  Difference to next joint: {diff_400_target}m")
    print(f"  Absolute difference: {abs(diff_400_target)}m")
    print(f"  Is marker (|diff| > 3): {abs(diff_400_target) > 3}")

print("\n" + "=" * 80)
