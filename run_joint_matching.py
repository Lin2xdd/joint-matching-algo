"""
Runner script for joint matching algorithm.
Connects to PostgreSQL database and executes joint matching.
Supports both legacy and flexible matching algorithms.
"""
import json
import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from Scripts.joint_matching import execute_joint_matching
from Scripts.flexible_joint_matching import FlexibleJointMatcher, format_matches_to_dataframe
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================
# ALGORITHM SELECTION
# ==============================================

# Algorithm modes:
# - 'legacy': Use the original joint matching algorithm (1-to-1 only)
# - 'flexible': Use the new flexible algorithm (handles splits/merges)
# - 'auto': Try legacy first, fallback to flexible if match rate < threshold
ALGORITHM_MODE = 'auto'  # Options: 'legacy', 'flexible', 'auto'

# Auto mode threshold: switch to flexible if legacy match rate below this percentage
AUTO_MODE_THRESHOLD = 50.0  # Switch if match rate < 50%

# Flexible algorithm parameters (used when ALGORITHM_MODE is 'flexible' or 'auto' fallback)
FLEXIBLE_PARAMS = {
    'length_tolerance': 0.10,           # 10% length tolerance
    'max_aggregate': 5,                 # Max joints to aggregate
    'marker_diff_threshold': 3.0,       # Min length change for markers (meters)
    'marker_distance_tolerance': 5.0,   # Distance tolerance for markers (meters)
    'marker_length_tolerance': 1.0,     # Length tolerance for markers (meters)
    'min_confidence': 0.60              # Minimum confidence threshold
}

# ==============================================

def export_to_excel(result, filename='joint_matching_results.xlsx'):
    """Export results to Excel file with multiple sheets."""
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_df = pd.DataFrame([result['run_summary']]).T
            summary_df.columns = ['Value']
            summary_df.to_excel(writer, sheet_name='Summary')
            
            # Matched joints sheet
            matched_df = pd.DataFrame(result['matched_joints'])
            matched_df.to_excel(writer, sheet_name='Matched Joints', index=False)
            
            # Unmatched joints sheet
            unmatched_df = pd.DataFrame(result['unmatched_joints'])
            unmatched_df.to_excel(writer, sheet_name='Unmatched Joints', index=False)
            
            # Questionable matches sheet (if any)
            if result['questionable_joints']:
                questionable_df = pd.DataFrame(result['questionable_joints'])
                questionable_df.to_excel(writer, sheet_name='Questionable', index=False)
        
        print(f"[OK] Results exported to Excel: {filename}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to export to Excel: {str(e)}")
        return False


def load_joints_from_database(engine, inspection_guid):
    """
    Load joints from database for a specific inspection.
    
    Args:
        engine: SQLAlchemy engine
        inspection_guid: Inspection GUID to load
        
    Returns:
        DataFrame with columns [joint_number, joint_length]
    """
    query = text("""
        SELECT DISTINCT
               CAST(joint_number AS INTEGER) as joint_number,
               joint_length
        FROM public.joints
        WHERE insp_guid = :guid
        ORDER BY CAST(joint_number AS INTEGER)
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql_query(con=conn, sql=query, params={'guid': str(inspection_guid)})
    
    # Remove nulls and ensure proper types
    df = df.dropna(subset=['joint_number', 'joint_length'])
    df['joint_number'] = df['joint_number'].astype(int)
    df['joint_length'] = df['joint_length'].astype(float)
    
    return df


def convert_flexible_to_legacy_format(matches, metadata, master_guid, target_guid, 
                                      master_ili_id, target_ili_id,
                                      total_master_joints, total_target_joints):
    """
    Convert flexible algorithm results to legacy format for consistent output.
    
    Args:
        matches: List of JointMatch objects from flexible algorithm
        metadata: Metadata dict from flexible algorithm
        master_guid: Master inspection GUID
        target_guid: Target inspection GUID
        master_ili_id: Master ILI ID
        target_ili_id: Target ILI ID
        total_master_joints: Total master joints count
        total_target_joints: Total target joints count
        
    Returns:
        Dict with legacy format: {run_summary, matched_joints, unmatched_joints, questionable_joints}
    """
    # Convert matches to DataFrame
    matches_df = format_matches_to_dataframe(matches)
    
    # Build matched joints list
    matched_joints_list = []
    questionable_joints_list = []
    
    matched_master_joints = set()
    matched_target_joints = set()
    
    marker_count = 0
    simple_match_count = 0
    split_count = 0
    merge_count = 0
    
    for _, row in matches_df.iterrows():
        master_joints = [int(j) for j in row['Master_Joint_Numbers'].split(',')]
        target_joints = [int(j) for j in row['Target_Joint_Numbers'].split(',')]
        match_type = row['Match_Type']
        
        # Track all matched joints
        matched_master_joints.update(master_joints)
        matched_target_joints.update(target_joints)
        
        # Count match types
        if match_type == 'marker':
            marker_count += 1
        elif match_type == '1-to-1':
            simple_match_count += 1
        elif row['Is_Split']:
            split_count += 1
        elif row['Is_Merge']:
            merge_count += 1
        
        # For 1-to-1 matches and markers, add to matched list
        if len(master_joints) == 1 and len(target_joints) == 1:
            matched_joints_list.append({
                'Master Joint Number': master_joints[0],
                'Target Joint Number': target_joints[0],
                'Match_Type': match_type,  # Preserve 'marker' or '1-to-1'
                'Confidence': row['Confidence'],
                'Master_Length': row['Master_Total_Length'],
                'Target_Length': row['Target_Total_Length'],
                'Length_Diff': row['Length_Difference']
            })
        else:
            # For splits/merges, add to questionable
            for m_joint in master_joints:
                for t_joint in target_joints:
                    questionable_joints_list.append({
                        'Master Joint Number': m_joint,
                        'Target Joint Number': t_joint,
                        'Match_Type': match_type,
                        'Confidence': row['Confidence'],
                        'Note': f"Part of {match_type} match (M:{','.join(map(str, master_joints))} ↔ T:{','.join(map(str, target_joints))})"
                    })
    
    # Build unmatched joints list
    unmatched_joints_list = []
    
    # Unmatched master joints
    for joint_num in range(1, total_master_joints + 1):
        if joint_num not in matched_master_joints:
            unmatched_joints_list.append({
                'Master Joint Number': joint_num,
                'Target Joint Number': None
            })
    
    # Unmatched target joints
    for joint_num in range(1, total_target_joints + 1):
        if joint_num not in matched_target_joints:
            unmatched_joints_list.append({
                'Master Joint Number': None,
                'Target Joint Number': joint_num
            })
    
    # Build run summary with all flexible algorithm metrics
    run_summary = {
        'Master_inspection_guid': master_guid,
        'Master_ili_id': master_ili_id,
        'Target_inspection_guid': target_guid,
        'Target_ili_id': target_ili_id,
        'Total_master_joints': total_master_joints,
        'Total_target_joints': total_target_joints,
        'Matched_joints': len(matched_joints_list),
        'Unmatched_joints': len(unmatched_joints_list),
        'Questionable_matches': len(questionable_joints_list),
        'Master_joint_percentage': round(metadata['master_match_rate'], 2),
        'Target_joint_percentage': round(metadata['target_match_rate'], 2),
        'Flow_direction': 'N/A',  # Flexible algorithm doesn't determine flow direction
        'Algorithm_used': 'flexible',
        'Simple_matches': simple_match_count,
        'Marker_matches': marker_count,
        'Split_matches': split_count,
        'Merge_matches': merge_count,
        'Average_confidence': round(metadata['avg_confidence'], 3),
        'Markers_found': metadata['markers_found']
    }
    
    return {
        'run_summary': run_summary,
        'matched_joints': matched_joints_list,
        'unmatched_joints': unmatched_joints_list,
        'questionable_joints': questionable_joints_list
    }


def execute_flexible_matching(engine, master_guid, target_guid):
    """
    Execute flexible joint matching algorithm.
    
    Args:
        engine: SQLAlchemy engine
        master_guid: Master inspection GUID
        target_guid: Target inspection GUID
        
    Returns:
        Dict with legacy-compatible format
    """
    logger.info("Using Flexible Joint Matching Algorithm")
    logger.info(f"Parameters: {FLEXIBLE_PARAMS}")
    
    # Load joint data from database
    logger.info(f"Loading master joints for GUID: {master_guid}")
    master_df = load_joints_from_database(engine, master_guid)
    
    logger.info(f"Loading target joints for GUID: {target_guid}")
    target_df = load_joints_from_database(engine, target_guid)
    
    if master_df.empty:
        raise ValueError(f"No joints found for master GUID: {master_guid}")
    if target_df.empty:
        raise ValueError(f"No joints found for target GUID: {target_guid}")
    
    # Get ILI IDs (query separately)
    query = text("SELECT ili_id FROM public.joints WHERE insp_guid = :guid LIMIT 1")
    with engine.connect() as conn:
        master_ili_id = conn.execute(query, {'guid': str(master_guid)}).scalar()
        target_ili_id = conn.execute(query, {'guid': str(target_guid)}).scalar()
    
    logger.info(f"Master: {len(master_df)} joints (ILI ID: {master_ili_id})")
    logger.info(f"Target: {len(target_df)} joints (ILI ID: {target_ili_id})")
    
    # Create matcher and run algorithm
    matcher = FlexibleJointMatcher(**FLEXIBLE_PARAMS)
    matches, metadata = matcher.match_inspections(master_df, target_df)
    
    # Convert to legacy format
    result = convert_flexible_to_legacy_format(
        matches, metadata,
        master_guid, target_guid,
        master_ili_id, target_ili_id,
        len(master_df), len(target_df)
    )
    
    return result


# ==============================================
# DATABASE CONNECTION
# ==============================================

# Database connection parameters
DB_USER = "postgres"
DB_PASSWORD = "RedPlums2025."  # No password
DB_HOST = "localhost"  # Assuming localhost since only port was provided
DB_PORT = "5432"
DB_NAME = "ili"

# Inspection GUIDs
MASTER_GUID = "8c7f3d9a-2e5b-4a1c-8f6d-3e2a9b5c1d7f"
TARGET_GUIDS = ["d3f9e5a1-7c2b-4f8d-9e3a-5b1c6a4d8f2e"]

# ========== CONFIGURATION PARAMETERS ==========

# Output path for Excel file (can be relative or absolute path)
# Examples:
#   "joint_matching_results.xlsx" - saves in current directory
#   "Sample Input/Seven Generations/results.xlsx" - saves in specific subfolder
#   "C:/Output/results.xlsx" - saves to absolute path
OUTPUT_PATH = r"C:\Dev\joint-matching-algo\Sample Input\North Wapiti\joint_matching_results.xlsx"

def main():
    """Main execution function."""
    print("=" * 80)
    print("JOINT MATCHING ALGORITHM - INTEGRATED VERSION")
    print("=" * 80)
    print(f"Algorithm Mode: {ALGORITHM_MODE.upper()}")
    if ALGORITHM_MODE == 'auto':
        print(f"Auto Mode Threshold: {AUTO_MODE_THRESHOLD}%")
    print("=" * 80)
    
    # Create database connection
    connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    print(f"\nConnecting to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    try:
        engine = create_engine(connection_string)
        
        # Test connection
        with engine.connect() as conn:
            print("[OK] Database connection successful")
        
        print(f"\nMaster GUID: {MASTER_GUID}")
        print(f"Target GUID(s): {TARGET_GUIDS}")
        print("\nExecuting joint matching algorithm...")
        print("-" * 80)
        
        # Execute joint matching based on selected mode
        result = None
        algorithm_used = None
        
        if ALGORITHM_MODE == 'legacy':
            # Use legacy algorithm only
            logger.info("Executing LEGACY joint matching algorithm...")
            result = execute_joint_matching(
                engine=engine,
                master_guid=MASTER_GUID,
                target_guids=TARGET_GUIDS
            )
            algorithm_used = 'legacy'
            
        elif ALGORITHM_MODE == 'flexible':
            # Use flexible algorithm only
            logger.info("Executing FLEXIBLE joint matching algorithm...")
            result = execute_flexible_matching(
                engine=engine,
                master_guid=MASTER_GUID,
                target_guid=TARGET_GUIDS[0]
            )
            algorithm_used = 'flexible'
            
        elif ALGORITHM_MODE == 'auto':
            # Try legacy first, fallback to flexible if needed
            logger.info("AUTO mode: Trying LEGACY algorithm first...")
            
            try:
                result = execute_joint_matching(
                    engine=engine,
                    master_guid=MASTER_GUID,
                    target_guids=TARGET_GUIDS
                )
                algorithm_used = 'legacy'
                
                # Check match rate
                master_match_rate = result['run_summary']['Master_joint_percentage']
                target_match_rate = result['run_summary']['Target_joint_percentage']
                avg_match_rate = (master_match_rate + target_match_rate) / 2
                
                logger.info(f"Legacy algorithm match rate: {avg_match_rate:.1f}%")
                
                if avg_match_rate < AUTO_MODE_THRESHOLD:
                    logger.warning(f"Match rate below threshold ({AUTO_MODE_THRESHOLD}%)")
                    logger.info("Switching to FLEXIBLE algorithm...")
                    
                    result = execute_flexible_matching(
                        engine=engine,
                        master_guid=MASTER_GUID,
                        target_guid=TARGET_GUIDS[0]
                    )
                    algorithm_used = 'flexible (auto-fallback)'
                    
                    new_match_rate = (result['run_summary']['Master_joint_percentage'] + 
                                     result['run_summary']['Target_joint_percentage']) / 2
                    logger.info(f"Flexible algorithm match rate: {new_match_rate:.1f}%")
                    
                    improvement = new_match_rate - avg_match_rate
                    if improvement > 0:
                        logger.info(f"✓ Improvement: +{improvement:.1f}%")
                    else:
                        logger.warning(f"⚠ No improvement: {improvement:.1f}%")
                else:
                    logger.info(f"✓ Match rate acceptable, using legacy results")
                    
            except Exception as e:
                logger.error(f"Legacy algorithm failed: {str(e)}")
                logger.info("Falling back to FLEXIBLE algorithm...")
                
                result = execute_flexible_matching(
                    engine=engine,
                    master_guid=MASTER_GUID,
                    target_guid=TARGET_GUIDS[0]
                )
                algorithm_used = 'flexible (auto-fallback)'
        
        else:
            raise ValueError(f"Invalid ALGORITHM_MODE: {ALGORITHM_MODE}. Use 'legacy', 'flexible', or 'auto'")
        
        print("\n" + "=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)
        
        # Add algorithm used to summary
        if 'Algorithm_used' not in result['run_summary']:
            result['run_summary']['Algorithm_used'] = algorithm_used
        
        # Display summary
        summary = result['run_summary']
        print(f"\nAlgorithm Used: {summary.get('Algorithm_used', 'legacy').upper()}")
        print(f"Master Inspection: {summary['Master_ili_id']} (GUID: {summary['Master_inspection_guid']})")
        print(f"Target Inspection: {summary['Target_ili_id']} (GUID: {summary['Target_inspection_guid']})")
        print(f"Flow Direction: {summary.get('Flow_direction', 'N/A')}")
        print(f"\nTotal Master Joints: {summary['Total_master_joints']}")
        print(f"Total Target Joints: {summary['Total_target_joints']}")
        print(f"Matched Joints: {summary['Matched_joints']}")
        print(f"Unmatched Joints: {summary['Unmatched_joints']}")
        print(f"Questionable Matches: {summary['Questionable_matches']}")
        print(f"\nMaster Joint Match Percentage: {summary['Master_joint_percentage']}%")
        print(f"Target Joint Match Percentage: {summary['Target_joint_percentage']}%")
        
        # Display flexible algorithm specific metrics if available
        if 'Marker_matches' in summary:
            print(f"\n--- Flexible Algorithm Metrics ---")
            print(f"Markers Found: {summary['Markers_found']}")
            print(f"Match Breakdown:")
            print(f"  - Simple (1-to-1): {summary['Simple_matches']}")
            print(f"  - Marker matches: {summary['Marker_matches']}")
            print(f"  - Split (1-to-many): {summary['Split_matches']}")
            print(f"  - Merge (many-to-1): {summary['Merge_matches']}")
            print(f"Average Confidence: {summary['Average_confidence']:.3f}")
        
        # Save results to JSON file
        output_file = "joint_matching_results.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\n[OK] Full results saved to: {output_file}")
        
        # Export to Excel
        print(f"\nExporting results to Excel...")
        
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(OUTPUT_PATH)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"[OK] Created output directory: {output_dir}")
        
        if export_to_excel(result, OUTPUT_PATH):
            abs_path = os.path.abspath(OUTPUT_PATH)
            print(f"[OK] Excel file saved to: {abs_path}")
        
        # Display sample matches
        if result['matched_joints']:
            print(f"\nSample Matched Joints (first 10):")
            print("-" * 80)
            for i, match in enumerate(result['matched_joints'][:10], 1):
                master_joint = match.get('Master Joint Number', 'N/A')
                target_joint = match.get('Target Joint Number', 'N/A')
                match_type = match.get('Match_Type', '1-to-1')
                confidence = match.get('Confidence', 'N/A')
                
                # Add marker indicator
                marker_indicator = " [MARKER]" if match_type == 'marker' else ""
                
                if confidence != 'N/A':
                    print(f"  {i}. M:{master_joint} → T:{target_joint} ({match_type}, conf={confidence:.3f}){marker_indicator}")
                else:
                    print(f"  {i}. M:{master_joint} → T:{target_joint}{marker_indicator}")
        
        # Display questionable matches (splits/merges) if any
        if result['questionable_joints']:
            print(f"\nSample Questionable Matches (first 5):")
            print("-" * 80)
            for i, match in enumerate(result['questionable_joints'][:5], 1):
                master_joint = match.get('Master Joint Number', 'N/A')
                target_joint = match.get('Target Joint Number', 'N/A')
                match_type = match.get('Match_Type', 'unknown')
                note = match.get('Note', '')
                print(f"  {i}. M:{master_joint} → T:{target_joint} ({match_type}) - {note}")
        
        # Display sample unmatched
        if result['unmatched_joints']:
            print(f"\nSample Unmatched Joints (first 5):")
            print("-" * 80)
            for i, unmatch in enumerate(result['unmatched_joints'][:5], 1):
                master_joint = unmatch.get('Master Joint Number', '') or 'N/A'
                target_joint = unmatch.get('Target Joint Number', '') or 'N/A'
                if master_joint != 'N/A' and target_joint == 'N/A':
                    print(f"  {i}. Unmatched Master: {master_joint}")
                elif target_joint != 'N/A' and master_joint == 'N/A':
                    print(f"  {i}. Unmatched Target: {target_joint}")
                else:
                    print(f"  {i}. Master: {master_joint}, Target: {target_joint}")
        
        print("\n" + "=" * 80)
        print("[OK] Joint matching completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
