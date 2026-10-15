
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from pymongo.errors import DuplicateKeyError

from app.database import (
    employees_collection,
    attendance_logs_collection,
)

router = APIRouter()
IST = ZoneInfo("Asia/Kolkata")

DAY_SECONDS = 24 * 60 * 60
GRACE_SECONDS = 10 * 60
MIN_OVERTIME_SECONDS = 30 * 60


def validate_epoch_ms(value):
    """Accept only integer Unix timestamps in milliseconds."""
    if value is None:
        return value

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Timestamp must be an integer in milliseconds.")

    # Reject epoch seconds and other clearly invalid small values.
    if value < 100000000000:
        raise ValueError("Timestamp must be epoch milliseconds.")

    try:
        datetime.fromtimestamp(value // 1000, timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise ValueError("Timestamp is outside the supported range.")

    return value


def to_utc_aware(value: datetime) -> datetime:
    """Normalize MongoDB datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def epoch_ms(value: datetime) -> int:
    """Convert a datetime to Unix epoch milliseconds."""
    return int(to_utc_aware(value).timestamp() * 1000)


def rounded_hours(seconds) -> float:
    """Round work hours to two decimal places using half-up rounding."""
    hours = Decimal(str(seconds)) / Decimal(3600)
    return float(
        hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def validate_iso_date(value, field_name):
    """Validate a calendar date in YYYY-MM-DD format."""
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field_name} must be a valid date "
                "in YYYY-MM-DD format."
            ),
        )


def parse_shift_time(value: str, field_name: str) -> tuple[int, int]:
    """Validate a shift time formatted as HH:MM."""
    try:
        parsed = datetime.strptime(value, "%H:%M")
        if parsed.strftime("%H:%M") != value:
            raise ValueError
        return parsed.hour, parsed.minute
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=500,
            detail=f"Employee has an invalid {field_name} shift time.",
        )


def calculate_late_minutes(
    local_time: datetime,
    start_minutes: int,
    end_minutes: int,
) -> int:
    """
    Calculate late minutes under the attendance rules.

    - The 10-minute grace period is strict: exactly 10 minutes is not late.
    - late_minutes counts whole elapsed minutes since shift start.
    - For overnight shifts, early-morning punches belong to the previous
      shift and are not treated as late starts.
    - A punch between the overnight shift's end and start is an early
      punch for the next shift, not a late punch.
    """
    current_minutes = local_time.hour * 60 + local_time.minute
    current_seconds = (
        local_time.hour * 3600
        + local_time.minute * 60
        + local_time.second
    )

    start_seconds = start_minutes * 60
    overnight = end_minutes <= start_minutes

    if not overnight:
        elapsed_seconds = current_seconds - start_seconds

    elif current_minutes < end_minutes:
        # Early-morning portion of the previous overnight shift.
        elapsed_seconds = 0

    elif current_minutes >= start_minutes:
        # At or after the start of the overnight shift.
        elapsed_seconds = current_seconds - start_seconds

    else:
        # Between the overnight shift end and start.
        elapsed_seconds = 0

    if elapsed_seconds > GRACE_SECONDS:
        return elapsed_seconds // 60

    return 0


class PunchInRequest(BaseModel):
    emp_code: str
    punched_at: int | None = None
    status: Literal["PRESENT", "WFH", "ON_DUTY"] = "PRESENT"

    @field_validator("punched_at", mode="before")
    @classmethod
    def validate_punch_timestamp(cls, value):
        return validate_epoch_ms(value)


class PunchOutRequest(BaseModel):
    emp_code: str
    punched_at: int | None = None

    @field_validator("punched_at", mode="before")
    @classmethod
    def validate_punch_timestamp(cls, value):
        return validate_epoch_ms(value)


# Enforce one attendance record per employee per IST date.
# This unique index is the primary protection against concurrent duplicates.
attendance_logs_collection.create_index(
    [("emp_code", 1), ("date", 1)],
    unique=True,
    name="unique_employee_attendance_date",
)


@router.post("/attendance/punch-in", status_code=201)
def punch_in(request: PunchInRequest):
    employee = employees_collection.find_one(
        {"emp_code": request.emp_code}
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found.",
        )

    instant_ms = request.punched_at
    if instant_ms is None:
        instant_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Truncate to whole seconds before calculations and storage.
    instant_ms = (instant_ms // 1000) * 1000

    punch_time = datetime.fromtimestamp(
        instant_ms // 1000,
        timezone.utc,
    )
    local_time = punch_time.astimezone(IST)

    shift_start = employee.get("shift_start", "09:30")
    shift_end = employee.get("shift_end", "18:30")

    start_hour, start_minute = parse_shift_time(
        shift_start, "start"
    )
    end_hour, end_minute = parse_shift_time(
        shift_end, "end"
    )

    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute
    current_minutes = local_time.hour * 60 + local_time.minute

    overnight = end_minutes <= start_minutes

    # Determine the attendance date in IST.
    attendance_date = local_time.date()

    if overnight and current_minutes < end_minutes:
        # An early-morning punch belongs to the previous shift date.
        attendance_date -= timedelta(days=1)

    late_minutes = calculate_late_minutes(
        local_time,
        start_minutes,
        end_minutes,
    )

    record = {
        "emp_code": request.emp_code,
        "date": attendance_date.isoformat(),
        "status": request.status,
        "punch_in": punch_time,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": int(late_minutes),
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }

    try:
        attendance_logs_collection.insert_one(record)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Employee has already punched in for this date.",
        )

    record.pop("_id", None)
    record["punch_in"] = instant_ms

    return record


@router.post("/attendance/punch-out", status_code=200)
def punch_out(request: PunchOutRequest):
    employee = employees_collection.find_one(
        {"emp_code": request.emp_code}
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found.",
        )

    instant_ms = request.punched_at
    if instant_ms is None:
        instant_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    instant_ms = (instant_ms // 1000) * 1000

    punch_out_time = datetime.fromtimestamp(
        instant_ms // 1000,
        timezone.utc,
    )

    # Find the latest punch-in at or before the requested punch-out time.
    record = attendance_logs_collection.find_one(
        {
            "emp_code": request.emp_code,
            "punch_in": {"$ne": None, "$lte": punch_out_time},
        },
        sort=[("punch_in", -1)],
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="No matching punch-in record found.",
        )

    if record.get("punch_out") is not None:
        raise HTTPException(
            status_code=409,
            detail="Employee has already punched out.",
        )

    punch_in_time = to_utc_aware(record["punch_in"])

    duration_seconds = (
        punch_out_time - punch_in_time
    ).total_seconds()

    if duration_seconds <= 0 or duration_seconds > DAY_SECONDS:
        raise HTTPException(
            status_code=422,
            detail="Punch-out must be after punch-in and within 24 hours.",
        )

    work_hours = rounded_hours(duration_seconds)

    shift_start = employee.get("shift_start", "09:30")
    shift_end = employee.get("shift_end", "18:30")

    start_hour, start_minute = parse_shift_time(
        shift_start, "start"
    )
    end_hour, end_minute = parse_shift_time(
        shift_end, "end"
    )

    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute
    overnight = end_minutes <= start_minutes

    attendance_date = datetime.strptime(
        record["date"], "%Y-%m-%d"
    ).date()

    shift_end_date = attendance_date
    if overnight:
        shift_end_date += timedelta(days=1)

    shift_end_local = datetime(
        shift_end_date.year,
        shift_end_date.month,
        shift_end_date.day,
        end_hour,
        end_minute,
        tzinfo=IST,
    )

    shift_end_utc = shift_end_local.astimezone(timezone.utc)

    overtime_seconds = (
        punch_out_time - shift_end_utc
    ).total_seconds()

    overtime_minutes = 0
    if overtime_seconds >= MIN_OVERTIME_SECONDS:
        overtime_minutes = int(overtime_seconds // 60)

    half_day = work_hours < 4.50

    # Atomic conditional update: only one concurrent punch-out can win.
    result = attendance_logs_collection.update_one(
        {
            "_id": record["_id"],
            "punch_out": None,
        },
        {
            "$set": {
                "punch_out": punch_out_time,
                "work_hours": work_hours,
                "overtime_minutes": overtime_minutes,
                "half_day": half_day,
            }
        },
    )

    if result.modified_count != 1:
        raise HTTPException(
            status_code=409,
            detail="Employee has already punched out.",
        )

    record["punch_in"] = epoch_ms(punch_in_time)
    record["punch_out"] = instant_ms
    record["work_hours"] = work_hours
    record["overtime_minutes"] = overtime_minutes
    record["half_day"] = half_day
    record.pop("_id", None)

    return record


@router.get("/attendance")
def get_attendance(
    emp_code: str | None = None,
    status: Literal[
        "PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"
    ] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    # Validate date filters before building the MongoDB query.
    parsed_from = (
        validate_iso_date(date_from, "date_from")
        if date_from is not None
        else None
    )

    parsed_to = (
        validate_iso_date(date_to, "date_to")
        if date_to is not None
        else None
    )

    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to.",
        )

    query = {}

    if emp_code:
        query["emp_code"] = emp_code

    if status:
        query["status"] = status

    if parsed_from or parsed_to:
        query["date"] = {}

        if parsed_from:
            query["date"]["$gte"] = parsed_from.isoformat()

        if parsed_to:
            query["date"]["$lte"] = parsed_to.isoformat()

    # Count matching records before pagination.
    total = attendance_logs_collection.count_documents(query)

    # Retrieve only the requested page from MongoDB.
    records = list(
        attendance_logs_collection.find(
            query,
            {"_id": 0},
        )
        .sort([("date", -1), ("emp_code", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    # Convert MongoDB timestamps to epoch milliseconds.
    for record in records:
        if record.get("punch_in") is not None:
            record["punch_in"] = epoch_ms(record["punch_in"])

        if record.get("punch_out") is not None:
            record["punch_out"] = epoch_ms(record["punch_out"])

        # Convert timestamps stored in audit-history entries.
        for item in record.get("history", []):
            for field in ("punch_in", "punch_out"):
                if isinstance(item.get(field), datetime):
                    item[field] = epoch_ms(item[field])

            if isinstance(item.get("corrected_at"), datetime):
                item["corrected_at"] = epoch_ms(
                    item["corrected_at"]
                )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "records": records,
    }
