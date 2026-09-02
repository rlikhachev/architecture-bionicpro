from datetime import date
from typing import Optional

import clickhouse_connect

from .config import settings

WATERMARK_TABLE = "reports_dm.etl_watermark"
MART_NAME = "mart_user_reports"
CDC_MART_TABLE = "reports_dm.mart_crm_reports"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = clickhouse_connect.get_client(host=settings.clickhouse_host, port=settings.clickhouse_port)
    return _client


def read_watermark() -> Optional[tuple[date, int]]:
    result = get_client().query(
        f"""
        SELECT last_processed_date, report_version
        FROM {WATERMARK_TABLE} FINAL
        WHERE mart = {{mart:String}}
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        parameters={"mart": MART_NAME},
    )
    for row in result.result_rows:
        return row[0], int(row[1])
    return None


def read_cdc_last_date() -> Optional[date]:
    result = get_client().query(f"SELECT max(report_date) FROM {CDC_MART_TABLE}")
    for row in result.result_rows:
        return row[0] if str(row[0]) != "1970-01-01" else None
    return None


def read_crm_report(user_id: str, date_from: date, date_to: date) -> list[dict]:
    result = get_client().query(
        f"""
        SELECT
            report_date,
            any(username) AS username,
            any(prosthetic_model) AS prosthetic_model,
            any(serial_number) AS serial_number,
            round(sum(steps)) AS steps,
            round(sum(battery_sum) / if(sum(battery_count) = 0, 1, sum(battery_count)), 2) AS battery_avg,
            round(sum(grip_cycles)) AS grip_cycles,
            uniqMerge(usage_hours) AS usage_hours
        FROM {CDC_MART_TABLE}
        WHERE user_id = {{user_id:String}}
          AND report_date >= {{date_from:Date}}
          AND report_date <= {{date_to:Date}}
        GROUP BY report_date
        ORDER BY report_date
        """,
        parameters={"user_id": user_id, "date_from": date_from, "date_to": date_to},
    )
    return [
        {
            "report_date": row[0].isoformat(),
            "username": row[1],
            "prosthetic_model": row[2],
            "serial_number": row[3],
            "steps": int(row[4]),
            "battery_avg": float(row[5]),
            "grip_cycles": int(row[6]),
            "usage_hours": int(row[7]),
        }
        for row in result.result_rows
    ]
