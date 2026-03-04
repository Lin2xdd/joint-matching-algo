"""
Check markers after joint 400 in ILI-19
"""
import pandas as pd
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:RedPlums2025.@localhost:5432/joint-matching')

target_guid = "d7c49f3d-7da7-49ff-9c2b-c09d388b74ba"  # ILI-19

query = text("""
    SELECT DISTINCT joint_number, joint_length, ili_id
    FROM public.joint_length
    WHERE insp_guid = :guid
    ORDER BY joint_number
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn, params={'guid': target_guid})

df['joint_number'] = df['joint_number'].astype(float)
df = df.sort_values('joint_number').reset_index(drop=True)

# Calculate differences
df['difference'] = df.joint_length.shift(-1) - df.joint_length
df['difference'] = df['difference'].fillna(0)
df['is_marker'] = df['difference'].abs() > 3

# Get markers after 400
markers_after_400 = df[(df['joint_number'] > 400) & (df['is_marker'] == True)].head(10)

print("=" * 80)
print("MARKERS IN ILI-19 AFTER JOINT 400")
print("=" * 80)

print(f"\nNext 10 markers after joint 400:")
for idx, row in markers_after_400.iterrows():
    print(f"  Joint {row['joint_number']:.0f}: Length {row['joint_length']:.3f}m, Diff {row['difference']:.3f}m")

# Also show the immediate joints after 400
print(f"\n\nImmediate joints after 400 in ILI-19:")
context = df[(df['joint_number'] >= 400) & (df['joint_number'] <= 430)]
for idx, row in context.iterrows():
    marker_flag = " <- MARKER" if row['is_marker'] else ""
    print(f"  Joint {row['joint_number']:.0f}: Length {row['joint_length']:.3f}m, Diff {row['difference']:.3f}m{marker_flag}")

print("=" * 80)
