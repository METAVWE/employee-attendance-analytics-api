
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

MONGO_DB = (
    os.getenv("MONGO_DB")
    or os.getenv("MONGODB_DATABASE")
    or "employee_attendance"
)

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is missing. Check your .env file."
    )

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
)

db = client[MONGO_DB]

employees_collection = db["employees"]
attendance_logs_collection = db["attendance_logs"]


def check_database_connection():
    """Check whether MongoDB Atlas is reachable."""
    return client.admin.command("ping")


def create_database_indexes():
    """Create indexes required for employee and attendance queries."""

    # Fast employee lookups; employee codes must be unique.
    employees_collection.create_index(
        [("emp_code", 1)],
        unique=True,
        name="unique_employee_code",
    )

    # Faster filtering by department.
    employees_collection.create_index(
        [("department", 1)],
        name="department_lookup",
    )

    # Prevent duplicate attendance records for an employee on a date.
    attendance_logs_collection.create_index(
        [("emp_code", 1), ("date", 1)],
        unique=True,
        name="unique_employee_attendance_date",
    )

    
    # Supports sorting late attendance records by late minutes.
    attendance_logs_collection.create_index(
        [("late_minutes", -1)],
        name="late_minutes_desc",
    )

