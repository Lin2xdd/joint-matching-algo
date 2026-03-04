"""
Test the forward matching logic specifically for joint 390
"""
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import sys
sys.path.append('Scripts')
from integrated_joint_matching import _evaluate_match_quality

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

print("=" * 80)
print("TESTING FORWARD MATCHING FOR JOINT 390")
print("=" * 80)

# Simulate the chunk that contains joint 390
# Based on the trace, chunk is from marker at index 36 to marker at index 38
init_fix = 36
end_fix = 38
init_move = 37  # Assuming similar offset in target
end_move = 39

print(f"\nChunk parameters:")
print(f"  Master: indices {init_fix} to {end_fix}")
print(f"  Target: indices {init_move} to {end_move}")

# Show what joints are in this range
print(f"\nMaster joints in range:")
for idx in range(init_fix, end_fix + 1):
    print(f"  Index {idx}: Joint {fix_df.loc[idx, 'joint_number']:.0f}, Length {fix_df.loc[idx, 'joint_length']:.3f}m")

print(f"\nTarget joints in range:")
for idx in range(init_move, end_move + 1):
    print(f"  Index {idx}: Joint {move_df.loc[idx, 'joint_number']:.0f}, Length {move_df.loc[idx, 'joint_length']:.3f}m")

# Simulate forward_match_check logic
min_move = int(min(end_move - init_move, end_fix - init_fix))
print(f"\nForward matching will check {min_move + 1} pairs (i=0 to i={min_move})")

for i in range(min_move + 1):
    print(f"\n--- Iteration i={i} ---")
    fix_idx = init_fix + i
    move_idx = init_move + i
    
    print(f"Checking: Master[{fix_idx}] vs Target[{move_idx}]")
    print(f"  Master joint {fix_df.loc[fix_idx, 'joint_number']:.0f}: {fix_df.loc[fix_idx, 'joint_length']:.3f}m")
    print(f"  Target joint {move_df.loc[move_idx, 'joint_number']:.0f}: {move_df.loc[move_idx, 'joint_length']:.3f}m")
    
    pair1_len_fix = fix_df.iloc[fix_idx]['joint_length']
    pair1_len_move = move_df.iloc[move_idx]['joint_length']
    pair1_accept, pair1_score, pair1_tier = _evaluate_match_quality(
        pair1_len_fix, pair1_len_move, confidence_threshold=0.60, tolerance=0.20
    )
    
    print(f"  Match quality: accept={pair1_accept}, score={pair1_score:.3f}, tier={pair1_tier}")
    
    if pair1_accept:
        print(f"  >>> WOULD BE MATCHED <<<")
    else:
        print(f"  >>> REJECTED <<<")
        print(f"  >>> Forward matching would BREAK here <<<")
        break

print("\n" + "=" * 80)
