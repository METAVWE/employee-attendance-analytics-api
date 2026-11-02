
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.database import (
    employees_collection,
    attendance_logs_collection,
)

PREFIX = "PERF_"
EMPLOYEE_COUNT = 100
RECORDS_PER_EMPLOYEE = 1000
BATCH_SIZE = 5000


def round_hours(seconds):
    value = Decimal(seconds) / Decimal(3600)
    return float(
        value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def main():
    print("=== Employee Attendance API Performance Test ===")
    print(f"Employees to create: {EMPLOYEE_COUNT}")
    print(
        "Attendance records to create:",
        EMPLOYEE_COUNT * RECORDS_PER_EMPLOYEE,
    )

    # Refuse to overwrite an earlier test run.
    existing = employees_collection.count_documents(
        {"emp_code": {"$regex": "^PERF_"}}
    )
    if existing:
        print(
            f"Found {existing} existing PERF_ employees. "
            "Clean up the previous test data before running again."
        )
        return

    employee_docs = []
    for i in range(EMPLOYEE_COUNT):
        employee_docs.append({
            "emp_code": f"PERF_{i:03d}",
            "name": f"Performance Employee {i:03d}",
            "department": "PerformanceTest",
            "joined_on": "2024-01-01",
            "created_at": datetime.now(timezone.utc),
        })

    start = time.perf_counter()
    employees_collection.insert_many(employee_docs, ordered=False)
    print(f"Employee insertion: {time.perf_counter() - start:.2f} seconds")

    # 1,000 distinct calendar dates per employee.
    first_day = date(2024, 1, 1)
    total = EMPLOYEE_COUNT * RECORDS_PER_EMPLOYEE
    batch = []
    inserted = 0

    start = time.perf_counter()

    for employee_number in range(EMPLOYEE_COUNT):
        emp_code = f"PERF_{employee_number:03d}"

        for day_number in range(RECORDS_PER_EMPLOYEE):
            work_date = first_day + timedelta(days=day_number)
            date_string = work_date.isoformat()

            # Example shift: 09:30–18:00 IST.
            punch_in_utc = datetime.combine(
                work_date,
                datetime_time(4, 0),
                tzinfo=timezone.utc,
            )
            punch_out_utc = datetime.combine(
                work_date,
                datetime_time(12, 30),
                tzinfo=timezone.utc,
            )

            batch.append({
                "emp_code": emp_code,
                "date": date_string,
                "status": "PRESENT",
                "punch_in": punch_in_utc,
                "punch_out": punch_out_utc,
                "work_hours": round_hours(8.5 * 3600),
                "late_minutes": 0,
                "overtime_minutes": 0,
                "half_day": False,
                "history": [],
            })

            if len(batch) >= BATCH_SIZE:
                attendance_logs_collection.insert_many(
                    batch, ordered=False
                )
                inserted += len(batch)
                batch.clear()
                print(f"Inserted {inserted:,}/{total:,} records")

    if batch:
        attendance_logs_collection.insert_many(batch, ordered=False)
        inserted += len(batch)

    print(
        f"Attendance insertion: {time.perf_counter() - start:.2f} seconds"
    )
    print(f"Total inserted: {inserted:,}")

    # Test 1: Employee/date lookup using the compound index.
    query = {
        "emp_code": "PERF_050",
        "date": "2025-06-15",
    }

    start = time.perf_counter()
    found = list(attendance_logs_collection.find(query))
    query_seconds = time.perf_counter() - start

    explain = attendance_logs_collection.database.command(
        "explain",
        {
            "find": attendance_logs_collection.name,
            "filter": query,
        },
        verbosity="executionStats",
    )

    winning_plan = explain.get("queryPlanner", {}).get(
        "winningPlan", {}
    )
    print("\n=== Indexed Lookup ===")
    print(f"Records returned: {len(found)}")
    print(f"Query time: {query_seconds * 1000:.2f} ms")
    print("Winning plan:", winning_plan)
    print(
        "Execution stats:",
        explain.get("executionStats", {}),
    )

    # Test 2: Aggregation over the test employees' records.
    pipeline = [
        {
            "$match": {
                "emp_code": {"$regex": "^PERF_"},
                "date": {
                    "$gte": "2025-01-01",
                    "$lte": "2025-12-31",
                },
            }
        },
        {
            "$group": {
                "_id": "$emp_code",
                "record_count": {"$sum": 1},
                "average_hours": {"$avg": "$work_hours"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    start = time.perf_counter()
    aggregation_result = list(
        attendance_logs_collection.aggregate(pipeline)
    )
    aggregation_seconds = time.perf_counter() - start

    print("\n=== Aggregation Test ===")
    print(f"Employees aggregated: {len(aggregation_result)}")
    print(f"Aggregation time: {aggregation_seconds:.2f} seconds")
    print("Sample results:", aggregation_result[:3])

    print("\nPerformance test completed.")
    print("Test records remain in MongoDB.")
    print("Run cleanup only after reviewing the results.")


if __name__ == "__main__":
    main()
