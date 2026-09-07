CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    keycloak_user_id VARCHAR(64) UNIQUE NOT NULL,
    username VARCHAR(128) NOT NULL,
    full_name VARCHAR(256) NOT NULL,
    email VARCHAR(256),
    city VARCHAR(128),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE prosthetics (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients (id),
    model VARCHAR(128) NOT NULL,
    serial_number VARCHAR(64) UNIQUE NOT NULL,
    fitted_at TIMESTAMP NOT NULL
);

CREATE TABLE telemetry (
    id BIGSERIAL PRIMARY KEY,
    prosthetic_id INTEGER NOT NULL REFERENCES prosthetics (id),
    metric VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    ts TIMESTAMP NOT NULL
);

CREATE INDEX idx_telemetry_ts ON telemetry (ts);
CREATE INDEX idx_telemetry_prosthetic_ts ON telemetry (prosthetic_id, ts);
CREATE INDEX idx_prosthetics_client ON prosthetics (client_id);

CREATE USER debezium WITH REPLICATION LOGIN PASSWORD 'dbz_password';
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;

CREATE PUBLICATION dbz_publication FOR TABLE clients, prosthetics, telemetry;

INSERT INTO clients (keycloak_user_id, username, full_name, email, city, created_at)
VALUES
    ('a1000000-0000-4000-8000-000000000011', 'prothetic1', 'Prothetic One', 'prothetic1@example.com', 'Berlin', now() - interval '90 days'),
    ('a1000000-0000-4000-8000-000000000012', 'prothetic2', 'Prothetic Two', 'prothetic2@example.com', 'Amsterdam', now() - interval '60 days'),
    ('a1000000-0000-4000-8000-000000000013', 'prothetic3', 'Prothetic Three', 'prothetic3@example.com', 'Belgrade', now() - interval '45 days');

INSERT INTO prosthetics (client_id, model, serial_number, fitted_at)
VALUES
    ((SELECT id FROM clients WHERE username = 'prothetic1'), 'BionicPRO Arm X1', 'BPX1-0001', now() - interval '80 days'),
    ((SELECT id FROM clients WHERE username = 'prothetic2'), 'BionicPRO Arm X2', 'BPX2-0002', now() - interval '50 days'),
    ((SELECT id FROM clients WHERE username = 'prothetic3'), 'BionicPRO Hand H1', 'BPH1-0003', now() - interval '40 days');

INSERT INTO telemetry (prosthetic_id, metric, value, ts)
SELECT
    p.id,
    m.metric,
    CASE
        WHEN m.metric = 'steps' THEN round(20 + random() * 180)::float8
        WHEN m.metric = 'battery_level' THEN round(35 + random() * 65)::float8
        ELSE round(random() * 500)::float8
    END,
    hour_ts
FROM generate_series(date_trunc('hour', now()) - interval '30 days', date_trunc('hour', now()) - interval '1 hour', interval '1 hour') AS hour_ts
CROSS JOIN prosthetics p
CROSS JOIN (VALUES ('steps'), ('battery_level'), ('grip_cycles')) AS m(metric);
