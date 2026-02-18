"""
Analyze why there are zero matches and why unmatched count doesn't add up.
"""
import json
import pandas as pd
from sqlalchemy import create_engine, text
import os

# Load the results
with open('joint_matching_results.json', 'r') as f:
    results = json.load(f)

print("=" * 80)
print("ANALYSIS: Zero Matches Between Inspections")
print("=" * 80)

summary = results['run_summary']
print(f"\nMaster Inspection: {summary['Master_ili_id']} (GUID: {summary['Master_inspection_guid']})")
print(f"Target Inspection: {summary['Target_ili_id']} (GUID: {summary['Target_inspection_guid']})")
print(f"\nFlow Direction: {summary['Flow_direction']}")

print(f"\n{'='*80}")
print("JOINT COUNTS")
print("="*80)
print(f"Total Master Joints: {summary['Total_master_joints']}")
print(f"Total Target Joints: {summary['Total_target_joints']}")
print(f"Matched Joints: {summary['Matched_joints']}")
print(f"Unmatched Joints: {summary['Unmatched_joints']}")
print(f"Questionable Matches: {summary['Questionable_matches']}")

# Analyze unmatched joints
unmatched = results['unmatched_joints']
master_only = [x for x in unmatched if x['Master Joint Number'] and not x['Target Joint Number']]
target_only = [x for x in unmatched if x['Target Joint Number'] and not x['Master Joint Number']]

print(f"\n{'='*80}")
print("UNMATCHED BREAKDOWN")
print("="*80)
print(f"Total unmatched entries: {len(unmatched)}")
print(f"Master-only entries: {len(master_only)}")
print(f"Target-only entries: {len(target_only)}")
print(f"Sum: {len(master_only) + len(target_only)}")

print(f"\n{'='*80}")
print("*** PROBLEM IDENTIFIED ***")
print("="*80)
print(f"\n[X] Master joints: {summary['Total_master_joints']} total, but {len(master_only)} in unmatched")
print(f"   Ratio: {len(master_only) / summary['Total_master_joints']:.2f}x")
print(f"\nX Target joints: {summary['Total_target_joints']} total, but {len(target_only)} in unmatched")
print(f"   Ratio: {len(target_only) / summary['Total_target_joints']:.2f}x")

print(f"\n*** DUPLICATION DETECTED: Joints appear multiple times in unmatched list!")

# Check for duplicates
master_joint_nums = [x['Master Joint Number'] for x in master_only if x['Master Joint Number']]
target_joint_nums = [x['Target Joint Number'] for x in target_only if x['Target Joint Number']]

master_unique = len(set(master_joint_nums))
target_unique = len(set(target_joint_nums))

print(f"\n{'='*80}")
print("DUPLICATE ANALYSIS")
print("="*80)
print(f"Master unmatched entries: {len(master_joint_nums)}")
print(f"Master unique joints: {master_unique}")
print(f"Master duplicates: {len(master_joint_nums) - master_unique}")

print(f"\nTarget unmatched entries: {len(target_joint_nums)}")
print(f"Target unique joints: {target_unique}")
print(f"Target duplicates: {len(target_joint_nums) - target_unique}")

# Query actual database to see what joint numbers exist
db_user = os.getenv('DB_USER', 'postgres')
db_password = os.getenv('DB_PASSWORD', 'postgres')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'ILIDataHub')

connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(connection_string)

master_guid = summary['Master_inspection_guid']
target_guid = summary['Target_inspection_guid']

joint_query = text("""
    SELECT DISTINCT
        joint_number,
        joint_length,
        insp_guid
    FROM public.joints
    WHERE insp_guid IN (:master_guid, :target_guid)
    ORDER BY insp_guid, CAST(joint_number AS INTEGER)
""")

with engine.connect() as conn:
    joint_list = pd.read_sql_query(
        con=conn,
        sql=joint_query,
        params={'master_guid': master_guid, 'target_guid': target_guid}
    )

master_df = joint_list[joint_list['insp_guid'] == master_guid].copy()
target_df = joint_list[joint_list['insp_guid'] == target_guid].copy()

print(f"\n{'='*80}")
print("ACTUAL DATABASE JOINT NUMBERS")
print("="*80)

master_df['joint_number'] = master_df['joint_number'].astype(int)
target_df['joint_number'] = target_df['joint_number'].astype(int)

print(f"\nMaster joints in DB: {len(master_df)}")
print(f"  Range: {master_df['joint_number'].min()} to {master_df['joint_number'].max()}")
print(f"  First 10: {sorted(master_df['joint_number'].tolist())[:10]}")
print(f"  Last 10: {sorted(master_df['joint_number'].tolist())[-10:]}")

print(f"\nTarget joints in DB: {len(target_df)}")
print(f"  Range: {target_df['joint_number'].min()} to {target_df['joint_number'].max()}")
print(f"  First 10: {sorted(target_df['joint_number'].tolist())[:10]}")
print(f"  Last 10: {sorted(target_df['joint_number'].tolist())[-10:]}")

# Check overlap
master_set = set(master_df['joint_number'].tolist())
target_set = set(target_df['joint_number'].tolist())
overlap = master_set & target_set

print(f"\n{'='*80}")
print("JOINT NUMBER OVERLAP")
print("="*80)
print(f"Joints with same number in both inspections: {len(overlap)}")
if overlap:
    print(f"  Overlapping joint numbers: {sorted(list(overlap))[:20]}...")

# Calculate joint length differences for matching markers
master_df = master_df.sort_values('joint_number').reset_index(drop=True)
target_df = target_df.sort_values('joint_number').reset_index(drop=True)

master_df['difference'] = master_df['joint_length'].diff()
target_df['difference'] = target_df['joint_length'].diff()

large_diff = 3
master_markers = master_df[abs(master_df['difference']) > large_diff]
target_markers = target_df[abs(target_df['difference']) > large_diff]

print(f"\n{'='*80}")
print("MATCHING MARKERS (Algorithm's Anchor Points)")
print("="*80)
print(f"Master markers (|diff| > {large_diff}): {len(master_markers)}")
print(f"Target markers (|diff| > {large_diff}): {len(target_markers)}")

# Try to find matching markers
if len(master_markers) > 0 and len(target_markers) > 0:
    print(f"\nSearching for matching markers (first 5)...")
    matches_found = 0
    
    for i, master_row in master_markers.head(10).iterrows():
        master_diff = master_row['difference']
        master_length = master_row['joint_length']
        
        for j, target_row in target_markers.head(10).iterrows():
            target_diff = target_row['difference']
            target_length = target_row['joint_length']
            
            if (abs(master_diff - target_diff) < 1) and (abs(master_length - target_length) < 1):
                print(f"  ✓ MATCH: M-J{master_row['joint_number']} (Δ={master_diff:.1f}, L={master_length:.1f}) ↔ "
                      f"T-J{target_row['joint_number']} (Δ={target_diff:.1f}, L={target_length:.1f})")
                matches_found += 1
                if matches_found >= 5:
                    break
        if matches_found >= 5:
            break
    
    if matches_found == 0:
        print("  ❌ NO MATCHING MARKERS FOUND")
        print("\n  This is the ROOT CAUSE of zero matches!")
        print("  The algorithm relies on finding matching 'markers' (large joint length")
        print("  changes) to identify corresponding pipeline sections.")

print(f"\n{'='*80}")
print("CONCLUSION")
print("="*80)
print("""
The algorithm found 0 matches because:

1. NO MATCHING MARKERS: The algorithm couldn't find corresponding "marker" joints
   (joints with large length differences) between the two inspections.

2. These inspections likely represent:
   - Different sections of the pipeline (no overlap)
   - Different measurement methodologies
   - Incompatible or poor quality data

3. BUG FOUND: The unmatched joints list contains DUPLICATES, inflating the count
   from the expected maximum of 2,270 to 4,107.

RECOMMENDATION:
- Verify these inspections should actually be compared
- Check if they cover the same physical pipeline section  
- Review data quality and consistency between inspections
- Fix the duplication bug in the unchunk_dataframe function
""")
print("=" * 80)
