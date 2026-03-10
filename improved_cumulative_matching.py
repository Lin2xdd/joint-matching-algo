"""
Improved 1-to-Many Cumulative Matching Algorithm

Strategy: Find the combinations that bracket the target (one below, one above),
then pick the best match based on confidence/tolerance.
"""

def find_best_1_to_many_match(master_joint, target_df, t_idx, max_aggregate=5, 
                               length_tolerance=0.30, min_confidence=0.60):
    """
    Improved 1-to-many matching that finds bracketing combinations.
    
    Algorithm:
    1. Accumulate target joints to find:
       - Best combination BELOW master joint length
       - Best combination ABOVE master joint length
    2. Check which passes confidence or tolerance threshold
    3. If both pass, pick the one with higher confidence
    4. If only one passes, use that one
    5. If neither passes, reject
    
    Args:
        master_joint: Single master joint to match
        target_df: DataFrame of target joints
        t_idx: Starting index in target_df
        max_aggregate: Maximum number of joints to combine
        length_tolerance: Percentage tolerance (default 0.30 = 30%)
        min_confidence: Minimum confidence threshold (default 0.60 = 60%)
    
    Returns:
        JointMatch object or None
    """
    master_length = master_joint['joint_length']
    
    # Track best combinations below and above target
    best_below = None
    best_above = None
    
    cumulative_target = 0
    target_joints_list = []
    
    # Test all combinations from 1 to max_aggregate
    for t_count in range(1, max_aggregate + 1):
        if t_idx + t_count > len(target_df):
            break
        
        current_target = target_df.iloc[t_idx + t_count - 1]
        cumulative_target += current_target['joint_length']
        target_joints_list.append(int(current_target['joint_number']))
        
        # Calculate confidence
        base_confidence = _calculate_confidence(master_length, cumulative_target, length_tolerance)
        # 5% penalty per additional joint beyond first
        split_penalty = 0.05 * (t_count - 1)
        confidence = max(base_confidence - split_penalty, 0.0)
        
        # Check if this combination passes threshold
        passes_confidence = confidence > min_confidence
        passes_tolerance = _is_length_within_tolerance(master_length, cumulative_target, length_tolerance)
        passes = passes_confidence or passes_tolerance
        
        # Store as candidate if it passes
        if passes:
            candidate = {
                'joint_count': t_count,
                'cumulative_length': cumulative_target,
                'target_joints': target_joints_list.copy(),
                'confidence': confidence,
                'diff': abs(master_length - cumulative_target),
                'diff_pct': abs(master_length - cumulative_target) / master_length * 100 if master_length > 0 else 0
            }
            
            if cumulative_target < master_length:
                # This combination is BELOW target
                if best_below is None or confidence > best_below['confidence']:
                    best_below = candidate
            elif cumulative_target > master_length:
                # This combination is ABOVE target
                if best_above is None or confidence > best_above['confidence']:
                    best_above = candidate
            else:
                # Exact match! Return immediately
                return _create_match_object(master_joint, candidate, min_confidence)
    
    # Now decide between best_below and best_above
    candidates = []
    if best_below is not None:
        candidates.append(best_below)
    if best_above is not None:
        candidates.append(best_above)
    
    if not candidates:
        # Neither below nor above passed thresholds
        return None
    
    if len(candidates) == 1:
        # Only one candidate passes
        return _create_match_object(master_joint, candidates[0], min_confidence)
    
    # Both pass - pick the one with higher confidence
    best_candidate = max(candidates, key=lambda x: x['confidence'])
    return _create_match_object(master_joint, best_candidate, min_confidence)


def _calculate_confidence(length1, length2, tolerance=0.30):
    """Calculate confidence score for a length match."""
    if length1 <= 0 or length2 <= 0:
        return 0.0
    
    diff = abs(length1 - length2)
    max_val = max(length1, length2)
    diff_ratio = diff / max_val
    
    # Confidence is inverse of difference ratio, normalized to tolerance
    confidence = 1.0 - (diff_ratio / tolerance)
    
    return max(0.0, min(1.0, confidence))


def _is_length_within_tolerance(length1, length2, tolerance=0.30):
    """Check if two lengths are within tolerance."""
    if length1 <= 0 or length2 <= 0:
        return False
    
    diff = abs(length1 - length2)
    max_val = max(length1, length2)
    diff_ratio = diff / max_val
    
    return diff_ratio <= tolerance


def _create_match_object(master_joint, candidate, min_confidence):
    """Create a JointMatch object from a candidate."""
    return {
        'master_joints': [int(master_joint['joint_number'])],
        'target_joints': candidate['target_joints'],
        'match_type': f"1-to-{candidate['joint_count']}",
        'confidence': candidate['confidence'] if candidate['confidence'] > min_confidence else min_confidence,
        'master_total_length': master_joint['joint_length'],
        'target_total_length': candidate['cumulative_length'],
        'length_difference': candidate['diff']
    }


# ============================================================================
# EXAMPLE: How this solves the 4480 issue
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EXAMPLE: Joint 4480 Matching with Improved Algorithm")
    print("=" * 80)
    print()
    
    # Simulate the data
    master_joint = {
        'joint_number': 4480,
        'joint_length': 3.312
    }
    
    target_joints = [
        {'joint_number': 4480, 'joint_length': 0.638},
        {'joint_number': 4490, 'joint_length': 0.370},
        {'joint_number': 4500, 'joint_length': 1.694},
        {'joint_number': 4510, 'joint_length': 0.638},
        {'joint_number': 4520, 'joint_length': 1.348}
    ]
    
    print(f"Master Joint 4480: {master_joint['joint_length']}m")
    print()
    print("Testing combinations:")
    print("-" * 80)
    
    cumulative = 0
    joints = []
    best_below = None
    best_above = None
    
    for i, tj in enumerate(target_joints[:4], 1):  # Test up to 4 joints
        cumulative += tj['joint_length']
        joints.append(tj['joint_number'])
        
        # Calculate confidence
        base_conf = _calculate_confidence(master_joint['joint_length'], cumulative, 0.30)
        penalty = 0.05 * (i - 1)
        confidence = max(base_conf - penalty, 0.0)
        
        diff = abs(master_joint['joint_length'] - cumulative)
        diff_pct = (diff / master_joint['joint_length']) * 100
        
        passes_conf = confidence > 0.60
        passes_tol = diff_pct <= 30
        passes = passes_conf or passes_tol
        
        status = "[PASS]" if passes else "[FAIL]"
        
        print(f"{i}. Joints {joints}:")
        print(f"   Total: {cumulative:.3f}m")
        print(f"   Diff: {diff:.3f}m ({diff_pct:.1f}%)")
        print(f"   Base confidence: {base_conf:.3f}")
        print(f"   Penalty: -{penalty:.3f}")
        print(f"   Final confidence: {confidence:.3f}")
        print(f"   Status: {status}")
        
        if passes:
            candidate = {
                'count': i,
                'cumulative': cumulative,
                'joints': joints.copy(),
                'confidence': confidence,
                'diff_pct': diff_pct
            }
            
            if cumulative < master_joint['joint_length']:
                if best_below is None or confidence > best_below['confidence']:
                    best_below = candidate
                    print(f"   -> Best BELOW candidate")
            elif cumulative > master_joint['joint_length']:
                if best_above is None or confidence > best_above['confidence']:
                    best_above = candidate
                    print(f"   -> Best ABOVE candidate")
        
        print()
    
    print("=" * 80)
    print("FINAL DECISION")
    print("=" * 80)
    
    if best_below:
        print(f"Best BELOW: {best_below['count']} joints, conf={best_below['confidence']:.3f}, diff={best_below['diff_pct']:.1f}%")
    else:
        print("Best BELOW: None")
    
    if best_above:
        print(f"Best ABOVE: {best_above['count']} joints, conf={best_above['confidence']:.3f}, diff={best_above['diff_pct']:.1f}%")
    else:
        print("Best ABOVE: None")
    
    print()
    
    if best_below and best_above:
        winner = best_above if best_above['confidence'] > best_below['confidence'] else best_below
        print(f"BOTH pass -> Choose higher confidence: {winner['count']} joints")
        print(f"  Joints: {winner['joints']}")
        print(f"  Confidence: {winner['confidence']:.3f}")
        print(f"  Difference: {winner['diff_pct']:.1f}%")
    elif best_below:
        print(f"Only BELOW passes -> Use {best_below['count']} joints")
    elif best_above:
        print(f"Only ABOVE passes -> Use {best_above['count']} joints")
    else:
        print("REJECT: No combination passes threshold")
    
    print()
    print("=" * 80)
    print("IMPROVEMENT")
    print("=" * 80)
    print("Old algorithm (first fit): 3 joints, 18.4% difference")
    print("New algorithm (best bracket): 4 joints, 0.8% difference [BETTER]")
    print()
