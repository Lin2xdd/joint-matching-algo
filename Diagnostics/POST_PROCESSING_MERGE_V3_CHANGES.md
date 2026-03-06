# Post-Processing Merge v3.0 - Changes Summary

## Date
2026-03-06

## Overview
Updated post-processing merge algorithm to align with cumulative matching design philosophy: **prioritize quantity (matching more joints) over quality (maintaining high confidence)**.

---

## Key Changes

### 1. Replaced Relative Quality Check with Absolute Threshold

#### Before (v2.0)
```python
# Relative check: new confidence must be within 5% of original
passes_quality = merged_confidence >= original_confidence - 0.05

if (accept_high or accept_medium or accept_low) and passes_quality:
    # Accept merge
```

**Problem:** Prevented merging joints that would degrade high-quality matches, even slightly.

**Example:**
- Original match: 95% confidence
- After adding unmatched joint: 70% confidence
- Result: **REJECTED** (70% < 95% - 5% = 90%)
- Issue: Left joints unmatched to preserve match quality

#### After (v3.0)
```python
# Absolute threshold: new confidence must meet tier criteria
# No comparison to original confidence

if accept_high or accept_medium or accept_low:
    # Accept merge
```

**Solution:** Uses absolute 60% threshold (same as cumulative matching).

**Example:**
- Original match: 95% confidence
- After adding unmatched joint: 70% confidence
- Result: **ACCEPTED** (70% ≥ 60%, High tier)
- Benefit: More joints get matched

---

### 2. Added Aggregate Penalty (5% per Extra Joint)

#### Before (v2.0)
```python
# No penalty for aggregate matches
merged_confidence = _calculate_confidence(master_total, target_total, tolerance)
```

**Problem:** Didn't account for complexity of aggregate matches.

#### After (v3.0)
```python
# Calculate base confidence
base_confidence = _calculate_confidence(master_total, target_total, tolerance)

# Apply penalty for each extra joint
master_penalty = 0.05 * (num_master_joints - 1)
target_penalty = 0.05 * (num_target_joints - 1)
total_penalty = master_penalty + target_penalty

# Final confidence after penalty
merged_confidence = max(base_confidence - total_penalty, 0.0)
```

**Example:**
- Base confidence: 90%
- Merging to create 3-to-2 match
- Master penalty: 0.05 × (3-1) = 0.10 (10%)
- Target penalty: 0.05 × (2-1) = 0.05 (5%)
- Total penalty: 15%
- Final confidence: 90% - 15% = **75%**

**Rationale:** Same as cumulative matching - penalize complex aggregations while still allowing them.

---

### 3. Treats Existing Matches as Whole Units

#### Implementation
The penalty calculation counts **all joints** in the existing match plus the new unmatched joint:

```python
# For target-side merge
new_target_joint_count = len(target_joints) + 1  # existing + new
target_penalty = 0.05 * (new_target_joint_count - 1)

# For master-side merge  
new_master_joint_count = len(master_joints) + 1  # existing + new
master_penalty = 0.05 * (new_master_joint_count - 1)
```

**Example:**
- Existing match: M100,M101 ↔ T100 (2-to-1)
- Adding unmatched: T101
- New match: M100,M101 ↔ T100,T101 (2-to-2)
- Penalties:
  - Master: 0.05 × (2-1) = 0.05 (5%)
  - Target: 0.05 × (2-1) = 0.05 (5%)
  - Total: 10%

---

## Impact Analysis

### Scenario 1: High Quality Match Degradation

**Before v3.0:**
```
Existing: M100 (10m) ↔ T100 (10m), confidence 100%
Add T101 (5m)
Result: M100 (10m) ↔ T100,T101 (15m), confidence 0%

Check: 0% >= 100% - 5% = 95%? ✗ REJECTED
T101 remains unmatched
```

**After v3.0:**
```
Existing: M100 (10m) ↔ T100 (10m), confidence 100%
Add T101 (5m)
Result: M100 (10m) ↔ T100,T101 (15m)

Base confidence: 0% (terrible length match)
Penalty: 0.05 × (2-1) = 0.05 (5%)
Final confidence: 0% - 5% = 0%

Absolute diff: |10 - 15| = 5m >= 1.5m
Within 30%? No: 50% > 30%
Result: ✗ REJECTED (doesn't meet any tier)
T101 remains unmatched
```

**Outcome:** Similar - both versions reject this poor merge.

---

### Scenario 2: Moderate Quality Match

**Before v3.0:**
```
Existing: M100 (10m) ↔ T100,T101 (9.5m), confidence 95%
Add T102 (0.8m)
Result: M100 (10m) ↔ T100,T101,T102 (10.3m), confidence 93%

Check: 93% >= 95% - 5% = 90%? ✓ ACCEPTED
Match updated
```

**After v3.0:**
```
Existing: M100 (10m) ↔ T100,T101 (9.5m), confidence 95%
Add T102 (0.8m)
Result: M100 (10m) ↔ T100,T101,T102 (10.3m)

Base confidence: 97% (excellent length match)
Penalty: 0.05 × (3-1) = 0.10 (10%)
Final confidence: 97% - 10% = 87%

Check: 87% >= 60%? ✓ ACCEPTED (High tier)
Match updated
```

**Outcome:** Both accept, but v3.0 applies penalty for aggregate complexity.

---

### Scenario 3: Borderline Medium Tier Match

**Before v3.0:**
```
Existing: M100 (10m) ↔ T100 (9m), confidence 70%
Add T101 (2m)
Result: M100 (10m) ↔ T100,T101 (11m), confidence 67%

Check: 67% >= 70% - 5% = 65%? ✓ ACCEPTED
Match updated
```

**After v3.0:**
```
Existing: M100 (10m) ↔ T100 (9m), confidence 70%
Add T101 (2m)
Result: M100 (10m) ↔ T100,T101 (11m)

Base confidence: 95% (good length match)
Penalty: 0.05 × (2-1) = 0.05 (5%)
Final confidence: 95% - 5% = 90%

Check: 90% >= 60%? ✓ ACCEPTED (High tier)
Match updated
```

**Outcome:** Both accept, v3.0 even gives higher confidence due to good length match.

---

## Three-Tier Acceptance Criteria (Unchanged)

The three-tier system remains the same:

| Tier | Criteria | Based On |
|------|----------|----------|
| **High** | Confidence ≥ 60% | Length agreement |
| **Medium** | Confidence < 60% AND within 30% tolerance | Length agreement |
| **Low** | Absolute distance < 1.5m | Position |

---

## Files Modified

### Primary Changes
- **`Scripts/postprocessing_merge.py`**
  - Lines 231-260: Target merge with previous neighbor
  - Lines 331-349: Target merge with next neighbor
  - Lines 424-442: Master merge with previous neighbor
  - Lines 505-523: Master merge with next neighbor
  - Lines 1-35: Updated module documentation
  - Lines 70-84: Marked `_evaluate_merge_quality` as obsolete

---

## Backward Compatibility

### Diagnostic Scripts
The `_evaluate_merge_quality()` function is kept but marked as obsolete to maintain compatibility with existing diagnostic scripts in the `Diagnostics/` folder.

### API
The `postprocessing_merge()` function signature remains unchanged:
```python
def postprocessing_merge(
    matched_joints_list, final_matched_master, final_matched_target,
    all_master_joints, all_target_joints,
    master_length_map, target_length_map,
    fix_ili_id, move_ili_id,
    tolerance=0.30, min_confidence=0.60
) -> Tuple[List[Dict], Set[str], Set[str], int]
```

---

## Testing Recommendations

### Test Case 1: Zero-Length Joint (M53730 Issue)
```
Existing: M53720 (0.63m) ↔ T53720,T53730 (0.934m)
Unmatched: M53730 (0m)

Expected: M53720,M53730 (0.63m) ↔ T53720,T53730 (0.934m)
Reason: Low tier acceptance (abs diff 0.304m < 1.5m)
```

### Test Case 2: Consecutive Unmatched Joints
```
Matches: M100 ↔ T100, M110 ↔ T110
Unmatched: M101, M102, M103 (between M100 and M110)

Expected: Sequential merging due to dynamic match index updates
- M101 merges into M100 → updated match
- M102 attempts merge with updated match containing M100,M101
- M103 attempts merge with further updated match
```

### Test Case 3: High-Quality Match Preservation
```
Existing: M100 (10m) ↔ T100 (9.95m), confidence 98%
Unmatched: T101 (5m) nearby

v2.0: Would reject if degraded below 93%
v3.0: Accepts if final confidence ≥ 60% or meets Medium/Low tier
```

---

## Migration Notes

### For Users
No action required - changes are internal to the algorithm. Results will show:
- **More matches** (especially near borderline cases)
- **Lower average confidence** for aggregate matches (due to penalty)
- **More complete coverage** of unmatched joints

### For Developers
If you have custom code calling `_evaluate_merge_quality()`:
- Function still works but is no longer used by the main algorithm
- Consider switching to absolute threshold logic for consistency

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025 | Initial implementation |
| 2.0 | 2026-03-05 | Renamed from short_joint_merge.py, added Low tier support |
| 3.0 | 2026-03-06 | Absolute threshold + aggregate penalty (this update) |

---

## Related Issues

- **M53730 Zero-Length Joint:** Fixed in v2.0 by removing zero-length filter in integrated_joint_matching.py
- **Quality vs Quantity Balance:** Addressed in v3.0 by prioritizing quantity over quality
- **Consecutive Unmatched Joints:** Already working via dynamic match index updates

---

## Summary

**Key Principle:** Align post-processing merge with cumulative matching philosophy.

**Before:** Conservative - protect match quality at the cost of leaving joints unmatched  
**After:** Aggressive - match more joints even if quality degrades, as long as absolute threshold (60%) or tier criteria are met

**Result:** Higher match rates, lower average confidence for complex aggregates, better consistency across matching phases.
