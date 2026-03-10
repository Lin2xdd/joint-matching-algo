# Flow Direction Detection

## Overview

The joint matching algorithm automatically detects whether two pipeline inspections run in the same direction (FORWARD) or opposite directions (REVERSE). This is critical for proper alignment.

## How It Works

### 1. Calculate Joint Length Differences

For each inspection, calculate the difference between consecutive joint lengths:

```python
# If joints are [18.3m, 18.2m, 18.4m, 18.5m]
# Differences: [-0.1m, +0.2m, +0.1m]
differences = joint_diff_calc(data, 'joint_length')
```

### 2. Generate Overlapping Pairs (Sliding Window)

Create pairs of consecutive non-zero differences:

```python
# Given differences: [1.0, -1.0, 3.0, -2.0, 2.0]
# Overlapping pairs:
#   (1.0, -1.0)
#   (-1.0, 3.0)
#   (3.0, -2.0)
#   (-2.0, 2.0)

pairs = pairs_generator(differences)
```

**Why overlapping?** Provides ~60% more data points for more robust pattern detection.

### 3. Compare Patterns with Spatial Validation

```python
# Enhanced version with spatial validation using distance column
# Forward: Compare master pairs to target pairs in normal order
fwd_match_pct = match_pct_calc_with_distance(master_pairs, target_pairs_fwd,
                                              master_df, target_df, tolerance=0.05)

# Reverse: Compare master pairs to target pairs in reversed order
rev_match_pct = match_pct_calc_with_distance(master_pairs, target_pairs_rev,
                                              master_df, RevMove_df, tolerance=0.05)
```

The enhanced function validates pattern matches using **two criteria**:
1. **Pattern match**: Joint length difference pairs must match (e.g., (+2, -1) == (+2, -1))
2. **Spatial validation**: Target relative distance must be within ±5% of master relative distance

This filters out false positive pattern matches that occur at wrong pipeline positions.

**Distance Column Handling**:
- Distance column is **required** for flow detection
- If occasional NaN values exist, they are automatically filled using:
  `current_distance = previous_distance + current_joint_length`
- Uses **relative distance** (from pipeline start) to handle pipelines that don't start at 0m

### 4. Select Direction

```python
if fwd_match_pct > rev_match_pct:
    direction = "FORWARD"
else:
    direction = "REVERSE"
```

The direction with higher match percentage wins.

## Example Results

### Good Detection (Clear Winner)

```
Master pairs: 185
Target pairs: 183

Forward (FWD): 13.66%
Reverse (REV): 3.28%

>>> DECISION: FORWARD (margin: 10.38%)
```

### Poor Detection (Ambiguous)

```
Master pairs: 116
Target pairs: 117

Forward (FWD): 5.13%
Reverse (REV): 7.69%

>>> DECISION: REVERSE (margin: 2.56%)
⚠️ Small margin indicates uncertain detection!
```

## Overlapping vs Non-Overlapping Pairs

### Non-Overlapping (OLD)

```
Differences: [A, B, C, D, E, F, G, H]
Pairs:       (A,B), (C,D), (E,F), (G,H)  ← 4 pairs
```

- **Advance by 2** after each pair
- Fewer samples
- Less robust to noise

### Overlapping (CURRENT)

```
Differences: [A, B, C, D, E, F, G, H]
Pairs:       (A,B), (B,C), (C,D), (D,E), (E,F), (F,G), (G,H)  ← 7 pairs
```

- **Advance by 1** after each pair (sliding window)
- More samples (~60% increase)
- More robust pattern detection

## Key Functions

### [`joint_diff_calc(data, column)`](Scripts/joint_matching.py:17)
Calculates differences between consecutive joint lengths.

### [`pairs_generator(data_diff)`](Scripts/joint_matching.py:23)
Generates overlapping pairs from differences using sliding window approach.

### [`match_pct_calc(master_pairs, target_pairs)`](Scripts/joint_matching.py:94)
Calculates percentage of master pairs that appear in target pairs (in order). Pattern-only version.

### [`match_pct_calc_with_distance(master_pairs, target_pairs, master_df, target_df, tolerance)`](Scripts/joint_matching.py:130)
Enhanced version with spatial validation using ±5% relative distance tolerance. **This is the version used for flow detection.**

### [`_fill_nan_distances(df, dist_col)`](Scripts/joint_matching.py:103)
Utility function that fills NaN distance values using cumulative joint length calculation.

## Diagnostic Tools

### Quick Diagnosis
```bash
python diagnose_flow_direction.py
```

Shows:
- Pair counts
- Match percentages for both directions
- Decision and margin
- Geometric evidence

### Comprehensive Testing
```bash
python test_flow_direction_all_sets.py
```

Tests flow direction detection on all ARC datasets and validates against geometric evidence.

## Interpretation Guide

### Match Percentages

| Range | Interpretation |
|-------|----------------|
| > 40% | Excellent correlation |
| 20-40% | Good correlation |
| 10-20% | Moderate correlation |
| 5-10% | Weak correlation |
| < 5% | Very weak correlation |

### Confidence Margins

| Margin | Confidence Level |
|--------|------------------|
| > 20% | Very high confidence |
| 10-20% | High confidence |
| 5-10% | Moderate confidence |
| 2-5% | Low confidence ⚠️ |
| < 2% | Very low confidence ⚠️⚠️ |

**Warning**: Margins below 5% may indicate unreliable detection. Review results carefully.

## Troubleshooting

### Issue: Wrong Direction Detected

**Symptoms**:
- Very low match rate (< 70%)
- Large alignment offsets (thousands of meters)
- First matched joint is near the end of the pipeline

**Possible Causes**:
1. Non-overlapping pairs (if using old version)
2. Very weak correlation in joint length patterns
3. Data quality issues (missing joints, incorrect lengths)

**Solutions**:
1. Ensure using overlapping pairs (current version)
2. Check match percentage margin - should be > 5%
3. Validate geometric evidence (start/end distances)
4. Inspect data quality

### Issue: Very Low Match Percentages

**Symptoms**:
- Both FWD and REV percentages < 10%
- Small margin between them (< 3%)

**Possible Causes**:
- Inspections have very different joint length patterns
- Significant pipeline changes between inspections
- Data quality issues

**Solutions**:
1. Review source data for quality
2. Check if inspections cover the same pipeline section
3. Consider if pipelines underwent modifications between inspections

## Best Practices

1. **Always check the confidence margin** - margins < 5% warrant manual review
2. **Validate with geometric evidence** - start/end distances should confirm direction
3. **Review match rates** - should typically be > 90% for good data
4. **Use diagnostic tools** - run `diagnose_flow_direction.py` when in doubt

## History

- **March 2026**:
  - **Phase 1**: Changed from non-overlapping to overlapping pairs
    - Fixed major alignment issue in ARC Set 5
    - Improved match rate from 60% to 99.88%
    - Increased confidence margins significantly
  - **Phase 2**: Added spatial validation with distance column
    - Enhanced flow detection with ±5% relative distance tolerance
    - Filters false positive pattern matches at wrong positions
    - Requires distance column; auto-fills occasional NaN values
    - Average 23% margin improvement across test datasets
    - All test datasets maintained correct direction decisions

See [`CHANGELOG_FLOW_DIRECTION_IMPROVEMENT.md`](CHANGELOG_FLOW_DIRECTION_IMPROVEMENT.md) for detailed information.
