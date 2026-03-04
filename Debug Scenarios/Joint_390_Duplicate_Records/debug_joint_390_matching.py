"""
Debug script to understand why joint 390 is not matching
"""
import pandas as pd
from sqlalchemy import create_engine, text
import numpy as np

# Database connection
engine = create_engine('postgresql://postgres:RedPlums2025.@localhost:5432/joint-matching')

# GUIDs
master_guid = "6f69d5d6-4d0e-4c16-a66d-207d03017b12"  # ILI-23
target_guid = "d7c49f3d-7da7-49ff-9c2b-c09d388b74ba"  # ILI-19

print("=" * 80)
print("DEBUGGING: Why Joint 390 is not matching")
print("=" * 80)

# Query database
placeholders = ':guid0,:guid1'
joint_query = text(f"""
    SELECT DISTINCT
           joint_number,
           joint_length,
           iliyr,
           insp_guid,
           ili_id
    FROM public.joint_length
    WHERE insp_guid IN ({placeholders})
    ORDER BY insp_guid, joint_number
""")

params = {'guid0': master_guid, 'guid1': target_guid}

with engine.connect() as conn:
    joint_list = pd.read_sql_query(con=conn, sql=joint_query, params=params)
    
    print(f"\n1. Raw query returned {len(joint_list)} records")
    
    # Drop nulls
    smaller_subset = ['joint_number', 'joint_length', 'insp_guid', 'ili_id']
    joint_list = joint_list.dropna(subset=smaller_subset).reset_index(drop=True)
    
    # Deduplicate
    records_before = len(joint_list)
    joint_list = joint_list.drop_duplicates(
        subset=['insp_guid', 'joint_number'], 
        keep='first'
    ).reset_index(drop=True)
    records_after = len(joint_list)
    
    print(f"2. After deduplication: {records_before} -> {records_after} ({records_before - records_after} removed)")

# Prepare datasets
joint_list["insp_guid"] = joint_list["insp_guid"].astype("str")

master_df = joint_list.loc[joint_list["insp_guid"] == master_guid].copy()
target_df = joint_list.loc[joint_list["insp_guid"] == target_guid].copy()

master_df['joint_number'] = master_df['joint_number'].astype(float)
target_df['joint_number'] = target_df['joint_number'].astype(float)

master_df = master_df.sort_values('joint_number').reset_index(drop=True)
target_df = target_df.sort_values('joint_number').reset_index(drop=True)

print(f"\n3. Master (ILI-23): {len(master_df)} joints")
print(f"   Target (ILI-19): {len(target_df)} joints")

# Check joint 390
master_390 = master_df[master_df['joint_number'] == 390]
target_390 = target_df[target_df['joint_number'] == 390]

print(f"\n4. Joint 390 Status:")
print(f"   Master (ILI-23) Joint 390: {'FOUND' if not master_390.empty else 'NOT FOUND'}")
if not master_390.empty:
    print(f"      Length: {master_390['joint_length'].iloc[0]}m")
    print(f"      Index: {master_390.index[0]}")
    
print(f"   Target (ILI-19) Joint 390: {'FOUND' if not target_390.empty else 'NOT FOUND'}")
if not target_390.empty:
    print(f"      Length: {target_390['joint_length'].iloc[0]}m")
    print(f"      Index: {target_390.index[0]}")

if not master_390.empty and not target_390.empty:
    m_len = master_390['joint_length'].iloc[0]
    t_len = target_390['joint_length'].iloc[0]
    diff = abs(m_len - t_len)
    avg = (m_len + t_len) / 2
    pct = (diff / avg) * 100
    print(f"\n5. Length Comparison:")
    print(f"   Difference: {diff:.3f}m ({pct:.2f}%)")
    print(f"   Within 20% tolerance: {pct <= 20}")
    
    # Calculate confidence
    confidence = 1.0 - (diff / avg) / 0.20
    confidence = max(0.0, min(1.0, confidence))
    print(f"   Confidence score: {confidence:.3f} ({confidence*100:.1f}%)")
    print(f"   Above 60% threshold: {confidence >= 0.60}")

# Check surrounding joints
print(f"\n6. Surrounding Joints in Master (ILI-23):")
master_context = master_df[(master_df['joint_number'] >= 385) & (master_df['joint_number'] <= 395)]
print(master_context[['joint_number', 'joint_length']].to_string(index=True))

print(f"\n7. Surrounding Joints in Target (ILI-19):")
target_context = target_df[(target_df['joint_number'] >= 385) & (target_df['joint_number'] <= 395)]
print(target_context[['joint_number', 'joint_length']].to_string(index=True))

# Check if they're in the same region or separated by markers
if not master_390.empty and not target_390.empty:
    m_idx = master_390.index[0]
    t_idx = target_390.index[0]
    
    print(f"\n8. Position Analysis:")
    print(f"   Master joint 390 at index: {m_idx} of {len(master_df)}")
    print(f"   Target joint 390 at index: {t_idx} of {len(target_df)}")
    
    # Check for large differences before/after (markers)
    if m_idx > 0:
        master_df['difference'] = master_df.joint_length.shift(-1) - master_df.joint_length
        master_df['difference'] = master_df['difference'].fillna(0)
        
        # Check for markers near joint 390
        large_diff = 3
        markers_before = master_df[(master_df.index < m_idx) & (abs(master_df['difference']) > large_diff)]
        markers_after = master_df[(master_df.index > m_idx) & (abs(master_df['difference']) > large_diff)]
        
        print(f"   Markers before joint 390 in master: {len(markers_before)}")
        if len(markers_before) > 0:
            print(f"      Closest marker at index {markers_before.index[-1]} (joint {master_df.loc[markers_before.index[-1], 'joint_number']})")
        
        print(f"   Markers after joint 390 in master: {len(markers_after)}")
        if len(markers_after) > 0:
            print(f"      Closest marker at index {markers_after.index[0]} (joint {master_df.loc[markers_after.index[0], 'joint_number']})")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
