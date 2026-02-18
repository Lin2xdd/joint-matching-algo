"""
Test script to compare original and flexible joint matching algorithms.

This script demonstrates the improvements of the flexible algorithm,
especially in handling cut/split joints and merged joints.
"""

import pandas as pd
import numpy as np
import logging
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# Add Scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / 'Scripts'))

from flexible_joint_matching import FlexibleJointMatcher, format_matches_to_dataframe

# ============================================================================
# CONFIGURATION - Edit these values for your database and inspections
# ============================================================================

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',        # Database host (or use environment variable DB_HOST)
    'port': '5432',             # Database port (or use environment variable DB_PORT)
    'database': 'ili',   # Database name (or use environment variable DB_NAME)
    'user': 'postgres',         # Database username (or use environment variable DB_USER)
    'password': 'RedPlums2025.'      # Database password (or use environment variable DB_PASSWORD)
}

# Inspection GUIDs for Database Testing
# Replace these with your actual inspection GUIDs
TEST_GUIDS = {
    'master_guid': 'f7e2c9d5-8a4b-4e1f-b3c6-d8a2e7f1c5b4',
    'target_guid': 'a3f5c2e1-7b9d-4f8c-9e2a-b1d6c4f7e2a9'
}

# Default output file path
DEFAULT_OUTPUT_PATH = r'C:\Dev\joint-matching-algo\Sample Input\CNRL\flexible_matching_database_results.xlsx'

# Example GUIDs from North Wapiti sample (if these exist in your database):
# TEST_GUIDS = {
#     'master_guid': 'd3f9e5a1-7c2b-4f8d-9e3a-5b1c6a4d8f2e',  # 2017 inspection
#     'target_guid': '8c7f3d9a-2e5b-4a1c-8f6d-3e2a9b5c1d7f'   # 2019 inspection
# }

# ============================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_scenario_with_cuts():
    """
    Create a synthetic test scenario where joints are cut between inspections.
    
    Returns:
        Tuple of (master_df, target_df, expected_matches)
    """
    # Master inspection (2017)
    master_data = {
        'joint_number': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'joint_length': [0.5, 0.4, 3.3, 0.3, 6.4, 0.4, 0.5, 3.5, 0.3, 6.5]
    }
    
    # Target inspection (2019) - Joint #3 and #5 were cut in half
    target_data = {
        'joint_number': [10, 20, 30, 31, 40, 50, 51, 60, 70, 80, 90, 100],
        'joint_length': [0.5, 0.4, 1.65, 1.65, 0.3, 3.2, 3.2, 0.4, 0.5, 3.5, 0.3, 6.5]
    }
    
    master_df = pd.DataFrame(master_data)
    target_df = pd.DataFrame(target_data)
    
    # Expected matches
    expected = {
        1: [10],      # 1-to-1
        2: [20],      # 1-to-1
        3: [30, 31],  # 1-to-2 (SPLIT) - This is the key test case!
        4: [40],      # 1-to-1
        5: [50, 51],  # 1-to-2 (SPLIT) - Another split joint
        6: [60],      # 1-to-1
        7: [70],      # 1-to-1
        8: [80],      # 1-to-1
        9: [90],      # 1-to-1
        10: [100]     # 1-to-1
    }
    
    return master_df, target_df, expected


def create_merge_test_scenario():
    """
    Create a test scenario where multiple joints are merged into one.
    
    Returns:
        Tuple of (master_df, target_df, expected_matches)
    """
    # Master inspection - has two small joints
    master_data = {
        'joint_number': [1, 2, 3, 4, 5],
        'joint_length': [0.5, 1.5, 1.5, 0.4, 6.5]
    }
    
    # Target inspection - joints 2 and 3 merged into one
    target_data = {
        'joint_number': [10, 20, 30, 40],
        'joint_length': [0.5, 3.0, 0.4, 6.5]
    }
    
    master_df = pd.DataFrame(master_data)
    target_df = pd.DataFrame(target_data)
    
    expected = {
        1: [10],      # 1-to-1
        (2, 3): [20], # 2-to-1 (MERGE)
        4: [30],      # 1-to-1
        5: [40]       # 1-to-1
    }
    
    return master_df, target_df, expected


def load_database_data(master_guid, target_guid):
    """
    Load joint data directly from database using same query as joint_matching.py.
    
    Args:
        master_guid: Master inspection GUID
        target_guid: Target inspection GUID
    
    Returns:
        Tuple of (master_df, target_df)
    """
    try:
        # Get database credentials from config, environment variables, or defaults
        db_host = os.getenv('DB_HOST', DB_CONFIG['host'])
        db_port = os.getenv('DB_PORT', DB_CONFIG['port'])
        db_name = os.getenv('DB_NAME', DB_CONFIG['database'])
        db_user = os.getenv('DB_USER', DB_CONFIG['user'])
        db_password = os.getenv('DB_PASSWORD', DB_CONFIG['password'])
        
        # Create connection string
        connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(connection_string)
        
        logger.info(f"Connecting to database: {db_host}:{db_port}/{db_name}")
        
        # Convert GUIDs to appropriate format (same as joint_matching.py)
        master_guid_tuple = tuple([master_guid])
        target_guid_list = tuple([target_guid])
        all_guid_list = master_guid_tuple + target_guid_list
        
        # Build SQL query with proper filtering, distinct, and ordering (same as joint_matching.py lines 302-313)
        placeholders = ','.join([f":guid{i}" for i in range(len(all_guid_list))])
        joint_query = text(f"""
            SELECT DISTINCT
                   joint_number,
                   joint_length,
                   iliyr,
                   insp_guid,
                   ili_id
            FROM public.joints
            WHERE insp_guid IN ({placeholders})
            ORDER BY insp_guid, CAST(joint_number AS INTEGER)
        """)
        
        # Create parameters dict (same as joint_matching.py lines 315-316)
        params = {f'guid{i}': str(guid) for i, guid in enumerate(all_guid_list)}
        
        # Query database (same as joint_matching.py lines 319-324)
        with engine.connect() as conn:
            joint_list = pd.read_sql_query(con=conn, sql=joint_query, params=params)
            
            # Drop null values
            smaller_subset = ['joint_number', 'joint_length', 'insp_guid', 'ili_id']
            joint_list = joint_list.dropna(subset=smaller_subset).reset_index(drop=True)
        
        logger.info("Database query successful")
        
        # Prepare master dataset (same as joint_matching.py lines 329-334)
        joint_list["insp_guid"] = joint_list["insp_guid"].astype("str")
        master_df = joint_list.loc[joint_list["insp_guid"] == master_guid_tuple[0]].copy()
        
        # Convert joint_number to integer and sort
        master_df['joint_number'] = master_df['joint_number'].astype(int)
        master_df = master_df.sort_values('joint_number').reset_index(drop=True)
        
        # Prepare target dataset (same as joint_matching.py lines 351-355)
        target_df = joint_list.loc[joint_list["insp_guid"] == target_guid].copy()
        
        # Convert joint_number to integer and sort
        target_df['joint_number'] = target_df['joint_number'].astype(int)
        target_df = target_df.sort_values('joint_number').reset_index(drop=True)
        
        # Extract only joint_number and joint_length for flexible matching
        master_df = master_df[['joint_number', 'joint_length']].copy()
        target_df = target_df[['joint_number', 'joint_length']].copy()
        
        logger.info(f"Loaded {len(master_df)} master joints and {len(target_df)} target joints from database")
        
        return master_df, target_df
        
    except Exception as e:
        logger.error(f"Failed to load data from database: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None


def load_real_sample_data():
    """Load real sample data from CSV files."""
    try:
        master_df = pd.read_csv('Sample Input/North Wapiti/2017.csv')
        target_df = pd.read_csv('Sample Input/North Wapiti/2019.csv')
        
        # Extract only joint_number and joint_length
        master_df = master_df[['joint_number', 'joint_length']].dropna()
        target_df = target_df[['joint_number', 'joint_length']].dropna()
        
        # Remove duplicates and sort
        master_df = master_df.drop_duplicates(subset=['joint_number']).sort_values('joint_number').reset_index(drop=True)
        target_df = target_df.drop_duplicates(subset=['joint_number']).sort_values('joint_number').reset_index(drop=True)
        
        return master_df, target_df
    except Exception as e:
        logger.warning(f"Could not load real sample data: {e}")
        return None, None


def test_synthetic_scenario(scenario_name, master_df, target_df, expected_matches=None):
    """Test the flexible algorithm on a synthetic scenario."""
    print("\n" + "=" * 80)
    print(f"TEST SCENARIO: {scenario_name}")
    print("=" * 80)
    
    print("\nMaster Inspection:")
    print(master_df.to_string(index=False))
    
    print("\nTarget Inspection:")
    print(target_df.to_string(index=False))
    
    if expected_matches:
        print("\nExpected Matches:")
        for master, target in expected_matches.items():
            print(f"  Master {master} -> Target {target}")
    
    # Run flexible matching
    print("\n" + "-" * 80)
    print("Running Flexible Joint Matching Algorithm...")
    print("-" * 80)
    
    matcher = FlexibleJointMatcher(
        length_tolerance=0.10,  # 10% tolerance
        max_aggregate=5,
        marker_diff_threshold=3.0,
        min_confidence=0.60
    )
    
    matches, metadata = matcher.match_inspections(master_df, target_df)
    
    # Display results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    print(f"\nTotal Matches Found: {metadata['total_matches']}")
    print(f"  - 1-to-1 matches: {metadata['simple_matches']}")
    print(f"  - Split matches (1-to-many): {metadata['split_matches']}")
    print(f"  - Merge matches (many-to-1): {metadata['merge_matches']}")
    print(f"\nMaster Match Rate: {metadata['master_match_rate']:.1f}%")
    print(f"Target Match Rate: {metadata['target_match_rate']:.1f}%")
    print(f"Average Confidence: {metadata['avg_confidence']:.3f}")
    
    print("\n" + "-" * 80)
    print("Detailed Matches:")
    print("-" * 80)
    
    for i, match in enumerate(matches, 1):
        master_str = ','.join(map(str, match.master_joints))
        target_str = ','.join(map(str, match.target_joints))
        
        status_icon = "[SPLIT]" if match.is_split() else "[MERGE]" if match.is_merge() else "[OK]"
        
        print(f"{status_icon} Match {i}: M[{master_str}] <-> T[{target_str}]")
        print(f"   Type: {match.match_type}, Confidence: {match.confidence:.3f}")
        print(f"   Lengths: M={match.master_total_length:.3f}m, "
              f"T={match.target_total_length:.3f}m, "
              f"Diff={match.length_difference:.3f}m")
    
    # Validate against expected matches if provided
    if expected_matches:
        print("\n" + "-" * 80)
        print("VALIDATION")
        print("-" * 80)
        
        found_correct = 0
        found_incorrect = 0
        missed = 0
        
        for master, expected_target in expected_matches.items():
            master_list = [master] if isinstance(master, int) else list(master)
            
            # Find matching result
            found = False
            for match in matches:
                if match.master_joints == master_list:
                    if set(match.target_joints) == set(expected_target):
                        print(f"[OK] CORRECT: M{master_list} -> T{match.target_joints}")
                        found_correct += 1
                        found = True
                    else:
                        print(f"[X] INCORRECT: M{master_list} -> T{match.target_joints} "
                              f"(expected T{expected_target})")
                        found_incorrect += 1
                        found = True
                    break
            
            if not found:
                print(f"[X] MISSED: M{master_list} -> T{expected_target}")
                missed += 1
        
        print(f"\nValidation Summary:")
        print(f"  Correct: {found_correct}/{len(expected_matches)}")
        print(f"  Incorrect: {found_incorrect}/{len(expected_matches)}")
        print(f"  Missed: {missed}/{len(expected_matches)}")
        
        success_rate = (found_correct / len(expected_matches) * 100) if expected_matches else 0
        print(f"  Success Rate: {success_rate:.1f}%")
    
    return matches, metadata


def test_real_data():
    """Test on real sample data."""
    print("\n" + "=" * 80)
    print("TEST: Real Sample Data (North Wapiti 2017 vs 2019)")
    print("=" * 80)
    
    master_df, target_df = load_real_sample_data()
    
    if master_df is None or target_df is None:
        print("[X] Real sample data not available. Skipping this test.")
        return None, None
    
    print(f"\nMaster Inspection (2017): {len(master_df)} joints")
    print(f"Target Inspection (2019): {len(target_df)} joints")
    print(f"\nFirst 10 Master Joints:")
    print(master_df.head(10).to_string(index=False))
    print(f"\nFirst 10 Target Joints:")
    print(target_df.head(10).to_string(index=False))
    
    # Run flexible matching
    print("\n" + "-" * 80)
    print("Running Flexible Joint Matching Algorithm...")
    print("-" * 80)
    
    matcher = FlexibleJointMatcher(
        length_tolerance=0.15,  # 15% tolerance for real data (more noise)
        max_aggregate=5,
        marker_diff_threshold=3.0,
        min_confidence=0.60
    )
    
    matches, metadata = matcher.match_inspections(master_df, target_df)
    
    # Display results summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Matches Found: {metadata['total_matches']}")
    print(f"  - 1-to-1 matches: {metadata['simple_matches']}")
    print(f"  - Split matches (1-to-many): {metadata['split_matches']}")
    print(f"  - Merge matches (many-to-1): {metadata['merge_matches']}")
    print(f"\nMaster Match Rate: {metadata['master_match_rate']:.1f}%")
    print(f"Target Match Rate: {metadata['target_match_rate']:.1f}%")
    print(f"Average Confidence: {metadata['avg_confidence']:.3f}")
    print(f"\nUnmatched Joints:")
    print(f"  - Master: {metadata['unmatched_master']}")
    print(f"  - Target: {metadata['unmatched_target']}")
    
    # Show interesting matches (splits and merges)
    splits = [m for m in matches if m.is_split()]
    merges = [m for m in matches if m.is_merge()]
    
    if splits:
        print("\n" + "-" * 80)
        print(f"SPLIT JOINTS DETECTED ({len(splits)} found):")
        print("-" * 80)
        for i, match in enumerate(splits[:10], 1):  # Show first 10
            master_str = ','.join(map(str, match.master_joints))
            target_str = ','.join(map(str, match.target_joints))
            print(f"{i}. Master Joint {master_str} (Length: {match.master_total_length:.3f}m)")
            print(f"   -> Split into Target Joints {target_str} "
                  f"(Total: {match.target_total_length:.3f}m)")
            print(f"   Confidence: {match.confidence:.3f}")
    
    if merges:
        print("\n" + "-" * 80)
        print(f"MERGED JOINTS DETECTED ({len(merges)} found):")
        print("-" * 80)
        for i, match in enumerate(merges[:10], 1):  # Show first 10
            master_str = ','.join(map(str, match.master_joints))
            target_str = ','.join(map(str, match.target_joints))
            print(f"{i}. Master Joints {master_str} (Total: {match.master_total_length:.3f}m)")
            print(f"   -> Merged into Target Joint {target_str} "
                  f"(Length: {match.target_total_length:.3f}m)")
            print(f"   Confidence: {match.confidence:.3f}")
    
    # Export results to CSV
    try:
        results_df = format_matches_to_dataframe(matches)
        output_path = 'flexible_matching_results.csv'
        results_df.to_csv(output_path, index=False)
        print(f"\n[OK] Results exported to: {output_path}")
    except Exception as e:
        print(f"\n[WARNING] Could not export results: {e}")
    
    return matches, metadata


def test_database_data(master_guid, target_guid, output_path=None):
    """
    Test the flexible algorithm on data loaded from database.
    
    Args:
        master_guid: Master inspection GUID
        target_guid: Target inspection GUID
        output_path: Path to save results Excel file (default: DEFAULT_OUTPUT_PATH)
    """
    if output_path is None:
        output_path = DEFAULT_OUTPUT_PATH
    print("\n" + "=" * 80)
    print("TEST: Database Data")
    print("=" * 80)
    
    master_df, target_df = load_database_data(master_guid, target_guid)
    
    if master_df is None or target_df is None:
        print("[X] Failed to load data from database.")
        return None, None
    
    print(f"\nMaster Inspection GUID: {master_guid}")
    print(f"Master Joints: {len(master_df)}")
    print(f"\nTarget Inspection GUID: {target_guid}")
    print(f"Target Joints: {len(target_df)}")
    
    print(f"\nFirst 10 Master Joints:")
    print(master_df.head(10).to_string(index=False))
    print(f"\nFirst 10 Target Joints:")
    print(target_df.head(10).to_string(index=False))
    
    # Run flexible matching
    print("\n" + "-" * 80)
    print("Running Flexible Joint Matching Algorithm...")
    print("-" * 80)
    
    matcher = FlexibleJointMatcher(
        length_tolerance=0.15,  # 15% tolerance for real data
        max_aggregate=5,
        marker_diff_threshold=3.0,
        min_confidence=0.60
    )
    
    matches, metadata = matcher.match_inspections(master_df, target_df)
    
    # Display results summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Matches Found: {metadata['total_matches']}")
    print(f"  - 1-to-1 matches: {metadata['simple_matches']}")
    print(f"  - Split matches (1-to-many): {metadata['split_matches']}")
    print(f"  - Merge matches (many-to-1): {metadata['merge_matches']}")
    print(f"\nMaster Match Rate: {metadata['master_match_rate']:.1f}%")
    print(f"Target Match Rate: {metadata['target_match_rate']:.1f}%")
    print(f"Average Confidence: {metadata['avg_confidence']:.3f}")
    print(f"\nUnmatched Joints:")
    print(f"  - Master: {metadata['unmatched_master']}")
    print(f"  - Target: {metadata['unmatched_target']}")
    
    # Show interesting matches (splits and merges)
    splits = [m for m in matches if m.is_split()]
    merges = [m for m in matches if m.is_merge()]
    
    if splits:
        print("\n" + "-" * 80)
        print(f"SPLIT JOINTS DETECTED ({len(splits)} found):")
        print("-" * 80)
        for i, match in enumerate(splits[:10], 1):
            master_str = ','.join(map(str, match.master_joints))
            target_str = ','.join(map(str, match.target_joints))
            print(f"{i}. Master Joint {master_str} (Length: {match.master_total_length:.3f}m)")
            print(f"   -> Split into Target Joints {target_str} "
                  f"(Total: {match.target_total_length:.3f}m)")
            print(f"   Confidence: {match.confidence:.3f}")
    
    if merges:
        print("\n" + "-" * 80)
        print(f"MERGED JOINTS DETECTED ({len(merges)} found):")
        print("-" * 80)
        for i, match in enumerate(merges[:10], 1):
            master_str = ','.join(map(str, match.master_joints))
            target_str = ','.join(map(str, match.target_joints))
            print(f"{i}. Master Joints {master_str} (Total: {match.master_total_length:.3f}m)")
            print(f"   -> Merged into Target Joint {target_str} "
                  f"(Length: {match.target_total_length:.3f}m)")
            print(f"   Confidence: {match.confidence:.3f}")
    
    # Export results to Excel with two tabs
    try:
        # Prepare matched joints dataframe
        matches_df = format_matches_to_dataframe(matches)
        
        # Prepare unmatched joints dataframe
        matched_master = set()
        matched_target = set()
        
        for match in matches:
            matched_master.update(match.master_joints)
            matched_target.update(match.target_joints)
        
        # Get all master and target joints
        all_master = set(master_df['joint_number'].tolist())
        all_target = set(target_df['joint_number'].tolist())
        
        # Find unmatched joints
        unmatched_master = sorted(all_master - matched_master)
        unmatched_target = sorted(all_target - matched_target)
        
        # Create unmatched dataframe
        unmatched_records = []
        
        # Add unmatched master joints
        for joint_num in unmatched_master:
            joint_data = master_df[master_df['joint_number'] == joint_num].iloc[0]
            unmatched_records.append({
                'Joint_Type': 'Master',
                'Joint_Number': int(joint_num),
                'Joint_Length': round(joint_data['joint_length'], 3),
                'Status': 'Unmatched in Target'
            })
        
        # Add unmatched target joints
        for joint_num in unmatched_target:
            joint_data = target_df[target_df['joint_number'] == joint_num].iloc[0]
            unmatched_records.append({
                'Joint_Type': 'Target',
                'Joint_Number': int(joint_num),
                'Joint_Length': round(joint_data['joint_length'], 3),
                'Status': 'Unmatched in Master'
            })
        
        unmatched_df = pd.DataFrame(unmatched_records)
        
        # Export to Excel with two sheets
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            matches_df.to_excel(writer, sheet_name='Matched Joints', index=False)
            unmatched_df.to_excel(writer, sheet_name='Unmatched Joints', index=False)
        
        print(f"\n[OK] Results exported to: {output_path}")
        print(f"     - Sheet 1: Matched Joints ({len(matches_df)} matches)")
        print(f"     - Sheet 2: Unmatched Joints ({len(unmatched_df)} joints)")
    except Exception as e:
        print(f"\n[WARNING] Could not export results: {e}")
        import traceback
        print(traceback.format_exc())
    
    return matches, metadata


def main():
    """
    Run all tests.
    
    Usage:
        # Test with database (using GUIDs from command line):
        python test_flexible_matching.py "master-guid" "target-guid" [output-path.xlsx]
        
        # Test with database (using GUIDs from TEST_GUIDS config):
        python test_flexible_matching.py --database [output-path.xlsx]
        
        # Test with database and custom output path:
        python test_flexible_matching.py --database "C:/path/to/results.xlsx"
        
        # Run standard test suite (synthetic + CSV data):
        python test_flexible_matching.py
    """
    print("\n" + "=" * 80)
    print("FLEXIBLE JOINT MATCHING - TEST SUITE")
    print("=" * 80)
    print("\nThis test suite demonstrates the capabilities of the flexible")
    print("joint matching algorithm, especially for handling cut/split joints.")
    
    # Check for database test mode
    if len(sys.argv) >= 2:
        if sys.argv[1] == '--database' or sys.argv[1] == '-db':
            # Use GUIDs from configuration
            master_guid = TEST_GUIDS['master_guid']
            target_guid = TEST_GUIDS['target_guid']
            
            # Check for optional output path argument
            output_path = sys.argv[2] if len(sys.argv) >= 3 else None
            
            if 'your-' in master_guid or 'your-' in target_guid:
                print("\n" + "!" * 80)
                print("ERROR: Please edit the TEST_GUIDS configuration in test_flexible_matching.py")
                print("Replace 'your-master-inspection-guid-here' and 'your-target-inspection-guid-here'")
                print("with your actual inspection GUIDs.")
                print("!" * 80)
                return
            
            print(f"\n[INFO] Database test mode activated (using TEST_GUIDS config)")
            print(f"[INFO] Master GUID: {master_guid}")
            print(f"[INFO] Target GUID: {target_guid}")
            if output_path:
                print(f"[INFO] Output path: {output_path}")
            
            test_database_data(master_guid, target_guid, output_path)
            
            print("\n" + "=" * 80)
            print("DATABASE TEST COMPLETE")
            print("=" * 80)
            return
        
        elif len(sys.argv) >= 3:
            # Use GUIDs from command line arguments
            master_guid = sys.argv[1]
            target_guid = sys.argv[2]
            
            # Check for optional output path argument
            output_path = sys.argv[3] if len(sys.argv) >= 4 else None
            
            print(f"\n[INFO] Database test mode activated (using command line GUIDs)")
            print(f"[INFO] Master GUID: {master_guid}")
            print(f"[INFO] Target GUID: {target_guid}")
            if output_path:
                print(f"[INFO] Output path: {output_path}")
            
            test_database_data(master_guid, target_guid, output_path)
            
            print("\n" + "=" * 80)
            print("DATABASE TEST COMPLETE")
            print("=" * 80)
            return
    
    # Run standard test suite
    # Test 1: Split joints scenario
    print("\n\n")
    master_df, target_df, expected = create_test_scenario_with_cuts()
    test_synthetic_scenario(
        "Split Joints (1-to-Many)",
        master_df,
        target_df,
        expected
    )
    
    # Test 2: Merged joints scenario
    print("\n\n")
    master_df, target_df, expected = create_merge_test_scenario()
    test_synthetic_scenario(
        "Merged Joints (Many-to-1)",
        master_df,
        target_df,
        expected
    )
    
    # Test 3: Real data
    print("\n\n")
    test_real_data()
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
