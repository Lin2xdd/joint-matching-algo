# Diagnostic Scripts for Post-Processing Merge

This folder contains diagnostic and debugging scripts used during development and troubleshooting of the post-processing merge algorithm.

## Scripts

### Core Debugging Tools

- **`debug_merge_logic.py`**: Tool to evaluate merge quality calculations and understand why specific merges succeed or fail
- **`test_why_2789_merges.py`**: Investigation into why joint 2789 merges in certain scenarios

### Test Cases for Issue Resolution

- **`test_postprocessing_merge.py`**: Primary unit test suite for post-processing merge functionality
- **`test_joint_2800_issue.py`**: Test case for joint 2800 matching issue (1-to-2 scenario)
- **`test_sequential_merge_issue.py`**: Test sequential merge operations when starting from 1-to-1 matches
- **`test_real_2810_scenario.py`**: Real-world test case for joint 2810 merge failure
- **`test_debug_merge_detailed.py`**: Detailed debugging of merge operations with verbose logging

## Historical Context

These scripts were created to diagnose and fix the following issues:

1. **T2810 Merge Rejection**: Joint 2810 from ILI-15 was not merging into existing match M2800 → T2790,T2800
   - Root cause: Quality check was rejecting Low confidence tier merges
   - Solution: Bypass quality check for Low tier (position-based) merges

2. **Match Index Synchronization**: Sequential merges failed because match_index wasn't being updated
   - Solution: Added `update_match_index_entry()` function

3. **Three-Tier Confidence System**: Need to support High/Medium/Low confidence tiers
   - High: >= 60% confidence
   - Medium: < 60% but within 30% tolerance
   - Low: Absolute distance < 1.5m (position-based)

## Usage

**Primary Test Suite**: `test_postprocessing_merge.py` has been updated with the correct imports and can be run directly:

```bash
python Diagnostics/test_postprocessing_merge.py
```

**Legacy Diagnostic Scripts**: The older diagnostic scripts import from the old `short_joint_merge.py` module. To run them after the rename, update imports:

```python
# Update imports from:
from short_joint_merge import merge_unmatched_joints_with_neighbors

# To:
from postprocessing_merge import postprocessing_merge
```

## Archive Date

Archived on: 2026-03-05
Reason: Post-processing merge algorithm finalized and renamed

## Related Files

- **Production script**: `Scripts/postprocessing_merge.py` (formerly `Scripts/short_joint_merge.py`)
- **Main integration**: `Scripts/integrated_joint_matching.py`
- **Primary unit tests**: `Diagnostics/test_postprocessing_merge.py` (formerly `test_short_joint_merge.py`)
