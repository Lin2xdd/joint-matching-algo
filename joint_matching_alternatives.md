# Joint Matching Algorithm Alternatives

## Problem Statement

The current joint matching algorithm fails to match joints when:
1. **A joint is cut/split**: One joint from Year 1 becomes two or more joints in Year 2
2. **Joints are merged**: Two or more joints from Year 1 become one joint in Year 2
3. **Joint renumbering**: Physical joints remain the same but numbering schemes change

### Example Scenario
```
Year 2017: Joint #11 (length: 3.304m)
Year 2019: Joint #110 (0.32m) + Joint #120 (3.35m) = 3.67m total
```
The existing algorithm only performs **1-to-1 matching**, so it cannot recognize that joints 110 and 120 together correspond to joint 11.

---

## Current Algorithm Analysis

### How It Works
1. **Marker Detection**: Finds joints with large length differences (|diff| > 3m) as "anchor points"
2. **Sequence Matching**: Matches sequences of joints between markers based on:
   - Similar joint lengths (within 1m tolerance)
   - Similar difference patterns between consecutive joints
3. **Forward/Backward Checks**: Fills in matches between markers

### Limitations
- ❌ **1-to-1 only**: Cannot handle one-to-many or many-to-one mappings
- ❌ **Relies on markers**: If markers shift due to cuts, matching fails
- ❌ **No cumulative length checking**: Doesn't consider that multiple small joints might equal one large joint
- ❌ **Sequential bias**: Assumes joint order is preserved with minimal disruption

---

## Alternative Algorithms

### **Algorithm 1: Dynamic Programming with Flexible Matching**

**Concept**: Use dynamic programming to find optimal alignment allowing 1-to-1, 1-to-many, and many-to-1 matches.

#### Key Features
- **Cumulative Length Matching**: Aggregates consecutive joints to match cumulative lengths
- **Gap Penalties**: Penalizes skipping joints but allows it when necessary
- **Match Quality Score**: Combines length similarity, position, and confidence

#### Implementation Approach
```python
def dp_flexible_matching(master_joints, target_joints, threshold=0.5):
    """
    Dynamic Programming approach allowing flexible joint matching.
    
    Args:
        master_joints: List of (joint_number, length) tuples from master inspection
        target_joints: List of (joint_number, length) tuples from target inspection
        threshold: Maximum length difference ratio to consider a match
    
    Returns:
        List of matches: [(master_joints, target_joints, score), ...]
    """
    n, m = len(master_joints), len(target_joints)
    
    # DP table: dp[i][j] = (score, backtrace)
    dp = [[None for _ in range(m+1)] for _ in range(n+1)]
    dp[0][0] = (0, None)
    
    # Fill DP table
    for i in range(n+1):
        for j in range(m+1):
            if dp[i][j] is None:
                continue
            
            current_score = dp[i][j][0]
            
            # Option 1: Skip master joint (gap in target)
            if i < n:
                score = current_score - GAP_PENALTY
                if dp[i+1][j] is None or dp[i+1][j][0] < score:
                    dp[i+1][j] = (score, ('skip_master', i, j))
            
            # Option 2: Skip target joint (gap in master)
            if j < m:
                score = current_score - GAP_PENALTY
                if dp[i][j+1] is None or dp[i][j+1][0] < score:
                    dp[i][j+1] = (score, ('skip_target', i, j))
            
            # Option 3: 1-to-1 match
            if i < n and j < m:
                match_score = calculate_match_score(master_joints[i], target_joints[j])
                if match_score > MATCH_THRESHOLD:
                    score = current_score + match_score
                    if dp[i+1][j+1] is None or dp[i+1][j+1][0] < score:
                        dp[i+1][j+1] = (score, ('match_1_1', i, j))
            
            # Option 4: 1-to-many (master joint split)
            if i < n:
                for k in range(j+1, min(j+MAX_SPLIT+1, m+1)):
                    cumulative_target = sum(target_joints[x][1] for x in range(j, k))
                    split_score = calculate_split_score(
                        master_joints[i][1], 
                        cumulative_target,
                        k - j
                    )
                    if split_score > SPLIT_THRESHOLD:
                        score = current_score + split_score
                        if dp[i+1][k] is None or dp[i+1][k][0] < score:
                            dp[i+1][k] = (score, ('match_1_many', i, j, k))
            
            # Option 5: many-to-1 (master joints merged)
            if j < m:
                for k in range(i+1, min(i+MAX_MERGE+1, n+1)):
                    cumulative_master = sum(master_joints[x][1] for x in range(i, k))
                    merge_score = calculate_merge_score(
                        cumulative_master,
                        target_joints[j][1],
                        k - i
                    )
                    if merge_score > MERGE_THRESHOLD:
                        score = current_score + merge_score
                        if dp[k][j+1] is None or dp[k][j+1][0] < score:
                            dp[k][j+1] = (score, ('match_many_1', i, k, j))
    
    # Backtrace to find optimal path
    return backtrace(dp, n, m, master_joints, target_joints)
```

#### Advantages
- ✅ Handles splits, merges, and gaps
- ✅ Global optimization (finds best overall alignment)
- ✅ Configurable penalties and thresholds

#### Disadvantages
- ⚠️ Computationally expensive: O(n²m²) for many-to-many matching
- ⚠️ Requires careful tuning of parameters
- ⚠️ May produce false positives if parameters are too lenient

---

### **Algorithm 2: Sliding Window Length-Based Matching**

**Concept**: Use cumulative length comparison with sliding windows to find matches regardless of joint numbering.

#### Key Features
- **Cumulative Distance Tracking**: Tracks total pipeline distance rather than joint numbers
- **Window Aggregation**: Groups consecutive joints to match target lengths
- **Statistical Confidence**: Uses multiple features (length, position, feature density)

#### Implementation Approach
```python
def sliding_window_matching(master_joints, target_joints, 
                           window_tolerance=0.1, min_overlap=0.8):
    """
    Sliding window approach to match based on cumulative lengths.
    
    Args:
        master_joints: DataFrame with columns [joint_number, joint_length, distance]
        target_joints: DataFrame with columns [joint_number, joint_length, distance]
        window_tolerance: Allowable length difference as fraction (10%)
        min_overlap: Minimum overlap ratio to consider a match (80%)
    
    Returns:
        List of matches with confidence scores
    """
    matches = []
    
    # Calculate cumulative distances
    master_joints['cumulative_dist'] = master_joints['joint_length'].cumsum()
    target_joints['cumulative_dist'] = target_joints['joint_length'].cumsum()
    
    master_idx = 0
    target_idx = 0
    
    while master_idx < len(master_joints) and target_idx < len(target_joints):
        master_start = master_idx
        target_start = target_idx
        
        master_length = master_joints.iloc[master_idx]['joint_length']
        target_cumulative = 0
        target_end = target_idx
        
        # Aggregate target joints until length matches
        while (target_end < len(target_joints) and 
               target_cumulative < master_length * (1 + window_tolerance)):
            target_cumulative += target_joints.iloc[target_end]['joint_length']
            target_end += 1
            
            # Check if cumulative target matches master
            length_diff = abs(target_cumulative - master_length)
            if length_diff <= master_length * window_tolerance:
                # Potential match found
                confidence = calculate_window_confidence(
                    master_joints.iloc[master_start:master_start+1],
                    target_joints.iloc[target_start:target_end],
                    length_diff
                )
                
                if confidence >= min_overlap:
                    matches.append({
                        'master_joints': [master_joints.iloc[master_start]['joint_number']],
                        'target_joints': target_joints.iloc[target_start:target_end]['joint_number'].tolist(),
                        'match_type': '1-to-many' if target_end - target_start > 1 else '1-to-1',
                        'confidence': confidence,
                        'length_diff': length_diff
                    })
                    
                    master_idx = master_start + 1
                    target_idx = target_end
                    break
        else:
            # No match found, try aggregating master joints
            master_end = master_start + 1
            master_cumulative = master_length
            
            while (master_end < len(master_joints) and
                   master_cumulative < target_cumulative * (1 + window_tolerance)):
                master_cumulative += master_joints.iloc[master_end]['joint_length']
                master_end += 1
                
                length_diff = abs(master_cumulative - target_cumulative)
                if length_diff <= target_cumulative * window_tolerance:
                    confidence = calculate_window_confidence(
                        master_joints.iloc[master_start:master_end],
                        target_joints.iloc[target_start:target_end],
                        length_diff
                    )
                    
                    if confidence >= min_overlap:
                        matches.append({
                            'master_joints': master_joints.iloc[master_start:master_end]['joint_number'].tolist(),
                            'target_joints': target_joints.iloc[target_start:target_end]['joint_number'].tolist(),
                            'match_type': 'many-to-many',
                            'confidence': confidence,
                            'length_diff': length_diff
                        })
                        
                        master_idx = master_end
                        target_idx = target_end
                        break
            else:
                # Skip to next position
                master_idx += 1
                target_idx = target_start
    
    return matches
```

#### Advantages
- ✅ Simple and intuitive
- ✅ Efficient: O(nm) time complexity
- ✅ Naturally handles splits and merges
- ✅ Robust to renumbering

#### Disadvantages
- ⚠️ May miss matches if start positions are significantly offset
- ⚠️ Greedy algorithm (locally optimal, not globally optimal)

---

### **Algorithm 3: Graph-Based Matching with Maximum Flow**

**Concept**: Model the matching problem as a bipartite graph and find maximum weighted matching.

#### Key Features
- **Node Creation**: Each joint or group of consecutive joints becomes a node
- **Edge Weights**: Based on length similarity, position proximity, and feature correlation
- **Maximum Weighted Matching**: Finds optimal global assignment

#### Implementation Approach
```python
import networkx as nx
from scipy.optimize import linear_sum_assignment

def graph_based_matching(master_joints, target_joints, max_group_size=5):
    """
    Graph-based approach using bipartite matching.
    
    Creates all possible groupings of consecutive joints (up to max_group_size)
    and finds optimal matching based on cumulative lengths.
    """
    # Create candidate groups
    master_groups = create_joint_groups(master_joints, max_group_size)
    target_groups = create_joint_groups(target_joints, max_group_size)
    
    # Build bipartite graph
    G = nx.Graph()
    
    # Add nodes
    for i, mg in enumerate(master_groups):
        G.add_node(f"M{i}", type='master', joints=mg['joints'], length=mg['length'])
    
    for j, tg in enumerate(target_groups):
        G.add_node(f"T{j}", type='target', joints=tg['joints'], length=tg['length'])
    
    # Add edges with weights
    cost_matrix = []
    for i, mg in enumerate(master_groups):
        row = []
        for j, tg in enumerate(target_groups):
            # Calculate match quality
            length_similarity = calculate_length_similarity(mg['length'], tg['length'])
            position_proximity = calculate_position_proximity(mg, tg)
            overlap_penalty = calculate_overlap_penalty(mg, tg, master_groups, target_groups)
            
            # Combined score
            score = (0.5 * length_similarity + 
                    0.3 * position_proximity - 
                    0.2 * overlap_penalty)
            
            if score > MINIMUM_EDGE_SCORE:
                G.add_edge(f"M{i}", f"T{j}", weight=score)
                row.append(-score)  # Negative for minimization
            else:
                row.append(np.inf)  # No edge
        cost_matrix.append(row)
    
    # Solve assignment problem
    cost_matrix = np.array(cost_matrix)
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    
    # Extract matches
    matches = []
    for i, j in zip(row_ind, col_ind):
        if cost_matrix[i][j] < np.inf:
            matches.append({
                'master_joints': master_groups[i]['joints'],
                'target_joints': target_groups[j]['joints'],
                'score': -cost_matrix[i][j],
                'match_type': determine_match_type(
                    len(master_groups[i]['joints']),
                    len(target_groups[j]['joints'])
                )
            })
    
    return matches

def create_joint_groups(joints, max_size):
    """Create all possible consecutive joint groupings."""
    groups = []
    n = len(joints)
    
    for start in range(n):
        for size in range(1, min(max_size + 1, n - start + 1)):
            end = start + size
            group_joints = joints.iloc[start:end]
            groups.append({
                'joints': group_joints['joint_number'].tolist(),
                'start_idx': start,
                'end_idx': end,
                'length': group_joints['joint_length'].sum(),
                'start_distance': group_joints.iloc[0]['distance'],
                'end_distance': group_joints.iloc[-1]['distance'] + group_joints.iloc[-1]['joint_length']
            })
    
    return groups
```

#### Advantages
- ✅ Globally optimal solution
- ✅ Handles complex scenarios (splits, merges, gaps)
- ✅ Configurable constraints and objectives
- ✅ Well-studied algorithms available

#### Disadvantages
- ⚠️ Very computationally expensive: O(n³m³) with grouping
- ⚠️ Complex implementation
- ⚠️ Difficult to interpret and debug

---

### **Algorithm 4: Hybrid Marker + Local Flexible Matching**

**Concept**: Combine the speed of marker-based matching with flexible local matching for problem areas.

#### Key Features
- **Phase 1**: Use existing marker-based approach to find reliable anchor points
- **Phase 2**: Apply flexible matching (Algorithm 1 or 2) within gaps
- **Phase 3**: Validate and refine matches

#### Implementation Approach
```python
def hybrid_matching(master_joints, target_joints):
    """
    Two-phase approach: marker-based for main alignment, 
    flexible for gap regions.
    """
    # Phase 1: Find reliable marker matches (existing algorithm)
    marker_matches = find_marker_based_matches(master_joints, target_joints)
    
    if not marker_matches:
        # No markers found - fall back to full flexible matching
        return sliding_window_matching(master_joints, target_joints)
    
    # Phase 2: Apply flexible matching in gaps between markers
    all_matches = []
    prev_master_idx = 0
    prev_target_idx = 0
    
    for marker_match in marker_matches:
        master_idx = marker_match['master_idx']
        target_idx = marker_match['target_idx']
        
        # Extract gap region
        gap_master = master_joints.iloc[prev_master_idx:master_idx]
        gap_target = target_joints.iloc[prev_target_idx:target_idx]
        
        # Apply flexible matching in gap
        if not gap_master.empty and not gap_target.empty:
            gap_matches = sliding_window_matching(gap_master, gap_target)
            all_matches.extend(gap_matches)
        
        # Add marker match
        all_matches.append(marker_match)
        
        prev_master_idx = master_idx + 1
        prev_target_idx = target_idx + 1
    
    # Handle remaining joints after last marker
    if prev_master_idx < len(master_joints) or prev_target_idx < len(target_joints):
        remaining_master = master_joints.iloc[prev_master_idx:]
        remaining_target = target_joints.iloc[prev_target_idx:]
        gap_matches = sliding_window_matching(remaining_master, remaining_target)
        all_matches.extend(gap_matches)
    
    return all_matches
```

#### Advantages
- ✅ Balances speed and flexibility
- ✅ Leverages strengths of existing algorithm
- ✅ More efficient than full flexible matching
- ✅ Easier to validate (markers provide checkpoints)

#### Disadvantages
- ⚠️ Still dependent on finding some markers
