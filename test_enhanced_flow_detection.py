"""
Test Enhanced Flow Direction Detection with Cumulative Distance Validation

Compare pattern-only vs pattern+distance approaches
"""
import pandas as pd
import numpy as np
import sys
sys.path.append('Scripts')
from joint_matching import pairs_generator

def joint_diff_calc(data: pd.DataFrame, column: str, decimals: int = 0) -> np.ndarray:
    """Calculate differences in joint lengths with specified precision."""
    data_diff = round(data[column].diff(), decimals)[1:].to_numpy()
    return data_diff

def match_pct_calc_original(master_pairs: np.ndarray, target_pairs: np.ndarray) -> float:
    """Original: Pattern matching only (no spatial validation)."""
    num_target_pairs = target_pairs.shape[0]
    match = 0
    ctrow = -1

    for mrow, mpair in enumerate(master_pairs):
        for trow in range((ctrow + 1), num_target_pairs):
            if (mpair == target_pairs[trow]).all():
                match += 1
                ctrow = trow
                break

    if num_target_pairs == 0:
        return 0.0

    match_pct = (match / num_target_pairs) * 100
    return match_pct


def match_pct_calc_enhanced(master_pairs: np.ndarray, target_pairs: np.ndarray,
                            master_df: pd.DataFrame, target_df: pd.DataFrame,
                            tolerance_pct: float = 0.05) -> tuple:
    """
    Enhanced: Pattern matching WITH cumulative distance validation.
    
    Only counts a match if:
    1. Pattern matches (e.g., (+2, -1) == (+2, -1))
    2. Target RELATIVE distance is within tolerance_pct of master RELATIVE distance
       (relative = distance from pipeline start, normalized to 0)
    
    Args:
        master_pairs: Master joint length difference pairs
        target_pairs: Target joint length difference pairs
        master_df: Master dataframe with distance column
        target_df: Target dataframe with distance column
        tolerance_pct: Percentage tolerance (default 0.05 = 5%)
    
    Returns: (match_percentage, spatial_valid_count, pattern_only_count)
    """
    num_target_pairs = target_pairs.shape[0]
    
    # Get distance column name (handle 'distance ' with trailing space)
    dist_col = 'distance ' if 'distance ' in master_df.columns else 'distance'
    
    # Get starting distances (to calculate relative positions)
    master_start_dist = master_df.iloc[0][dist_col]
    target_start_dist = target_df.iloc[0][dist_col]
    
    # Check for NaN values - fall back to pattern-only if distance data is bad
    if pd.isna(master_start_dist) or pd.isna(target_start_dist):
        return match_pct_calc(master_pairs, target_pairs), 0, 0
    
    spatial_valid_matches = 0  # Matches that pass both pattern AND spatial check
    pattern_only_matches = 0   # Matches that pass pattern only
    ctrow = -1

    for mrow, mpair in enumerate(master_pairs):
        for trow in range((ctrow + 1), num_target_pairs):
            if (mpair == target_pairs[trow]).all():
                # Pattern matches
                pattern_only_matches += 1
                
                # Now check spatial consistency using RELATIVE distance
                try:
                    # Calculate relative distances (distance from start)
                    master_abs_dist = master_df.iloc[mrow][dist_col]
                    target_abs_dist = target_df.iloc[trow][dist_col]
                    
                    master_rel_dist = master_abs_dist - master_start_dist
                    target_rel_dist = target_abs_dist - target_start_dist
                    
                    # Calculate acceptable range: master_relative ± tolerance%
                    lower_bound = master_rel_dist * (1.0 - tolerance_pct)
                    upper_bound = master_rel_dist * (1.0 + tolerance_pct)
                    
                    if lower_bound <= target_rel_dist <= upper_bound:
                        # Both pattern AND spatial match (within tolerance%)
                        spatial_valid_matches += 1
                        ctrow = trow
                        break
                    else:
                        # Pattern matches but spatial mismatch - continue searching
                        continue
                        
                except (KeyError, ValueError, TypeError):
                    # Distance data unavailable - count as valid (fallback)
                    spatial_valid_matches += 1
                    ctrow = trow
                    break

    if num_target_pairs == 0:
        return 0.0, 0, 0

    match_pct = (spatial_valid_matches / num_target_pairs) * 100
    return match_pct, spatial_valid_matches, pattern_only_matches


def test_dataset(master_path, target_path, dataset_name, decimals=0):
    """Test both approaches on a dataset."""
    print(f"\n{'='*80}")
    print(f"{dataset_name} - PRECISION: {decimals} decimal place(s)")
    print(f"{'='*80}")
    
    # Load data
    master_df = pd.read_csv(master_path)
    target_df = pd.read_csv(target_path)
    
    print(f"Master: {len(master_df)} joints")
    print(f"Target: {len(target_df)} joints")
    
    # Calculate differences and pairs with specified precision
    master_diff = joint_diff_calc(master_df, 'joint_length', decimals)
    target_diff = joint_diff_calc(target_df, 'joint_length', decimals)
    
    master_pairs = pairs_generator(master_diff)
    target_pairs_fwd = pairs_generator(target_diff)
    target_pairs_rev = pairs_generator(target_diff[::-1])
    
    # Count unique patterns for diversity analysis
    master_unique = len(set(map(tuple, master_pairs)))
    target_unique = len(set(map(tuple, target_pairs_fwd)))
    
    print(f"\nPairs generated:")
    print(f"  Master: {len(master_pairs)} pairs, Unique: {master_unique} ({100*master_unique/len(master_pairs):.1f}%)")
    print(f"  Target: {len(target_pairs_fwd)} pairs, Unique: {target_unique} ({100*target_unique/len(target_pairs_fwd):.1f}%)")
    
    # ========================================================================
    # ORIGINAL APPROACH (Pattern Only)
    # ========================================================================
    print(f"\n{'-'*80}")
    print("ORIGINAL: Pattern Matching Only")
    print(f"{'-'*80}")
    
    fwd_orig = match_pct_calc_original(master_pairs, target_pairs_fwd)
    rev_orig = match_pct_calc_original(master_pairs, target_pairs_rev)
    margin_orig = abs(fwd_orig - rev_orig)
    decision_orig = "FORWARD" if fwd_orig > rev_orig else "REVERSE"
    
    print(f"Forward: {fwd_orig:.2f}%")
    print(f"Reverse: {rev_orig:.2f}%")
    print(f"Margin: {margin_orig:.2f}%")
    print(f"Decision: {decision_orig}")
    
    # ========================================================================
    # ENHANCED APPROACH (Pattern + Cumulative Distance) - ONLY 5%
    # ========================================================================
    print(f"\n{'-'*80}")
    print("ENHANCED: Pattern + Distance (±5% tolerance)")
    print(f"{'-'*80}")
    
    # Only test 5% tolerance
    tolerance = 0.05
    
    # Forward
    fwd_enh, fwd_spatial, fwd_pattern = match_pct_calc_enhanced(
        master_pairs, target_pairs_fwd, master_df, target_df, tolerance
    )
    
    # Reverse (need to reverse target_df for distance lookups)
    target_df_rev = target_df.iloc[::-1].reset_index(drop=True)
    rev_enh, rev_spatial, rev_pattern = match_pct_calc_enhanced(
        master_pairs, target_pairs_rev, master_df, target_df_rev, tolerance
    )
    
    margin_enh = abs(fwd_enh - rev_enh)
    decision_enh = "FORWARD" if fwd_enh > rev_enh else "REVERSE"
    
    print(f"Forward: {fwd_enh:.1f}% ({fwd_spatial} spatial valid out of {fwd_pattern} pattern matches)")
    print(f"Reverse: {rev_enh:.1f}% ({rev_spatial} spatial valid out of {rev_pattern} pattern matches)")
    print(f"Margin: {margin_enh:.1f}%")
    print(f"Decision: {decision_enh}")
    
    # Compare with original
    margin_improvement = margin_enh - margin_orig
    if margin_improvement > 0:
        print(f">>> IMPROVED by {margin_improvement:.1f}%")
    
    # No separate summary needed since we only test one tolerance
    
    return {
        'dataset': dataset_name,
        'orig_margin': margin_orig,
        'enh_margin': margin_enh,
        'improvement': margin_enh - margin_orig,
        'orig_decision': decision_orig,
        'enh_decision': decision_enh,
        'same': decision_orig == decision_enh
    }


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    print("="*80)
    print("ENHANCED FLOW DETECTION TEST - All Datasets with Distance Column")
    print("="*80)
    print("Testing: 0 decimals + ±5% distance tolerance")
    
    all_results = []
    decimals = 0  # Keep 0 decimals (faster)
    
    # Test all datasets that have distance column
    datasets = [
        {
            'master': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2019 - 16in 4-25 to 10-7.csv',
            'target': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2022 - 16in 4-25 to 10-7.csv',
            'name': 'SET 1: 2022 vs 2019'
        },
        {
            'master': 'Data & results/ARC/Set 2 5000 joints/input/Onstream 2015.csv',
            'target': 'Data & results/ARC/Set 2 5000 joints/input/Onstream 2018.csv',
            'name': 'SET 2: 2018 vs 2015'
        },
        {
            'master': 'Data & results/ARC/Set 3 100 joints/INPUT/UPP 2018 60340 3 .csv',
            'target': 'Data & results/ARC/Set 3 100 joints/INPUT/UPP 2022 60340 3.csv',
            'name': 'SET 3: 2022 vs 2018'
        },
        {
            'master': 'Data & results/ARC/Set 4 1300 joints/Inputs/Onstream 2020 59158 3.csv',
            'target': 'Data & results/ARC/Set 4 1300 joints/Inputs/Onstream 2022 59158 3.csv',
            'name': 'SET 4: 2022 vs 2020'
        }
    ]
    
    for dataset in datasets:
        try:
            result = test_dataset(
                dataset['master'],
                dataset['target'],
                dataset['name'],
                decimals
            )
            all_results.append(result)
        except Exception as e:
            print(f"\nERROR testing {dataset['name']}: {e}")
            print("Skipping this dataset...\n")
    
    # Overall summary
    print(f"\n{'='*80}")
    print("SUMMARY: Enhanced Flow Detection Results")
    print(f"{'='*80}")
    
    if not all_results:
        print("No results to display")
        return
    
    print(f"\n{'Dataset':<25} {'Pattern Only':<15} {'With Distance':<15} {'Improvement':<15}")
    print("-"*80)
    
    total_improvement = 0
    for result in all_results:
        improvement = result['enh_margin'] - result['orig_margin']
        improvement_str = f"+{improvement:.1f}%" if improvement >= 0 else f"{improvement:.1f}%"
        print(f"{result['dataset']:<25} {result['orig_margin']:<15.1f} {result['enh_margin']:<15.1f} {improvement_str:<15}")
        total_improvement += improvement
    
    print("-"*80)
    avg_improvement = total_improvement / len(all_results)
    print(f"Average improvement: {avg_improvement:.1f}%")
    
    # Check if all decisions are same
    all_same = all(r['same'] for r in all_results)
    if all_same:
        print("\n[OK] All datasets: Same decision with and without distance validation")
    else:
        print("\n[WARNING] Some datasets changed decisions!")
        for r in all_results:
            if not r['same']:
                print(f"  - {r['dataset']}: {r['orig_decision']} -> {r['enh_decision']}")
    
    # Recommendation
    print(f"\nRECOMMENDATION:")
    if avg_improvement > 5:
        print(f"  IMPLEMENT distance validation - Average {avg_improvement:.1f}% margin improvement")
        print(f"  Significantly improves flow direction detection confidence")
    elif avg_improvement > 0:
        print(f"  CONSIDER distance validation - Small improvement ({avg_improvement:.1f}%)")
    else:
        print(f"  Distance validation may not be necessary for these datasets")

if __name__ == "__main__":
    main()
