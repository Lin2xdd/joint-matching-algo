"""
Integrated Joint Matching Algorithm
Single-phase matching with marker alignment, confidence-based forward/backward matching,
cumulative length matching for complex joint relationships, absolute distance matching,
and short joint merge post-processing.

Workflow:
1. Marker alignment between inspections
2. For each chunk between markers:
   - Step 1: Forward matching (high-confidence 1-to-1 matches)
   - Step 2: Backward matching (high-confidence 1-to-1 matches in gaps)
   - Step 3: Cumulative matching (aggregate matches for unmatched joints)
3. Head section (before first marker):
   - Step 1: Backward matching (from first marker toward start)
   - Step 2: Forward matching (fill gaps from start)
   - Step 3: Cumulative matching in reverse order (align with backward direction)
   - **EXCLUDES first marker** to prevent duplicate matching
4. Tail section (after last marker):
   - Step 1: Forward matching (from last marker toward end)
   - Step 2: Backward matching (fill gaps from end)
   - Step 3: Cumulative matching in forward order (align with forward direction)
   - **EXCLUDES last marker** to prevent duplicate matching
5. Absolute distance matching:
   - Match remaining unmatched joints with absolute length difference < 1.5m
   - Position-based matching between known matched joints (low confidence)
6. Short joint merge post-processing:
   - Merge unmatched short joints (< 3m) with neighboring matched joints
   - Creates 1-to-many, many-to-1, or many-to-many matches as appropriate
   - Validates merged matches against confidence & tolerance thresholds
   - Example: M2770 → T2770 (1-to-1) + unmatched T2780 → M2770 → T2770+T2780 (1-to-2)
7. Merge all matched results and report unmatched joints
8. Export to Excel with matched and unmatched tabs

Key Design Notes:
- Head section cumulative matching processes in REVERSE order to align with
  backward matching direction (prevents incorrect sequential matches)
- Tail section cumulative matching processes in FORWARD order to align with
  forward matching direction
- Both head and tail use full matching pipeline: backward/forward → cumulative
- **Marker Exclusion:** Markers are excluded from head/tail cumulative matching
  ranges because they're already matched during marker alignment (Step 1).
  This prevents duplicate matches where the same joint is matched multiple times.
- **Absolute Distance Matching:** Matches unmatched joints where absolute length
  difference < 1.5m, using position context from matched joints. Produces LOW confidence.
- **Unmatched Joint Merge:** Post-processes ALL remaining unmatched joints by attempting
  to merge them with neighboring matched joints. Processes joints sequentially and updates
  match index dynamically, enabling cascading merges. Prevents greedy 1-to-1 bias where a
  dominant piece matches but leaves other pieces unmatched.

Author: Integrated Joint Matching System
Date: 2026-03-05 (Added short joint merge post-processing)
"""

import uuid
import numpy as np
import pandas as pd
from sqlalchemy import Engine, text
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
import os

# Import original joint matching functions
from joint_matching import (
    joint_diff_calc,
    pairs_generator,
    match_pct_calc,
    match_pct_calc_with_distance,
    unchunk_dataframe,
    clean_column_none_to_null,
    smart_column_filter,
    safe_rename_columns
)

# Import post-processing merge
from postprocessing_merge import postprocessing_merge

logger = logging.getLogger(__name__)


def _calculate_confidence(length1: float, length2: float, tolerance: float = 0.30) -> float:
    """Calculate confidence score for a length match."""
    if length1 <= 0 or length2 <= 0:
        return 0.0
    
    avg_length = (length1 + length2) / 2
    diff = abs(length1 - length2)
    diff_ratio = diff / avg_length
    
    # Confidence is inverse of difference ratio, normalized to tolerance
    confidence = 1.0 - (diff_ratio / tolerance)
    
    return max(0.0, min(1.0, confidence))


def _is_length_within_tolerance(length1: float, length2: float, tolerance: float = 0.30) -> bool:
    """Check if two lengths are within percentage tolerance."""
    if length1 <= 0 or length2 <= 0:
        return False

    avg_length = (length1 + length2) / 2
    diff = abs(length1 - length2)
    diff_ratio = diff / avg_length
    return diff_ratio <= tolerance


def _evaluate_match_quality(length1: float,
                           length2: float,
                           confidence_threshold: float = 0.60,
                           tolerance: float = 0.30) -> Tuple[bool, float, str]:
    """
    Determine match acceptance and confidence tier.

    Rules:
    a) confidence >= 60% (score >= 0.60) -> accepted as high confidence
    b) else if length ratio within tolerance (diff <= 20%) -> accepted as medium confidence
    c) else rejected

    Confidence Levels:
    - High: >= 60% (confidence score >= 0.60)
    - Medium: < 60% but length difference ratio <= 20% (within tolerance but below high threshold)
    - Low: Only for absolute distance matches (absolute length difference < 1.5m, matched by position)

    Returns:
        (accepted, score_to_store, tier)
        tier in {'high', 'medium', 'reject'}
    """
    confidence = _calculate_confidence(length1, length2, tolerance=tolerance)

    if confidence > confidence_threshold:
        return True, confidence, 'high'

    if _is_length_within_tolerance(length1, length2, tolerance=tolerance):
        # Accepted by tolerance fallback; store as medium confidence floor.
        return True, confidence_threshold, 'medium'

    return False, confidence, 'reject'


def _confidence_level_from_score(confidence_score, match_source: str = '') -> str:
    """
    Map numeric confidence score to a level label for reporting.
    
    Confidence Levels:
    - High: >= 60% (score >= 0.60) - Strong length agreement
    - Medium: < 60% (score < 0.60) but within 20% length tolerance
    - Low: Only for absolute distance matches (absolute length difference < 1.5m)
    
    Note: The match_source 'Absolute Distance Matching' always gets 'Low' confidence.
    """
    if match_source == 'Unmatched Master' or match_source == 'Unmatched Target':
        return ''
    if match_source == 'Marker':
        return 'High'
    if match_source == 'Absolute Distance Matching':
        return 'Low'

    try:
        score = float(confidence_score)
    except (TypeError, ValueError):
        return ''

    # High confidence: >= 60%
    # Medium confidence: < 60% (these are within tolerance fallback matches)
    return 'High' if score >= 0.60 else 'Medium'


def forward_match_check(fix: pd.DataFrame, move: pd.DataFrame,
                        init_fix: int, init_move: int,
                        end_fix: int, end_move: int,
                        threshold: float, min_confidence: float = 0.60) -> Tuple[pd.DataFrame, int, int]:
    """
    Forward match check function with confidence + tolerance fallback:
      a) confidence >= min_confidence (0.60 = 60%) -> high confidence match
      b) else if within length tolerance (diff <= 0.30 = 30%) -> medium confidence match
      c) else reject
    
    Args:
        fix: Master dataframe
        move: Target dataframe
        init_fix: Starting index in master
        init_move: Starting index in target
        end_fix: Ending index in master
        end_move: Ending index in target
        threshold: Length difference threshold (legacy parameter, kept for compatibility)
        min_confidence: High-confidence threshold (default 0.60 = 60%)
    
    Returns:
        Tuple of (matched_pairs DataFrame, fix_break_loc, move_break_loc)
    """
    matched_pairs = pd.DataFrame(columns=['FIX_ID', 'MOVE_ID', 'CONFIDENCE', 'SOURCE'])
    min_move = int(min(end_move - init_move, end_fix - init_fix))
    fix_break_loc = None
    move_break_loc = None

    for i in range(min_move + 1):
        pair1_len_fix = fix.iloc[init_fix + i]['joint_length']
        pair1_len_move = move.iloc[init_move + i]['joint_length']
        pair1_accept, pair1_score, _ = _evaluate_match_quality(
            pair1_len_fix, pair1_len_move, confidence_threshold=min_confidence, tolerance=0.30
        )
        
        try:
            pair2_len_fix = fix.iloc[init_fix + i + 1]['joint_length']
            pair2_len_move = move.iloc[init_move + i + 1]['joint_length']
            pair2_accept, _, _ = _evaluate_match_quality(
                pair2_len_fix, pair2_len_move, confidence_threshold=min_confidence, tolerance=0.30
            )
        except:
            pair2_accept = False
            
        try:
            pair3_len_fix = fix.iloc[init_fix + i + 2]['joint_length']
            pair3_len_move = move.iloc[init_move + i + 2]['joint_length']
            pair3_accept, _, _ = _evaluate_match_quality(
                pair3_len_fix, pair3_len_move, confidence_threshold=min_confidence, tolerance=0.30
            )
        except:
            pair3_accept = False

        if pair1_accept:
            matched_points = pd.DataFrame(
                [[i + init_fix, i + init_move, pair1_score, 'Forward']],
                columns=matched_pairs.columns
            )
            matched_pairs = pd.concat(
                [matched_pairs, matched_points], ignore_index=True)
        elif (not pair1_accept) and pair2_accept and pair3_accept:
            # Skip this joint but continue if next two are confident.
            # Do NOT append this below-threshold pair as a match record.
            continue
        else:
            fix_break_loc = i + init_fix
            move_break_loc = i + init_move
            break

    return matched_pairs, fix_break_loc, move_break_loc


def backward_match_check(fix: pd.DataFrame, move: pd.DataFrame,
                         init_fix: int, init_move: int,
                         end_fix: int, end_move: int,
                         threshold: float, min_confidence: float = 0.60) -> Tuple[pd.DataFrame, int, int]:
    """
    Backward match check function with confidence + tolerance fallback:
      a) confidence >= min_confidence (0.60 = 60%) -> high confidence match
      b) else if within length tolerance (diff <= 0.30 = 30%) -> medium confidence match
      c) else reject
    
    Args:
        fix: Master dataframe
        move: Target dataframe
        init_fix: Starting index in master
        init_move: Starting index in target
        end_fix: Ending index in master
        end_move: Ending index in target
        threshold: Length difference threshold (legacy parameter, kept for compatibility)
        min_confidence: High-confidence threshold (default 0.60 = 60%)
    
    Returns:
        Tuple of (matched_pairs DataFrame, fix_break_loc, move_break_loc)
    """
    matched_pairs = pd.DataFrame(columns=['FIX_ID', 'MOVE_ID', 'CONFIDENCE', 'SOURCE'])
    min_move = int(min(end_move - init_move, end_fix - init_fix))
    fix_break_loc = None
    move_break_loc = None

    for i in range(1, min_move + 1):
        pair1_len_fix = fix.iloc[end_fix - i]['joint_length']
        pair1_len_move = move.iloc[end_move - i]['joint_length']
        pair1_accept, pair1_score, _ = _evaluate_match_quality(
            pair1_len_fix, pair1_len_move, confidence_threshold=min_confidence, tolerance=0.30
        )
        
        pair2_len_fix = fix.iloc[end_fix - i - 1]['joint_length']
        pair2_len_move = move.iloc[end_move - i - 1]['joint_length']
        pair2_accept, _, _ = _evaluate_match_quality(
            pair2_len_fix, pair2_len_move, confidence_threshold=min_confidence, tolerance=0.30
        )
        
        pair3_len_fix = fix.iloc[end_fix - i - 2]['joint_length']
        pair3_len_move = move.iloc[end_move - i - 2]['joint_length']
        pair3_accept, _, _ = _evaluate_match_quality(
            pair3_len_fix, pair3_len_move, confidence_threshold=min_confidence, tolerance=0.30
        )

        if pair1_accept:
            matched_points = pd.DataFrame(
                [[end_fix - i, end_move - i, pair1_score, 'Backward']],
                columns=matched_pairs.columns
            )
            matched_pairs = pd.concat(
                [matched_pairs, matched_points], ignore_index=True)
        elif (not pair1_accept) and pair2_accept and pair3_accept:
            # Skip this joint but continue if next two are confident.
            # Do NOT append this below-threshold pair as a match record.
            continue
        else:
            fix_break_loc = end_fix - i
            move_break_loc = end_move - i
            break

    return matched_pairs, fix_break_loc, move_break_loc


@dataclass
class JointMatch:
    """Represents a match between master and target joints."""
    master_joints: List[int]
    target_joints: List[int]
    match_type: str  # '1-to-1', '1-to-N', 'N-to-1', 'marker', 'original'
    confidence: float  # 0.0 to 1.0
    master_total_length: float
    target_total_length: float
    length_difference: float
    
    def is_split(self) -> bool:
        """Check if this represents a joint split (1-to-many)."""
        return len(self.master_joints) == 1 and len(self.target_joints) > 1
    
    def is_merge(self) -> bool:
        """Check if this represents a joint merge (many-to-1)."""
        return len(self.master_joints) > 1 and len(self.target_joints) == 1
    
    def is_simple(self) -> bool:
        """Check if this is a simple 1-to-1 match."""
        return len(self.master_joints) == 1 and len(self.target_joints) == 1


class CumulativeLengthMatcher:
    """
    Cumulative length matching for unmatched joints.
    Handles 1-to-1, 1-to-many, and many-to-1 matching.
    """
    
    def __init__(self,
                 length_tolerance: float = 0.30,
                 max_aggregate: int = 5,
                 min_confidence: float = 0.60):
        """
        Initialize the cumulative length matcher.
        
        Args:
            length_tolerance: Percentage tolerance for length matching (default 20%)
            max_aggregate: Maximum number of joints to aggregate (default 5)
            min_confidence: Minimum confidence to accept a match (default 0.60)
        """
        self.length_tolerance = length_tolerance
        self.max_aggregate = max_aggregate
        self.min_confidence = min_confidence
    
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
    
    def match_joint(self,
                   master_df: pd.DataFrame,
                   m_idx: int,
                   target_df: pd.DataFrame,
                   t_idx: int) -> Optional[JointMatch]:
        """
        Try to match a joint using cumulative length comparison.
        
        Attempts matching in order:
        1. 1-to-many (master joint split)
        2. many-to-1 (master joints merged)
        
        Note: 1-to-1 matching is now handled by the confidence-based forward/backward
        matching in the original algorithm, so it's removed from here.
        
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
        
        # Try 1-to-1 first with the same decision policy used by forward/backward.
        # a) confidence >= 60% -> high, b) else within 20% tolerance -> medium, c) else reject.
        pair_accept, pair_score, _ = _evaluate_match_quality(
            master_joint['joint_length'],
            target_joint['joint_length'],
            confidence_threshold=self.min_confidence,
            tolerance=self.length_tolerance
        )
        if pair_accept:
            return JointMatch(
                master_joints=[int(master_joint['joint_number'])],
                target_joints=[int(target_joint['joint_number'])],
                match_type='1-to-1',
                confidence=pair_score,
                master_total_length=master_joint['joint_length'],
                target_total_length=target_joint['joint_length'],
                length_difference=abs(master_joint['joint_length'] - target_joint['joint_length'])
            )

        # Try 1-to-many (master joint was split into multiple target joints)
        # Use bracket-based approach: find best combinations below and above target,
        # then pick the one with higher confidence
        cumulative_target = 0
        target_joints_list = []
        best_below = None
        best_above = None
        
        for t_count in range(1, self.max_aggregate + 1):
            if t_idx + t_count > len(target_df):
                break
            
            current_target = target_df.iloc[t_idx + t_count - 1]
            cumulative_target += current_target['joint_length']
            target_joints_list.append(int(current_target['joint_number']))
            
            # Calculate confidence for this combination
            base_confidence = self._calculate_confidence(
                master_joint['joint_length'],
                cumulative_target
            )
            # Reduce confidence by 5% per additional joint
            split_penalty = 0.05 * (t_count - 1)
            confidence = max(base_confidence - split_penalty, 0.0)
            
            # Check if this combination passes thresholds
            passes_confidence = confidence > self.min_confidence
            passes_tolerance = self._is_length_match(master_joint['joint_length'], cumulative_target)
            
            if passes_confidence or passes_tolerance:
                candidate = {
                    'count': t_count,
                    'cumulative': cumulative_target,
                    'joints': target_joints_list.copy(),
                    'confidence': confidence if confidence > self.min_confidence else self.min_confidence,
                    'diff': abs(master_joint['joint_length'] - cumulative_target)
                }
                
                if cumulative_target < master_joint['joint_length']:
                    # This combination is BELOW target length
                    if best_below is None or confidence > best_below['confidence']:
                        best_below = candidate
                elif cumulative_target > master_joint['joint_length']:
                    # This combination is ABOVE target length
                    if best_above is None or confidence > best_above['confidence']:
                        best_above = candidate
                else:
                    # Exact match! Return immediately
                    return JointMatch(
                        master_joints=[int(master_joint['joint_number'])],
                        target_joints=candidate['joints'],
                        match_type=f'1-to-{t_count}',
                        confidence=candidate['confidence'],
                        master_total_length=master_joint['joint_length'],
                        target_total_length=cumulative_target,
                        length_difference=candidate['diff']
                    )
        
        # Choose best match between below and above candidates
        candidates = []
        if best_below is not None:
            candidates.append(best_below)
        if best_above is not None:
            candidates.append(best_above)
        
        if candidates:
            # Pick the candidate with higher confidence
            best_candidate = max(candidates, key=lambda x: x['confidence'])
            return JointMatch(
                master_joints=[int(master_joint['joint_number'])],
                target_joints=best_candidate['joints'],
                match_type=f'1-to-{best_candidate["count"]}',
                confidence=best_candidate['confidence'],
                master_total_length=master_joint['joint_length'],
                target_total_length=best_candidate['cumulative'],
                length_difference=best_candidate['diff']
            )
        
        # Try many-to-1 (multiple master joints merged into one target joint)
        # Use bracket-based approach: find best combinations below and above target,
        # then pick the one with higher confidence
        cumulative_master = 0
        master_joints_list = []
        best_below = None
        best_above = None
        
        for m_count in range(1, self.max_aggregate + 1):
            if m_idx + m_count > len(master_df):
                break
            
            current_master = master_df.iloc[m_idx + m_count - 1]
            cumulative_master += current_master['joint_length']
            master_joints_list.append(int(current_master['joint_number']))
            
            # Calculate confidence for this combination
            base_confidence = self._calculate_confidence(
                cumulative_master,
                target_joint['joint_length']
            )
            merge_penalty = 0.05 * (m_count - 1)
            confidence = max(base_confidence - merge_penalty, 0.0)
            
            # Check if this combination passes thresholds
            passes_confidence = confidence > self.min_confidence
            passes_tolerance = self._is_length_match(cumulative_master, target_joint['joint_length'])
            
            if passes_confidence or passes_tolerance:
                candidate = {
                    'count': m_count,
                    'cumulative': cumulative_master,
                    'joints': master_joints_list.copy(),
                    'confidence': confidence if confidence > self.min_confidence else self.min_confidence,
                    'diff': abs(cumulative_master - target_joint['joint_length'])
                }
                
                if cumulative_master < target_joint['joint_length']:
                    # This combination is BELOW target length
                    if best_below is None or confidence > best_below['confidence']:
                        best_below = candidate
                elif cumulative_master > target_joint['joint_length']:
                    # This combination is ABOVE target length
                    if best_above is None or confidence > best_above['confidence']:
                        best_above = candidate
                else:
                    # Exact match! Return immediately
                    return JointMatch(
                        master_joints=candidate['joints'],
                        target_joints=[int(target_joint['joint_number'])],
                        match_type=f'{m_count}-to-1',
                        confidence=candidate['confidence'],
                        master_total_length=cumulative_master,
                        target_total_length=target_joint['joint_length'],
                        length_difference=candidate['diff']
                    )
        
        # Choose best match between below and above candidates
        candidates = []
        if best_below is not None:
            candidates.append(best_below)
        if best_above is not None:
            candidates.append(best_above)
        
        if candidates:
            # Pick the candidate with higher confidence
            best_candidate = max(candidates, key=lambda x: x['confidence'])
            return JointMatch(
                master_joints=best_candidate['joints'],
                target_joints=[int(target_joint['joint_number'])],
                match_type=f'{best_candidate["count"]}-to-1',
                confidence=best_candidate['confidence'],
                master_total_length=best_candidate['cumulative'],
                target_total_length=target_joint['joint_length'],
                length_difference=best_candidate['diff']
            )
        
        # No match found
        return None


def _categorize_match_type(match_type_str: str) -> str:
    """
    Categorize match type string into standardized categories.
    
    Args:
        match_type_str: Match type string (e.g., '1-to-1', '1-to-2', '2-to-1', 'Unmatched')
    
    Returns:
        Category: '1-1', '1-many', 'many-1', 'many-many', or 'Unmatched'
    """
    if not match_type_str or match_type_str == 'Unmatched':
        return 'Unmatched'
    
    # Handle absolute distance format: '1-to-1 (absolute distance)'
    match_type_str = match_type_str.replace(' (absolute distance)', '')
    
    # Parse the match type (e.g., '1-to-1', '1-to-2', '2-to-1', '2-to-3')
    if '-to-' in match_type_str:
        parts = match_type_str.split('-to-')
        if len(parts) == 2:
            master_count = int(parts[0])
            target_count = int(parts[1])
            
            if master_count == 1 and target_count == 1:
                return '1-1'
            elif master_count == 1 and target_count > 1:
                return '1-many'
            elif master_count > 1 and target_count == 1:
                return 'many-1'
            elif master_count > 1 and target_count > 1:
                return 'many-many'
    
    # Default fallback for '1-to-1'
    if match_type_str == '1-to-1':
        return '1-1'
    
    return 'Unknown'


def export_to_excel(matched_joints: pd.DataFrame,
                   unmatched_joints: pd.DataFrame,
                   run_summary: Dict,
                   output_path: str) -> bool:
    """
    Export matching results to Excel with separate tabs for matched and unmatched joints.
    
    Args:
        matched_joints: DataFrame with matched joints
        unmatched_joints: DataFrame with unmatched joints
        run_summary: Dictionary with run summary statistics
        output_path: Path to output Excel file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        
        # Build summary DataFrame
        summary_data = {
            'Metric': [
                'Master Inspection GUID',
                'Master ILI ID',
                'Target Inspection GUID',
                'Target ILI ID',
                'Total Master Joints',
                'Total Target Joints',
                'Total Matched Joints',
                '  - From Original Algorithm',
                '  - From Cumulative Matching',
                '  - From Absolute Distance',
                '  - From Post-Processing Merge',
                'Total Unmatched Joints',
                'Questionable Matches',
                'Master Match Percentage',
                'Target Match Percentage',
                'Flow Direction',
                'Cumulative Matching Enabled'
            ],
            'Value': [
                run_summary.get('Master_inspection_guid', ''),
                run_summary.get('Master_ili_id', ''),
                run_summary.get('Target_inspection_guid', ''),
                run_summary.get('Target_ili_id', ''),
                run_summary.get('Total_master_joints', 0),
                run_summary.get('Total_target_joints', 0),
                run_summary.get('Matched_joints', 0),
                run_summary.get('Matched_from_original', 0),
                run_summary.get('Matched_from_cumulative', 0),
                run_summary.get('Matched_from_absolute_distance', 0),
                run_summary.get('Matched_from_postprocessing_merge', 0),
                run_summary.get('Unmatched_joints', 0),
                run_summary.get('Questionable_matches', 0),
                f"{run_summary.get('Master_joint_percentage', 0):.2f}%",
                f"{run_summary.get('Target_joint_percentage', 0):.2f}%",
                run_summary.get('Flow_direction', ''),
                run_summary.get('Cumulative_matching_enabled', False)
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        
        # Build match type breakdown table
        breakdown_df = None
        if not matched_joints.empty and 'Match Source' in matched_joints.columns and 'Match Type' in matched_joints.columns:
            # Filter to only actual matches (exclude unmatched rows)
            actual_matches = matched_joints[
                ~matched_joints['Match Source'].isin(['Unmatched Master', 'Unmatched Target'])
            ].copy()
            
            if not actual_matches.empty:
                # Categorize match types
                actual_matches['Match_Type_Category'] = actual_matches['Match Type'].apply(_categorize_match_type)
                
                # Create pivot table
                breakdown_pivot = pd.crosstab(
                    actual_matches['Match Source'],
                    actual_matches['Match_Type_Category'],
                    margins=False
                )
                
                # Ensure all expected columns exist (in desired order)
                expected_columns = ['1-1', '1-many', 'many-1', 'many-many']
                for col in expected_columns:
                    if col not in breakdown_pivot.columns:
                        breakdown_pivot[col] = 0
                
                # Reorder columns and convert to int
                breakdown_pivot = breakdown_pivot[expected_columns].fillna(0).astype(int)
                
                # Reset index to make Match Source a column
                breakdown_pivot = breakdown_pivot.reset_index()
                breakdown_pivot = breakdown_pivot.rename(columns={'Match Source': 'Match Source'})
                
                breakdown_df = breakdown_pivot
                logger.info(f"Created match type breakdown table with {len(breakdown_df)} sources")
        
        # Write to Excel with multiple sheets
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary tab with breakdown table
            summary_df.to_excel(writer, sheet_name='Summary', index=False, startrow=0)
            
            # Add breakdown table below summary (with spacing)
            if breakdown_df is not None:
                startrow = len(summary_df) + 3  # Leave 2 blank rows
                
                # Add a header for the breakdown table
                breakdown_header_df = pd.DataFrame({
                    'Match Source': [''],
                    '1-1': ['MATCH TYPE BREAKDOWN BY SOURCE']
                })
                breakdown_header_df.to_excel(
                    writer,
                    sheet_name='Summary',
                    index=False,
                    startrow=startrow,
                    header=False
                )
                
                # Add the breakdown table
                breakdown_df.to_excel(
                    writer,
                    sheet_name='Summary',
                    index=False,
                    startrow=startrow + 1
                )
            
            # Matched joints tab
            if not matched_joints.empty:
                matched_joints.to_excel(writer, sheet_name='Matched Joints', index=False)
            else:
                pd.DataFrame({'Message': ['No matched joints']}).to_excel(
                    writer, sheet_name='Matched Joints', index=False)
            
            # Unmatched joints tab
            if not unmatched_joints.empty:
                unmatched_joints.to_excel(writer, sheet_name='Unmatched Joints', index=False)
            else:
                pd.DataFrame({'Message': ['No unmatched joints']}).to_excel(
                    writer, sheet_name='Unmatched Joints', index=False)
        
        logger.info(f"Results exported to: {os.path.abspath(output_path)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to export results: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def execute_integrated_joint_matching(engine: Engine, master_guid: str, target_guids: List[str],
                                      output_path: Optional[str] = None,
                                      use_cumulative_for_unmatched: bool = True,
                                      cumulative_tolerance: float = 0.30,
                                      cumulative_max_aggregate: int = 5,
                                      cumulative_min_confidence: float = 0.60) -> Dict:
    """
    Execute integrated joint matching algorithm between master and target inspections.
    
    Workflow:
    1. Run original algorithm (marker alignment, forward/backward matching)
    2. Collect unmatched joints
    3. Apply cumulative length matching to unmatched joints (if enabled)
    4. Merge all results
    5. Export to Excel (if output_path provided)
    
    Args:
        engine: SQLAlchemy engine for database connection
        master_guid: Master inspection GUID
        target_guids: List of target inspection GUIDs
        output_path: Path to output Excel file (optional)
        use_cumulative_for_unmatched: Apply cumulative matching to unmatched joints
        cumulative_tolerance: Length tolerance for cumulative matching (default 20%)
        cumulative_max_aggregate: Max joints to aggregate in cumulative matching
        cumulative_min_confidence: Min confidence for cumulative matching
    
    Returns:
        Dict with keys: run_summary, matched_joints, unmatched_joints, questionable_joints
    """
    logger.info("=" * 80)
    logger.info("INTEGRATED JOINT MATCHING")
    logger.info("=" * 80)
    logger.info(f"Starting integrated matching: master={master_guid}, targets={target_guids}")
    logger.info(f"Cumulative matching for unmatched: {use_cumulative_for_unmatched}")
    
    # Convert GUIDs to appropriate format
    master_guid_tuple = tuple([master_guid])
    target_guid_list = tuple(target_guids)
    all_guid_list = master_guid_tuple + target_guid_list
    
    # Build SQL query with proper filtering, distinct, and ordering
    placeholders = ','.join([f":guid{i}" for i in range(len(all_guid_list))])
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
    
    # Create parameters dict
    params = {f'guid{i}': str(guid) for i, guid in enumerate(all_guid_list)}
    
    logger.info(f"SQL Query: {joint_query}")
    logger.info(f"Parameters: {params}")
    
    # Query database
    with engine.connect() as conn:
        joint_list = pd.read_sql_query(con=conn, sql=joint_query, params=params)
        
        logger.info(f"Raw query returned {len(joint_list)} records")
        
        # Log records per GUID before filtering
        if not joint_list.empty:
            guid_counts = joint_list.groupby('insp_guid').size()
            logger.info("Records per GUID (before NULL filtering):")
            for guid, count in guid_counts.items():
                logger.info(f"  {guid}: {count} records")
        
        # Drop null values
        smaller_subset = ['joint_number', 'joint_length', 'insp_guid', 'ili_id']
        joint_list = joint_list.dropna(subset=smaller_subset).reset_index(drop=True)
        
        # Deduplicate: Keep only the first entry per joint number for each inspection
        # This handles cases where multiple records exist for the same joint (e.g., features/anomalies)
        records_before_dedup = len(joint_list)
        joint_list = joint_list.drop_duplicates(
            subset=['insp_guid', 'joint_number'],
            keep='first'
        ).reset_index(drop=True)
        records_after_dedup = len(joint_list)
        
        if records_before_dedup > records_after_dedup:
            duplicates_removed = records_before_dedup - records_after_dedup
            logger.info(f"Deduplication: Removed {duplicates_removed} duplicate joint records")
            logger.info(f"  (Kept first occurrence of each joint_number per insp_guid)")
        
        logger.info(f"After NULL filtering: {len(joint_list)} records")
        
        # Log records per GUID after filtering
        if not joint_list.empty:
            guid_counts = joint_list.groupby('insp_guid').size()
            logger.info("Records per GUID (after NULL filtering):")
            for guid, count in guid_counts.items():
                logger.info(f"  {guid}: {count} records")
    
    logger.info("Database query successful")
    
    # Prepare master dataset - filter and ensure proper ordering
    joint_list["insp_guid"] = joint_list["insp_guid"].astype("str")
    
    logger.info(f"Looking for master GUID: '{master_guid_tuple[0]}'")
    logger.info(f"Available GUIDs in dataset: {sorted(joint_list['insp_guid'].unique().tolist())}")
    
    fix_df = joint_list.loc[joint_list["insp_guid"] == master_guid_tuple[0]].copy()
    
    logger.info(f"Master dataset contains {len(fix_df)} records")
    
    # Convert joint_number to integer and sort
    if not fix_df.empty:
        fix_df['joint_number'] = fix_df['joint_number'].astype(int)
        fix_df = fix_df.sort_values('joint_number').reset_index(drop=True)
    
    if fix_df.empty or (not fix_df.empty and fix_df["joint_length"].empty):
        error_msg = (
            f"Master dataset is empty for GUID: '{master_guid_tuple[0]}'\n"
            f"Records retrieved from database: {len(joint_list)}\n"
        )
        if not joint_list.empty:
            available_guids = sorted(joint_list['insp_guid'].unique().tolist())
            error_msg += f"Available GUIDs after filtering: {available_guids}\n\n"
            error_msg += "TROUBLESHOOTING:\n"
            error_msg += "1. Check if the master GUID matches exactly (case-sensitive)\n"
            error_msg += "2. Verify data has non-NULL values for: joint_number, joint_length, insp_guid, ili_id\n"
            error_msg += "3. Run 'python list_available_guids.py' to see all available inspections"
        else:
            error_msg += "No records found after NULL filtering.\n"
            error_msg += "This means all records have NULL values in required fields."
        raise ValueError(error_msg)
    
    fix_iliyr = np.unique(fix_df["iliyr"])[0]
    fix_ili_id = np.unique(fix_df["ili_id"])[0]
    
    # Create a mapping from joint_number to joint_length for easy lookup
    master_length_map = dict(zip(fix_df['joint_number'].astype(int), fix_df['joint_length']))
    
    # Process each target GUID
    results_list = []
    
    for target_guid in target_guid_list:
        logger.info("-" * 80)
        logger.info(f"Processing target: {target_guid}")
        
        move_df = joint_list.loc[joint_list["insp_guid"] == target_guid].copy()
        
        # Convert joint_number to integer and sort
        move_df['joint_number'] = move_df['joint_number'].astype(int)
        move_df = move_df.sort_values('joint_number').reset_index(drop=True)
        
        if move_df.empty or move_df["joint_length"].empty:
            logger.warning(f"Target {target_guid} is empty, skipping")
            continue
        
        # Create a mapping from joint_number to joint_length for target
        target_length_map = dict(zip(move_df['joint_number'].astype(int), move_df['joint_length']))
        
        RevMove = move_df.loc[::-1]
        move_iliyr = np.unique(move_df["iliyr"])[0]
        move_ili_id = np.unique(move_df["ili_id"])[0]
        
        logger.info(f"Master {fix_iliyr}: {len(fix_df)} joints, Target {move_iliyr}: {len(move_df)} joints")
        
        # ========== INTEGRATED MATCHING: MARKER ALIGNMENT + FORWARD/BACKWARD + CUMULATIVE ==========
        logger.info("Running integrated matching algorithm (Marker Alignment → Forward/Backward → Cumulative)...")
        
        # Flow direction determination
        column = "joint_length"
        fix_diff = joint_diff_calc(fix_df, column=column)
        move_diff = joint_diff_calc(move_df, column=column)
        RevMove_diff = joint_diff_calc(RevMove, column=column)
        
        fix_pairs = pairs_generator(fix_diff)
        move_pairs = pairs_generator(move_diff)
        RevMove_pairs = pairs_generator(RevMove_diff)
        
        match_pct_move = match_pct_calc_with_distance(fix_pairs, move_pairs, fix_df, move_df, 0.05)
        match_pct_RevMove = match_pct_calc_with_distance(fix_pairs, RevMove_pairs, fix_df, RevMove, 0.05)
        
        if match_pct_move > match_pct_RevMove:
            direction = "FWD"
            logger.info(f"  Direction: Forward ({match_pct_move:.2f}%)")
        elif match_pct_move < match_pct_RevMove:
            direction = "REV"
            logger.info(f"  Direction: Reverse ({match_pct_RevMove:.2f}%)")
        else:
            direction = "FWD"  # Default to forward on tie
            logger.warning("  Direction: Tie, defaulting to Forward")
        
        # Joint matching algorithm
        large_diff = 3
        
        fix_df['difference'] = fix_df.joint_length.shift(-1) - fix_df.joint_length
        fix_df['difference'] = fix_df['difference'].fillna(0)
        fix_df = fix_df.reset_index(drop=True)
        fix_df = fix_df.rename(columns={"ili_id": "Master_ili_id"})
        fix_data = fix_df.copy()
        
        move_data = move_df.copy()
        move_data = move_data.rename(columns={"ili_id": "Target_ili_id"})
        
        if direction == "Reverse" or direction == "REV":
            move_data["joint_number_org"] = move_df["joint_number"]
            move_data = move_data.loc[::-1]
            move_data["joint_number"] = move_df["joint_number"].astype(
                int).sort_values(ascending=True).values
        
        move_data['difference'] = move_data.joint_length.shift(-1) - move_data.joint_length
        move_data['difference'] = move_data['difference'].fillna(0)
        
        if direction == "Reverse" or direction == "REV":
            move_data = move_data[["joint_number", "difference",
                                   "joint_length", "joint_number_org", "Target_ili_id"]]
        else:
            move_data = move_data[["joint_number",
                                   "difference", "joint_length", "Target_ili_id"]]
        
        move_data = move_data.reset_index(drop=True)
        
        Match_df = pd.DataFrame([], columns=['FIX_ID', 'MOVE_ID', 'CONFIDENCE', 'SOURCE'])
        Unmatch = pd.DataFrame(
            columns=['FIX_START', 'FIX_END', 'MOVE_START', 'MOVE_END'])
        
        move_marker = move_data[abs(move_data.difference) > large_diff]
        fix_marker = fix_data[abs(fix_data.difference) > large_diff]
        
        j = 0
        temp_move_match = 0
        
        # Find all chunk markers
        logger.info(f"  Starting marker matching: {len(move_marker)} target markers, {len(fix_marker)} master markers")
        markers_matched_count = 0
        markers_skipped_count = 0
        
        for i in move_marker.index:
            target_joint_num = move_marker.loc[i]['joint_number']
            logger.debug(f"  Evaluating target marker at index {i} (joint {target_joint_num:.0f})")
            
            temp = pd.Series(
                (abs(move_marker.loc[i]['difference'] - fix_marker.difference[fix_marker.index > j]) < 1) &
                (abs(move_marker.loc[i]["joint_length"] -
                 fix_marker.joint_length[fix_marker.index > j]) < 1)
            )
            
            if not temp.any():
                logger.debug(f"    No master marker match found for target joint {target_joint_num:.0f} (skipping)")
                markers_skipped_count += 1
                continue
            
            try:
                next_temp1 = pd.Series(
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 1]['difference'] -
                         fix_marker.difference[fix_marker.index > temp.idxmax()]) < 1) &
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 1]["joint_length"] -
                         fix_marker.joint_length[fix_marker.index > temp.idxmax()]) < 1)
                )
                next_temp2 = pd.Series(
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 2]['difference'] -
                         fix_marker.difference[fix_marker.index > next_temp1.idxmax()]) < 1) &
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 2]["joint_length"] -
                         fix_marker.joint_length[fix_marker.index > next_temp1.idxmax()]) < 1)
                )
                next_temp3 = pd.Series(
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 3]['difference'] -
                         fix_marker.difference[fix_marker.index > next_temp2.idxmax()]) < 1) &
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 3]["joint_length"] -
                         fix_marker.joint_length[fix_marker.index > next_temp2.idxmax()]) < 1)
                )
            except:
                continue
            
            try:
                fix_diff_sum = np.sum(
                    fix_data.loc[j:temp.idxmax()].joint_length)
                move_diff_sum = np.sum(
                    move_data.loc[temp_move_match:i].joint_length)
                length_diff = abs(fix_diff_sum - move_diff_sum)
            except:
                length_diff = 0.05
            
            try:
                index_diff2 = abs(
                    abs(next_temp1.idxmax() - move_marker.iloc[[move_marker.index.get_loc(i) + 1]].index) -
                    abs(temp.idxmax() - i)
                )
            except:
                index_diff2 = 0
            
            try:
                index_diff3 = abs(
                    abs(next_temp2.idxmax() - move_marker.iloc[[move_marker.index.get_loc(i) + 2]].index) -
                    abs(temp.idxmax() - i)
                )
            except:
                index_diff3 = 0
            
            try:
                index_diff4 = abs(
                    abs(next_temp3.idxmax() - move_marker.iloc[[move_marker.index.get_loc(i) + 3]].index) -
                    abs(temp.idxmax() - i)
                )
            except:
                index_diff4 = 0
            
            if Match_df.empty:
                temp_fix_match = temp.idxmax()
                master_joint_num = fix_data.loc[temp_fix_match, 'joint_number']
                logger.debug(f"    MATCHED (first): Master joint {master_joint_num:.0f} <-> Target joint {target_joint_num:.0f}")
                matched_points = pd.DataFrame(
                    [[temp_fix_match, i, 1.0, 'Marker']],
                    columns=Match_df.columns
                )
                Match_df = pd.concat(
                    [Match_df, matched_points], ignore_index=True)
                j = temp_fix_match
                temp_move_match = i
                markers_matched_count += 1
            else:
                # Require BOTH reasonable cumulative length AND marker alignment
                # This prevents matching joints from completely different pipeline sections
                if temp.any() & (length_diff < 10) & ((index_diff2 == 0) | (index_diff3 == 0) | (index_diff4 == 0)):
                    temp_fix_match = temp.idxmax()
                    master_joint_num = fix_data.loc[temp_fix_match, 'joint_number']
                    logger.debug(f"    MATCHED: Master joint {master_joint_num:.0f} <-> Target joint {target_joint_num:.0f} (length_diff={length_diff:.2f}m)")
                    matched_points = pd.DataFrame(
                        [[temp_fix_match, i, 1.0, 'Marker']],
                        columns=Match_df.columns
                    )
                    Match_df = pd.concat(
                        [Match_df, matched_points], ignore_index=True)
                    j = temp_fix_match
                    temp_move_match = i
                    markers_matched_count += 1
                else:
                    logger.debug(f"    NOT matched: Target joint {target_joint_num:.0f} - validation failed (length_diff={length_diff:.2f}m)")
                    markers_skipped_count += 1
        
        logger.info(f"  Marker matching complete: {markers_matched_count} matched, {markers_skipped_count} skipped")
        
        # Process matched chunks with integrated cumulative matching
        it_chunks = Match_df[
            ((Match_df['FIX_ID'].shift(-1) - Match_df['FIX_ID']) != 1) &
            ((Match_df['MOVE_ID'].shift(-1) - Match_df['MOVE_ID']) != 1)
        ]
        it_chunks2 = it_chunks.head(-1)
        
        # Create cumulative matcher if enabled
        cumulative_matcher = None
        cumulative_matches = []
        if use_cumulative_for_unmatched:
            cumulative_matcher = CumulativeLengthMatcher(
                length_tolerance=cumulative_tolerance,
                max_aggregate=cumulative_max_aggregate,
                min_confidence=cumulative_min_confidence
            )
        
        logger.info("Processing chunks with 3-step matching (Forward → Backward → Cumulative)...")
        
        for chunk_idx, i in enumerate(it_chunks2.index):
            init_fix = it_chunks.loc[i]["FIX_ID"]
            init_move = it_chunks.loc[i]['MOVE_ID']
            end_fix = it_chunks.iloc[it_chunks.index.get_loc(i) + 1]['FIX_ID']
            end_move = it_chunks.iloc[it_chunks.index.get_loc(
                i) + 1]['MOVE_ID']
            
            logger.debug(f"  Chunk {chunk_idx + 1}: Master[{init_fix}:{end_fix}] ↔ Target[{init_move}:{end_move}]")
            
            # Step 1: Forward matching (confidence-based)
            matches, fix_break, move_break = forward_match_check(
                fix_data, move_data, init_fix, init_move, end_fix, end_move, 1, min_confidence=0.60
            )
            Match_df = pd.concat([Match_df, matches])
            chunk_forward_count = len(matches)
            
            # Step 2: Backward matching (confidence-based) if there's a gap
            chunk_backward_count = 0
            if (fix_break != end_fix) & (move_break != end_move) & (fix_break is not None):
                matches2, fix_break2, move_break2 = backward_match_check(
                    fix_data, move_data, fix_break, move_break, end_fix, end_move, 1, min_confidence=0.60
                )
                Match_df = pd.concat([Match_df, matches2])
                chunk_backward_count = len(matches2)
                
                # Step 3: Cumulative matching on unmatched joints in this chunk
                if cumulative_matcher and fix_break2 is not None and move_break2 is not None:
                    # Get unmatched joints in this chunk gap
                    chunk_unmatched_master = fix_data.iloc[fix_break:fix_break2+1].copy()
                    chunk_unmatched_target = move_data.iloc[move_break:move_break2+1].copy()
                    
                    chunk_unmatched_master = chunk_unmatched_master.reset_index(drop=True)
                    chunk_unmatched_target = chunk_unmatched_target.reset_index(drop=True)
                    
                    # Apply cumulative matching to this chunk
                    m_idx = 0
                    t_idx = 0
                    chunk_cumulative_count = 0
                    
                    while m_idx < len(chunk_unmatched_master) and t_idx < len(chunk_unmatched_target):
                        match = cumulative_matcher.match_joint(
                            chunk_unmatched_master, m_idx,
                            chunk_unmatched_target, t_idx
                        )
                        
                        if match is not None:
                            cumulative_matches.append(match)
                            chunk_cumulative_count += 1
                            
                            # Advance indices
                            m_idx += len(match.master_joints)
                            t_idx += len(match.target_joints)
                            
                            logger.debug(
                                f"    Cumulative: M{match.master_joints} ↔ T{match.target_joints} "
                                f"({match.match_type}, conf={match.confidence:.2f})"
                            )
                        else:
                            # No direct match. Try shifting target by one to recover alignment
                            # before giving up on this master joint.
                            shifted_match = None
                            if t_idx + 1 < len(chunk_unmatched_target):
                                shifted_match = cumulative_matcher.match_joint(
                                    chunk_unmatched_master, m_idx,
                                    chunk_unmatched_target, t_idx + 1
                                )

                            if shifted_match is not None:
                                t_idx += 1
                            else:
                                # Fall back to advancing master.
                                m_idx += 1
                    
                    logger.debug(f"    Chunk {chunk_idx + 1}: Forward={chunk_forward_count}, "
                               f"Backward={chunk_backward_count}, Cumulative={chunk_cumulative_count}")
                else:
                    # Record unmatched chunk for later if cumulative not enabled
                    if fix_break2 is not None and move_break2 is not None:
                        unmatch_chunks = pd.DataFrame(
                            np.array([fix_break, move_break, fix_break2, move_break2]).reshape(1, 4),
                            columns=Unmatch.columns
                        )
                        Unmatch = pd.concat([Unmatch, unmatch_chunks], ignore_index=True)
        
        # Match joints before first marker (head section) with Backward -> Forward -> Cumulative pipeline
        try:
            head_init_fix = 0
            head_init_move = 0
            head_end_fix = int(it_chunks.iloc[0, 0])
            head_end_move = int(it_chunks.iloc[0, 1])
            
            logger.debug(f"  HEAD SECTION: Master [{head_init_fix}:{head_end_fix}], Target [{head_init_move}:{head_end_move}]")
            
            # Track matched indices in head section
            head_matched_master_indices = set()
            head_matched_target_indices = set()
            
            # Run backward matching first
            matches_head_bwd, head_fix_break, head_move_break = backward_match_check(
                fix_data, move_data,
                head_init_fix, head_init_move,
                head_end_fix, head_end_move,
                1, min_confidence=0.60
            )
            Match_df = pd.concat([Match_df, matches_head_bwd])
            
            # Track backward matches
            for _, row in matches_head_bwd.iterrows():
                head_matched_master_indices.add(int(row['FIX_ID']))
                head_matched_target_indices.add(int(row['MOVE_ID']))
            
            logger.debug(f"    Backward: {len(matches_head_bwd)} matches, break at M[{head_fix_break}], T[{head_move_break}]")
            
            # Then run forward matching if needed
            if (head_fix_break != head_init_fix) & (head_move_break != head_init_move) & (head_fix_break is not None):
                matches_head_fwd, head_fix_break2, head_move_break2 = forward_match_check(
                    fix_data, move_data,
                    head_init_fix, head_init_move,
                    head_fix_break, head_move_break,
                    1, min_confidence=0.60
                )
                Match_df = pd.concat([Match_df, matches_head_fwd])
                
                # Track forward matches
                for _, row in matches_head_fwd.iterrows():
                    head_matched_master_indices.add(int(row['FIX_ID']))
                    head_matched_target_indices.add(int(row['MOVE_ID']))
                
                logger.debug(f"    Forward: {len(matches_head_fwd)} matches, break at M[{head_fix_break2}], T[{head_move_break2}]")
                
            # Comprehensive cumulative matching: Process ALL unmatched joints in head section
            if cumulative_matcher:
                # Get all joints in head section (EXCLUDING the first marker at head_end_fix)
                # WHY EXCLUDE: The marker at head_end_fix was already matched during marker alignment.
                # Including it here would create duplicate matches (same joint matched twice).
                # Range: [head_init_fix, head_end_fix) - excludes head_end_fix
                all_head_master = fix_data.iloc[head_init_fix:head_end_fix].copy()
                all_head_target = move_data.iloc[head_init_move:head_end_move].copy()
                
                # Filter to only unmatched joints
                head_unmatched_master = all_head_master[~all_head_master.index.isin(head_matched_master_indices)].copy().reset_index(drop=True)
                head_unmatched_target = all_head_target[~all_head_target.index.isin(head_matched_target_indices)].copy().reset_index(drop=True)
                
                logger.debug(f"    Cumulative (head): Processing {len(head_unmatched_master)} unmatched master, {len(head_unmatched_target)} unmatched target (reverse order)")
                
                if len(head_unmatched_master) > 0 and len(head_unmatched_target) > 0:
                    # Process in REVERSE order for head section (to align with backward matching direction)
                    m_idx = len(head_unmatched_master) - 1
                    t_idx = len(head_unmatched_target) - 1
                    head_cumulative_count = 0
                    
                    while m_idx >= 0 and t_idx >= 0:
                        match = cumulative_matcher.match_joint(
                            head_unmatched_master, m_idx,
                            head_unmatched_target, t_idx
                        )
                        
                        if match is not None:
                            master_joints_str = ', '.join(str(j) for j in match.master_joints)
                            target_joints_str = ', '.join(str(j) for j in match.target_joints)
                            logger.debug(f"      Cumulative (head): M[{master_joints_str}] <-> T[{target_joints_str}] (conf={match.confidence:.2f})")
                            cumulative_matches.append(match)
                            m_idx -= len(match.master_joints)
                            t_idx -= len(match.target_joints)
                            head_cumulative_count += 1
                        else:
                            # Try shifting target by one to recover alignment
                            shifted_match = None
                            if t_idx - 1 >= 0:
                                shifted_match = cumulative_matcher.match_joint(
                                    head_unmatched_master, m_idx,
                                    head_unmatched_target, t_idx - 1
                                )
                            if shifted_match is not None:
                                t_idx -= 1
                            else:
                                m_idx -= 1
                    
                    logger.debug(f"    Cumulative (head): Found {head_cumulative_count} matches")
        except Exception as e:
            logger.error(f"  HEAD SECTION ERROR: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        try:
            # Process after-last-marker block with full Forward -> Backward -> Cumulative pipeline
            tail_init_fix = int(it_chunks.iloc[-1, 0])
            tail_init_move = int(it_chunks.iloc[-1, 1])
            tail_end_fix = len(fix_data) - 1
            tail_end_move = len(move_data) - 1
            
            logger.debug(f"  TAIL SECTION: Master [{tail_init_fix}:{tail_end_fix}], Target [{tail_init_move}:{tail_end_move}]")
            
            # Track matched indices in tail section
            tail_matched_master_indices = set()
            tail_matched_target_indices = set()

            matches_tail_fwd, tail_fix_break, tail_move_break = forward_match_check(
                fix_data, move_data,
                tail_init_fix, tail_init_move,
                tail_end_fix, tail_end_move,
                1, min_confidence=0.60
            )
            Match_df = pd.concat([Match_df, matches_tail_fwd])
            
            # Track forward matches
            for _, row in matches_tail_fwd.iterrows():
                tail_matched_master_indices.add(int(row['FIX_ID']))
                tail_matched_target_indices.add(int(row['MOVE_ID']))
            
            logger.debug(f"    Forward: {len(matches_tail_fwd)} matches, break at M[{tail_fix_break}], T[{tail_move_break}]")

            if (tail_fix_break != tail_end_fix) & (tail_move_break != tail_end_move) & (tail_fix_break is not None):
                matches_tail_bwd, tail_fix_break2, tail_move_break2 = backward_match_check(
                    fix_data, move_data,
                    tail_fix_break, tail_move_break,
                    tail_end_fix, tail_end_move,
                    1, min_confidence=0.60
                )
                Match_df = pd.concat([Match_df, matches_tail_bwd])
                
                # Track backward matches
                for _, row in matches_tail_bwd.iterrows():
                    tail_matched_master_indices.add(int(row['FIX_ID']))
                    tail_matched_target_indices.add(int(row['MOVE_ID']))
                
                logger.debug(f"    Backward: {len(matches_tail_bwd)} matches, break at M[{tail_fix_break2}], T[{tail_move_break2}]")

            # Comprehensive cumulative matching: Process ALL unmatched joints in tail section
            if cumulative_matcher:
                # Get all joints in tail section (EXCLUDING the last marker at tail_init_fix)
                # WHY EXCLUDE: The marker at tail_init_fix was already matched during marker alignment.
                # Including it here would create duplicate matches (same joint matched twice).
                # Range: (tail_init_fix, tail_end_fix] - excludes tail_init_fix
                all_tail_master = fix_data.iloc[tail_init_fix+1:tail_end_fix+1].copy()
                all_tail_target = move_data.iloc[tail_init_move+1:tail_end_move+1].copy()
                
                # Filter to only unmatched joints
                tail_unmatched_master = all_tail_master[~all_tail_master.index.isin(tail_matched_master_indices)].copy().reset_index(drop=True)
                tail_unmatched_target = all_tail_target[~all_tail_target.index.isin(tail_matched_target_indices)].copy().reset_index(drop=True)
                
                logger.debug(f"    Cumulative (tail): Processing {len(tail_unmatched_master)} unmatched master, {len(tail_unmatched_target)} unmatched target (forward order)")
                
                if len(tail_unmatched_master) > 0 and len(tail_unmatched_target) > 0:
                    # Process in FORWARD order for tail section (to align with forward matching direction)
                    m_idx = 0
                    t_idx = 0
                    tail_cumulative_count = 0
                    
                    while m_idx < len(tail_unmatched_master) and t_idx < len(tail_unmatched_target):
                        match = cumulative_matcher.match_joint(
                            tail_unmatched_master, m_idx,
                            tail_unmatched_target, t_idx
                        )

                        if match is not None:
                            master_joints_str = ', '.join(str(j) for j in match.master_joints)
                            target_joints_str = ', '.join(str(j) for j in match.target_joints)
                            logger.debug(f"      Cumulative (tail): M[{master_joints_str}] <-> T[{target_joints_str}] (conf={match.confidence:.2f})")
                            cumulative_matches.append(match)
                            m_idx += len(match.master_joints)
                            t_idx += len(match.target_joints)
                            tail_cumulative_count += 1
                        else:
                            # Try shifting target by one to recover alignment
                            shifted_match = None
                            if t_idx + 1 < len(tail_unmatched_target):
                                shifted_match = cumulative_matcher.match_joint(
                                    tail_unmatched_master, m_idx,
                                    tail_unmatched_target, t_idx + 1
                                )
                            if shifted_match is not None:
                                t_idx += 1
                            else:
                                m_idx += 1
                    
                    logger.debug(f"    Cumulative (tail): Found {tail_cumulative_count} matches")
        except Exception as e:
            logger.error(f"  TAIL SECTION ERROR: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        if Match_df.empty:
            logger.warning("  No chunks found in marker-based matching")
        else:
            Match_df = Match_df.drop_duplicates(["FIX_ID", "MOVE_ID"], keep="first").sort_values(
                by="FIX_ID", ignore_index=True
            )
            logger.info(f"  Marker-based matching (forward/backward) found {len(Match_df)} matches")
        
        # Transform output
        temp_output = pd.merge(
            pd.merge(Match_df, fix_data, left_on='FIX_ID',
                     right_index=True, how='left'),
            move_data, left_on='MOVE_ID', right_index=True, how='left'
        )
        
        if direction == "Reverse" or direction == "REV":
            temp_output = temp_output.rename(columns={
                'ili_id_x': 'Master_ili_id',
                'joint_number_x': 'Master_joint_number',
                'joint_number_y': 'Alias_joint_number',
                "joint_number_org": "Target_joint_number",
                'ili_id_y': 'Target_ili_id',
                'CONFIDENCE': 'Confidence',
                'SOURCE': 'Match_Source'
            })
            Match_output = temp_output[['Master_ili_id', 'Master_joint_number',
                                        'Target_joint_number', 'Alias_joint_number', 'Target_ili_id', 'Confidence', 'Match_Source']]
        else:
            temp_output = temp_output.rename(columns={
                'ili_id_x': 'Master_ili_id',
                'joint_number_x': 'Master_joint_number',
                'joint_number_y': "Target_joint_number",
                'ili_id_y': 'Target_ili_id',
                'CONFIDENCE': 'Confidence',
                'SOURCE': 'Match_Source'
            })
            Match_output = temp_output[[
                'Master_ili_id', 'Master_joint_number', 'Target_joint_number', 'Target_ili_id', 'Confidence', 'Match_Source']]
        
        Match_all = Match_output.reset_index(drop=True)
        
        # Handle questionable matches (duplicates)
        questionable = Match_all[
            (Match_all["Target_joint_number"].duplicated(keep=False)) |
            (Match_all["Master_joint_number"].duplicated(keep=False))
        ]
        
        if not questionable.empty:
            Match_all = Match_all.loc[~Match_all.index.isin(
                questionable.index)]
            Match_df = Match_df.loc[~Match_df.index.isin(questionable.index)]
            logger.warning(f"  Found {len(questionable)} questionable matches from forward/backward matching")
        
        # Track matched joints from forward/backward matching
        forward_backward_matched_master = set(Match_all["Master_joint_number"].astype(str).tolist())
        forward_backward_matched_target = set(Match_all["Target_joint_number"].astype(str).tolist())
        
        logger.info(f"  Forward/Backward matching: {len(forward_backward_matched_master)} master joints matched, "
                   f"{len(forward_backward_matched_target)} target joints matched")
        
        # Transform to output format
        Match_df["Master_joint_number"] = fix_df.loc[Match_df["FIX_ID"]]["joint_number"].array
        Match_df["Target_joint_number"] = move_df.loc[Match_df["MOVE_ID"]]["joint_number"].array
        
        # Determine unmatched joints from forward/backward matching
        all_master_joints = set(fix_df["joint_number"].astype(str).tolist())
        all_target_joints = set(move_df["joint_number"].astype(str).tolist())
        
        unmatched_master_from_forward_backward = all_master_joints - forward_backward_matched_master
        unmatched_target_from_forward_backward = all_target_joints - forward_backward_matched_target
        
        logger.info(f"  Unmatched from forward/backward: {len(unmatched_master_from_forward_backward)} master, "
                   f"{len(unmatched_target_from_forward_backward)} target")
        
        # ========== REPORT CUMULATIVE MATCHING RESULTS ==========
        # Track matched joints from cumulative matching (already done within chunks)
        final_matched_master = forward_backward_matched_master.copy()
        final_matched_target = forward_backward_matched_target.copy()
        
        if cumulative_matches:
            for match in cumulative_matches:
                final_matched_master.update([str(j) for j in match.master_joints])
                final_matched_target.update([str(j) for j in match.target_joints])
            
            logger.info(f"Cumulative matching found {len(cumulative_matches)} additional matches")
            
            splits = sum(1 for m in cumulative_matches if m.is_split())
            merges = sum(1 for m in cumulative_matches if m.is_merge())
            
            logger.info(f"  - Splits (1-to-many): {splits}")
            logger.info(f"  - Merges (many-to-1): {merges}")
        
        # ========== MERGE RESULTS ==========
        logger.info("Merging results from forward/backward matching and cumulative matching...")
        
        # Build matched joints DataFrame with all required fields
        matched_joints_list = []
        
        # Add forward/backward matching results (using calculated confidence scores)
        for _, row in Match_all.iterrows():
            master_joint_num = int(row['Master_joint_number'])
            target_joint_num = int(row['Target_joint_number'])
            
            master_length = master_length_map.get(master_joint_num, 0)
            target_length = target_length_map.get(target_joint_num, 0)
            
            length_diff = abs(master_length - target_length)
            avg_length = (master_length + target_length) / 2
            ratio = (length_diff / avg_length) if avg_length > 0 else 0
            
            # Use the confidence score and source from matching
            confidence = row.get('Confidence', 1.0)  # Default to 1.0 if not present
            match_source = row.get('Match_Source', 'Unknown')  # Get the source (Marker, Forward, or Backward)
            
            matched_joints_list.append({
                'Master ILI ID': row['Master_ili_id'],
                'Master Joint Number': master_joint_num,
                'Master Total Length (m)': round(master_length, 3),
                'Target Joint Number': target_joint_num,
                'Target Total Length (m)': round(target_length, 3),
                'Target ILI ID': row['Target_ili_id'],
                'Length Difference (m)': round(length_diff, 3),
                'Length Ratio': round(ratio, 4),
                'Confidence Score': round(confidence, 3),
                'Confidence Level': _confidence_level_from_score(round(confidence, 3), match_source),
                'Match Source': match_source,
                'Match Type': '1-to-1'
            })
        
        # Add cumulative matches
        for match in cumulative_matches:
            master_joints_str = ','.join(map(str, match.master_joints))
            target_joints_str = ','.join(map(str, match.target_joints))
            
            avg_length = (match.master_total_length + match.target_total_length) / 2
            ratio = (match.length_difference / avg_length) if avg_length > 0 else 0
            
            matched_joints_list.append({
                'Master ILI ID': fix_ili_id,
                'Master Joint Number': master_joints_str,
                'Master Total Length (m)': round(match.master_total_length, 3),
                'Target Joint Number': target_joints_str,
                'Target Total Length (m)': round(match.target_total_length, 3),
                'Target ILI ID': move_ili_id,
                'Length Difference (m)': round(match.length_difference, 3),
                'Length Ratio': round(ratio, 4),
                'Confidence Score': round(match.confidence, 3),
                'Confidence Level': _confidence_level_from_score(round(match.confidence, 3), 'Cumulative Matching'),
                'Match Source': 'Cumulative Matching',
                'Match Type': match.match_type
            })
        
        # Determine final unmatched joints
        final_unmatched_master = all_master_joints - final_matched_master
        final_unmatched_target = all_target_joints - final_matched_target
        
        # ========== ABSOLUTE DISTANCE MATCHING ==========
        # For remaining unmatched joints, match those with absolute length difference < 1.5m.
        # This is the only scenario that produces LOW confidence matches.
        # Strategy: Find unmatched joints "trapped" between matched joints and match them
        # to target joints in the corresponding bounded region where absolute length difference < 1.5m.
        # Matching is position-based with absolute distance validation.
        logger.info("Performing absolute distance matching for unmatched joints (absolute difference < 1.5m)...")
        
        # Build mapping of matched joints (master -> target)
        master_to_target_map = {}
        for match_dict in matched_joints_list:
            master_joint = match_dict['Master Joint Number']
            target_joint = match_dict['Target Joint Number']
            # Handle comma-separated (aggregate) matches - use first joint
            if isinstance(master_joint, str) and ',' in master_joint:
                master_joint = int(master_joint.split(',')[0])
            else:
                master_joint = int(master_joint)
            if isinstance(target_joint, str) and ',' in target_joint:
                target_joint = int(target_joint.split(',')[0])
            else:
                target_joint = int(target_joint)
            master_to_target_map[master_joint] = target_joint
        
        # Get sorted list of all master and target joints
        all_master_sorted = sorted([int(j) for j in all_master_joints])
        all_target_sorted = sorted([int(j) for j in all_target_joints])
        
        # Build list of all unmatched joints with their lengths
        # INCLUDES zero-length joints (e.g., M53730) - they should be matchable by position
        unmatched_master = []
        for joint_num_str in final_unmatched_master:
            joint_num = int(joint_num_str)
            length = master_length_map.get(joint_num, 0)
            unmatched_master.append((joint_num, length))  # Include ALL joints, even zero-length
        
        unmatched_target = []
        for joint_num_str in final_unmatched_target:
            joint_num = int(joint_num_str)
            length = target_length_map.get(joint_num, 0)
            unmatched_target.append((joint_num, length))  # Include ALL joints, even zero-length
        
        absolute_distance_matches = []
        used_target_joints = set()
        
        # For each unmatched master joint
        for m_joint_num, m_length in unmatched_master:
            # Find matched joints immediately before and after this master joint
            m_idx = all_master_sorted.index(m_joint_num)
            
            # Find previous matched master joint
            prev_matched_master = None
            for i in range(m_idx - 1, -1, -1):
                if all_master_sorted[i] in master_to_target_map:
                    prev_matched_master = all_master_sorted[i]
                    break
            
            # Find next matched master joint
            next_matched_master = None
            for i in range(m_idx + 1, len(all_master_sorted)):
                if all_master_sorted[i] in master_to_target_map:
                    next_matched_master = all_master_sorted[i]
                    break
            
            # Determine the search range in target using matched joints' positions
            if prev_matched_master is not None and next_matched_master is not None:
                # Normal case: bounded by two matched joints
                prev_matched_target = master_to_target_map[prev_matched_master]
                next_matched_target = master_to_target_map[next_matched_master]
                
                # Find ALL unmatched target joints in this range with absolute distance < 1.5m
                candidates = []
                for t_joint_num, t_length in unmatched_target:
                    if t_joint_num in used_target_joints:
                        continue
                    if min(prev_matched_target, next_matched_target) < t_joint_num < max(prev_matched_target, next_matched_target):
                        # Check if absolute length difference < 1.5m
                        if abs(m_length - t_length) < 1.5:
                            candidates.append((t_joint_num, t_length))
                
            elif prev_matched_master is not None:
                # At the end: only have previous matched joint
                prev_matched_target = master_to_target_map[prev_matched_master]
                candidates = []
                for t_joint_num, t_length in unmatched_target:
                    if t_joint_num in used_target_joints:
                        continue
                    if t_joint_num > prev_matched_target:
                        # Check if absolute length difference < 1.5m
                        if abs(m_length - t_length) < 1.5:
                            candidates.append((t_joint_num, t_length))
                        
            elif next_matched_master is not None:
                # At the beginning: only have next matched joint
                next_matched_target = master_to_target_map[next_matched_master]
                candidates = []
                for t_joint_num, t_length in unmatched_target:
                    if t_joint_num in used_target_joints:
                        continue
                    if t_joint_num < next_matched_target:
                        # Check if absolute length difference < 1.5m
                        if abs(m_length - t_length) < 1.5:
                            candidates.append((t_joint_num, t_length))
            else:
                # No matched joints before or after - skip this joint
                continue
            
            # If we found candidate(s), match with the closest one by joint number
            # Absolute distance < 1.5m validation already applied above
            if candidates:
                candidates.sort(key=lambda x: abs(x[0] - m_joint_num))
                t_joint_num, t_length = candidates[0]
                used_target_joints.add(t_joint_num)
                
                # Create LOW confidence match (position-based with absolute distance < 1.5m validation)
                # This is the ONLY scenario that produces Low confidence matches.
                # Sequencing + absolute distance < 1.5m confirms the match.
                # Calculate confidence score dynamically from actual length data
                length_diff = abs(m_length - t_length)
                avg_length = (m_length + t_length) / 2
                diff_ratio = (length_diff / avg_length) if avg_length > 0 else 0
                
                # Calculate confidence using standard formula but without tolerance constraint
                # confidence = 1.0 - (diff_ratio / tolerance)
                # Using tolerance of 0.30 for calculation only (not as a filter)
                tolerance = 0.30
                calculated_confidence = max(0.0, 1.0 - (diff_ratio / tolerance))
                
                absolute_distance_matches.append({
                    'Master ILI ID': fix_ili_id,
                    'Master Joint Number': m_joint_num,
                    'Master Total Length (m)': round(m_length, 3),
                    'Target Joint Number': t_joint_num,
                    'Target Total Length (m)': round(t_length, 3),
                    'Target ILI ID': move_ili_id,
                    'Length Difference (m)': round(length_diff, 3),
                    'Length Ratio': round(diff_ratio, 4),
                    'Confidence Score': round(calculated_confidence, 3),  # Calculated from data
                    'Confidence Level': _confidence_level_from_score(round(calculated_confidence, 3), 'Absolute Distance Matching'),  # Always 'Low'
                    'Match Source': 'Absolute Distance Matching',
                    'Match Type': '1-to-1 (absolute distance)'
                })
                
                # Update matched sets
                final_matched_master.add(str(m_joint_num))
                final_matched_target.add(str(t_joint_num))
        
        if absolute_distance_matches:
            logger.info(f"  Found {len(absolute_distance_matches)} absolute distance matches (absolute diff < 1.5m)")
            matched_joints_list.extend(absolute_distance_matches)
        else:
            logger.info("  No absolute distance matches found")
        
        # Recalculate final unmatched joints after absolute distance matching
        final_unmatched_master = all_master_joints - final_matched_master
        final_unmatched_target = all_target_joints - final_matched_target
        
        # ========== POST-PROCESSING MERGE ==========
        # Merge ALL unmatched joints with neighboring matched joints
        # This handles cases like M2770 → T2770 matched (1-to-1), but T2780 remains unmatched
        # The merge creates M2770 → T2770+T2780 (1-to-2) if it improves match quality
        # Processes ALL unmatched joints sequentially, updating match index dynamically
        logger.info("Performing post-processing merge...")
        
        matched_joints_list, final_matched_master, final_matched_target, postprocessing_merge_count = \
            postprocessing_merge(
                matched_joints_list=matched_joints_list,
                final_matched_master=final_matched_master,
                final_matched_target=final_matched_target,
                all_master_joints=all_master_joints,
                all_target_joints=all_target_joints,
                master_length_map=master_length_map,
                target_length_map=target_length_map,
                fix_ili_id=fix_ili_id,
                move_ili_id=move_ili_id,
                tolerance=cumulative_tolerance,
                min_confidence=cumulative_min_confidence
            )
        
        if postprocessing_merge_count > 0:
            logger.info(f"  Post-processing merge: {postprocessing_merge_count} joints merged into existing matches")
        
        # Recalculate final unmatched joints after unmatched joint merging
        final_unmatched_master = all_master_joints - final_matched_master
        final_unmatched_target = all_target_joints - final_matched_target
        
        # Create integrated list with matched and unmatched joints interleaved
        integrated_list = []
        
        # Sort matched joints by master joint number (handle comma-separated lists)
        matched_with_sort_key = []
        for match_row in matched_joints_list:
            master_joints_str = str(match_row['Master Joint Number'])
            # Get first master joint number for sorting
            first_master = int(master_joints_str.split(',')[0]) if ',' in master_joints_str else int(master_joints_str)
            matched_with_sort_key.append((first_master, match_row))
        
        matched_with_sort_key.sort(key=lambda x: x[0])
        
        # Track last processed joint numbers
        last_master_joint = 0
        last_target_joint = 0
        
        for idx, (sort_key, match_row) in enumerate(matched_with_sort_key):
            master_joints_str = str(match_row['Master Joint Number'])
            target_joints_str = str(match_row['Target Joint Number'])
            
            # Parse master joint range
            if ',' in master_joints_str:
                master_joints = [int(j) for j in master_joints_str.split(',')]
                current_master_start = min(master_joints)
                current_master_end = max(master_joints)
            else:
                current_master_start = int(master_joints_str)
                current_master_end = int(master_joints_str)
            
            # Parse target joint range
            if ',' in target_joints_str:
                target_joints = [int(j) for j in target_joints_str.split(',')]
                current_target_start = min(target_joints)
                current_target_end = max(target_joints)
            else:
                current_target_start = int(target_joints_str)
                current_target_end = int(target_joints_str)
            
            # Add unmatched master joints before this match
            unmatched_masters_in_gap = [
                int(j) for j in final_unmatched_master
                if last_master_joint < int(j) < current_master_start
            ]
            for joint_num in sorted(unmatched_masters_in_gap):
                length = master_length_map.get(joint_num, 0)
                integrated_list.append({
                    'Master ILI ID': fix_ili_id,
                    'Master Joint Number': joint_num,
                    'Master Total Length (m)': round(length, 3),
                    'Target Joint Number': '',
                    'Target Total Length (m)': '',
                    'Target ILI ID': '',
                    'Length Difference (m)': '',
                    'Length Ratio': '',
                    'Confidence Score': '',
                    'Confidence Level': '',
                    'Match Source': 'Unmatched Master',
                    'Match Type': 'Unmatched'
                })
            
            # Add unmatched target joints before this match
            unmatched_targets_in_gap = [
                int(j) for j in final_unmatched_target
                if last_target_joint < int(j) < current_target_start
            ]
            for joint_num in sorted(unmatched_targets_in_gap):
                length = target_length_map.get(joint_num, 0)
                integrated_list.append({
                    'Master ILI ID': '',
                    'Master Joint Number': '',
                    'Master Total Length (m)': '',
                    'Target Joint Number': joint_num,
                    'Target Total Length (m)': round(length, 3),
                    'Target ILI ID': move_ili_id,
                    'Length Difference (m)': '',
                    'Length Ratio': '',
                    'Confidence Score': '',
                    'Confidence Level': '',
                    'Match Source': 'Unmatched Target',
                    'Match Type': 'Unmatched'
                })
            
            # Add the matched pair
            integrated_list.append(match_row)
            
            # Update last processed positions
            last_master_joint = current_master_end
            last_target_joint = current_target_end
        
        # Add remaining unmatched joints after the last match
        remaining_unmatched_masters = [
            int(j) for j in final_unmatched_master
            if int(j) > last_master_joint
        ]
        for joint_num in sorted(remaining_unmatched_masters):
            length = master_length_map.get(joint_num, 0)
            integrated_list.append({
                'Master ILI ID': fix_ili_id,
                'Master Joint Number': joint_num,
                'Master Total Length (m)': round(length, 3),
                'Target Joint Number': '',
                'Target Total Length (m)': '',
                'Target ILI ID': '',
                'Length Difference (m)': '',
                'Length Ratio': '',
                'Confidence Score': '',
                'Confidence Level': '',
                'Match Source': 'Unmatched Master',
                'Match Type': 'Unmatched'
            })
        
        remaining_unmatched_targets = [
            int(j) for j in final_unmatched_target
            if int(j) > last_target_joint
        ]
        for joint_num in sorted(remaining_unmatched_targets):
            length = target_length_map.get(joint_num, 0)
            integrated_list.append({
                'Master ILI ID': '',
                'Master Joint Number': '',
                'Master Total Length (m)': '',
                'Target Joint Number': joint_num,
                'Target Total Length (m)': round(length, 3),
                'Target ILI ID': move_ili_id,
                'Length Difference (m)': '',
                'Length Ratio': '',
                'Confidence Score': '',
                'Confidence Level': '',
                'Match Source': 'Unmatched Target',
                'Match Type': 'Unmatched'
            })
        
        # Create the integrated matched joints DataFrame (includes both matched and unmatched)
        matched_joints = pd.DataFrame(integrated_list)
        
        # Create separate unmatched joints DataFrame for the Unmatched tab
        unmatched_joints_list = []
        for joint_num in sorted([int(j) for j in final_unmatched_master]):
            length = master_length_map.get(joint_num, 0)
            unmatched_joints_list.append({
                'Inspection': 'Master',
                'ILI ID': fix_ili_id,
                'Joint Number': joint_num,
                'Length (m)': round(length, 3)
            })
        
        for joint_num in sorted([int(j) for j in final_unmatched_target]):
            length = target_length_map.get(joint_num, 0)
            unmatched_joints_list.append({
                'Inspection': 'Target',
                'ILI ID': move_ili_id,
                'Joint Number': joint_num,
                'Length (m)': round(length, 3)
            })
        
        unmatched_joints = pd.DataFrame(unmatched_joints_list)
        
        # Process questionable joints
        questionable_joints_list = []
        if not questionable.empty:
            for _, row in questionable.iterrows():
                master_joint_num = int(row['Master_joint_number'])
                target_joint_num = int(row['Target_joint_number'])
                
                master_length = master_length_map.get(master_joint_num, 0)
                target_length = target_length_map.get(target_joint_num, 0)
                
                questionable_joints_list.append({
                    'Master ILI ID': row['Master_ili_id'],
                    'Master Joint Number': master_joint_num,
                    'Master Total Length (m)': round(master_length, 3),
                    'Target Joint Number': target_joint_num,
                    'Target Total Length (m)': round(target_length, 3),
                    'Target ILI ID': row['Target_ili_id'],
                    'Reason': 'Duplicate'
                })
        
        questionable_df = pd.DataFrame(questionable_joints_list)
        
        # Build run summary
        run_summary = {
            "Master_inspection_guid": master_guid_tuple[0],
            "Master_ili_id": fix_ili_id,
            "Target_inspection_guid": target_guid,
            "Target_ili_id": move_ili_id,
            "Total_master_joints": len(fix_df),
            "Total_target_joints": len(move_df),
            "Matched_joints": len(matched_joints),
            "Matched_from_original": len(Match_all),
            "Matched_from_cumulative": len(cumulative_matches),
            "Matched_from_absolute_distance": len(absolute_distance_matches),
            "Matched_from_postprocessing_merge": postprocessing_merge_count,
            "Unmatched_joints": len(unmatched_joints),
            "Questionable_matches": len(questionable),
            "Master_joint_percentage": round((len(final_matched_master) / len(fix_df)) * 100, 2),
            "Target_joint_percentage": round((len(final_matched_target) / len(move_df)) * 100, 2),
            "Flow_direction": direction,
            "Cumulative_matching_enabled": use_cumulative_for_unmatched
        }
        
        logger.info("=" * 80)
        logger.info("MATCHING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total matched: {len(matched_joints)}")
        logger.info(f"  - From original algorithm: {len(Match_all)}")
        logger.info(f"  - From cumulative matching: {len(cumulative_matches)}")
        logger.info(f"  - From absolute distance: {len(absolute_distance_matches)}")
        logger.info(f"  - From post-processing merge: {postprocessing_merge_count}")
        logger.info(f"Total unmatched: {len(unmatched_joints)}")
        logger.info(f"Master match rate: {run_summary['Master_joint_percentage']:.2f}%")
        logger.info(f"Target match rate: {run_summary['Target_joint_percentage']:.2f}%")
        logger.info("=" * 80)
        
        # Export to Excel if output_path provided
        export_success = None
        exported_output_path = None
        if output_path:
            export_success = export_to_excel(matched_joints, unmatched_joints, run_summary, output_path)
            exported_output_path = os.path.abspath(output_path)
            if export_success:
                logger.info(f"✓ Results exported to: {exported_output_path}")
            else:
                logger.error(f"✗ Results were not exported to: {exported_output_path}")
        
        # Convert DataFrames to list of dicts for JSON serialization
        matched_joints_list = matched_joints.replace({np.nan: None}).to_dict('records')
        unmatched_joints_list = unmatched_joints.replace({np.nan: None}).to_dict('records')
        questionable_joints_list = questionable_df.replace({np.nan: None}).to_dict('records')
        
        # Store result for this target
        results_list.append({
            "run_summary": run_summary,
            "matched_joints": matched_joints_list,
            "unmatched_joints": unmatched_joints_list,
            "questionable_joints": questionable_joints_list,
            "export_success": export_success,
            "output_path": exported_output_path
        })
        
        logger.info(f"Completed target {target_guid}")
    
    # For simplicity, return the first result (single target for now)
    if not results_list:
        raise ValueError("No valid target inspections found")
    
    return results_list[0]
