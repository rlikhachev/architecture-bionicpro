from datetime import date, datetime, timedelta, timezone
import json
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from .auth import get_current_user, reject
from .config import settings
from .reports_store import read_cdc_last_date, read_crm_report, read_watermark
from .s3_store import s3_store

app = FastAPI(title="bionicpro-api")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/reports")
async def get_reports(
    request: Request,
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
):
    claims = await get_current_user(request)
    if claims is None:
        return reject("not authenticated", 401)

    user_id = claims.get("sub")
    if not user_id:
        return reject("invalid token", 401)

    last_processed = read_cdc_last_date()
    if last_processed is None:
        return JSONResponse(
            {
                "error": "report data has not been processed yet",
                "detail": "no CDC data in reports_dm.mart_crm_reports; try again later",
            },
            status_code=409,
        )

    watermark = read_watermark()
    report_version = watermark[1] if watermark else 1

    if date_to is None:
        date_to = last_processed
    if date_from is None:
        date_from = date_to - timedelta(days=settings.default_report_days - 1)
    if date_from > date_to:
        return reject("date_from must be <= date_to", 400)

    if date_to > last_processed:
        return JSONResponse(
            {
                "error": "requested period has not been processed yet",
                "detail": f"data is available only up to {last_processed.isoformat()}",
                "last_processed_date": last_processed.isoformat(),
            },
            status_code=409,
        )

    object_key = f"{user_id}/v{report_version}/{date_from.isoformat()}_{date_to.isoformat()}.json"
    report_url = f"{settings.cdn_base_url.rstrip('/')}/{object_key}"

    if s3_store.exists(object_key):
        return {
            "report_url": report_url,
            "cached": True,
            "storage": "s3",
            "user_id": user_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "report_version": report_version,
            "last_processed_date": last_processed.isoformat(),
        }

    days = read_crm_report(user_id, date_from, date_to)
    payload = {
        "user_id": user_id,
        "username": claims.get("preferred_username"),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "report_version": report_version,
        "last_processed_date": last_processed.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "clickhouse:reports_dm.mart_crm_reports (CDC: Debezium -> Kafka -> ClickHouse)",
        "days": days,
    }
    s3_store.put_json(object_key, json.dumps(payload, ensure_ascii=False))

    return {
        "report_url": report_url,
        "cached": False,
        "storage": "s3",
        "user_id": user_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "report_version": report_version,
        "last_processed_date": last_processed.isoformat(),
    }
