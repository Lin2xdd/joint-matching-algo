"""
Core joint matching algorithm extracted from JointMatching.py.
Refactored to return data structures instead of writing files.
"""
import uuid
import numpy as np
import pandas as pd
from sqlalchemy import Engine, text
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


# ========== Utility Functions (from JointMatching.py) ==========

def joint_diff_calc(data: pd.DataFrame, column: str) -> np.ndarray:
    """Calculate differences in joint lengths in a single dataset."""
    data_diff = round(data[column].diff(), 0)[1:].to_numpy()
    return data_diff


def pairs_generator(data_diff: np.ndarray) -> np.ndarray:
    """Determine pairs in a single dataset."""
    row = 0
    pairs = np.array([])

    while row < (len(data_diff) - 1):
        if data_diff[row] != 0:
            if data_diff[row + 1] != 0:
                pairs = np.append(pairs, data_diff[[row, (row + 1)]])
            row += 2
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


def match_pct_calc(master_pairs: np.ndarray, target_pairs: np.ndarray) -> float:
    """Calculate percentage of match pairs between master and target."""
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


def forward_match_check(fix: pd.DataFrame, move: pd.DataFrame,
                        init_fix: int, init_move: int,
                        end_fix: int, end_move: int,
                        threshold: float) -> Tuple[pd.DataFrame, int, int]:
    """Forward match check function."""
    matched_pairs = pd.DataFrame(columns=['FIX_ID', 'MOVE_ID', 'STATUS'])
    min_move = int(min(end_move - init_move, end_fix - init_fix))
    fix_break_loc = None
    move_break_loc = None

    for i in range(min_move + 1):
        pair1 = abs(fix.iloc[init_fix + i]['joint_length'] -
                    move.iloc[init_move + i]['joint_length'])
        try:
            pair2 = abs(fix.iloc[init_fix + i + 1]['joint_length'] -
                        move.iloc[init_move + i + 1]['joint_length'])
        except:
            pair2 = 0
        try:
            pair3 = abs(fix.iloc[init_fix + i + 2]['joint_length'] -
                        move.iloc[init_move + i + 2]['joint_length'])
        except:
            pair3 = 0

        if pair1 < threshold:
            matched_points = pd.DataFrame(
                np.array([i + init_fix, i + init_move, 2]).reshape(1, 3),
                columns=matched_pairs.columns
            )
            matched_pairs = pd.concat(
                [matched_pairs, matched_points], ignore_index=True)
        elif (pair1 >= threshold) & (pair2 < threshold) & (pair3 < threshold):
            matched_points = pd.DataFrame(
                np.array([i + init_fix, i + init_move, 3]).reshape(1, 3),
                columns=matched_pairs.columns
            )
            matched_pairs = pd.concat(
                [matched_pairs, matched_points], ignore_index=True)
        else:
            fix_break_loc = i + init_fix
            move_break_loc = i + init_move
            break

    return matched_pairs, fix_break_loc, move_break_loc


def backward_match_check(fix: pd.DataFrame, move: pd.DataFrame,
                         init_fix: int, init_move: int,
                         end_fix: int, end_move: int,
                         threshold: float) -> Tuple[pd.DataFrame, int, int]:
    """Backward match check function."""
    matched_pairs = pd.DataFrame(columns=['FIX_ID', 'MOVE_ID', 'STATUS'])
    min_move = int(min(end_move - init_move, end_fix - init_fix))
    fix_break_loc = None
    move_break_loc = None

    for i in range(1, min_move + 1):
        pair1 = abs(fix.iloc[end_fix - i]['joint_length'] -
                    move.iloc[end_move - i]['joint_length'])
        pair2 = abs(fix.iloc[end_fix - i - 1]['joint_length'] -
                    move.iloc[end_move - i - 1]['joint_length'])
        pair3 = abs(fix.iloc[end_fix - i - 2]['joint_length'] -
                    move.iloc[end_move - i - 2]['joint_length'])

        if pair1 < threshold:
            matched_points = pd.DataFrame(
                np.array([end_fix - i, end_move - i, 2]).reshape(1, 3),
                columns=matched_pairs.columns
            )
            matched_pairs = pd.concat(
                [matched_pairs, matched_points], ignore_index=True)
        elif (pair1 >= threshold) & (pair2 < threshold) & (pair3 < threshold):
            matched_points = pd.DataFrame(
                np.array([end_fix - i, end_move - i, 3]).reshape(1, 3),
                columns=matched_pairs.columns
            )
            matched_pairs = pd.concat(
                [matched_pairs, matched_points], ignore_index=True)
        else:
            fix_break_loc = end_fix - i
            move_break_loc = end_move - i
            break

    return matched_pairs, fix_break_loc, move_break_loc


def unchunk_dataframe(unmatched_chunks: pd.DataFrame, fix_df: pd.DataFrame, move_df: pd.DataFrame) -> pd.DataFrame:
    """
    Expand master and target joint ranges into individual joints.
    
    Removes duplicates that may occur when chunks overlap or joints appear
    in multiple unmatched ranges.
    """
    master_unmatched_joints = pd.DataFrame()
    target_unmatched_joints = pd.DataFrame()

    for _, row in unmatched_chunks.iterrows():
        # Safely get values using .get() method with default np.nan
        master_start = int(row.get('Master_joint_start', np.nan)) if not pd.isna(
            row.get('Master_joint_start', np.nan)) else np.nan
        master_end = int(row.get('Master_joint_end', np.nan)) if not pd.isna(
            row.get('Master_joint_end', np.nan)) else np.nan
        target_start = int(row.get('Target_joint_start', np.nan)) if not pd.isna(
            row.get('Target_joint_start', np.nan)) else np.nan
        target_end = int(row.get('Target_joint_end', np.nan)) if not pd.isna(
            row.get('Target_joint_end', np.nan)) else np.nan

        # Process master joints if start is valid
        if not pd.isna(master_start):
            if pd.isna(master_end):
                master_batch = fix_df.loc[(
                    fix_df['joint_number'].astype(int) >= master_start)]
            else:
                master_batch = fix_df.loc[
                    ((fix_df['joint_number'].astype(int) >= master_start) &
                     (fix_df['joint_number'].astype(int) <= master_end))
                ]
            master_unmatched_joints = pd.concat(
                [master_unmatched_joints, master_batch], ignore_index=True)

        # Process target joints if start is valid
        if not pd.isna(target_start):
            if pd.isna(target_end):
                target_batch = move_df.loc[(
                    move_df['joint_number'].astype(int) >= target_start)]
            else:
                target_batch = move_df.loc[
                    ((move_df['joint_number'].astype(int) >= target_start) &
                     (move_df['joint_number'].astype(int) <= target_end))
                ]
            target_unmatched_joints = pd.concat(
                [target_unmatched_joints, target_batch], ignore_index=True)

    # Remove duplicates - joints may appear in multiple unmatched chunk ranges
    # This can happen due to overlapping ranges or algorithm edge cases
    master_unmatched_joints = master_unmatched_joints.drop_duplicates(
        subset=['joint_number'], keep='first')
    target_unmatched_joints = target_unmatched_joints.drop_duplicates(
        subset=['joint_number'], keep='first')

    all_dfs = []
    for _, row in master_unmatched_joints.iterrows():
        all_dfs.append(
            {'Master_joint_number': row['joint_number'], 'Target_joint_number': ''})
    for _, row in target_unmatched_joints.iterrows():
        all_dfs.append({'Master_joint_number': '',
                       'Target_joint_number': row['joint_number']})

    return pd.DataFrame(all_dfs)


def clean_column_none_to_null(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Convert NaN values to None (JSON null) in specified column."""
    if column in df.columns:
        df[column] = df[column].apply(
            lambda x: None if pd.isna(x) or x is None else x)
    return df


def smart_column_filter(df, priority_cols=None, exclude_cols=None):
    """
    Smart column filtering that preserves all data while organizing output.

    Args:
        df: DataFrame to filter
        priority_cols: List of columns to appear first (in order)
        exclude_cols: List of columns to exclude from output

    Returns:
        DataFrame with columns reordered but all data preserved
    """
    if priority_cols is None:
        priority_cols = []
    if exclude_cols is None:
        exclude_cols = []

    # Get existing priority columns
    existing_priority = [col for col in priority_cols if col in df.columns]

    # Get other columns (not in priority, not excluded)
    other_cols = [col for col in df.columns
                  if col not in priority_cols and col not in exclude_cols]

    # Return with priority columns first, then others
    return df[existing_priority + other_cols]


def safe_rename_columns(df, old_cols, new_cols, prefix=""):
    """
    Safely rename columns, only renaming those that exist in the dataframe.
    This prevents KeyError when config lists contain columns not in the data.

    Args:
        df: DataFrame to rename columns for
        old_cols: List of current column names
        new_cols: List of new column names
        prefix: Optional prefix for new column names

    Returns:
        DataFrame with safely renamed columns
    """
    rename_dict = {}
    for old_col, new_col in zip(old_cols, new_cols):
        if old_col in df.columns:
            rename_dict[old_col] = f"{prefix}{new_col}" if prefix else new_col
    return df.rename(columns=rename_dict)


# ========== Main Joint Matching Logic ==========

def execute_joint_matching(engine: Engine, master_guid: str, target_guids: List[str]) -> Dict:
    """
    Execute joint matching algorithm between master and target inspections.

    Args:
        engine: SQLAlchemy engine for database connection
        master_guid: Master inspection GUID
        target_guids: List of target inspection GUIDs

    Returns:
        Dict with keys: run_summary, matched_joints, unmatched_joints, questionable_joints
    """
    logger.info(
        f"Starting joint matching: master={master_guid}, targets={target_guids}")

    # Convert GUIDs to appropriate format
    master_guid_tuple = tuple([master_guid])
    target_guid_list = tuple(target_guids)
    all_guid_list = master_guid_tuple + target_guid_list

    # Build SQL query with proper filtering, distinct, and ordering
    placeholders = ','.join([f":guid{i}" for i in range(len(all_guid_list))])
    joint_query = text(f"""
        SELECT DISTINCT
               joint_number,
               joint_length,
               iliyr,
               insp_guid,
               ili_id
        FROM public.joints
        WHERE insp_guid IN ({placeholders})
        ORDER BY insp_guid, CAST(joint_number AS INTEGER)
    """)

    # Create parameters dict
    params = {f'guid{i}': str(guid) for i, guid in enumerate(all_guid_list)}

    # Query database
    with engine.connect() as conn:
        joint_list = pd.read_sql_query(con=conn, sql=joint_query, params=params)
        
        logger.info(f"Raw query returned {len(joint_list)} records")
        
        # Drop null values
        smaller_subset = ['joint_number', 'joint_length', 'insp_guid', 'ili_id']
        joint_list = joint_list.dropna(subset=smaller_subset).reset_index(drop=True)
        
        # Deduplicate: Keep only the first entry per joint number for each inspection
        # This handles cases where multiple records exist for the same joint (e.g., features/anomalies)
        records_before_dedup = len(joint_list)
        joint_list = joint_list.drop_duplicates(
            subset=['insp_guid', 'joint_number'],
            keep='first'
        ).reset_index(drop=True)
        records_after_dedup = len(joint_list)
        
        if records_before_dedup > records_after_dedup:
            duplicates_removed = records_before_dedup - records_after_dedup
            logger.info(f"Deduplication: Removed {duplicates_removed} duplicate joint records")
            logger.info(f"  (Kept first occurrence of each joint_number per insp_guid)")

    logger.info("Database query successful")

    # Prepare master dataset - filter and ensure proper ordering
    joint_list["insp_guid"] = joint_list["insp_guid"].astype("str")
    fix_df = joint_list.loc[joint_list["insp_guid"] == master_guid_tuple[0]].copy()
    
    # Convert joint_number to integer and sort
    fix_df['joint_number'] = fix_df['joint_number'].astype(int)
    fix_df = fix_df.sort_values('joint_number').reset_index(drop=True)

    if fix_df.empty or fix_df["joint_length"].empty:
        raise ValueError("Master dataset is empty")

    fix_iliyr = np.unique(fix_df["iliyr"])[0]
    fix_ili_id = np.unique(fix_df["ili_id"])[0]
    
    # Track master joints for coverage check
    master_joints = sorted(fix_df["joint_number"].astype(str).tolist())

    # Process each target GUID
    results_list = []

    for target_guid in target_guid_list:
        logger.info(f"Processing target: {target_guid}")

        move_df = joint_list.loc[joint_list["insp_guid"] == target_guid].copy()
        
        # Convert joint_number to integer and sort
        move_df['joint_number'] = move_df['joint_number'].astype(int)
        move_df = move_df.sort_values('joint_number').reset_index(drop=True)

        if move_df.empty or move_df["joint_length"].empty:
            logger.warning(f"Target {target_guid} is empty, skipping")
            continue

        RevMove = move_df.loc[::-1]
        move_iliyr = np.unique(move_df["iliyr"])[0]
        move_ili_id = np.unique(move_df["ili_id"])[0]

        logger.info(
            f"Master {fix_iliyr}: {len(fix_df)} joints, Target {move_iliyr}: {len(move_df)} joints")

        # Flow direction determination
        column = "joint_length"
        fix_diff = joint_diff_calc(fix_df, column=column)
        move_diff = joint_diff_calc(move_df, column=column)
        RevMove_diff = joint_diff_calc(RevMove, column=column)

        fix_pairs = pairs_generator(fix_diff)
        move_pairs = pairs_generator(move_diff)
        RevMove_pairs = pairs_generator(RevMove_diff)

        match_pct_move = match_pct_calc(fix_pairs, move_pairs)
        match_pct_RevMove = match_pct_calc(fix_pairs, RevMove_pairs)

        if match_pct_move > match_pct_RevMove:
            direction = "FWD"
            logger.info(f"Direction: Forward ({match_pct_move:.2f}%)")
        elif match_pct_move < match_pct_RevMove:
            direction = "REV"
            logger.info(f"Direction: Reverse ({match_pct_RevMove:.2f}%)")
        else:
            direction = "FWD"  # Default to forward on tie
            logger.warning("Direction: Tie, defaulting to Forward")

        # Joint matching algorithm
        large_diff = 3

        fix_df['difference'] = fix_df.joint_length.shift(
            -1) - fix_df.joint_length
        fix_df['difference'] = fix_df['difference'].fillna(0)
        fix_df = fix_df.reset_index(drop=True)
        fix_df = fix_df.rename(columns={"ili_id": "Master_ili_id"})
        fix_data = fix_df.copy()

        move_data = move_df.copy()
        move_data = move_data.rename(columns={"ili_id": "Target_ili_id"})

        if direction == "Reverse" or direction == "REV":
            move_data["joint_number_org"] = move_df["joint_number"]
            move_data = move_data.loc[::-1]
            move_data["joint_number"] = move_df["joint_number"].astype(
                int).sort_values(ascending=True).values

        move_data['difference'] = move_data.joint_length.shift(
            -1) - move_data.joint_length
        move_data['difference'] = move_data['difference'].fillna(0)

        if direction == "Reverse" or direction == "REV":
            move_data = move_data[["joint_number", "difference",
                                   "joint_length", "joint_number_org", "Target_ili_id"]]
        else:
            move_data = move_data[["joint_number",
                                   "difference", "joint_length", "Target_ili_id"]]

        move_data = move_data.reset_index(drop=True)

        Match_df = pd.DataFrame([], columns=['FIX_ID', 'MOVE_ID', 'STATUS'])
        Unmatch = pd.DataFrame(
            columns=['FIX_START', 'FIX_END', 'MOVE_START', 'MOVE_END'])

        move_marker = move_data[abs(move_data.difference) > large_diff]
        fix_marker = fix_data[abs(fix_data.difference) > large_diff]

        j = 0
        temp_move_match = 0

        # Find all chunk markers
        for i in move_marker.index:
            temp = pd.Series(
                (abs(move_marker.loc[i]['difference'] - fix_marker.difference[fix_marker.index > j]) < 1) &
                (abs(move_marker.loc[i]["joint_length"] -
                 fix_marker.joint_length[fix_marker.index > j]) < 1)
            )

            try:
                next_temp1 = pd.Series(
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 1]['difference'] -
                         fix_marker.difference[fix_marker.index > temp.idxmax()]) < 1) &
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 1]["joint_length"] -
                         fix_marker.joint_length[fix_marker.index > temp.idxmax()]) < 1)
                )
                next_temp2 = pd.Series(
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 2]['difference'] -
                         fix_marker.difference[fix_marker.index > next_temp1.idxmax()]) < 1) &
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 2]["joint_length"] -
                         fix_marker.joint_length[fix_marker.index > next_temp1.idxmax()]) < 1)
                )
                next_temp3 = pd.Series(
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 3]['difference'] -
                         fix_marker.difference[fix_marker.index > next_temp2.idxmax()]) < 1) &
                    (abs(move_marker.iloc[move_marker.index.get_loc(i) + 3]["joint_length"] -
                         fix_marker.joint_length[fix_marker.index > next_temp2.idxmax()]) < 1)
                )
            except:
                continue

            try:
                fix_diff_sum = np.sum(
                    fix_data.loc[j:temp.idxmax()].joint_length)
                move_diff_sum = np.sum(
                    move_data.loc[temp_move_match:i].joint_length)
                length_diff = abs(fix_diff_sum - move_diff_sum)
            except:
                length_diff = 0.05

            try:
                index_diff2 = abs(
                    abs(next_temp1.idxmax() - move_marker.iloc[[move_marker.index.get_loc(i) + 1]].index) -
                    abs(temp.idxmax() - i)
                )
            except:
                index_diff2 = 0

            try:
                index_diff3 = abs(
                    abs(next_temp2.idxmax() - move_marker.iloc[[move_marker.index.get_loc(i) + 2]].index) -
                    abs(temp.idxmax() - i)
                )
            except:
                index_diff3 = 0

            try:
                index_diff4 = abs(
                    abs(next_temp3.idxmax() - move_marker.iloc[[move_marker.index.get_loc(i) + 3]].index) -
                    abs(temp.idxmax() - i)
                )
            except:
                index_diff4 = 0

            if Match_df.empty:
                temp_fix_match = temp.idxmax()
                matched_points = pd.DataFrame(
                    np.array([temp_fix_match, i, 1]).reshape(1, 3),
                    columns=Match_df.columns
                )
                Match_df = pd.concat(
                    [Match_df, matched_points], ignore_index=True)
                j = temp_fix_match
                temp_move_match = i
            else:
                # Require BOTH reasonable cumulative length AND marker alignment
                # This prevents matching joints from completely different pipeline sections
                if temp.any() & (length_diff < 10) & ((index_diff2 == 0) | (index_diff3 == 0) | (index_diff4 == 0)):
                    temp_fix_match = temp.idxmax()
                    matched_points = pd.DataFrame(
                        np.array([temp_fix_match, i, 1]).reshape(1, 3),
                        columns=Match_df.columns
                    )
                    Match_df = pd.concat(
                        [Match_df, matched_points], ignore_index=True)
                    j = temp_fix_match
                    temp_move_match = i

        # Process matched chunks
        it_chunks = Match_df[
            ((Match_df['FIX_ID'].shift(-1) - Match_df['FIX_ID']) != 1) &
            ((Match_df['MOVE_ID'].shift(-1) - Match_df['MOVE_ID']) != 1)
        ]
        it_chunks2 = it_chunks.head(-1)

        for i in it_chunks2.index:
            init_fix = it_chunks.loc[i]["FIX_ID"]
            init_move = it_chunks.loc[i]['MOVE_ID']
            end_fix = it_chunks.iloc[it_chunks.index.get_loc(i) + 1]['FIX_ID']
            end_move = it_chunks.iloc[it_chunks.index.get_loc(
                i) + 1]['MOVE_ID']

            matches, fix_break, move_break = forward_match_check(
                fix_data, move_data, init_fix, init_move, end_fix, end_move, 1
            )
            Match_df = pd.concat([Match_df, matches])

            if (fix_break != end_fix) & (move_break != end_move) & (fix_break is not None):
                matches2, fix_break2, move_break2 = backward_match_check(
                    fix_data, move_data, fix_break, move_break, end_fix, end_move, 1
                )
                unmatch_chunks = pd.DataFrame(
                    np.array([fix_break, move_break, fix_break2,
                             move_break2]).reshape(1, 4),
                    columns=Unmatch.columns
                )
                Unmatch = pd.concat(
                    [Unmatch, unmatch_chunks], ignore_index=True)
                Match_df = pd.concat([Match_df, matches2])

        # Match joints before first marker and after last marker
        try:
            matches, _, _ = backward_match_check(
                fix_data, move_data, 0, 0, it_chunks.iloc[0,
                                                          0], it_chunks.iloc[0, 1], 1
            )
            Match_df = pd.concat([Match_df, matches])
        except:
            pass

        try:
            matches, _, _ = forward_match_check(
                fix_data, move_data, it_chunks.iloc[-1,
                                                    0], it_chunks.iloc[-1, 1],
                int(fix_data.iloc[-1, 0]), int(move_data.iloc[-1, 0]), 1
            )
            Match_df = pd.concat([Match_df, matches])
        except:
            pass

        if Match_df.empty:
            logger.warning("No chunks found, skipping target")
            continue

        Match_df = Match_df.drop_duplicates(["FIX_ID", "MOVE_ID"], keep="first").sort_values(
            by="FIX_ID", ignore_index=True
        )

        # Transform output
        temp_output = pd.merge(
            pd.merge(Match_df, fix_data, left_on='FIX_ID',
                     right_index=True, how='left'),
            move_data, left_on='MOVE_ID', right_index=True, how='left'
        )

        if direction == "Reverse" or direction == "REV":
            temp_output = temp_output.rename(columns={
                'ili_id_x': 'Master_ili_id',
                'joint_number_x': 'Master_joint_number',
                'joint_number_y': 'Alias_joint_number',
                "joint_number_org": "Target_joint_number",
                'ili_id_y': 'Target_ili_id'
            })
            Match_output = temp_output[['Master_ili_id', 'Master_joint_number',
                                        'Target_joint_number', 'Alias_joint_number', 'Target_ili_id']]
        else:
            temp_output = temp_output.rename(columns={
                'ili_id_x': 'Master_ili_id',
                'joint_number_x': 'Master_joint_number',
                'joint_number_y': "Target_joint_number",
                'ili_id_y': 'Target_ili_id'
            })
            Match_output = temp_output[[
                'Master_ili_id', 'Master_joint_number', 'Target_joint_number', 'Target_ili_id']]

        Match_all = Match_output.reset_index(drop=True)

        # Handle questionable matches (duplicates)
        questionable = Match_all[
            (Match_all["Target_joint_number"].duplicated(keep=False)) |
            (Match_all["Master_joint_number"].duplicated(keep=False))
        ]

        if not questionable.empty:
            Match_all = Match_all.loc[~Match_all.index.isin(
                questionable.index)]
            Match_df = Match_df.loc[~Match_df.index.isin(questionable.index)]
            logger.warning(f"Found {len(questionable)} questionable matches")

        # Transform to output format
        Match_df["Master_joint_number"] = fix_df.loc[Match_df["FIX_ID"]
                                                     ]["joint_number"].array
        Match_df["Target_joint_number"] = move_df.loc[Match_df["MOVE_ID"]
                                                      ]["joint_number"].array

        # Process unmatched chunks
        Mat_pairs_sort = Match_df.drop(
            ["Master_joint_number", "Target_joint_number"], axis=1)
        
        if not Mat_pairs_sort.empty:
            # Find gaps between matched joints
            unmatch_start = Mat_pairs_sort[
                ((Mat_pairs_sort['FIX_ID'].shift(-1) -
                 Mat_pairs_sort['FIX_ID']) != 1)
            ] + 1
            unmatch_start = unmatch_start.reset_index(drop=True)
            unmatch_end = Mat_pairs_sort[
                ((Mat_pairs_sort['FIX_ID'].shift(1) -
                 Mat_pairs_sort['FIX_ID']) != -1)
            ] - 1
            unmatch_end = unmatch_end.tail(-1).reset_index(drop=True)
            
            # Create initial unmatched chunks from gaps
            unmatched_chunks = pd.concat(
                [unmatch_start, unmatch_end], ignore_index=True, axis=1).drop([2, 5], axis=1)
            unmatched_chunks = unmatched_chunks.rename(columns={
                0: 'FIX_START', 1: 'MOVE_START', 3: 'FIX_END', 4: 'MOVE_END'
            })
            
            # Merge in the Unmatch chunks from forward/backward breaks (if any)
            if not Unmatch.empty:
                unmatched_chunks = pd.concat([unmatched_chunks, Unmatch], ignore_index=True)
        else:
            # No matches at all - start with Unmatch chunks (if any)
            unmatched_chunks = Unmatch.copy() if not Unmatch.empty else pd.DataFrame(
                columns=['FIX_START', 'MOVE_START', 'FIX_END', 'MOVE_END'])
        
        # Add joints BEFORE first match and AFTER last match (if any)
        if not Mat_pairs_sort.empty:
            first_match_fix_id = Mat_pairs_sort['FIX_ID'].iloc[0]
            first_match_move_id = Mat_pairs_sort['MOVE_ID'].iloc[0]
            
            if first_match_fix_id > 0:
                # There are Master joints before the first match
                # Don't include Target joints - they may be matched to other Master joints
                before_first_chunk = pd.DataFrame([{
                    'FIX_START': 0,
                    'MOVE_START': np.nan,
                    'FIX_END': first_match_fix_id - 1,
                    'MOVE_END': np.nan
                }])
                unmatched_chunks = pd.concat([before_first_chunk, unmatched_chunks], ignore_index=True)
            
            # Add joints AFTER last match (if any)
            last_match_fix_id = Mat_pairs_sort['FIX_ID'].iloc[-1]
            last_match_move_id = Mat_pairs_sort['MOVE_ID'].iloc[-1]
            max_fix_id = len(fix_df) - 1
            max_move_id = len(move_df) - 1
            
            if last_match_fix_id < max_fix_id:
                # There are Master joints after the last match
                # Don't include Target joints - they may be matched to other Master joints
                after_last_chunk = pd.DataFrame([{
                    'FIX_START': last_match_fix_id + 1,
                    'MOVE_START': np.nan,
                    'FIX_END': max_fix_id,
                    'MOVE_END': np.nan
                }])
                unmatched_chunks = pd.concat([unmatched_chunks, after_last_chunk], ignore_index=True)
        else:
            # No matches at all - all Master and Target joints are unmatched
            max_fix_id = len(fix_df) - 1
            max_move_id = len(move_df) - 1
            all_unmatched_chunk = pd.DataFrame([{
                'FIX_START': 0,
                'MOVE_START': 0,
                'FIX_END': max_fix_id,
                'MOVE_END': max_move_id
            }])
            unmatched_chunks = pd.concat([unmatched_chunks, all_unmatched_chunk], ignore_index=True)
            logger.warning(f"No matches found - all {len(fix_df)} Master and {len(move_df)} Target joints are unmatched")

        # Map FIX/MOVE indices to actual joint numbers
        # Use .iloc for integer-based indexing
        for idx, row in unmatched_chunks.iterrows():
            if pd.notna(row["FIX_START"]):
                fix_start_idx = int(row["FIX_START"])
                if 0 <= fix_start_idx < len(fix_df):
                    unmatched_chunks.at[idx, "Master_joint_start"] = fix_df.iloc[fix_start_idx]["joint_number"]
            
            if pd.notna(row["FIX_END"]):
                fix_end_idx = int(row["FIX_END"])
                if 0 <= fix_end_idx < len(fix_df):
                    unmatched_chunks.at[idx, "Master_joint_end"] = fix_df.iloc[fix_end_idx]["joint_number"]
            
            if pd.notna(row["MOVE_START"]):
                move_start_idx = int(row["MOVE_START"])
                if 0 <= move_start_idx < len(move_df):
                    unmatched_chunks.at[idx, "Target_joint_start"] = move_df.iloc[move_start_idx]["joint_number"]
            
            if pd.notna(row["MOVE_END"]):
                move_end_idx = int(row["MOVE_END"])
                if 0 <= move_end_idx < len(move_df):
                    unmatched_chunks.at[idx, "Target_joint_end"] = move_df.iloc[move_end_idx]["joint_number"]

        # Drop the index columns if they exist
        cols_to_drop = [col for col in ["FIX_START", "FIX_END", "MOVE_START", "MOVE_END"] if col in unmatched_chunks.columns]
        if cols_to_drop:
            unmatched_chunks.drop(cols_to_drop, axis=1, inplace=True)
        
        # Reorder columns, only including those that exist
        desired_cols = ["Master_joint_start", "Master_joint_end", "Target_joint_start", "Target_joint_end"]
        existing_cols = [col for col in desired_cols if col in unmatched_chunks.columns]
        if existing_cols:
            unmatched_chunks = unmatched_chunks[existing_cols]

        # Expand unmatched chunks
        unmatched_joints = unchunk_dataframe(unmatched_chunks, fix_df, move_df)
        
        # Find unmatched Target joints (not in any match AND not already in unmatched_joints)
        if not Match_all.empty:
            matched_target_joints = set(Match_all["Target_joint_number"].dropna().astype(str).tolist())
            all_target_joints = set(move_df["joint_number"].astype(str).tolist())
            already_unmatched_target = set(unmatched_joints[unmatched_joints["Target_joint_number"] != ""]["Target_joint_number"].astype(str).tolist())
            unmatched_target_joints = all_target_joints - matched_target_joints - already_unmatched_target
            
            if unmatched_target_joints:
                # Add any remaining unmatched Target joints not already in unmatched_joints
                for target_joint in unmatched_target_joints:
                    unmatched_joints = pd.concat([
                        unmatched_joints,
                        pd.DataFrame([{'Master_joint_number': '', 'Target_joint_number': target_joint}])
                    ], ignore_index=True)

        # Prepare final output DataFrames
        rename_map = {
            "Master_joint_number": "Master Joint Number",
            "Target_joint_number": "Target Joint Number"
        }

        # Process questionable joints
        if not questionable.empty:
            questionable = questionable.drop_duplicates(
                subset=['Master_joint_number', 'Target_joint_number'], keep='first'
            )
            
            questionable.rename(columns=rename_map, inplace=True)

        # Merge matched joints with additional data
        matched_joints = pd.merge(Match_all, Match_df, on=[
                                  'Master_joint_number', 'Target_joint_number'], how='inner')
        matched_joints = matched_joints.rename(
            columns={'STATUS': 'Iterations'})
        matched_joints.rename(columns=rename_map, inplace=True)

        unmatched_joints.rename(columns=rename_map, inplace=True)

        # Build run summary
        run_summary = {
            "Master_inspection_guid": master_guid_tuple[0],
            "Master_ili_id": fix_ili_id,
            "Target_inspection_guid": target_guid,
            "Target_ili_id": move_ili_id,
            "Total_master_joints": len(fix_df),
            "Total_target_joints": len(move_df),
            "Matched_joints": len(matched_joints),
            "Unmatched_joints": len(unmatched_joints),
            "Questionable_matches": len(questionable),
            "Master_joint_percentage": round((len(Match_all.index) / len(fix_data.index)) * 100, 2),
            "Target_joint_percentage": round((len(Match_all.index) / len(move_df.index)) * 100, 2),
            "Flow_direction": direction,
        }

        # Convert DataFrames to list of dicts for JSON serialization
        # Replace NaN with None for JSON compliance
        matched_joints_list = matched_joints.replace(
            {np.nan: None}).to_dict('records')
        unmatched_joints_list = unmatched_joints.replace(
            {np.nan: None}).to_dict('records')
        questionable_joints_list = questionable.replace({np.nan: None}).to_dict(
            'records') if not questionable.empty else []

        # Store result for this target
        results_list.append({
            "run_summary": run_summary,
            "matched_joints": matched_joints_list,
            "unmatched_joints": unmatched_joints_list,
            "questionable_joints": questionable_joints_list
        })

        logger.info(
            f"Completed target {target_guid}: {len(matched_joints)} matched, {len(unmatched_joints)} unmatched, {len(questionable)} questionable")

    # For simplicity, return the first result (single target for now)
    # In future, could aggregate multiple targets
    if not results_list:
        raise ValueError("No valid target inspections found")

    return results_list[0]
