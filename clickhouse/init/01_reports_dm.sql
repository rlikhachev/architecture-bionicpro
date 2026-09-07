CREATE DATABASE IF NOT EXISTS reports_dm;

CREATE TABLE IF NOT EXISTS reports_dm.mart_user_reports
(
    report_date Date,
    user_id String,
    username String,
    prosthetic_model String,
    serial_number String,
    steps UInt64,
    battery_avg Float64,
    grip_cycles UInt64,
    usage_hours UInt64,
    updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date);

CREATE TABLE IF NOT EXISTS reports_dm.etl_watermark
(
    mart String,
    last_processed_date Date,
    report_version UInt64,
    updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY mart;
