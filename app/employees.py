
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import DuplicateKeyError

from app.database import employees_collection
from app.models import EmployeeCreate

router = APIRouter()


def epoch_ms(value: datetime) -> int:
    """Convert a datetime to epoch milliseconds."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return int(value.timestamp() * 1000)


@router.post("/employees", status_code=201)
def create_employee(employee: EmployeeCreate):
    employee_data = employee.model_dump(mode="json")

    # Store creation time as epoch milliseconds.
    employee_data["created_at"] = epoch_ms(
        datetime.now(timezone.utc)
    )

    try:
        # Insert a copy so MongoDB's _id does not affect the response.
        employees_collection.insert_one(employee_data.copy())
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Employee code already exists.",
        )

    return employee_data


@router.get("/employees")
def list_employees(
    department: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    query = {}

    if department:
        query["department"] = department

    total = employees_collection.count_documents(query)

    employees = list(
        employees_collection.find(query, {"_id": 0})
        .sort("emp_code", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "employees": employees,
    }
