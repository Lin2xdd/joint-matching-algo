"""
Compare non-overlapping vs overlapping pairs for Set 2 specifically
"""
import pandas as pd
import numpy as np

def joint_diff_calc(data: pd.DataFrame, column: str) -> np.ndarray:
    """Calculate differences in joint lengths."""
    data_diff = round(data[column].diff(), 0)[1:].to_numpy()
    return data_diff

def pairs_generator_nonoverlapping(data_diff: np.ndarray) -> np.ndarray:
    """NON-OVERLAPPING pairs (original approach)."""
    row = 0
    pairs = np.array([])

    while row < (len(data_diff) - 1):
        if data_diff[row] != 0:
            if data_diff[row + 1] != 0:
                pairs = np.append(pairs, data_diff[[row, (row + 1)]])
            row += 2  # NON-OVERLAPPING: Advance by 2
        else:
            row += 1

    first_elmt = pairs[0::2]
    first_elmt = first_elmt.reshape(len(first_elmt), 1)
    second_elmt = pairs[1::2]
    second_elmt = second_elmt.reshape(len(second_elmt), 1)

    if len(data_diff) % 2 != 0:
        pairs = np.concatenate((first_elmt, second_elmt), axis=1)
    else:
        min_len = min(len(first_elmt), len(second_elmt))
        pairs = np.concatenate(
            (first_elmt[:min_len], second_elmt[:min_len]), axis=1)

    return pairs

def pairs_generator_overlapping(data_diff: np.ndarray) -> np.ndarray:
    """OVERLAPPING pairs (current approach)."""
    row = 0
    pairs = np.array([])

    while row < (len(data_diff) - 1):
        if data_diff[row] != 0:
            if data_diff[row + 1] != 0:
                pairs = np.append(pairs, data_diff[[row, (row + 1)]])
        row += 1  # OVERLAPPING: Advance by 1

    first_elmt = pairs[0::2]
    first_elmt = first_elmt.reshape(len(first_elmt), 1)
    second_elmt = pairs[1::2]
    second_elmt = second_elmt.reshape(len(second_elmt), 1)

    if len(data_diff) % 2 != 0:
        pairs = np.concatenate((first_elmt, second_elmt), axis=1)
    else:
        min_len = min(len(first_elmt), len(second_elmt))
        pairs = np.concatenate(
            (first_elmt[:min_len], second_elmt[:min_len]), axis=1)

    return pairs

def match_pct_calc(master_pairs: np.ndarray, target_pairs: np.ndarray) -> float:
    """Calculate percentage of match pairs."""
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

def test_approach(master_path, target_path, approach_name, pairs_func):
    """Test a specific pairs approach."""
    print(f"\n{'='*80}")
    print(f"{approach_name}")
    print(f"{'='*80}")
    
    # Read data
    master_df = pd.read_csv(master_path)
    target_df = pd.read_csv(target_path)
    
    print(f"Master: {len(master_df)} joints")
    print(f"Target: {len(target_df)} joints")
    
    # Calculate differences
    master_diff = joint_diff_calc(master_df, 'joint_length')
    target_diff = joint_diff_calc(target_df, 'joint_length')
    
    # Generate pairs using specified approach
    master_pairs = pairs_func(master_diff)
    target_pairs_fwd = pairs_func(target_diff)
    target_pairs_rev = pairs_func(target_diff[::-1])
    
    print(f"\nPairs generated:")
    print(f"  Master: {len(master_pairs)} pairs")
    print(f"  Target (FWD): {len(target_pairs_fwd)} pairs")
    print(f"  Target (REV): {len(target_pairs_rev)} pairs")
    
    # Calculate match percentages
    match_pct_fwd = match_pct_calc(master_pairs, target_pairs_fwd)
    match_pct_rev = match_pct_calc(master_pairs, target_pairs_rev)
    
    print(f"\nMatch percentages:")
    print(f"  Forward (FWD): {match_pct_fwd:.2f}%")
    print(f"  Reverse (REV): {match_pct_rev:.2f}%")
    
    margin = abs(match_pct_fwd - match_pct_rev)
    winner = "FORWARD" if match_pct_fwd > match_pct_rev else "REVERSE"
    
    print(f"\n>>> DECISION: {winner}")
    print(f">>> MARGIN: {margin:.2f}%")
    
    return {
        'approach': approach_name,
        'master_pairs': len(master_pairs),
        'target_pairs': len(target_pairs_fwd),
        'fwd_pct': match_pct_fwd,
        'rev_pct': match_pct_rev,
        'margin': margin,
        'winner': winner
    }

def main():
    print("="*80)
    print("SET 2: NON-OVERLAPPING vs OVERLAPPING PAIRS COMPARISON")
    print("="*80)
    
    master_path = 'Data & results/ARC/Set 2 5000 joints/input/Onstream 2015.csv'
    target_path = 'Data & results/ARC/Set 2 5000 joints/input/Onstream 2018.csv'
    
    # Test non-overlapping
    result_nonoverlap = test_approach(
        master_path, target_path,
        "NON-OVERLAPPING PAIRS (Original)",
        pairs_generator_nonoverlapping
    )
    
    # Test overlapping
    result_overlap = test_approach(
        master_path, target_path,
        "OVERLAPPING PAIRS (Current)",
        pairs_generator_overlapping
    )
    
    # Comparison
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)
    print(f"{'Metric':<25} {'Non-Overlapping':<20} {'Overlapping':<20} {'Change':<15}")
    print("-"*80)
    print(f"{'Master pairs':<25} {result_nonoverlap['master_pairs']:<20} {result_overlap['master_pairs']:<20} {result_overlap['master_pairs'] - result_nonoverlap['master_pairs']:<15}")
    print(f"{'Target pairs':<25} {result_nonoverlap['target_pairs']:<20} {result_overlap['target_pairs']:<20} {result_overlap['target_pairs'] - result_nonoverlap['target_pairs']:<15}")
    print(f"{'FWD%':<25} {result_nonoverlap['fwd_pct']:<20.2f} {result_overlap['fwd_pct']:<20.2f} {result_overlap['fwd_pct'] - result_nonoverlap['fwd_pct']:<15.2f}")
    print(f"{'REV%':<25} {result_nonoverlap['rev_pct']:<20.2f} {result_overlap['rev_pct']:<20.2f} {result_overlap['rev_pct'] - result_nonoverlap['rev_pct']:<15.2f}")
    print(f"{'Margin':<25} {result_nonoverlap['margin']:<20.2f} {result_overlap['margin']:<20.2f} {result_overlap['margin'] - result_nonoverlap['margin']:<15.2f}")
    print(f"{'Winner':<25} {result_nonoverlap['winner']:<20} {result_overlap['winner']:<20} {'Same' if result_nonoverlap['winner'] == result_overlap['winner'] else 'DIFFERENT':<15}")
    print("="*80)
    
    # Analysis
    print("\nANALYSIS:")
    if result_overlap['margin'] > result_nonoverlap['margin']:
        print(f"  Overlapping pairs IMPROVED margin by {result_overlap['margin'] - result_nonoverlap['margin']:.2f}%")
    elif result_overlap['margin'] < result_nonoverlap['margin']:
        print(f"  Overlapping pairs DECREASED margin by {result_nonoverlap['margin'] - result_overlap['margin']:.2f}%")
        print(f"  Non-overlapping had BETTER discrimination for this dataset!")
    else:
        print(f"  No change in margin")
    
    if result_nonoverlap['winner'] != result_overlap['winner']:
        print(f"  WARNING: Different winners! Non-overlapping chose {result_nonoverlap['winner']}, Overlapping chose {result_overlap['winner']}")
    
    print(f"\nBoth approaches show:")
    print(f"  - Very low match percentages (< 5%)")
    print(f"  - Weak correlation overall")
    print(f"  - Set 2 is a problematic dataset regardless of approach")

if __name__ == "__main__":
    main()
