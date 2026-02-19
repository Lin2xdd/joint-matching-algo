-- Creates a table in database `ili` using headers from `Sample Input/CNRL/2016.csv`
-- Notes on normalization:
--   - `feature_ type` -> `feature_type`
--   - `distance `     -> `distance`

CREATE TABLE IF NOT EXISTS public.joint_length (
    id BIGSERIAL PRIMARY KEY,
    insp_guid TEXT,
    ili_id TEXT,
    iliyr NUMERIC,
    joint_NUMERIC NUMERIC,
    feature_NUMERIC TEXT,
    cluster_NUMERIC TEXT,
    feature_type TEXT,
    distance NUMERIC,
    joint_length NUMERIC,
    dist_to_us TEXT,
    dist_to_gs TEXT,
    length TEXT,
    wideth TEXT,
    depth TEXT,
    wall_surface TEXT,
    estimated_repair_factor TEXT,
    burst_pressure TEXT,
    wall_thickness TEXT,
    od_restriction TEXT,
    latitude TEXT,
    longitude TEXT,
    elevation TEXT
);

