"""
Check what matches exist around joint 390
"""
import pandas as pd

df = pd.read_excel('Sample Output/integrated_matching_results.xlsx', sheet_name='Matched Joints')

# Filter for matched records only (not unmatched)
matched = df[df['Match Source'].notna() & 
             (df['Match Source'] != 'Unmatched Master') & 
             (df['Match Source'] != 'Unmatched Target')]

print("=" * 80)
print("MATCHES AROUND JOINT 390")
print("=" * 80)

# Get all matched joints and sort by master joint number
matched_copy = matched.copy()

# Handle aggregate matches (comma-separated joint numbers)
def get_first_joint(val):
    if pd.isna(val) or val == '':
        return None
    val_str = str(val)
    if ',' in val_str:
        return float(val_str.split(',')[0])
    return float(val_str)

matched_copy['master_first'] = matched_copy['Master Joint Number'].apply(get_first_joint)
matched_copy['target_first'] = matched_copy['Target Joint Number'].apply(get_first_joint)

# Show matches where master or target is between 370 and 410
relevant = matched_copy[
    ((matched_copy['master_first'] >= 370) & (matched_copy['master_first'] <= 410)) |
    ((matched_copy['target_first'] >= 370) & (matched_copy['target_first'] <= 410))
]

relevant = relevant.sort_values('master_first', na_position='last')

print("\nMatches with Master or Target joint between 370 and 410:")
print(relevant[['Master Joint Number', 'Target Joint Number', 'Match Source', 'Confidence Level']].to_string(index=False))

print("\n" + "=" * 80)
print("CHECKING IF JOINT 390 EXISTS IN MATCHED RECORDS:")
print("=" * 80)

# Check if 390 appears anywhere in matched records
master_390 = matched_copy[matched_copy['Master Joint Number'] == 390]
target_390 = matched_copy[matched_copy['Target Joint Number'] == 390]

if not master_390.empty:
    print(f"\n✓ Found Master Joint 390 matched!")
    print(master_390[['Master Joint Number', 'Target Joint Number', 'Match Source', 'Confidence Score']].to_string(index=False))
else:
    print(f"\n✗ Master Joint 390 NOT in matched records")

if not target_390.empty:
    print(f"\n✓ Found Target Joint 390 matched!")
    print(target_390[['Master Joint Number', 'Target Joint Number', 'Match Source', 'Confidence Score']].to_string(index=False))
else:
    print(f"\n✗ Target Joint 390 NOT in matched records")

print("\n" + "=" * 80)
