# Integrated Joint Matching - Quick Start Guide

## What Is It?

A two-phase joint matching algorithm that combines:
1. **Original Algorithm**: Fast marker-based matching
2. **Cumulative Length Matching**: Handles splits, merges, and unmatched joints

## How to Use

### Quick Start

1. Open [`run_integrated_matching.py`](run_integrated_matching.py)
2. Update your configuration:
   ```python
   MASTER_GUID = "your-master-inspection-guid"
   TARGET_GUIDS = ["your-target-inspection-guid"]
   OUTPUT_PATH = "results.xlsx"
   ```
3. Run: `python run_integrated_matching.py`

### Output

Excel file with 3 tabs:
- **Summary**: Overall statistics
- **Matched Joints**: All matches with confidence scores, length differences, ratios
- **Unmatched Joints**: Joints that couldn't be matched

## Workflow

### Phase 1: Original Algorithm
- Detects flow direction (forward/reverse)
- Finds markers (large length changes)
- Performs forward/backward matching
- Fast and accurate for well-aligned data

### Phase 2: Cumulative Length Matching (for unmatched joints)
- Handles 1-to-1, 1-to-many (splits), many-to-1 (merges)
- Uses configurable tolerance (default 20%)
- Calculates confidence scores
- Greedy matching strategy with local target-shift recovery

## Matching Determination Rules (Current)

For forward, backward, and cumulative matching:

1. Calculate confidence score from length ratio difference.
2. **High confidence match** if `confidence > 0.60`.
3. If not high, check length ratio tolerance.
4. **Low confidence match** if length ratio difference is within `20%` tolerance.
5. Otherwise reject.

This means:
- `High` = score above 0.60
- `Low` = score at or below 0.60 but still within 20% tolerance
- Rejected = outside tolerance

## Key Parameters

```python
USE_CUMULATIVE = True              # Enable cumulative matching
CUMULATIVE_TOLERANCE = 0.20        # 20% length tolerance
CUMULATIVE_MAX_AGGREGATE = 5       # Max joints to combine
CUMULATIVE_MIN_CONFIDENCE = 0.60   # Minimum confidence
```

## Output Columns (Matched Joints)

- Master/Target ILI ID
- Master/Target Joint Number
- Master/Target Length (m)
- **Length Difference (m)**: Absolute difference
- **Length Ratio**: Difference / Average length
- **Confidence Score**: 0.60 to 1.00 (for accepted matches)
- **Confidence Level**: `High` or `Low`
- **Match Source**: "Original Algorithm" or "Cumulative Matching"
- **Match Type**: "1-to-1", "1-to-2", "2-to-1", etc.

## Confidence vs Length-Difference Ratio Chart

Confidence is computed from ratio using:

```text
confidence = 1 - (length_ratio_diff / tolerance)
length_ratio_diff = (1 - confidence) * tolerance
```

Where `length_ratio_diff = abs(L1 - L2) / ((L1 + L2) / 2)`.

### Current system (tolerance = 20% = 0.20)

| Confidence Score | Length Ratio Diff |
|---|---:|
| 100% (1.00) | 0.00 |
| 90% (0.90) | 0.02 |
| 80% (0.80) | 0.04 |
| 70% (0.70) | 0.06 |
| 60% (0.60) | 0.08 |
| 50% (0.50) | 0.10 |
| 40% (0.40) | 0.12 |
| 30% (0.30) | 0.14 |
| 20% (0.20) | 0.16 |
| 10% (0.10) | 0.18 |
| 0% (0.00) | 0.20 |

### Note on the `60% -> 0.04` example

That mapping is true when tolerance is **10%** (`0.10`):

`length_ratio_diff = (1 - 0.60) * 0.10 = 0.04`

With the updated **20%** tolerance, `60%` corresponds to `0.08`.

## Typical Pipe Joint Length Reference

Confidence classes used below:
- `High`: confidence `> 0.60` ⇒ `length_ratio_diff < 0.08`
- `Low`: confidence `<= 0.60` and accepted by tolerance ⇒ `0.08 <= length_ratio_diff <= 0.20`

Range formula for a nominal joint length `L` and ratio limit `r`:
- `T_min = L * (2 - r) / (2 + r)`
- `T_max = L * (2 + r) / (2 - r)`

| Pipe Material | Typical Joint Length(s) | High Confidence Match Length Range (m) | Low Confidence Match Length Range (m) |
|---|---|---|---|
| Carbon steel | 6 m (SRL), 12 m (DRL) | 6 m: 5.538–6.500; 12 m: 11.077–13.000 | 6 m: 4.909–7.333; 12 m: 9.818–14.667 |
| Stainless steel | 6 m | 5.538–6.500 | 4.909–7.333 |
| Ductile iron | 5.5–6 m | 5.5 m: 5.077–5.958; 6 m: 5.538–6.500 | 5.5 m: 4.500–6.722; 6 m: 4.909–7.333 |
| Cast iron | 3–4 m | 3 m: 2.769–3.250; 4 m: 3.692–4.333 | 3 m: 2.455–3.667; 4 m: 3.273–4.889 |
| Concrete | 2.5–4 m | 2.5 m: 2.308–2.708; 4 m: 3.692–4.333 | 2.5 m: 2.045–3.056; 4 m: 3.273–4.889 |
| PVC | 6 m | 5.538–6.500 | 4.909–7.333 |
| HDPE | 6 m, 12 m, coils | 6 m: 5.538–6.500; 12 m: 11.077–13.000 | 6 m: 4.909–7.333; 12 m: 9.818–14.667 |
| GRE / GRP | 6–12 m | 6 m: 5.538–6.500; 12 m: 11.077–13.000 | 6 m: 4.909–7.333; 12 m: 9.818–14.667 |
| Copper | 6 m | 5.538–6.500 | 4.909–7.333 |

## Implemented Fixes

1. **Skip-branch recording fix (forward/backward)**
   - Previously, a skipped low-confidence pair could still be appended to matched records.
   - Now skipped pairs are not recorded as matches.

2. **Confidence level reporting**
   - Added output column: `Confidence Level`.
   - Levels now use `High` / `Low` with unmatched rows blank.

3. **Tolerance upgrade to 20%**
   - Default tolerance updated from 10% to 20% for integrated/cumulative matching behavior.

4. **Tail block processing fix (after last marker)**
   - After-last-marker region now runs full **Forward → Backward → Cumulative** flow.
   - Uses index-safe bounds and avoids relying on joint-number values as dataframe indices.

5. **Cumulative alignment recovery**
   - Added one-step target-shift probe in cumulative unmatched loop to recover local offset alignment.

## When to Adjust Parameters

**High-quality data:**
```python
cumulative_tolerance = 0.05        # Stricter (5%)
cumulative_min_confidence = 0.70   # Higher bar
```

**Noisy data:**
```python
cumulative_tolerance = 0.15        # More lenient (15%)
cumulative_min_confidence = 0.50   # Lower bar
```

**Many splits/merges:**
```python
cumulative_max_aggregate = 10      # Allow more aggregation
```

## Files

- [`Scripts/integrated_joint_matching.py`](Scripts/integrated_joint_matching.py) - Main algorithm
- [`run_integrated_matching.py`](run_integrated_matching.py) - Easy runner script
- [`Scripts/joint_matching.py`](Scripts/joint_matching.py) - Original algorithm
- [`Scripts/flexible_joint_matching.py`](Scripts/flexible_joint_matching.py) - Cumulative matching

## Advantages

✅ Higher match rate than original alone  
✅ Handles joint splits and merges  
✅ Fast baseline from original algorithm  
✅ High confidence + flexible cumulative matches  
✅ Detailed Excel output with all metrics  

---

**Date**: 2026-02-19  
**Version**: 1.1
