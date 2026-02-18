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
- Uses configurable tolerance (default 10%)
- Calculates confidence scores
- Greedy matching strategy

## Key Parameters

```python
USE_CUMULATIVE = True              # Enable cumulative matching
CUMULATIVE_TOLERANCE = 0.10        # 10% length tolerance
CUMULATIVE_MAX_AGGREGATE = 5       # Max joints to combine
CUMULATIVE_MIN_CONFIDENCE = 0.60   # Minimum confidence
```

## Output Columns (Matched Joints)

- Master/Target ILI ID
- Master/Target Joint Number
- Master/Target Length (m)
- **Length Difference (m)**: Absolute difference
- **Length Ratio**: Difference / Average length
- **Confidence Score**: 0.60 to 1.00
- **Match Source**: "Original Algorithm" or "Cumulative Matching"
- **Match Type**: "1-to-1", "1-to-2", "2-to-1", etc.

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

**Date**: 2026-02-13  
**Version**: 1.0
