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

### Phase 1: Original Algorithm (Marker-Based Matching)
- Detects flow direction (forward/reverse)
- Finds markers (large length changes > 3m)
- **Marker Validation**: Requires BOTH cumulative length validation (<10m) AND marker alignment
  - Prevents matching joints from completely different pipeline sections
  - Fixed issue where joints 1000s of meters apart could be incorrectly matched
- Performs forward/backward matching between markers
- **Head Section** (before first marker):
  - Backward matching (from first marker toward start)
  - Forward matching (fill gaps from start)
  - Cumulative matching in **reverse order** (align with backward direction)
- **Between Markers**: Forward → Backward → Cumulative matching
- **Tail Section** (after last marker):
  - Forward matching (from last marker toward end)
  - Backward matching (fill gaps from end)
  - Cumulative matching in **forward order** (align with forward direction)
- Fast and accurate for well-aligned data

### Phase 2: Cumulative Length Matching (for unmatched joints)
- Handles 1-to-1, 1-to-many (splits), many-to-1 (merges)
- Uses configurable tolerance (default 30%)
- Calculates confidence scores
- Greedy matching strategy with local target-shift recovery

### Phase 3: Absolute Distance Matching (for remaining unmatched joints)
- Position-based matching for joints with absolute length difference < 1.5m
- Uses the sequence of nearby matched joints to define search boundaries
- Validates candidates using absolute distance threshold (< 1.5m)
- Selects matches based on numeric proximity of joint numbers
- Produces Low confidence matches

**How Absolute Distance Matching Works:**

1. **Boundary Detection**: For each unmatched master joint:
   - Find the nearest matched master joint **before** it
   - Find the nearest matched master joint **after** it
   - Map these to their corresponding matched target joints
   
2. **Candidate Search**: Search for target candidates **within the bounded region** where absolute length difference < 1.5m:
   ```
   Example:
   Master:  [Joint 100 (matched) ... Joint 105 (unmatched) ... Joint 110 (matched)]
             ↓                                                  ↓
   Target:  [Joint 200 (matched) ... Joints 203,204,205 ... Joint 209 (matched)]
   
   Search region: Target joints between 200 and 209
   Validation: |master_length - target_length| < 1.5m
   ```

3. **Candidate Selection**: Among validated candidates (absolute diff < 1.5m), select the target joint with the **numerically closest joint number**:
   - Filter candidates where `|master_length - target_length| < 1.5`
   - Sort remaining candidates by `|target_joint_number - master_joint_number|`
   - Select the one with minimum absolute difference
   - Mark both joints as matched with Low confidence

4. **Confidence Scoring**:
   - Calculated dynamically from actual length data using standard formula
   - Always displayed as "Low" confidence level (position-based match)
   - Absolute distance < 1.5m requirement ensures reasonable length agreement

**Key Characteristics:**
- ✅ Leverages spatial consistency from nearby matched joints
- ✅ Prevents cross-region false matches
- ✅ Works for any joint length where absolute difference < 1.5m
- ✅ More lenient than percentage-based tolerance for longer joints
- ⚠️ Assumes joint numbering is roughly aligned between inspections

## Matching Determination Rules (Current)

For forward, backward, and cumulative matching:

1. Calculate confidence score from length ratio difference.
2. **High confidence match** if `confidence > 0.60`.
3. If not high, check length ratio tolerance.
4. **Medium confidence match** if length ratio difference is within `30%` tolerance.
5. Otherwise reject.

For absolute distance matching (final round):

1. Filter candidates where `|master_length - target_length| < 1.5m`.
2. Select best match by position proximity.
3. **Low confidence match** for all absolute distance matches.

This means:
- `High` = score above 0.60 (forward/backward/cumulative matching)
- `Medium` = score at or below 0.60 but still within 30% tolerance (cumulative matching)
- `Low` = absolute distance < 1.5m, position-based match (absolute distance matching)
- Rejected = outside tolerance and not within absolute distance threshold

## Key Parameters

```python
USE_CUMULATIVE = True              # Enable cumulative matching
CUMULATIVE_TOLERANCE = 0.30        # 30% length tolerance
CUMULATIVE_MAX_AGGREGATE = 5       # Max joints to combine
CUMULATIVE_MIN_CONFIDENCE = 0.60   # Minimum confidence (60%)
```

## Output Columns (Matched Joints)

- Master/Target ILI ID
- Master/Target Joint Number
- Master/Target Length (m)
- **Length Difference (m)**: Absolute difference
- **Length Ratio**: Difference / Average length
- **Confidence Score**: 0.00 to 1.00 (calculated from length data)
- **Confidence Level**: `High`, `Medium`, or `Low`
- **Match Source**: "Marker", "Forward", "Backward", "Cumulative Matching", or "Absolute Distance Matching"
- **Match Type**: "1-to-1", "1-to-2", "2-to-1", "1-to-1 (absolute distance)", etc.

## Confidence vs Length-Difference Ratio Chart

Confidence is computed from ratio using:

```text
confidence = 1 - (length_ratio_diff / tolerance)
length_ratio_diff = (1 - confidence) * tolerance
```

Where `length_ratio_diff = abs(L1 - L2) / ((L1 + L2) / 2)`.

### Current system (tolerance = 30% = 0.30)

| Confidence Score | Length Ratio Diff |
|---|---:|
| 100% (1.00) | 0.00 |
| 90% (0.90) | 0.03 |
| 80% (0.80) | 0.06 |
| 70% (0.70) | 0.09 |
| 60% (0.60) | 0.12 |
| 50% (0.50) | 0.15 |
| 40% (0.40) | 0.18 |
| 30% (0.30) | 0.21 |
| 20% (0.20) | 0.24 |
| 10% (0.10) | 0.27 |
| 0% (0.00) | 0.30 |

### Historical tolerance values

**20% tolerance** (previous): `60%` confidence corresponds to `0.08` length ratio diff
**10% tolerance** (original): `60%` confidence corresponds to `0.04` length ratio diff
**30% tolerance** (current): `60%` confidence corresponds to `0.12` length ratio diff

## Typical Pipe Joint Length Reference

Confidence classes used below:
- `High`: confidence `> 0.60` ⇒ `length_ratio_diff < 0.12`
- `Medium`: confidence `<= 0.60` and accepted by tolerance ⇒ `0.12 <= length_ratio_diff <= 0.30`
- `Low`: absolute distance matching (absolute length difference < 1.5m)

Range formula for a nominal joint length `L` and ratio limit `r`:
- `T_min = L * (2 - r) / (2 + r)`
- `T_max = L * (2 + r) / (2 - r)`

| Pipe Material | Typical Joint Length(s) | High Confidence Match Length Range (m) | Low Confidence Match Length Range (m) |
|---|---|---|---|
| Carbon steel | 6 m (SRL), 12 m (DRL) | 6 m: 5.217–6.818; 12 m: 10.435–13.636 | 6 m: 4.615–9.231; 12 m: 9.231–18.462 |
| Stainless steel | 6 m | 5.217–6.818 | 4.615–9.231 |
| Ductile iron | 5.5–6 m | 5.5 m: 4.783–6.250; 6 m: 5.217–6.818 | 5.5 m: 4.231–8.462; 6 m: 4.615–9.231 |
| Cast iron | 3–4 m | 3 m: 2.609–3.409; 4 m: 3.478–4.545 | 3 m: 2.308–4.615; 4 m: 3.077–6.154 |
| Concrete | 2.5–4 m | 2.5 m: 2.174–2.841; 4 m: 3.478–4.545 | 2.5 m: 1.923–3.846; 4 m: 3.077–6.154 |
| PVC | 6 m | 5.217–6.818 | 4.615–9.231 |
| HDPE | 6 m, 12 m, coils | 6 m: 5.217–6.818; 12 m: 10.435–13.636 | 6 m: 4.615–9.231; 12 m: 9.231–18.462 |
| GRE / GRP | 6–12 m | 6 m: 5.217–6.818; 12 m: 10.435–13.636 | 6 m: 4.615–9.231; 12 m: 9.231–18.462 |
| Copper | 6 m | 5.217–6.818 | 4.615–9.231 |

## Implemented Fixes

1. **Skip-branch recording fix (forward/backward)**
   - Previously, a skipped low-confidence pair could still be appended to matched records.
   - Now skipped pairs are not recorded as matches.

2. **Confidence level reporting**
   - Added output column: `Confidence Level`.
   - Levels now use `High` / `Low` with unmatched rows blank.

3. **Tolerance upgrade to 30%**
   - Default tolerance updated from 10% → 20% → 30% for integrated/cumulative matching behavior.
   - More lenient tolerance allows matching joints with greater length variations.

4. **Tail block processing fix (after last marker)**
   - After-last-marker region now runs full **Forward → Backward → Cumulative** flow.
   - Uses index-safe bounds and avoids relying on joint-number values as dataframe indices.

5. **Cumulative alignment recovery**
   - Added one-step target-shift probe in cumulative unmatched loop to recover local offset alignment.

6. **Marker matching validation fix (2026-03-04)**
   - **Problem**: Flawed OR condition allowed matching joints from completely different pipeline sections
     - Example: Target joint 390 → Master joint 5070 (6,364m cumulative length difference!)
   - **Root Cause**: Validation accepted matches if EITHER:
     - Cumulative length < 10m, OR
     - Next 3 markers aligned perfectly
   - **Fix**: Changed to AND condition requiring BOTH:
     - Cumulative length < 10m, AND
     - At least one of next 3 markers aligns
   - **Impact**: Prevents absurd misalignments across distant pipeline sections
   - **Results**: Match rate improved from 8% to 50%+ with correct joint alignment

7. **Head/Tail section cumulative matching fix (2026-03-04)**
   - **Problem**: Head section (before first marker) only used backward matching, missing 1-to-many aggregations
     - Example: Joint 20 from ILI-23 (1.582m) couldn't match to joints 20+30 from ILI-19 (1.788m)
     - Only tested 1-to-1: Joint 20 vs Joint 20 (1.160m) = 26.7% diff → rejected
   - **Root Cause**: Head section lacked cumulative matching pipeline
   - **Fix**: Added full matching pipeline to both head and tail sections:
     - **Head section**: Backward → Forward → Cumulative (reverse order)
     - **Tail section**: Forward → Backward → Cumulative (forward order)
   - **Key Insight**: Head section cumulative matching must process in REVERSE order to align with backward matching direction
     - Forward processing caused incorrect sequential matches (e.g., M[10]→T[20] blocked M[20]→T[20,30])
     - Reverse processing correctly matches from end to start (e.g., M[20]→T[20,30] then M[10]→remaining)
   - **Impact**: Joint 20 now matches correctly with 60% confidence (13% length difference within 30% tolerance)
   - **Results**: Increased cumulative splits from 1 to 2, reduced unmatched joints from 6 to 5

8. **Comprehensive head/tail cumulative matching enhancement (2026-03-04)**
   - **Problem**: Cumulative matching only processed gaps between forward/backward breaks, missing other unmatched joints
     - Example: Joint 10 and other early joints might be skipped if not in the specific gap region
     - Previous logic: Only match joints between `head_fix_break2` and `head_fix_break`
   - **Root Cause**: Limited scope of cumulative matching in head/tail sections
   - **Fix**: Comprehensive unmatched joint collection and processing:
     - Track ALL matched indices from forward and backward matching
     - Collect ALL joints in head/tail section
     - Filter to ONLY unmatched joints
     - Apply cumulative matching to ALL unmatched joints (not just gap region)
   - **Scientific Justification**:
     - Ensures complete coverage of all joints in head/tail sections
     - Maintains directional processing integrity (reverse for head, forward for tail)
     - Prevents duplicate matching using tracked indices
     - Uses same confidence thresholds (60%) and tolerance (30%)
   - **Impact**: Significantly improves match rate in head and tail sections
   - **Result**: Joints like #10 now get proper cumulative matching consideration

9. **Absolute Distance Matching (2026-03-05)**
   - **Change**: Replaced "Short Joint Matching" with "Absolute Distance Matching"
   - **Previous Behavior**: Matched only joints < 1m without length validation
   - **New Behavior**: Matches ANY unmatched joints where absolute length difference < 1.5m
   - **Benefits**:
     - More lenient for longer joints (e.g., 10m joint with 1.4m difference = 14% ratio)
     - Still validates length agreement (< 1.5m absolute difference)
     - Better handles measurement variations on longer joints
     - Uses same position-based strategy between matched joints
   - **Confidence**: All matches get Low confidence level
   - **Match Type**: "1-to-1 (absolute distance)"

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

**Date**: 2026-03-05
**Version**: 1.5

### Version History
- **v1.5** (2026-03-05): Replaced short joint matching with absolute distance matching
  - Changed from matching only joints < 1m to matching any joints with absolute difference < 1.5m
  - More lenient for longer joints while maintaining length validation
  - Better handles measurement variations across all joint lengths
  - All absolute distance matches produce Low confidence level
- **v1.4** (2026-03-04): Comprehensive head/tail cumulative matching enhancement
  - Enhanced cumulative matching to process ALL unmatched joints in head/tail sections
  - Track matched indices from forward/backward phases to prevent duplicates
  - Filter entire section to only unmatched joints before cumulative processing
  - Maintains directional integrity (reverse for head, forward for tail)
  - Significantly improves match rate for early and late joints (e.g., joint #10)
- **v1.3** (2026-03-04): Head/tail section cumulative matching with directional processing
  - Added full backward→forward→cumulative pipeline to head section (reverse order)
  - Added full forward→backward→cumulative pipeline to tail section (forward order)
  - Fixed joint 20 matching issue (1-to-2 aggregation now works in head section)
- **v1.2** (2026-03-04): Marker matching validation fix, tolerance increased to 30%
- **v1.1** (2026-02-19): Initial integrated matching implementation
