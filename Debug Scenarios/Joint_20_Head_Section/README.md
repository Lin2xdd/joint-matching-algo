# Debug Scenario: Joint 20 Head Section Matching

## Issue
Joint 20 from ILI-23 (1.582m) couldn't match to joints 20+30 from ILI-19 (1.788m total). Only 1-to-1 matching was tested: Joint 20 vs Joint 20 (1.160m) = 26.7% diff → rejected.

## Root Cause
Head section (before first marker) only used `backward_match_check`, which doesn't support 1-to-many aggregations. The cumulative matching step was missing from the head section processing.

## Solution (v1.3)
Added full matching pipeline to head section:
1. **Backward matching** (from first marker toward start)
2. **Forward matching** (fill gaps from start)
3. **Cumulative matching in reverse order** (align with backward direction)

Key insight: Head section cumulative matching must process in **REVERSE order** to align with backward matching direction.

## Impact
- Joint 20 now matches correctly with 60% confidence
- Length difference: 13% (within 30% tolerance)
- Increased cumulative splits from 1 to 2
- Reduced unmatched joints from 6 to 5

## Files
- `debug_joint_20_matching.py` - Investigation script
- `diagnose_joint_20_head_section.py` - Detailed diagnosis

## Status
✅ RESOLVED - Full matching pipeline implemented in head section (v1.3)
