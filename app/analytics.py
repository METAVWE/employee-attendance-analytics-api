
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, Query

from app.database import (
    employees_collection,
    attendance_logs_collection,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

PRESENT_STATUSES = ["PRESENT", "WFH", "ON_DUTY"]


def count_working_days(start_date: date, end_date: date) -> int:
    """Count weekdays, including both endpoints."""
    if start_date > end_date:
        return 0

    total = 0
    current = start_date

    while current <= end_date:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)

    return total


def round_half_up(value, places=4):
    """Round using decimal ROUND_HALF_UP."""
    quantum = Decimal("1").scaleb(-places)
    return float(
        Decimal(str(value)).quantize(
            quantum,
            rounding=ROUND_HALF_UP,
        )
    )


def parse_joined_on(value) -> date:
    """Read either the current or legacy employee joining-date field."""
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return date.fromisoformat(value[:10])

    raise ValueError("Invalid joining date")


def get_joined_on(employee) -> date:
    """Prefer joined_on but support older date_of_joining records."""
    value = employee.get("joined_on") or employee.get("date_of_joining")

    if not value:
        raise ValueError("Missing joining date")

    return parse_joined_on(value)


def month_bounds(year: int, month: int):
    """Return the first and last calendar dates of a month."""
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, end


def attendance_weekday_expression():
    """MongoDB weekday expression: Monday-Friday in India."""
    return {
        "$in": [
            {
                "$dayOfWeek": {
                    "$dateFromString": {
                        "dateString": "$date",
                        "format": "%Y-%m-%d",
                        "timezone": "Asia/Kolkata",
                    }
                }
            },
            [2, 3, 4, 5, 6],
        ]
    }


@router.get("/employees/{emp_code}/monthly")
def employee_monthly_analytics(
    emp_code: str,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    employee = employees_collection.find_one(
        {"emp_code": emp_code},
        {"_id": 0},
    )

    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    month_start, month_end = month_bounds(year, month)

    try:
        joined_on = get_joined_on(employee)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="Employee joining date is missing or invalid.",
        )

    eligible_start = max(month_start, joined_on)

    working_days = (
        count_working_days(eligible_start, month_end)
        if eligible_start <= month_end
        else 0
    )

    if eligible_start > month_end:
        stats = {}
    else:
        pipeline = [
            {
                "$match": {
                    "emp_code": emp_code,
                    "date": {
                        "$gte": eligible_start.isoformat(),
                        "$lte": month_end.isoformat(),
                    },
                }
            },
            {
                "$addFields": {
                    "is_weekday": attendance_weekday_expression(),
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_records": {"$sum": 1},
                    "present_days": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$in": ["$status", PRESENT_STATUSES]},
                                        "$is_weekday",
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "absent_days": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "ABSENT"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "leave_days": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "LEAVE"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "late_days": {
                        "$sum": {
                            "$cond": [
                                {"$gt": ["$late_minutes", 0]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_late_minutes": {
                        "$sum": {"$ifNull": ["$late_minutes", 0]}
                    },
                    "total_overtime_minutes": {
                        "$sum": {"$ifNull": ["$overtime_minutes", 0]}
                    },
                    "half_days": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$half_day", True]},
                                1,
                                0,
                            ]
                        }
                    },
                    "average_work_hours": {"$avg": "$work_hours"},
                }
            },
        ]

        results = list(attendance_logs_collection.aggregate(pipeline))
        stats = results[0] if results else {}

    present_days = stats.get("present_days", 0)

    attendance_rate = (
        round_half_up(present_days / working_days, 4)
        if working_days > 0
        else 0.0
    )

    average_hours = stats.get("average_work_hours")

    return {
        "emp_code": emp_code,
        "name": employee.get("name"),
        "department": employee.get("department"),
        "year": year,
        "month": month,
        "joined_on": joined_on.isoformat(),
        "working_days": working_days,
        "present_days": present_days,
        "present_weekdays": present_days,
        "absent_days": stats.get("absent_days", 0),
        "leave_days": stats.get("leave_days", 0),
        "late_days": stats.get("late_days", 0),
        "total_late_minutes": stats.get("total_late_minutes", 0),
        "total_overtime_minutes": stats.get("total_overtime_minutes", 0),
        "half_days": stats.get("half_days", 0),
        "average_work_hours": (
            round_half_up(average_hours, 2)
            if average_hours is not None
            else None
        ),
        "attendance_rate": attendance_rate,
    }


@router.get("/departments/summary")
def department_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    month_start, month_end = month_bounds(year, month)
    start_str = month_start.isoformat()
    end_str = month_end.isoformat()

    # Count employees who joined on or before the month's final day.
    # Support both current and legacy joining-date fields.
    employee_pipeline = [
        {
            "$addFields": {
                "effective_joined_on": {
                    "$ifNull": ["$joined_on", "$date_of_joining"]
                }
            }
        },
        {
            "$addFields": {
                "joined_date_parsed": {
                    "$convert": {
                        "input": "$effective_joined_on",
                        "to": "date",
                        "onError": None,
                        "onNull": None,
                    }
                }
            }
        },
        {
            "$match": {
                "joined_date_parsed": {
                    "$ne": None,
                    "$lt": datetime.combine(
                        month_end + timedelta(days=1),
                        datetime.min.time(),
                    ),
                }
            }
        },
        {
            "$group": {
                "_id": "$department",
                "headcount": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    employee_results = list(
        employees_collection.aggregate(employee_pipeline)
    )

    # Aggregate monthly attendance by department.
    # employees_with_attendance is based on distinct employee codes,
    # not the number of daily attendance records.
    attendance_pipeline = [
        {
            "$match": {
                "date": {"$gte": start_str, "$lte": end_str}
            }
        },
        {
            "$lookup": {
                "from": employees_collection.name,
                "localField": "emp_code",
                "foreignField": "emp_code",
                "as": "employee",
            }
        },
        {"$unwind": "$employee"},
        {
            "$group": {
                "_id": "$employee.department",

                "present_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$in": ["$status", PRESENT_STATUSES]},
                                    attendance_weekday_expression(),
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                "absent_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$status", "ABSENT"]},
                                    attendance_weekday_expression(),
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                "leave_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$status", "LEAVE"]},
                                    attendance_weekday_expression(),
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                # Late and overtime include weekend attendance records.
                "late_days": {
                    "$sum": {
                        "$cond": [
                            {"$gt": ["$late_minutes", 0]},
                            1,
                            0,
                        ]
                    }
                },

                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                },

                "total_overtime_minutes": {
                    "$sum": {"$ifNull": ["$overtime_minutes", 0]}
                },

                # Average across qualifying attendance records.
                "average_work_hours": {"$avg": "$work_hours"},

                # Kept separately for internal aggregation/debugging.
                "attendance_records": {"$sum": 1},

                # Each employee is counted only once per department/month.
                "employee_codes": {"$addToSet": "$emp_code"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    attendance_results = list(
        attendance_logs_collection.aggregate(attendance_pipeline)
    )

    attendance_by_department = {
        item["_id"]: item for item in attendance_results
    }

    departments = []

    for employee_result in employee_results:
        department = employee_result["_id"]
        attendance = attendance_by_department.get(department, {})
        average_hours = attendance.get("average_work_hours")

        departments.append({
            "department": department,
            "headcount": employee_result["headcount"],

            # FIX: unique employees, not total attendance records.
            "employees_with_attendance": len(
                attendance.get("employee_codes", [])
            ),

            "present_days": attendance.get("present_days", 0),
            "absent_days": attendance.get("absent_days", 0),
            "leave_days": attendance.get("leave_days", 0),
            "late_days": attendance.get("late_days", 0),
            "total_late_minutes": attendance.get("total_late_minutes", 0),
            "total_overtime_minutes": attendance.get(
                "total_overtime_minutes", 0
            ),
            "average_work_hours": (
                round_half_up(average_hours, 2)
                if average_hours is not None
                else None
            ),
        })

    return {
        "year": year,
        "month": month,
        "departments": departments,
    }


@router.get("/leaderboard/late")
def late_arrival_leaderboard(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    limit: int = Query(10, ge=1, le=100),
):
    month_start, month_end = month_bounds(year, month)

    pipeline = [
        {
            "$match": {
                "date": {
                    "$gte": month_start.isoformat(),
                    "$lte": month_end.isoformat(),
                },
                "late_minutes": {"$gt": 0},
            }
        },
        {
            "$group": {
                "_id": "$emp_code",
                "late_days": {"$sum": 1},
                "total_late_minutes": {"$sum": "$late_minutes"},
            }
        },
        {
            "$lookup": {
                "from": employees_collection.name,
                "localField": "_id",
                "foreignField": "emp_code",
                "as": "employee",
            }
        },
        {"$unwind": "$employee"},
        {
            "$project": {
                "_id": 0,
                "emp_code": "$_id",
                "name": "$employee.name",
                "department": "$employee.department",
                "late_days": 1,
                "total_late_minutes": 1,
            }
        },
        {
            "$sort": {
                "total_late_minutes": -1,
                "emp_code": 1,
            }
        },
        {
            "$setWindowFields": {
                "sortBy": {"total_late_minutes": -1},
                "output": {"rank": {"$rank": {}}},
            }
        },
        # Include every employee tied at the cutoff rank.
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"rank": 1, "emp_code": 1}},
    ]

    results = list(attendance_logs_collection.aggregate(pipeline))

    return {
        "year": year,
        "month": month,
        "limit": limit,
        "count": len(results),
        "leaderboard": results,
    }


@router.get("/departments/{department}/trend")
def department_attendance_trend(
    department: str,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    month_start, month_end = month_bounds(year, month)

    if not employees_collection.find_one(
        {"department": department},
        {"_id": 1},
    ):
        raise HTTPException(
            status_code=404,
            detail="Department not found.",
        )

    pipeline = [
        {
            "$match": {
                "date": {
                    "$gte": month_start.isoformat(),
                    "$lte": month_end.isoformat(),
                }
            }
        },
        {
            "$lookup": {
                "from": employees_collection.name,
                "localField": "emp_code",
                "foreignField": "emp_code",
                "as": "employee",
            }
        },
        {"$unwind": "$employee"},
        {"$match": {"employee.department": department}},
        {
            "$addFields": {
                "is_weekday": attendance_weekday_expression(),
            }
        },
        {
            "$group": {
                "_id": "$date",

                "present_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$in": ["$status", PRESENT_STATUSES]},
                                    "$is_weekday",
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                "absent_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$status", "ABSENT"]},
                                    "$is_weekday",
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                "leave_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$status", "LEAVE"]},
                                    "$is_weekday",
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },

                # Weekend records still count for late/overtime.
                "late_days": {
                    "$sum": {
                        "$cond": [
                            {"$gt": ["$late_minutes", 0]},
                            1,
                            0,
                        ]
                    }
                },

                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                },

                "total_overtime_minutes": {
                    "$sum": {"$ifNull": ["$overtime_minutes", 0]}
                },
            }
        },
        {"$sort": {"_id": 1}},
    ]

    results = list(attendance_logs_collection.aggregate(pipeline))
    daily_data = {item["_id"]: item for item in results}

    daily_trend = []
    current_date = month_start

    while current_date <= month_end:
        key = current_date.isoformat()
        item = daily_data.get(key, {})

        daily_trend.append({
            "date": key,
            "present_days": item.get("present_days", 0),
            "absent_days": item.get("absent_days", 0),
            "leave_days": item.get("leave_days", 0),
            "late_days": item.get("late_days", 0),
            "total_late_minutes": item.get("total_late_minutes", 0),
            "total_overtime_minutes": item.get("total_overtime_minutes", 0),
        })

        current_date += timedelta(days=1)

    # Shorten the window for the first six days of the month.
    for index, item in enumerate(daily_trend):
        window = daily_trend[max(0, index - 6):index + 1]

        item["moving_average_7_day"] = round_half_up(
            sum(day["present_days"] for day in window) / len(window),
            2,
        )

    return {
        "department": department,
        "year": year,
        "month": month,
        "days": len(daily_trend),
        "trend": daily_trend,
    }
