# postprocessing_merge.py
"""
Post-Processing Merge Module for Joint Matching

This module handles merging of unmatched joints with neighboring matched joints
after the main matching algorithms (marker alignment, forward/backward, cumulative,
and absolute distance matching) have completed.

Key Features:
- Merges ALL unmatched joints (no length filtering) with neighboring matched joints
- Supports three-tier confidence acceptance system:
  * High: confidence >= 60% (strong length agreement)
  * Medium: confidence < 60% but within 30% tolerance (acceptable length match)
  * Low: absolute length difference < 1.5m (position-based, independent of percentage)
- Uses absolute confidence threshold (same as cumulative matching)
- Applies 5% penalty per extra joint for aggregate matches
- Dynamic match index updating for sequential merge operations
- Creates 1-to-many, many-to-1, or many-to-many matches as appropriate

Algorithm:
1. Identifies ALL unmatched master and target joints
2. For each unmatched joint, finds neighboring matched joints (by sequence)
3. Attempts to merge the unmatched joint into the neighbor's existing match
4. Calculates base confidence from length matching
5. Applies aggregate penalty: 5% per extra joint (treating existing match as whole)
6. Validates using three-tier acceptance criteria (absolute 60% threshold)
7. Updates match index dynamically for subsequent merges

Confidence Calculation:
- Base confidence = f(length_match) using standard formula
- Aggregate penalty = 0.05 × (num_master_joints - 1) + 0.05 × (num_target_joints - 1)
- Final confidence = max(base_confidence - aggregate_penalty, 0.0)
- Acceptance: High (≥60%), Medium (within 30%), or Low (abs diff < 1.5m)

Important Notes:
- Uses absolute 60% threshold (not relative to original match quality)
- Prioritizes quantity over quality: matches more joints even if quality degrades
- Consecutive unmatched joints can be merged sequentially due to dynamic index updates
- Same design philosophy as cumulative length matching algorithm

Author: Joint Matching System
Date: 2026-03-06
Version: 3.0 (Updated to absolute threshold + aggregate penalty)
"""

import logging
from typing import List, Dict, Set, Tuple

# Configure logger
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


def _evaluate_merge_quality(original_confidence: float,
                            merged_confidence: float,
                            improvement_threshold: float = 0.05) -> bool:
    """
    [OBSOLETE - No longer used as of v3.0]
    
    Previously used to determine if a merge improved match quality (relative check).
    Replaced with absolute 60% threshold to prioritize quantity over quality.
    
    This function is kept for backward compatibility with diagnostic scripts.
    
    Args:
        original_confidence: Confidence of the original match
        merged_confidence: Confidence of the proposed merged match
        improvement_threshold: Minimum improvement required (default 5%)
    
    Returns:
        True if merge improves match quality by at least threshold
    """
    return merged_confidence >= original_confidence - improvement_threshold


def _confidence_level_from_score(confidence_score: float, min_confidence: float = 0.60) -> str:
    """
    Map numeric confidence score to a level label using the original criteria.
    
    Confidence Levels:
    - High: >= 60% (score >= 0.60) - Strong length agreement
    - Medium: < 60% (score < 0.60) but within 30% length tolerance
    - Low: Only for merges where absolute length difference < 1.5m (if enabled)
    
    For short joint merge, Low confidence is used when the merge maintains
    positional alignment but has weaker length agreement.
    """
    if confidence_score >= min_confidence:
        return 'High'
    else:
        # Medium confidence: below 60% but within tolerance
        # (passes_tolerance was already validated before calling this)
        return 'Medium'


def postprocessing_merge(
    matched_joints_list: List[Dict],
    final_matched_master: Set[str],
    final_matched_target: Set[str],
    all_master_joints: Set[str],
    all_target_joints: Set[str],
    master_length_map: Dict[int, float],
    target_length_map: Dict[int, float],
    fix_ili_id: str,
    move_ili_id: str,
    tolerance: float = 0.30,
    min_confidence: float = 0.60
) -> Tuple[List[Dict], Set[str], Set[str], int]:
    """
    Post-processing merge: Merge ALL unmatched joints with neighboring matched joints.
    
    Args:
        matched_joints_list: List of existing matched joint dictionaries
        final_matched_master: Set of matched master joint numbers (as strings)
        final_matched_target: Set of matched target joint numbers (as strings)
        all_master_joints: Set of all master joint numbers (as strings)
        all_target_joints: Set of all target joint numbers (as strings)
        master_length_map: Map of master joint numbers to lengths
        target_length_map: Map of target joint numbers to lengths
        fix_ili_id: Master ILI ID
        move_ili_id: Target ILI ID
        tolerance: Length tolerance for matching (default 0.30 = 30%)
        min_confidence: Minimum confidence threshold (default 0.60 = 60%)
    
    Returns:
        Tuple of (updated_matched_joints_list, updated_matched_master, updated_matched_target, merge_count)
    """
    logger.info(f"Starting post-processing merge (processing ALL unmatched joints)...")
    
    # Find ALL unmatched joints (no length filtering)
    unmatched_master = all_master_joints - final_matched_master
    unmatched_target = all_target_joints - final_matched_target
    
    logger.info(f"  Found {len(unmatched_master)} unmatched master joints")
    logger.info(f"  Found {len(unmatched_target)} unmatched target joints")
    
    if not unmatched_master and not unmatched_target:
        logger.info("  No unmatched joints to process")
        return matched_joints_list, final_matched_master, final_matched_target, 0
    
    # Create index of matched joints for quick lookup
    # Key: (master_joint_nums_str, target_joint_nums_str) -> match_dict
    match_index = {}
    for match_dict in matched_joints_list:
        master_key = str(match_dict['Master Joint Number'])
        target_key = str(match_dict['Target Joint Number'])
        match_index[(master_key, target_key)] = match_dict
    
    # Track all joints sorted for neighbor finding
    all_master_sorted = sorted([int(j) for j in all_master_joints])
    all_target_sorted = sorted([int(j) for j in all_target_joints])
    
    merge_count = 0
    updated_matches = []
    merged_joints = set()  # Track which joints have been merged
    
    # Helper function to update match_index after a merge
    def update_match_index_entry(old_master_key, old_target_key, new_match):
        """Update match_index with new match structure after a merge."""
        # Remove old entry
        if (old_master_key, old_target_key) in match_index:
            del match_index[(old_master_key, old_target_key)]
        # Add new entry
        new_master_key = str(new_match['Master Joint Number'])
        new_target_key = str(new_match['Target Joint Number'])
        match_index[(new_master_key, new_target_key)] = new_match
    
    # Process ALL unmatched target joints in order (1-to-many merges)
    for unmatched_target_str in sorted(unmatched_target, key=int):
        if unmatched_target_str in merged_joints:
            continue
            
        unmatched_target_num = int(unmatched_target_str)
        unmatched_target_length = target_length_map.get(unmatched_target_num, 0)
        
        # DEBUG: Log processing of joint 2810
        if unmatched_target_num == 2810:
            logger.info(f"\n=== DEBUG: Processing T2810 ===")
            logger.info(f"  Length: {unmatched_target_length}m")
            logger.info(f"  All target sorted: {all_target_sorted}")
        
        # Find neighboring target joints (before and after)
        target_idx = all_target_sorted.index(unmatched_target_num)
        
        # Check previous target joint
        prev_target_num = all_target_sorted[target_idx - 1] if target_idx > 0 else None
        # Check next target joint
        next_target_num = all_target_sorted[target_idx + 1] if target_idx < len(all_target_sorted) - 1 else None
        
        # DEBUG: Log neighbors for joint 2810
        if unmatched_target_num == 2810:
            logger.info(f"  Previous neighbor: T{prev_target_num} (matched={str(prev_target_num) in final_matched_target if prev_target_num else 'N/A'})")
            logger.info(f"  Next neighbor: T{next_target_num} (matched={str(next_target_num) in final_matched_target if next_target_num else 'N/A'})")
            logger.info(f"  Current match_index keys: {list(match_index.keys())}")
        
        # Try merging with previous matched joint
        if prev_target_num and str(prev_target_num) in final_matched_target:
            # DEBUG for 2810
            if unmatched_target_num == 2810:
                logger.info(f"  Searching for match containing T{prev_target_num}...")
            
            # Find the match containing prev_target_num
            for master_key, target_key in match_index.keys():
                target_joints = [int(j) for j in target_key.split(',')]
                if prev_target_num in target_joints:
                    # Found the match - try merging short_target into it
                    original_match = match_index[(master_key, target_key)]
                    master_joints = [int(j) for j in master_key.split(',')]
                    
                    # Calculate merged lengths
                    master_total = sum(master_length_map.get(j, 0) for j in master_joints)
                    target_total = sum(target_length_map.get(j, 0) for j in target_joints) + unmatched_target_length
                    
                    # DEBUG for 2810
                    if unmatched_target_num == 2810:
                        logger.info(f"  Found match: M{master_key} <-> T{target_key}")
                        logger.info(f"  Master total: {master_total}m, Target before: {target_total - unmatched_target_length}m")
                        logger.info(f"  After merge: Master {master_total}m vs Target {target_total}m")
                    
                    # Calculate base confidence from length match
                    base_confidence = _calculate_confidence(master_total, target_total, tolerance)
                    
                    # Apply aggregate penalty (5% per extra joint, same as cumulative matching)
                    # Existing match is treated as a whole unit when counting penalties
                    # Example: Merging into 2-to-1 match adds penalties for both existing master joints
                    new_target_joint_count = len(target_joints) + 1  # Adding unmatched_target
                    master_joint_count = len(master_joints)  # Existing match's master side
                    
                    # Calculate penalties: 5% per joint beyond the first (1-to-1 has no penalty)
                    master_penalty = 0.05 * (master_joint_count - 1) if master_joint_count > 1 else 0
                    target_penalty = 0.05 * (new_target_joint_count - 1) if new_target_joint_count > 1 else 0
                    total_penalty = master_penalty + target_penalty
                    
                    # Final confidence after applying aggregate complexity penalty
                    merged_confidence = max(base_confidence - total_penalty, 0.0)
                    
                    passes_tolerance = _is_length_within_tolerance(master_total, target_total, tolerance)
                    passes_absolute_distance = abs(master_total - target_total) < 1.5
                    
                    # Three-tier acceptance criteria (absolute threshold - prioritizes quantity over quality):
                    # High: confidence >= 60% (min_confidence) - strong length agreement
                    # Medium: confidence < 60% but within 30% tolerance - acceptable length match
                    # Low: absolute length difference < 1.5m - position-based (ignores percentage)
                    accept_high = merged_confidence >= min_confidence
                    accept_medium = merged_confidence < min_confidence and passes_tolerance
                    accept_low = merged_confidence < min_confidence and not passes_tolerance and passes_absolute_distance
                    
                    # DEBUG for 2810
                    if unmatched_target_num == 2810:
                        logger.info(f"  Base conf: {base_confidence:.3f}, Penalty: {total_penalty:.3f}, Final: {merged_confidence:.3f}")
                        logger.info(f"  Accept high: {accept_high}, medium: {accept_medium}, low: {accept_low}")
                    
                    # Accept merge using absolute threshold (v3.0: no comparison to original match quality)
                    # This prioritizes matching more joints even if it degrades high-quality matches
                    if accept_high or accept_medium or accept_low:
                        
                        # Create updated match
                        new_target_joints = target_joints + [unmatched_target_num]
                        new_target_joints_str = ','.join(map(str, sorted(new_target_joints)))
                        
                        match_type = f"{len(master_joints)}-to-{len(new_target_joints)}"
                        
                        final_confidence = merged_confidence if merged_confidence >= min_confidence else min_confidence
                        
                        # Determine confidence level based on three-tier system
                        if accept_high:
                            confidence_level = 'High'
                        elif accept_medium:
                            confidence_level = 'Medium'
                        elif accept_low:
                            confidence_level = 'Low'
                        else:
                            confidence_level = _confidence_level_from_score(final_confidence, min_confidence)
                        
                        # Preserve original match source and combine with merge
                        original_source = original_match.get('Match Source', 'Unknown')
                        combined_source = f"{original_source} + Post-Processing Merge"
                        
                        updated_match = {
                            'Master ILI ID': fix_ili_id,
                            'Master Joint Number': master_key,
                            'Master Total Length (m)': round(master_total, 3),
                            'Target Joint Number': new_target_joints_str,
                            'Target Total Length (m)': round(target_total, 3),
                            'Target ILI ID': move_ili_id,
                            'Length Difference (m)': round(abs(master_total - target_total), 3),
                            'Length Ratio': round(abs(master_total - target_total) / ((master_total + target_total) / 2), 4) if (master_total + target_total) > 0 else 0,
                            'Confidence Score': round(final_confidence, 3),
                            'Confidence Level': confidence_level,
                            'Match Source': combined_source,
                            'Match Type': match_type
                        }
                        
                        updated_matches.append((master_key, target_key, updated_match))
                        merged_joints.add(unmatched_target_str)
                        final_matched_target.add(unmatched_target_str)
                        merge_count += 1
                        
                        # Update match_index so subsequent merges can find this updated match
                        update_match_index_entry(master_key, target_key, updated_match)
                        
                        logger.info(f"  Merged T{unmatched_target_num} into match M{master_key} <-> T{target_key} -> T{new_target_joints_str} (conf={final_confidence:.3f})")
                        break
                    else:
                        # DEBUG for 2810: Log why merge was rejected
                        if unmatched_target_num == 2810:
                            logger.info(f"  REJECTED: Merge did not pass any acceptance tier")
                            logger.info(f"    High tier (>=60%): {accept_high}")
                            logger.info(f"    Medium tier (within 30%): {accept_medium}")
                            logger.info(f"    Low tier (abs<1.5m): {accept_low}")
        
        # If not merged with previous, try merging with next matched joint
        if unmatched_target_str not in merged_joints and next_target_num and str(next_target_num) in final_matched_target:
            for master_key, target_key in match_index.keys():
                target_joints = [int(j) for j in target_key.split(',')]
                if next_target_num in target_joints:
                    original_match = match_index[(master_key, target_key)]
                    master_joints = [int(j) for j in master_key.split(',')]
                    
                    master_total = sum(master_length_map.get(j, 0) for j in master_joints)
                    target_total = sum(target_length_map.get(j, 0) for j in target_joints) + unmatched_target_length
                    
                    # Calculate base confidence from length match
                    base_confidence = _calculate_confidence(master_total, target_total, tolerance)
                    
                    # Apply aggregate penalty (5% per extra joint)
                    new_target_joint_count = len(target_joints) + 1  # Adding unmatched_target
                    master_joint_count = len(master_joints)
                    
                    master_penalty = 0.05 * (master_joint_count - 1) if master_joint_count > 1 else 0
                    target_penalty = 0.05 * (new_target_joint_count - 1) if new_target_joint_count > 1 else 0
                    total_penalty = master_penalty + target_penalty
                    
                    merged_confidence = max(base_confidence - total_penalty, 0.0)
                    
                    passes_tolerance = _is_length_within_tolerance(master_total, target_total, tolerance)
                    passes_absolute_distance = abs(master_total - target_total) < 1.5
                    
                    # Three-tier acceptance criteria (absolute threshold)
                    accept_high = merged_confidence >= min_confidence
                    accept_medium = merged_confidence < min_confidence and passes_tolerance
                    accept_low = merged_confidence < min_confidence and not passes_tolerance and passes_absolute_distance
                    
                    # Accept merge if it meets any tier (no relative quality check)
                    if accept_high or accept_medium or accept_low:
                        
                        new_target_joints = [unmatched_target_num] + target_joints
                        new_target_joints_str = ','.join(map(str, sorted(new_target_joints)))
                        
                        match_type = f"{len(master_joints)}-to-{len(new_target_joints)}"
                        final_confidence = merged_confidence if merged_confidence >= min_confidence else min_confidence
                        
                        # Determine confidence level based on three-tier system
                        if accept_high:
                            confidence_level = 'High'
                        elif accept_medium:
                            confidence_level = 'Medium'
                        elif accept_low:
                            confidence_level = 'Low'
                        else:
                            confidence_level = _confidence_level_from_score(final_confidence, min_confidence)
                        
                        # Preserve original match source and combine with merge
                        original_source = original_match.get('Match Source', 'Unknown')
                        combined_source = f"{original_source} + Post-Processing Merge"
                        
                        updated_match = {
                            'Master ILI ID': fix_ili_id,
                            'Master Joint Number': master_key,
                            'Master Total Length (m)': round(master_total, 3),
                            'Target Joint Number': new_target_joints_str,
                            'Target Total Length (m)': round(target_total, 3),
                            'Target ILI ID': move_ili_id,
                            'Length Difference (m)': round(abs(master_total - target_total), 3),
                            'Length Ratio': round(abs(master_total - target_total) / ((master_total + target_total) / 2), 4) if (master_total + target_total) > 0 else 0,
                            'Confidence Score': round(final_confidence, 3),
                            'Confidence Level': confidence_level,
                            'Match Source': combined_source,
                            'Match Type': match_type
                        }
                        
                        updated_matches.append((master_key, target_key, updated_match))
                        merged_joints.add(unmatched_target_str)
                        final_matched_target.add(unmatched_target_str)
                        merge_count += 1
                        
                        # Update match_index so subsequent merges can find this updated match
                        update_match_index_entry(master_key, target_key, updated_match)
                        
                        logger.debug(f"  Merged T{unmatched_target_num} into match M{master_key} <-> T{target_key} -> T{new_target_joints_str} (conf={final_confidence:.3f})")
                        break
    
    # Process short unmatched master joints (many-to-1 merges)
    for unmatched_master_str in sorted(unmatched_master, key=int):
        if unmatched_master_str in merged_joints:
            continue
            
        unmatched_master_num = int(unmatched_master_str)
        unmatched_master_length = master_length_map.get(unmatched_master_num, 0)
        
        master_idx = all_master_sorted.index(unmatched_master_num)
        prev_master_num = all_master_sorted[master_idx - 1] if master_idx > 0 else None
        next_master_num = all_master_sorted[master_idx + 1] if master_idx < len(all_master_sorted) - 1 else None
        
        # Try merging with previous matched joint
        if prev_master_num and str(prev_master_num) in final_matched_master:
            for master_key, target_key in match_index.keys():
                master_joints = [int(j) for j in master_key.split(',')]
                if prev_master_num in master_joints:
                    original_match = match_index[(master_key, target_key)]
                    target_joints = [int(j) for j in target_key.split(',')]
                    
                    master_total = sum(master_length_map.get(j, 0) for j in master_joints) + unmatched_master_length
                    target_total = sum(target_length_map.get(j, 0) for j in target_joints)
                    
                    # Calculate base confidence from length match
                    base_confidence = _calculate_confidence(master_total, target_total, tolerance)
                    
                    # Apply aggregate penalty (5% per extra joint)
                    new_master_joint_count = len(master_joints) + 1  # Adding unmatched_master
                    target_joint_count = len(target_joints)
                    
                    master_penalty = 0.05 * (new_master_joint_count - 1) if new_master_joint_count > 1 else 0
                    target_penalty = 0.05 * (target_joint_count - 1) if target_joint_count > 1 else 0
                    total_penalty = master_penalty + target_penalty
                    
                    merged_confidence = max(base_confidence - total_penalty, 0.0)
                    
                    passes_tolerance = _is_length_within_tolerance(master_total, target_total, tolerance)
                    passes_absolute_distance = abs(master_total - target_total) < 1.5
                    
                    # Three-tier acceptance criteria (absolute threshold)
                    accept_high = merged_confidence >= min_confidence
                    accept_medium = merged_confidence < min_confidence and passes_tolerance
                    accept_low = merged_confidence < min_confidence and not passes_tolerance and passes_absolute_distance
                    
                    # Accept merge if it meets any tier (no relative quality check)
                    if accept_high or accept_medium or accept_low:
                        
                        new_master_joints = master_joints + [unmatched_master_num]
                        new_master_joints_str = ','.join(map(str, sorted(new_master_joints)))
                        
                        match_type = f"{len(new_master_joints)}-to-{len(target_joints)}"
                        final_confidence = merged_confidence if merged_confidence >= min_confidence else min_confidence
                        
                        # Determine confidence level based on three-tier system
                        if accept_high:
                            confidence_level = 'High'
                        elif accept_medium:
                            confidence_level = 'Medium'
                        elif accept_low:
                            confidence_level = 'Low'
                        else:
                            confidence_level = _confidence_level_from_score(final_confidence, min_confidence)
                        
                        # Preserve original match source and combine with merge
                        original_source = original_match.get('Match Source', 'Unknown')
                        combined_source = f"{original_source} + Post-Processing Merge"
                        
                        updated_match = {
                            'Master ILI ID': fix_ili_id,
                            'Master Joint Number': new_master_joints_str,
                            'Master Total Length (m)': round(master_total, 3),
                            'Target Joint Number': target_key,
                            'Target Total Length (m)': round(target_total, 3),
                            'Target ILI ID': move_ili_id,
                            'Length Difference (m)': round(abs(master_total - target_total), 3),
                            'Length Ratio': round(abs(master_total - target_total) / ((master_total + target_total) / 2), 4) if (master_total + target_total) > 0 else 0,
                            'Confidence Score': round(final_confidence, 3),
                            'Confidence Level': confidence_level,
                            'Match Source': combined_source,
                            'Match Type': match_type
                        }
                        
                        updated_matches.append((master_key, target_key, updated_match))
                        merged_joints.add(unmatched_master_str)
                        final_matched_master.add(unmatched_master_str)
                        merge_count += 1
                        
                        # Update match_index so subsequent merges can find this updated match
                        update_match_index_entry(master_key, target_key, updated_match)
                        
                        logger.debug(f"  Merged M{unmatched_master_num} into match M{master_key} <-> T{target_key} -> M{new_master_joints_str} (conf={final_confidence:.3f})")
                        break
        
        # If not merged with previous, try merging with next matched joint
        if unmatched_master_str not in merged_joints and next_master_num and str(next_master_num) in final_matched_master:
            for master_key, target_key in match_index.keys():
                master_joints = [int(j) for j in master_key.split(',')]
                if next_master_num in master_joints:
                    original_match = match_index[(master_key, target_key)]
                    target_joints = [int(j) for j in target_key.split(',')]
                    
                    master_total = sum(master_length_map.get(j, 0) for j in master_joints) + unmatched_master_length
                    target_total = sum(target_length_map.get(j, 0) for j in target_joints)
                    
                    # Calculate base confidence from length match
                    base_confidence = _calculate_confidence(master_total, target_total, tolerance)
                    
                    # Apply aggregate penalty (5% per extra joint)
                    new_master_joint_count = len(master_joints) + 1  # Adding unmatched_master
                    target_joint_count = len(target_joints)
                    
                    master_penalty = 0.05 * (new_master_joint_count - 1) if new_master_joint_count > 1 else 0
                    target_penalty = 0.05 * (target_joint_count - 1) if target_joint_count > 1 else 0
                    total_penalty = master_penalty + target_penalty
                    
                    merged_confidence = max(base_confidence - total_penalty, 0.0)
                    
                    passes_tolerance = _is_length_within_tolerance(master_total, target_total, tolerance)
                    passes_absolute_distance = abs(master_total - target_total) < 1.5
                    
                    # Three-tier acceptance criteria (absolute threshold)
                    accept_high = merged_confidence >= min_confidence
                    accept_medium = merged_confidence < min_confidence and passes_tolerance
                    accept_low = merged_confidence < min_confidence and not passes_tolerance and passes_absolute_distance
                    
                    # Accept merge if it meets any tier (no relative quality check)
                    if accept_high or accept_medium or accept_low:
                        
                        new_master_joints = [unmatched_master_num] + master_joints
                        new_master_joints_str = ','.join(map(str, sorted(new_master_joints)))
                        
                        match_type = f"{len(new_master_joints)}-to-{len(target_joints)}"
                        final_confidence = merged_confidence if merged_confidence >= min_confidence else min_confidence
                        
                        # Determine confidence level based on three-tier system
                        if accept_high:
                            confidence_level = 'High'
                        elif accept_medium:
                            confidence_level = 'Medium'
                        elif accept_low:
                            confidence_level = 'Low'
                        else:
                            confidence_level = _confidence_level_from_score(final_confidence, min_confidence)
                        
                        # Preserve original match source and combine with merge
                        original_source = original_match.get('Match Source', 'Unknown')
                        combined_source = f"{original_source} + Post-Processing Merge"
                        
                        updated_match = {
                            'Master ILI ID': fix_ili_id,
                            'Master Joint Number': new_master_joints_str,
                            'Master Total Length (m)': round(master_total, 3),
                            'Target Joint Number': target_key,
                            'Target Total Length (m)': round(target_total, 3),
                            'Target ILI ID': move_ili_id,
                            'Length Difference (m)': round(abs(master_total - target_total), 3),
                            'Length Ratio': round(abs(master_total - target_total) / ((master_total + target_total) / 2), 4) if (master_total + target_total) > 0 else 0,
                            'Confidence Score': round(final_confidence, 3),
                            'Confidence Level': confidence_level,
                            'Match Source': combined_source,
                            'Match Type': match_type
                        }
                        
                        updated_matches.append((master_key, target_key, updated_match))
                        merged_joints.add(unmatched_master_str)
                        final_matched_master.add(unmatched_master_str)
                        merge_count += 1
                        
                        # Update match_index so subsequent merges can find this updated match
                        update_match_index_entry(master_key, target_key, updated_match)
                        
                        logger.debug(f"  Merged M{unmatched_master_num} into match M{master_key} <-> T{target_key} -> M{new_master_joints_str} (conf={final_confidence:.3f})")
                        break
    
    # Apply updates to matched_joints_list
    updated_matched_joints_list = []
    for match_dict in matched_joints_list:
        master_key = str(match_dict['Master Joint Number'])
        target_key = str(match_dict['Target Joint Number'])
        
        # Check if this match was updated
        was_updated = False
        for old_master, old_target, new_match in updated_matches:
            if master_key == old_master and target_key == old_target:
                updated_matched_joints_list.append(new_match)
                was_updated = True
                break
        
        if not was_updated:
            updated_matched_joints_list.append(match_dict)
    
    logger.info(f"  Post-processing merge complete: {merge_count} joints merged into existing matches")
    
    return updated_matched_joints_list, final_matched_master, final_matched_target, merge_count
