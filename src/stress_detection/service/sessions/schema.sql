CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at_ms INTEGER NOT NULL,
    ended_at_ms INTEGER,
    user_label TEXT,
    notes TEXT,
    user_id TEXT,
    use_calibration INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS samples (
    session_id TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    bpm REAL, avg_bpm REAL, temp_c REAL, gsr REAL,
    PRIMARY KEY (session_id, timestamp_ms)
);

CREATE TABLE IF NOT EXISTS predictions (
    session_id TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    label TEXT, confidence REAL,
    smoothed_label TEXT, smoothed_confidence REAL,
    p_baseline REAL, p_stress REAL,
    PRIMARY KEY (session_id, timestamp_ms)
);

CREATE TABLE IF NOT EXISTS labels (
    session_id TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (session_id, timestamp_ms)
);

CREATE TABLE IF NOT EXISTS calibrations (
    user_id TEXT PRIMARY KEY,
    gsr_baseline REAL,
    hr_baseline REAL,
    temp_baseline REAL,
    captured_at_ms INTEGER,
    payload_json TEXT
);
