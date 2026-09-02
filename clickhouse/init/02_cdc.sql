CREATE TABLE IF NOT EXISTS reports_dm.kafka_crm_clients
(
    id Int64,
    keycloak_user_id String,
    username String,
    full_name String,
    email Nullable(String),
    city Nullable(String),
    created_at Nullable(Int64),
    __op String,
    __ts_ms Int64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:29092',
         kafka_topic_list = 'crm.clients',
         kafka_group_name = 'clickhouse_crm_clients',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS reports_dm.kafka_crm_prosthetics
(
    id Int64,
    client_id Int64,
    model String,
    serial_number String,
    fitted_at Nullable(Int64),
    __op String,
    __ts_ms Int64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:29092',
         kafka_topic_list = 'crm.prosthetics',
         kafka_group_name = 'clickhouse_crm_prosthetics',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS reports_dm.kafka_crm_telemetry
(
    id Int64,
    prosthetic_id Int64,
    metric String,
    value Float64,
    ts Int64,
    __op String,
    __ts_ms Int64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:29092',
         kafka_topic_list = 'crm.telemetry',
         kafka_group_name = 'clickhouse_crm_telemetry',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS reports_dm.crm_clients
(
    id Int64,
    keycloak_user_id String,
    username String,
    full_name String,
    email Nullable(String),
    city Nullable(String),
    created_at Nullable(DateTime),
    updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS reports_dm.crm_prosthetics
(
    id Int64,
    client_id Int64,
    model String,
    serial_number String,
    fitted_at Nullable(DateTime),
    updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports_dm.mv_crm_clients
TO reports_dm.crm_clients AS
SELECT
    id,
    keycloak_user_id,
    username,
    full_name,
    email,
    city,
    toDateTime(intDiv(created_at, 1000)) AS created_at,
    toDateTime(intDiv(__ts_ms, 1000)) AS updated_at
FROM reports_dm.kafka_crm_clients
WHERE __op IN ('c', 'r', 'u') AND id != 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports_dm.mv_crm_prosthetics
TO reports_dm.crm_prosthetics AS
SELECT
    id,
    client_id,
    model,
    serial_number,
    toDateTime(intDiv(fitted_at, 1000)) AS fitted_at,
    toDateTime(intDiv(__ts_ms, 1000)) AS updated_at
FROM reports_dm.kafka_crm_prosthetics
WHERE __op IN ('c', 'r', 'u') AND id != 0;

CREATE TABLE IF NOT EXISTS reports_dm.mart_crm_reports
(
    report_date Date,
    user_id String,
    username String,
    prosthetic_model String,
    serial_number String,
    steps SimpleAggregateFunction(sum, Float64),
    battery_sum SimpleAggregateFunction(sum, Float64),
    battery_count SimpleAggregateFunction(sum, UInt64),
    grip_cycles SimpleAggregateFunction(sum, Float64),
    usage_hours AggregateFunction(uniq, DateTime)
)
ENGINE = AggregatingMergeTree
ORDER BY (user_id, report_date, serial_number);

CREATE MATERIALIZED VIEW IF NOT EXISTS reports_dm.mv_crm_reports
TO reports_dm.mart_crm_reports AS
SELECT
    toDate(toDateTime(intDiv(t.ts, 1000))) AS report_date,
    coalesce(cl.keycloak_user_id, '') AS user_id,
    coalesce(cl.username, '') AS username,
    coalesce(pr.model, '') AS prosthetic_model,
    coalesce(pr.serial_number, '') AS serial_number,
    sumIf(t.value, t.metric = 'steps') AS steps,
    sumIf(t.value, t.metric = 'battery_level') AS battery_sum,
    countIf(t.metric = 'battery_level') AS battery_count,
    sumIf(t.value, t.metric = 'grip_cycles') AS grip_cycles,
    uniqState(toStartOfHour(toDateTime(intDiv(t.ts, 1000)))) AS usage_hours
FROM reports_dm.kafka_crm_telemetry AS t
LEFT JOIN reports_dm.crm_prosthetics AS pr FINAL ON pr.id = t.prosthetic_id
LEFT JOIN reports_dm.crm_clients AS cl FINAL ON cl.id = pr.client_id
WHERE t.__op IN ('c', 'r', 'u')
GROUP BY report_date, user_id, username, prosthetic_model, serial_number;
