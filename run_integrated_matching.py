"""
Runner script for integrated joint matching algorithm.

This script combines:
1. Original joint matching (marker alignment, forward/backward matching)
2. Cumulative length matching for unmatched joints

Usage:
    python run_integrated_matching.py

Configure your GUIDs and database settings below.
"""

import logging
import sys
from sqlalchemy import create_engine

# Import the integrated matching function
sys.path.append('Scripts')
from integrated_joint_matching import execute_integrated_joint_matching

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    
    # ========== CONFIGURATION ==========
    # Database connection settings
    DB_CONFIG = {
        'host': 'localhost',
        'port': '5432',
        'database': 'ili',
        'user': 'postgres',
        'password': 'RedPlums2025.'
    }
    
    # Inspection GUIDs
    MASTER_GUID = "f7e2c9d5-8a4b-4e1f-b3c6-d8a2e7f1c5b4"
    TARGET_GUIDS = ["a3f5c2e1-7b9d-4f8c-9e2a-b1d6c4f7e2a9"]
    
    # Output file path
    OUTPUT_PATH = "integrated_matching_results.xlsx"
    
    # Cumulative matching parameters
    USE_CUMULATIVE = True  # Set to False to disable cumulative matching
    CUMULATIVE_TOLERANCE = 0.10  # 10% length tolerance
    CUMULATIVE_MAX_AGGREGATE = 5  # Max joints to combine
    CUMULATIVE_MIN_CONFIDENCE = 0.60  # Minimum confidence score
    
    # ===================================
    
    logger.info("=" * 80)
    logger.info("INTEGRATED JOINT MATCHING - RUNNER")
    logger.info("=" * 80)
    logger.info(f"Master GUID: {MASTER_GUID}")
    logger.info(f"Target GUIDs: {TARGET_GUIDS}")
    logger.info(f"Output file: {OUTPUT_PATH}")
    logger.info(f"Cumulative matching: {'ENABLED' if USE_CUMULATIVE else 'DISABLED'}")
    logger.info("=" * 80)
    
    try:
        # Create database engine
        connection_string = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )
        engine = create_engine(connection_string)
        logger.info("Database connection established")
        
        # Execute integrated matching
        result = execute_integrated_joint_matching(
            engine=engine,
            master_guid=MASTER_GUID,
            target_guids=TARGET_GUIDS,
            output_path=OUTPUT_PATH,
            use_cumulative_for_unmatched=USE_CUMULATIVE,
            cumulative_tolerance=CUMULATIVE_TOLERANCE,
            cumulative_max_aggregate=CUMULATIVE_MAX_AGGREGATE,
            cumulative_min_confidence=CUMULATIVE_MIN_CONFIDENCE
        )
        
        # Display summary
        summary = result['run_summary']
        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL RESULTS SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Master: {summary['Master_ili_id']} ({summary['Total_master_joints']} joints)")
        logger.info(f"Target: {summary['Target_ili_id']} ({summary['Total_target_joints']} joints)")
        logger.info(f"")
        logger.info(f"MATCHED JOINTS:")
        logger.info(f"  Total matched: {summary['Matched_joints']}")
        logger.info(f"    - From original algorithm: {summary['Matched_from_original']}")
        logger.info(f"    - From cumulative matching: {summary['Matched_from_cumulative']}")
        logger.info(f"")
        logger.info(f"UNMATCHED JOINTS: {summary['Unmatched_joints']}")
        logger.info(f"")
        logger.info(f"MATCH RATES:")
        logger.info(f"  Master: {summary['Master_joint_percentage']:.2f}%")
        logger.info(f"  Target: {summary['Target_joint_percentage']:.2f}%")
        logger.info(f"")
        logger.info(f"Flow Direction: {summary['Flow_direction']}")
        logger.info("=" * 80)
        logger.info(f"✓ Results saved to: {OUTPUT_PATH}")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during matching: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
