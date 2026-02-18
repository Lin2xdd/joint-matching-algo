"""
Flexible Joint Matching Algorithm
Overcomes limitations of the existing algorithm by allowing:
- 1-to-1 matching (normal)
- 1-to-many matching (joint splits)
- many-to-1 matching (joint merges)
- Distance-based marker alignment
- Adaptive tolerance thresholds

Features:
- Database connectivity for loading joints
- Excel export with matched/unmatched tabs
- Standalone execution capability

Author: Enhanced Joint Matching System
Date: 2026-02-12
Updated: 2026-02-13 - Added database and Excel export
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import logging
from sqlalchemy import create_engine, text, Engine
import os

logger = logging.getLogger(__name__)


@dataclass
class JointMatch:
    """Represents a match between master and target joints."""
    master_joints: List[int]
    target_joints: List[int]
    match_type: str  # '1-to-1', '1-to-N', 'N-to-1', 'N-to-M'
    confidence: float  # 0.0 to 1.0
    master_total_length: float
    target_total_length: float
    length_difference: float
    master_start_distance: float
    target_start_distance: float
    
    def is_split(self) -> bool:
        """Check if this represents a joint split (1-to-many)."""
        return len(self.master_joints) == 1 and len(self.target_joints) > 1
    
    def is_merge(self) -> bool:
        """Check if this represents a joint merge (many-to-1)."""
        return len(self.master_joints) > 1 and len(self.target_joints) == 1
    
    def is_simple(self) -> bool:
        """Check if this is a simple 1-to-1 match."""
        return len(self.master_joints) == 1 and len(self.target_joints) == 1


@dataclass
class MarkerMatch:
    """Represents a matched marker (anchor point) between inspections."""
    master_joint: int
    target_joint: int
    master_distance: float
    target_distance: float
    master_length: float
    target_length: float
    confidence: float


class FlexibleJointMatcher:
    """
    Implements integrated flexible joint matching with:
    - Solution 1: Cumulative Length Matching
    - Solution 2: Distance-Based Markers
    - Solution 3: Greedy Best-Match
    """
    
    def __init__(self, 
                 length_tolerance: float = 0.10,
                 max_aggregate: int = 5,
                 marker_diff_threshold: float = 3.0,
                 marker_distance_tolerance: float = 5.0,
                 marker_length_tolerance: float = 1.0,
                 min_confidence: float = 0.60):
        """
        Initialize the flexible joint matcher.
        
        Args:
            length_tolerance: Percentage tolerance for length matching (default 10%)
            max_aggregate: Maximum number of joints to aggregate (default 5)
            marker_diff_threshold: Minimum length difference for marker detection (default 3m)
            marker_distance_tolerance: Distance tolerance for marker matching (default 5m)
            marker_length_tolerance: Length tolerance for marker matching (default 1m)
            min_confidence: Minimum confidence to accept a match (default 0.60)
        """
        self.length_tolerance = length_tolerance
        self.max_aggregate = max_aggregate
        self.marker_diff_threshold = marker_diff_threshold
        self.marker_distance_tolerance = marker_distance_tolerance
        self.marker_length_tolerance = marker_length_tolerance
        self.min_confidence = min_confidence
    
    def prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare joint dataframe with computed fields.
        
        Args:
            df: DataFrame with columns [joint_number, joint_length]
        
        Returns:
            Enhanced DataFrame with cumulative_distance and difference columns
        """
        df = df.copy()
        
        # Ensure proper sorting by joint number
        df['joint_number'] = df['joint_number'].astype(int)
        df = df.sort_values('joint_number').reset_index(drop=True)
        
        # Calculate cumulative distance from start
        df['cumulative_distance'] = df['joint_length'].cumsum()
        
        # Calculate difference (length change) from previous joint
        df['difference'] = df['joint_length'].diff().fillna(0)
        
        return df
    
    def find_distance_based_markers(self, 
                                    master_df: pd.DataFrame, 
                                    target_df: pd.DataFrame) -> List[MarkerMatch]:
        """
        Solution 2: Find markers based on cumulative distance and length signatures.
        
        Identifies "anchor points" where large length changes occur and matches them
        between inspections based on their position (cumulative distance) and signature.
        
        Args:
            master_df: Master inspection joints
            target_df: Target inspection joints
        
        Returns:
            List of matched markers
        """
        # Find potential markers (joints with large length differences)
        master_markers = master_df[
            abs(master_df['difference']) > self.marker_diff_threshold
        ].copy()
        
        target_markers = target_df[
            abs(target_df['difference']) > self.marker_diff_threshold
        ].copy()
        
        logger.info(f"Found {len(master_markers)} master markers and {len(target_markers)} target markers")
        
        # Match markers based on cumulative distance and signature
        marker_matches = []
        used_target_indices = set()
        
        for _, master_marker in master_markers.iterrows():
            best_match = None
            best_score = 0
            best_target_idx = None
            
            for target_idx, target_marker in target_markers.iterrows():
                if target_idx in used_target_indices:
                    continue
                
                # Calculate similarity score
                distance_diff = abs(
                    master_marker['cumulative_distance'] - 
                    target_marker['cumulative_distance']
                )
                
                length_diff = abs(
                    master_marker['joint_length'] - 
                    target_marker['joint_length']
                )
                
                signature_diff = abs(
                    master_marker['difference'] - 
                    target_marker['difference']
                )
                
                # Check if within tolerances
                if (distance_diff <= self.marker_distance_tolerance and
                    length_diff <= self.marker_length_tolerance and
                    signature_diff <= self.marker_length_tolerance):
                    
                    # Calculate confidence score (inverse of normalized differences)
                    distance_score = 1.0 - min(distance_diff / self.marker_distance_tolerance, 1.0)
                    length_score = 1.0 - min(length_diff / self.marker_length_tolerance, 1.0)
                    signature_score = 1.0 - min(signature_diff / self.marker_length_tolerance, 1.0)
                    
                    # Weighted average (distance most important, then signature, then length)
                    score = 0.5 * distance_score + 0.3 * signature_score + 0.2 * length_score
                    
                    if score > best_score:
                        best_score = score
                        best_match = target_marker
                        best_target_idx = target_idx
            
            # If a good match found, record it
            if best_match is not None and best_score >= 0.7:
                marker_matches.append(MarkerMatch(
                    master_joint=int(master_marker['joint_number']),
                    target_joint=int(best_match['joint_number']),
                    master_distance=master_marker['cumulative_distance'],
                    target_distance=best_match['cumulative_distance'],
                    master_length=master_marker['joint_length'],
                    target_length=best_match['joint_length'],
                    confidence=best_score
                ))
                used_target_indices.add(best_target_idx)
                
                logger.debug(
                    f"Marker match: M-J{master_marker['joint_number']} "
                    f"(@{master_marker['cumulative_distance']:.1f}m) ↔ "
                    f"T-J{best_match['joint_number']} "
                    f"(@{best_match['cumulative_distance']:.1f}m) "
                    f"confidence={best_score:.2f}"
                )
        
        logger.info(f"Matched {len(marker_matches)} markers with confidence >= 0.7")
        return marker_matches
    
    def cumulative_length_matching(self,
                                   master_df: pd.DataFrame,
                                   m_idx: int,
                                   target_df: pd.DataFrame,
                                   t_idx: int) -> Optional[JointMatch]:
        """
        Solution 1: Try to match joints using cumulative length comparison.
        
        Attempts matching in order:
        1. 1-to-1 (fastest)
        2. 1-to-many (master joint split)
        3. many-to-1 (master joints merged)
        
        Args:
            master_df: Master inspection joints
            m_idx: Current master index
            target_df: Target inspection joints
            t_idx: Current target index
        
        Returns:
            JointMatch if successful, None otherwise
        """
        if m_idx >= len(master_df) or t_idx >= len(target_df):
            return None
        
        master_joint = master_df.iloc[m_idx]
        target_joint = target_df.iloc[t_idx]
        
        # Try 1-to-1 match first (fastest path)
        if self._is_length_match(master_joint['joint_length'], 
                                 target_joint['joint_length']):
            confidence = self._calculate_confidence(
                master_joint['joint_length'],
                target_joint['joint_length']
            )
            
            if confidence >= self.min_confidence:
                return JointMatch(
                    master_joints=[int(master_joint['joint_number'])],
                    target_joints=[int(target_joint['joint_number'])],
                    match_type='1-to-1',
                    confidence=confidence,
                    master_total_length=master_joint['joint_length'],
                    target_total_length=target_joint['joint_length'],
                    length_difference=abs(master_joint['joint_length'] - 
                                        target_joint['joint_length']),
                    master_start_distance=master_joint['cumulative_distance'] - 
                                         master_joint['joint_length'],
                    target_start_distance=target_joint['cumulative_distance'] - 
                                         target_joint['joint_length']
                )
        
        # Try 1-to-many (master joint was split into multiple target joints)
        cumulative_target = 0
        target_joints_list = []
        
        for t_count in range(1, self.max_aggregate + 1):
            if t_idx + t_count > len(target_df):
                break
            
            current_target = target_df.iloc[t_idx + t_count - 1]
            cumulative_target += current_target['joint_length']
            target_joints_list.append(int(current_target['joint_number']))
            
            if self._is_length_match(master_joint['joint_length'], cumulative_target):
                # Penalize confidence slightly for splits (more uncertainty)
                base_confidence = self._calculate_confidence(
                    master_joint['joint_length'],
                    cumulative_target
                )
                # Reduce confidence by 5% per additional joint
                split_penalty = 0.05 * (t_count - 1)
                confidence = max(base_confidence - split_penalty, 0.0)
                
                if confidence >= self.min_confidence:
                    return JointMatch(
                        master_joints=[int(master_joint['joint_number'])],
                        target_joints=target_joints_list.copy(),
                        match_type=f'1-to-{t_count}',
                        confidence=confidence,
                        master_total_length=master_joint['joint_length'],
                        target_total_length=cumulative_target,
                        length_difference=abs(master_joint['joint_length'] - 
                                            cumulative_target),
                        master_start_distance=master_joint['cumulative_distance'] - 
                                             master_joint['joint_length'],
                        target_start_distance=target_df.iloc[t_idx]['cumulative_distance'] - 
                                             target_df.iloc[t_idx]['joint_length']
                    )
        
        # Try many-to-1 (multiple master joints merged into one target joint)
        cumulative_master = 0
        master_joints_list = []
        
        for m_count in range(1, self.max_aggregate + 1):
            if m_idx + m_count > len(master_df):
                break
            
            current_master = master_df.iloc[m_idx + m_count - 1]
            cumulative_master += current_master['joint_length']
            master_joints_list.append(int(current_master['joint_number']))
            
            if self._is_length_match(cumulative_master, target_joint['joint_length']):
                # Penalize confidence slightly for merges
                base_confidence = self._calculate_confidence(
                    cumulative_master,
                    target_joint['joint_length']
                )
                merge_penalty = 0.05 * (m_count - 1)
                confidence = max(base_confidence - merge_penalty, 0.0)
                
                if confidence >= self.min_confidence:
                    return JointMatch(
                        master_joints=master_joints_list.copy(),
                        target_joints=[int(target_joint['joint_number'])],
                        match_type=f'{m_count}-to-1',
                        confidence=confidence,
                        master_total_length=cumulative_master,
                        target_total_length=target_joint['joint_length'],
                        length_difference=abs(cumulative_master - 
                                            target_joint['joint_length']),
                        master_start_distance=master_df.iloc[m_idx]['cumulative_distance'] - 
                                             master_df.iloc[m_idx]['joint_length'],
                        target_start_distance=target_joint['cumulative_distance'] - 
                                             target_joint['joint_length']
                    )
        
        # No match found
        return None
    
    def _is_length_match(self, length1: float, length2: float) -> bool:
        """Check if two lengths match within percentage tolerance."""
        if length1 <= 0 or length2 <= 0:
            return False
        
        avg_length = (length1 + length2) / 2
        diff = abs(length1 - length2)
        diff_ratio = diff / avg_length
        
        return diff_ratio <= self.length_tolerance
    
    def _calculate_confidence(self, length1: float, length2: float) -> float:
        """Calculate confidence score for a length match."""
        if length1 <= 0 or length2 <= 0:
            return 0.0
        
        avg_length = (length1 + length2) / 2
        diff = abs(length1 - length2)
        diff_ratio = diff / avg_length
        
        # Confidence is inverse of difference ratio, normalized to tolerance
        confidence = 1.0 - (diff_ratio / self.length_tolerance)
        
        return max(0.0, min(1.0, confidence))
    
    def greedy_segment_matching(self,
                               master_df: pd.DataFrame,
                               target_df: pd.DataFrame,
                               master_start: int = 0,
                               master_end: Optional[int] = None,
                               target_start: int = 0,
                               target_end: Optional[int] = None) -> List[JointMatch]:
        """
        Solution 3: Greedy best-match algorithm for a segment.
        
        Iterates through joints and tries to find the best match at each position.
        """
        if master_end is None:
            master_end = len(master_df)
        if target_end is None:
            target_end = len(target_df)
        
        matches = []
        m_idx = master_start
        t_idx = target_start
        
        logger.debug(
            f"Matching segment: Master[{master_start}:{master_end}] "
            f"↔ Target[{target_start}:{target_end}]"
        )
        
        while m_idx < master_end and t_idx < target_end:
            # Try to find a match at current position
            match = self.cumulative_length_matching(
                master_df, m_idx, target_df, t_idx
            )
            
            if match is not None:
                matches.append(match)
                
                # Advance indices based on match type
                m_idx += len(match.master_joints)
                t_idx += len(match.target_joints)
                
                logger.debug(
                    f"  Match: M{match.master_joints} ↔ T{match.target_joints} "
                    f"({match.match_type}, conf={match.confidence:.2f})"
                )
            else:
                # No match found at current position, advance master
                logger.debug(
                    f"  No match for master joint {master_df.iloc[m_idx]['joint_number']}"
                )
                m_idx += 1
        
        logger.debug(f"Segment complete: {len(matches)} matches found")
        return matches
    
    def match_inspections(self,
                         master_df: pd.DataFrame,
                         target_df: pd.DataFrame) -> Tuple[List[JointMatch], Dict]:
        """
        Main entry point: Match two inspections using the integrated algorithm.
        
        Combines all three solutions:
        1. Find distance-based markers
        2. Divide into segments
        3. Apply greedy matching with cumulative length comparison
        """
        logger.info("=" * 80)
        logger.info("Starting Flexible Joint Matching")
        logger.info("=" * 80)
        
        # Prepare dataframes
        master_df = self.prepare_dataframe(master_df)
        target_df = self.prepare_dataframe(target_df)
        
        logger.info(f"Master inspection: {len(master_df)} joints")
        logger.info(f"Target inspection: {len(target_df)} joints")
        
        # Find markers
        markers = self.find_distance_based_markers(master_df, target_df)
        
        all_matches = []
        
        if len(markers) == 0:
            logger.warning("No markers found, processing entire dataset as one segment")
            segment_matches = self.greedy_segment_matching(
                master_df, target_df
            )
            all_matches.extend(segment_matches)
        else:
            logger.info(f"Processing {len(markers) + 1} segments between markers")
            
            # Process segments between consecutive markers
            prev_master_idx = 0
            prev_target_idx = 0
            
            for marker in markers:
                # Find current marker indices
                curr_master_idx = master_df[
                    master_df['joint_number'] == marker.master_joint
                ].index[0]
                
                curr_target_idx = target_df[
                    target_df['joint_number'] == marker.target_joint
                ].index[0]
                
                # Match segment before this marker
                if curr_master_idx > prev_master_idx or curr_target_idx > prev_target_idx:
                    segment_matches = self.greedy_segment_matching(
                        master_df, target_df,
                        prev_master_idx, curr_master_idx,
                        prev_target_idx, curr_target_idx
                    )
                    all_matches.extend(segment_matches)
                
                # Add marker as a match
                marker_match = JointMatch(
                    master_joints=[marker.master_joint],
                    target_joints=[marker.target_joint],
                    match_type='marker',
                    confidence=marker.confidence,
                    master_total_length=marker.master_length,
                    target_total_length=marker.target_length,
                    length_difference=abs(marker.master_length - marker.target_length),
                    master_start_distance=marker.master_distance - marker.master_length,
                    target_start_distance=marker.target_distance - marker.target_length
                )
                all_matches.append(marker_match)
                
                # Update for next iteration
                prev_master_idx = curr_master_idx + 1
                prev_target_idx = curr_target_idx + 1
            
            # Match remaining segment after last marker
            if prev_master_idx < len(master_df) or prev_target_idx < len(target_df):
                segment_matches = self.greedy_segment_matching(
                    master_df, target_df,
                    prev_master_idx, len(master_df),
                    prev_target_idx, len(target_df)
                )
                all_matches.extend(segment_matches)
        
        # Compile metadata
        matched_master = set()
        matched_target = set()
        
        for match in all_matches:
            matched_master.update(match.master_joints)
            matched_target.update(match.target_joints)
        
        splits = sum(1 for m in all_matches if m.is_split())
        merges = sum(1 for m in all_matches if m.is_merge())
        simple = sum(1 for m in all_matches if m.is_simple())
        
        metadata = {
            'total_matches': len(all_matches),
            'simple_matches': simple,
            'split_matches': splits,
            'merge_matches': merges,
            'master_joints_matched': len(matched_master),
            'target_joints_matched': len(matched_target),
            'master_match_rate': len(matched_master) / len(master_df) * 100 if len(master_df) > 0 else 0,
            'target_match_rate': len(matched_target) / len(target_df) * 100 if len(target_df) > 0 else 0,
            'unmatched_master': len(master_df) - len(matched_master),
            'unmatched_target': len(target_df) - len(matched_target),
            'markers_found': len(markers),
            'avg_confidence': np.mean([m.confidence for m in all_matches]) if all_matches else 0
        }
        
        logger.info("=" * 80)
        logger.info("Matching Complete")
        logger.info("=" * 80)
        logger.info(f"Total matches: {metadata['total_matches']}")
        logger.info(f"  - 1-to-1 matches: {simple}")
        logger.info(f"  - Split matches (1-to-many): {splits}")
        logger.info(f"  - Merge matches (many-to-1): {merges}")
        logger.info(f"Master match rate: {metadata['master_match_rate']:.1f}%")
        logger.info(f"Target match rate: {metadata['target_match_rate']:.1f}%")
        logger.info(f"Average confidence: {metadata['avg_confidence']:.2f}")
        logger.info("=" * 80)
        
        return all_matches, metadata


def format_matches_to_dataframe(matches: List[JointMatch]) -> pd.DataFrame:
    """Convert list of JointMatch objects to a pandas DataFrame."""
    records = []
    
    for match in matches:
        records.append({
            'Master_Joint_Numbers': ','.join(map(str, match.master_joints)),
            'Target_Joint_Numbers': ','.join(map(str, match.target_joints)),
            'Match_Type': match.match_type,
            'Confidence': round(match.confidence, 3),
            'Master_Total_Length': round(match.master_total_length, 3),
            'Target_Total_Length': round(match.target_total_length, 3),
            'Length_Difference': round(match.length_difference, 3),
            'Master_Start_Distance': round(match.master_start_distance, 3),
            'Target_Start_Distance': round(match.target_start_distance, 3),
            'Is_Split': match.is_split(),
            'Is_Merge': match.is_merge()
        })
    
    return pd.DataFrame(records)


# ========== Database Integration ==========

def create_database_engine(host: str = 'localhost',
                          port: str = '5432',
                          database: str = 'ili',
                          user: str = 'postgres',
                          password: str = '') -> Engine:
    """
    Create SQLAlchemy engine for database connection.
    
    Args:
        host: Database host (default: localhost)
        port: Database port (default: 5432)
        database: Database name (default: ili)
        user: Database user (default: postgres)
        password: Database password
        
    Returns:
        SQLAlchemy Engine
    """
    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    engine = create_engine(connection_string)
    logger.info(f"Database engine created: {host}:{port}/{database}")
    return engine


def load_joints_from_database(engine: Engine, inspection_guid: str) -> pd.DataFrame:
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
    
    logger.info(f"Loading joints for inspection GUID: {inspection_guid}")
    
    with engine.connect() as conn:
        df = pd.read_sql_query(con=conn, sql=query, params={'guid': str(inspection_guid)})
    
    # Remove nulls and ensure proper types
    df = df.dropna(subset=['joint_number', 'joint_length'])
    df['joint_number'] = df['joint_number'].astype(int)
    df['joint_length'] = df['joint_length'].astype(float)
    
    logger.info(f"Loaded {len(df)} joints")
    return df


def get_ili_id_from_database(engine: Engine, inspection_guid: str) -> str:
    """
    Get ILI ID for an inspection from database.
    
    Args:
        engine: SQLAlchemy engine
        inspection_guid: Inspection GUID
        
    Returns:
        ILI ID string
    """
    query = text("SELECT ili_id FROM public.joints WHERE insp_guid = :guid LIMIT 1")
    
    with engine.connect() as conn:
        ili_id = conn.execute(query, {'guid': str(inspection_guid)}).scalar()
    
    return str(ili_id) if ili_id else 'Unknown'


# ========== Excel Export ==========

def export_results_to_excel(matches: List[JointMatch],
                            metadata: Dict,
                            master_df: pd.DataFrame,
                            target_df: pd.DataFrame,
                            output_path: str,
                            master_ili_id: str = 'Master',
                            target_ili_id: str = 'Target') -> bool:
    """
    Export matching results to Excel file with separate tabs.
    
    Args:
        matches: List of JointMatch objects
        metadata: Metadata dictionary from matching
        master_df: Master inspection DataFrame
        target_df: Target inspection DataFrame
        output_path: Path to output Excel file
        master_ili_id: Master ILI ID for display
        target_ili_id: Target ILI ID for display
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert matches to DataFrame
        matches_df = format_matches_to_dataframe(matches)
        
        # Build matched joints (1-to-1 and markers)
        matched_list = []
        split_merge_list = []
        matched_master_joints = set()
        matched_target_joints = set()
        
        for _, row in matches_df.iterrows():
            master_joints = [int(j) for j in row['Master_Joint_Numbers'].split(',')]
            target_joints = [int(j) for j in row['Target_Joint_Numbers'].split(',')]
            
            matched_master_joints.update(master_joints)
            matched_target_joints.update(target_joints)
            
            if len(master_joints) == 1 and len(target_joints) == 1:
                # Simple 1-to-1 match or marker
                matched_list.append({
                    'Master Joint': master_joints[0],
                    'Target Joint': target_joints[0],
                    'Match Type': row['Match_Type'],
                    'Confidence': row['Confidence'],
                    'Master Length (m)': row['Master_Total_Length'],
                    'Target Length (m)': row['Target_Total_Length'],
                    'Length Diff (m)': row['Length_Difference']
                })
            else:
                # Split or merge
                split_merge_list.append({
                    'Master Joints': row['Master_Joint_Numbers'],
                    'Target Joints': row['Target_Joint_Numbers'],
                    'Match Type': row['Match_Type'],
                    'Confidence': row['Confidence'],
                    'Master Total Length (m)': row['Master_Total_Length'],
                    'Target Total Length (m)': row['Target_Total_Length'],
                    'Length Diff (m)': row['Length_Difference']
                })
        
        # Build unmatched joints
        unmatched_master = []
        unmatched_target = []
        
        for _, row in master_df.iterrows():
            joint_num = int(row['joint_number'])
            if joint_num not in matched_master_joints:
                unmatched_master.append({
                    'Joint Number': joint_num,
                    'Length (m)': row['joint_length']
                })
        
        for _, row in target_df.iterrows():
            joint_num = int(row['joint_number'])
            if joint_num not in matched_target_joints:
                unmatched_target.append({
                    'Joint Number': joint_num,
                    'Length (m)': row['joint_length']
                })
        
        # Create DataFrames
        matched_df = pd.DataFrame(matched_list)
        splits_merges_df = pd.DataFrame(split_merge_list)
        unmatched_master_df = pd.DataFrame(unmatched_master)
        unmatched_target_df = pd.DataFrame(unmatched_target)
        
        # Build summary
        summary_data = {
            'Metric': [
                'Master ILI ID',
                'Target ILI ID',
                'Total Master Joints',
                'Total Target Joints',
                'Matched Master Joints',
                'Matched Target Joints',
                'Master Match Rate (%)',
                'Target Match Rate (%)',
                'Total Matches',
                '  - Simple (1-to-1)',
                '  - Marker Matches',
                '  - Split Matches (1-to-many)',
                '  - Merge Matches (many-to-1)',
                'Unmatched Master Joints',
                'Unmatched Target Joints',
                'Markers Found',
                'Average Confidence'
            ],
            'Value': [
                master_ili_id,
                target_ili_id,
                len(master_df),
                len(target_df),
                len(matched_master_joints),
                len(matched_target_joints),
                round(metadata['master_match_rate'], 2),
                round(metadata['target_match_rate'], 2),
                metadata['total_matches'],
                metadata['simple_matches'],
                sum(1 for m in matches if m.match_type == 'marker'),
                metadata['split_matches'],
                metadata['merge_matches'],
                len(unmatched_master),
                len(unmatched_target),
                metadata['markers_found'],
                round(metadata['avg_confidence'], 3)
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        
        # Write to Excel with multiple sheets
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            matched_df.to_excel(writer, sheet_name='Matched Joints', index=False)
            unmatched_master_df.to_excel(writer, sheet_name=f'Unmatched {master_ili_id}', index=False)
            unmatched_target_df.to_excel(writer, sheet_name=f'Unmatched {target_ili_id}', index=False)
            
            if not splits_merges_df.empty:
                splits_merges_df.to_excel(writer, sheet_name='Splits & Merges', index=False)
        
        logger.info(f"Results exported to: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to export results: {str(e)}")
        return False


# ========== Main Execution Function ==========

def run_flexible_matching(master_guid: str,
                         target_guid: str,
                         output_path: str,
                         db_host: str = 'localhost',
                         db_port: str = '5432',
                         db_name: str = 'ili',
                         db_user: str = 'postgres',
                         db_password: str = '',
                         length_tolerance: float = 0.10,
                         max_aggregate: int = 5,
                         marker_diff_threshold: float = 3.0,
                         marker_distance_tolerance: float = 5.0,
                         marker_length_tolerance: float = 1.0,
                         min_confidence: float = 0.60) -> Dict:
    """
    Complete flexible joint matching workflow: load from database, match, export to Excel.
    
    Args:
        master_guid: Master inspection GUID
        target_guid: Target inspection GUID
        output_path: Path to output Excel file
        db_host: Database host (default: localhost)
        db_port: Database port (default: 5432)
        db_name: Database name (default: ili)
        db_user: Database user (default: postgres)
        db_password: Database password
        length_tolerance: Percentage tolerance for length matching (default: 0.10 = 10%)
        max_aggregate: Maximum joints to aggregate (default: 5)
        marker_diff_threshold: Min length change for markers in meters (default: 3.0)
        marker_distance_tolerance: Distance tolerance for markers in meters (default: 5.0)
        marker_length_tolerance: Length tolerance for markers in meters (default: 1.0)
        min_confidence: Minimum confidence threshold (default: 0.60)
        
    Returns:
        Dictionary with metadata and status
    """
    logger.info("=" * 80)
    logger.info("Flexible Joint Matching - Standalone Execution")
    logger.info("=" * 80)
    
    try:
        # Create database engine
        engine = create_database_engine(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        
        # Load joint data
        logger.info(f"Master GUID: {master_guid}")
        master_df = load_joints_from_database(engine, master_guid)
        master_ili_id = get_ili_id_from_database(engine, master_guid)
        
        logger.info(f"Target GUID: {target_guid}")
        target_df = load_joints_from_database(engine, target_guid)
        target_ili_id = get_ili_id_from_database(engine, target_guid)
        
        if master_df.empty:
            raise ValueError(f"No joints found for master GUID: {master_guid}")
        if target_df.empty:
            raise ValueError(f"No joints found for target GUID: {target_guid}")
        
        logger.info(f"Master: {master_ili_id} ({len(master_df)} joints)")
        logger.info(f"Target: {target_ili_id} ({len(target_df)} joints)")
        
        # Create matcher with specified parameters
        matcher = FlexibleJointMatcher(
            length_tolerance=length_tolerance,
            max_aggregate=max_aggregate,
            marker_diff_threshold=marker_diff_threshold,
            marker_distance_tolerance=marker_distance_tolerance,
            marker_length_tolerance=marker_length_tolerance,
            min_confidence=min_confidence
        )
        
        # Execute matching
        matches, metadata = matcher.match_inspections(master_df, target_df)
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        
        # Export to Excel
        success = export_results_to_excel(
            matches=matches,
            metadata=metadata,
            master_df=master_df,
            target_df=target_df,
            output_path=output_path,
            master_ili_id=master_ili_id,
            target_ili_id=target_ili_id
        )
        
        if success:
            logger.info("=" * 80)
            logger.info("✓ Matching completed successfully!")
            logger.info(f"✓ Results saved to: {os.path.abspath(output_path)}")
            logger.info("=" * 80)
        
        return {
            'success': success,
            'output_path': os.path.abspath(output_path),
            'master_ili_id': master_ili_id,
            'target_ili_id': target_ili_id,
            'metadata': metadata
        }
        
    except Exception as e:
        logger.error(f"Error during matching: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


# ========== CLI Entry Point ==========

if __name__ == "__main__":
    """
    Example usage when running as standalone script.
    """
    import sys
    
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example configuration
    MASTER_GUID = "8c7f3d9a-2e5b-4a1c-8f6d-3e2a9b5c1d7f"
    TARGET_GUID = "d3f9e5a1-7c2b-4f8d-9e3a-5b1c6a4d8f2e"
    OUTPUT_PATH = "flexible_matching_results.xlsx"
    
    # Database credentials
    DB_CONFIG = {
        'db_host': 'localhost',
        'db_port': '5432',
        'db_name': 'ili',
        'db_user': 'postgres',
        'db_password': 'RedPlums2025.'
    }
    
    print("\n" + "=" * 80)
    print("FLEXIBLE JOINT MATCHING - STANDALONE MODE")
    print("=" * 80)
    print("\nTo use with your own data, edit the configuration in this file:")
    print(f"  - MASTER_GUID: {MASTER_GUID}")
    print(f"  - TARGET_GUID: {TARGET_GUID}")
    print(f"  - OUTPUT_PATH: {OUTPUT_PATH}")
    print(f"  - DB_CONFIG: {DB_CONFIG}")
    print("\nOr call run_flexible_matching() function directly.")
    print("=" * 80 + "\n")
    
    # Run matching
    result = run_flexible_matching(
        master_guid=MASTER_GUID,
        target_guid=TARGET_GUID,
        output_path=OUTPUT_PATH,
        **DB_CONFIG
    )
    
    if result['success']:
        sys.exit(0)
    else:
        sys.exit(1)
