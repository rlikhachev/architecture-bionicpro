import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import psycopg2
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

CRM_DSN = "host=crm_db port=5432 dbname=crm_db user=crm_user password=crm_password"
CLICKHOUSE_URL = "http://clickhouse:8123"
MART_TABLE = "reports_dm.mart_user_reports"
WATERMARK_TABLE = "reports_dm.etl_watermark"
MART_NAME = "mart_user_reports"

EXTRACT_SQL = """
SELECT
    to_char(date_trunc('day', t.ts), 'YYYY-MM-DD') AS report_date,
    c.keycloak_user_id AS user_id,
    c.username AS username,
    p.model AS prosthetic_model,
    p.serial_number AS serial_number,
    COALESCE(SUM(t.value) FILTER (WHERE t.metric = 'steps'), 0)::bigint AS steps,
    COALESCE(ROUND(AVG(t.value) FILTER (WHERE t.metric = 'battery_level')::numeric, 2), 0)::float8 AS battery_avg,
    COALESCE(SUM(t.value) FILTER (WHERE t.metric = 'grip_cycles'), 0)::bigint AS grip_cycles,
    COUNT(DISTINCT date_trunc('hour', t.ts))::bigint AS usage_hours
FROM telemetry t
JOIN prosthetics p ON p.id = t.prosthetic_id
JOIN clients c ON c.id = p.client_id
WHERE t.ts >= %(since)s AND t.ts < %(until)s
GROUP BY 1, 2, 3, 4, 5
ORDER BY 1, 2
"""

default_args = {
    "owner": "bionicpro",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def ch_execute(query: str, body: str = "") -> str:
    response = requests.post(f"{CLICKHOUSE_URL}/?query={quote(query)}", data=body.encode("utf-8"), timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"ClickHouse error {response.status_code}: {response.text}")
    return response.text


def read_watermark() -> tuple[str | None, int]:
    text = ch_execute(
        f"SELECT last_processed_date, report_version FROM {WATERMARK_TABLE} FINAL WHERE mart = '{MART_NAME}' LIMIT 1"
    ).strip()
    if not text:
        return None, 0
    last_date, version = text.split("\t")
    return last_date, int(version)


def extract_from_crm(since: datetime, until: datetime) -> list[dict]:
    with psycopg2.connect(CRM_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(EXTRACT_SQL, {"since": since, "until": until})
            columns = [d[0] for d in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def load_to_clickhouse(rows: list[dict]) -> None:
    if not rows:
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    for row in rows:
        record = dict(row)
        record["updated_at"] = now
        lines.append(json.dumps(record, ensure_ascii=False))
    ch_execute(f"INSERT INTO {MART_TABLE} FORMAT JSONEachRow", body="\n".join(lines))


def write_watermark(last_date: str, version: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    body = json.dumps(
        {"mart": MART_NAME, "last_processed_date": last_date, "report_version": version, "updated_at": now}
    )
    ch_execute(f"INSERT INTO {WATERMARK_TABLE} FORMAT JSONEachRow", body=body)


def run_etl(**context) -> None:
    logical_time = context["data_interval_end"]
    until = datetime(logical_time.year, logical_time.month, logical_time.day, tzinfo=timezone.utc)

    watermark, version = read_watermark()
    if watermark:
        since = datetime.fromisoformat(watermark) + timedelta(days=1)
        since = datetime(since.year, since.month, since.day, tzinfo=timezone.utc)
    else:
        since = until - timedelta(days=30)

    if since < until:
        rows = extract_from_crm(since, until)
        print(f"extracted {len(rows)} rows for period {since.date()}..{(until - timedelta(days=1)).date()}")
        load_to_clickhouse(rows)
        if rows:
            last_date = max(row["report_date"] for row in rows)
        else:
            last_date = (until - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        last_date = watermark or (until - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"nothing new to process: watermark={watermark}, until={until.date()}")

    new_version = version + 1
    write_watermark(last_date, new_version)
    print(f"watermark={last_date}, report_version={new_version}")


with DAG(
    dag_id="report_etl",
    description="ETL: CRM + telemetry -> ClickHouse mart_user_reports",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 * * * *",
    is_paused_upon_creation=False,
    catchup=False,
    tags=["bionicpro", "reports"],
) as dag:
    PythonOperator(task_id="crm_to_clickhouse", python_callable=run_etl)
