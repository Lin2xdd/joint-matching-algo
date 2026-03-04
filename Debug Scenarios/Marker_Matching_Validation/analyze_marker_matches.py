"""
Analyze which marker pairs were actually matched
"""
import pandas as pd

df = pd.read_excel('Sample Output/integrated_matching_results.xlsx', sheet_name='Matched Joints')

# Get all marker matches
markers = df[df['Match Source'] == 'Marker'].copy()

print("=" * 80)
print("ALL MARKER MATCHES FROM THE RUN")
print("=" * 80)

if not markers.empty:
    markers = markers.sort_values('Master Joint Number')
    print(f"\nTotal marker matches: {len(markers)}\n")
    
    for idx, row in markers.iterrows():
        m_joint = row['Master Joint Number']
        t_joint = row['Target Joint Number']
        m_len = row['Master Total Length (m)']
        t_len = row['Target Total Length (m)']
        print(f"  Master {m_joint:>6.0f} ({m_len:>6.3f}m) <-> Target {t_joint:>6.0f} ({t_len:>6.3f}m)")
    
    print("\n" + "=" * 80)
    print("GAP ANALYSIS")
    print("=" * 80)
    
    # Find gaps in the marker sequence
    master_joints = markers['Master Joint Number'].tolist()
    for i in range(len(master_joints) - 1):
        current = master_joints[i]
        next_joint = master_joints[i + 1]
        gap = next_joint - current
        
        if gap > 50:  # Large gap
            print(f"\nLARGE GAP DETECTED:")
            print(f"  From Master joint {current} to {next_joint}")
            print(f"  Gap size: {gap} joints")
            print(f"  This gap contains joint 390!" if (current < 390 < next_joint) else f"  Joint 390 is NOT in this gap")
else:
    print("No marker matches found!")

print("\n" + "=" * 80)
