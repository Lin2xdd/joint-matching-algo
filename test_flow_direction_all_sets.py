"""
Test flow direction detection on all ARC datasets (Sets 1-4)
"""
import pandas as pd
import numpy as np
from Scripts.joint_matching import joint_diff_calc, pairs_generator, match_pct_calc

def test_flow_direction(master_path: str, target_path: str, set_name: str):
    """Test flow direction detection for a dataset pair."""
    print(f"\n{'='*80}")
    print(f"{set_name}")
    print(f"{'='*80}")
    print(f"Master: {master_path}")
    print(f"Target: {target_path}")
    
    try:
        # Read data
        master_df = pd.read_csv(master_path)
        target_df = pd.read_csv(target_path)
        
        print(f"\nMaster: {len(master_df)} joints")
        print(f"Target: {len(target_df)} joints")
        
        # Calculate joint differences
        master_diff = joint_diff_calc(master_df, 'joint_length')
        target_diff = joint_diff_calc(target_df, 'joint_length')
        
        # Generate pairs
        master_pairs = pairs_generator(master_diff)
        target_pairs_fwd = pairs_generator(target_diff)
        target_pairs_rev = pairs_generator(target_diff[::-1])
        
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
        
        # Determine direction
        if match_pct_fwd > match_pct_rev:
            direction = "FORWARD"
            margin = match_pct_fwd - match_pct_rev
        elif match_pct_rev > match_pct_fwd:
            direction = "REVERSE"
            margin = match_pct_rev - match_pct_fwd
        else:
            direction = "FORWARD (tie, default)"
            margin = 0.0
        
        print(f"\n>>> DECISION: {direction} (margin: {margin:.2f}%)")
        
        # Show geometric evidence using distance column
        # Column might be 'distance ' (with space) or 'distance'
        dist_col = 'distance ' if 'distance ' in master_df.columns else 'distance'
        
        master_start_dist = master_df.iloc[0][dist_col]
        master_end_dist = master_df.iloc[-1][dist_col]
        target_start_dist = target_df.iloc[0][dist_col]
        target_end_dist = target_df.iloc[-1][dist_col]
        
        print(f"\nGeometric evidence:")
        print(f"  Master: {master_start_dist:.1f}m -> {master_end_dist:.1f}m")
        print(f"  Target: {target_start_dist:.1f}m -> {target_end_dist:.1f}m")
        
        # Determine expected direction based on geometry
        master_ascending = master_end_dist > master_start_dist
        target_ascending = target_end_dist > target_start_dist
        
        if master_ascending == target_ascending:
            expected = "FORWARD"
        else:
            expected = "REVERSE"
        
        print(f"  Expected direction (geometry): {expected}")
        
        # Check if detection matches geometry
        matches_geometry = (direction.startswith(expected))
        status = "[OK] CORRECT" if matches_geometry else "[X] INCORRECT"
        print(f"\n{status}: Algorithm detection {'matches' if matches_geometry else 'does NOT match'} geometric evidence")
        
        return {
            'set': set_name,
            'direction': direction,
            'fwd_pct': match_pct_fwd,
            'rev_pct': match_pct_rev,
            'margin': margin,
            'expected': expected,
            'correct': matches_geometry
        }
        
    except Exception as e:
        print(f"\nERROR: {e}")
        return None

def main():
    """Test all dataset pairs."""
    print("="*80)
    print("FLOW DIRECTION DETECTION TEST - ALL DATASETS")
    print("="*80)
    
    test_cases = [
        # Set 1: 500 joints (test multiple combinations)
        {
            'master': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2019 - 16in 4-25 to 10-7.csv',
            'target': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2022 - 16in 4-25 to 10-7.csv',
            'name': 'SET 1a: 2022 vs 2019'
        },
        {
            'master': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2019 - 16in 4-25 to 10-7.csv',
            'target': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2023 - 16in 4-25 to 10-7.csv',
            'name': 'SET 1b: 2023 vs 2019'
        },
        {
            'master': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2022 - 16in 4-25 to 10-7.csv',
            'target': 'Data & results/ARC/Set 1 500 joints/input/Onstream 2023 - 16in 4-25 to 10-7.csv',
            'name': 'SET 1c: 2023 vs 2022'
        },
        
        # Set 2: 5000 joints
        {
            'master': 'Data & results/ARC/Set 2 5000 joints/input/Onstream 2015.csv',
            'target': 'Data & results/ARC/Set 2 5000 joints/input/Onstream 2018.csv',
            'name': 'SET 2: 2018 vs 2015'
        },
        
        # Set 3: 100 joints
        {
            'master': 'Data & results/ARC/Set 3 100 joints/INPUT/UPP 2018 60340 3 .csv',
            'target': 'Data & results/ARC/Set 3 100 joints/INPUT/UPP 2022 60340 3.csv',
            'name': 'SET 3: 2022 vs 2018'
        },
        
        # Set 4: 1300 joints
        {
            'master': 'Data & results/ARC/Set 4 1300 joints/Inputs/Onstream 2020 59158 3.csv',
            'target': 'Data & results/ARC/Set 4 1300 joints/Inputs/Onstream 2022 59158 3.csv',
            'name': 'SET 4: 2022 vs 2020'
        }
    ]
    
    results = []
    for test_case in test_cases:
        result = test_flow_direction(
            test_case['master'],
            test_case['target'],
            test_case['name']
        )
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if not results:
        print("No results to display - all tests failed")
        print("="*80)
        return
    
    print(f"{'Dataset':<20} {'Direction':<20} {'FWD%':<10} {'REV%':<10} {'Margin':<10} {'Status':<10}")
    print("-"*80)
    
    correct_count = 0
    for r in results:
        status = "[OK]" if r['correct'] else "[WRONG]"
        if r['correct']:
            correct_count += 1
        print(f"{r['set']:<20} {r['direction']:<20} {r['fwd_pct']:<10.2f} {r['rev_pct']:<10.2f} {r['margin']:<10.2f} {status:<10}")
    
    print("-"*80)
    print(f"Correct: {correct_count}/{len(results)} ({100*correct_count/len(results):.1f}%)")
    print("="*80)

if __name__ == "__main__":
    main()
