"""
View joint matching results in tabular format.
Reads from joint_matching_results.json and displays as tables.
Can also export to CSV/Excel.
"""
import json
import pandas as pd
import sys

def load_results(filename='joint_matching_results.json'):
    """Load results from JSON file."""
    with open(filename, 'r') as f:
        return json.load(f)

def display_summary(results):
    """Display run summary as table."""
    print("\n" + "=" * 80)
    print("RUN SUMMARY")
    print("=" * 80)
    
    summary = results['run_summary']
    summary_df = pd.DataFrame([summary]).T
    summary_df.columns = ['Value']
    print(summary_df.to_string())
    print()

def display_matched_joints(results, limit=None):
    """Display matched joints as table."""
    print("\n" + "=" * 80)
    print("MATCHED JOINTS")
    print("=" * 80)
    
    matched = pd.DataFrame(results['matched_joints'])
    
    if limit:
        print(f"\nShowing first {limit} of {len(matched)} matched joints:\n")
        print(matched.head(limit).to_string(index=False))
    else:
        print(f"\nTotal: {len(matched)} matched joints\n")
        print(matched.to_string(index=False))
    print()

def display_unmatched_joints(results, limit=None):
    """Display unmatched joints as table."""
    print("\n" + "=" * 80)
    print("UNMATCHED JOINTS")
    print("=" * 80)
    
    unmatched = pd.DataFrame(results['unmatched_joints'])
    
    if limit:
        print(f"\nShowing first {limit} of {len(unmatched)} unmatched joints:\n")
        print(unmatched.head(limit).to_string(index=False))
    else:
        print(f"\nTotal: {len(unmatched)} unmatched joints\n")
        print(unmatched.to_string(index=False))
    print()

def display_questionable_joints(results):
    """Display questionable joints as table."""
    if results['questionable_joints']:
        print("\n" + "=" * 80)
        print("QUESTIONABLE MATCHES")
        print("=" * 80)
        
        questionable = pd.DataFrame(results['questionable_joints'])
        print(f"\nTotal: {len(questionable)} questionable matches\n")
        print(questionable.to_string(index=False))
        print()
    else:
        print("\n[No questionable matches found]")

def export_to_csv(results, prefix='joint_matching'):
    """Export results to CSV files."""
    # Export matched joints
    matched_df = pd.DataFrame(results['matched_joints'])
    matched_file = f"{prefix}_matched.csv"
    matched_df.to_csv(matched_file, index=False)
    print(f"[OK] Matched joints exported to: {matched_file}")
    
    # Export unmatched joints
    unmatched_df = pd.DataFrame(results['unmatched_joints'])
    unmatched_file = f"{prefix}_unmatched.csv"
    unmatched_df.to_csv(unmatched_file, index=False)
    print(f"[OK] Unmatched joints exported to: {unmatched_file}")
    
    # Export summary
    summary_df = pd.DataFrame([results['run_summary']]).T
    summary_df.columns = ['Value']
    summary_file = f"{prefix}_summary.csv"
    summary_df.to_csv(summary_file)
    print(f"[OK] Summary exported to: {summary_file}")
    
    if results['questionable_joints']:
        questionable_df = pd.DataFrame(results['questionable_joints'])
        questionable_file = f"{prefix}_questionable.csv"
        questionable_df.to_csv(questionable_file, index=False)
        print(f"[OK] Questionable matches exported to: {questionable_file}")

def export_to_excel(results, filename='joint_matching_results.xlsx'):
    """Export all results to a single Excel file with multiple sheets."""
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_df = pd.DataFrame([results['run_summary']]).T
            summary_df.columns = ['Value']
            summary_df.to_excel(writer, sheet_name='Summary')
            
            # Matched joints sheet
            matched_df = pd.DataFrame(results['matched_joints'])
            matched_df.to_excel(writer, sheet_name='Matched Joints', index=False)
            
            # Unmatched joints sheet
            unmatched_df = pd.DataFrame(results['unmatched_joints'])
            unmatched_df.to_excel(writer, sheet_name='Unmatched Joints', index=False)
            
            # Questionable matches sheet (if any)
            if results['questionable_joints']:
                questionable_df = pd.DataFrame(results['questionable_joints'])
                questionable_df.to_excel(writer, sheet_name='Questionable', index=False)
        
        print(f"[OK] All results exported to Excel: {filename}")
    except ImportError:
        print("[ERROR] openpyxl not installed. Install with: pip install openpyxl")
        print("Falling back to CSV export...")
        export_to_csv(results)

def main():
    """Main function."""
    print("=" * 80)
    print("JOINT MATCHING RESULTS VIEWER")
    print("=" * 80)
    
    # Load results
    try:
        results = load_results()
        print("[OK] Loaded results from joint_matching_results.json")
    except FileNotFoundError:
        print("[ERROR] joint_matching_results.json not found. Run joint matching first.")
        sys.exit(1)
    
    # Display all results
    display_summary(results)
    display_matched_joints(results, limit=20)  # Show first 20
    display_unmatched_joints(results, limit=20)  # Show first 20
    display_questionable_joints(results)
    
    # Ask user what to do
    print("\n" + "=" * 80)
    print("EXPORT OPTIONS")
    print("=" * 80)
    print("\n1. Export to CSV files")
    print("2. Export to Excel file")
    print("3. Show ALL matched joints (no limit)")
    print("4. Show ALL unmatched joints (no limit)")
    print("5. Exit")
    
    try:
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            export_to_csv(results)
        elif choice == '2':
            export_to_excel(results)
        elif choice == '3':
            display_matched_joints(results, limit=None)
        elif choice == '4':
            display_unmatched_joints(results, limit=None)
        elif choice == '5':
            print("\nGoodbye!")
        else:
            print("\nInvalid choice. Exiting.")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting.")
    except EOFError:
        print("\n\nNo input detected. Exiting.")

if __name__ == "__main__":
    main()
