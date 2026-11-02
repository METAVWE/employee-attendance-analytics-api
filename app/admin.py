
from fastapi import APIRouter, HTTPException, Query

from app.database import (
    employees_collection,
    attendance_logs_collection,
)

router = APIRouter(tags=["Admin"])


# Supported query-plan examples and their intended indexes.
SUPPORTED_ENDPOINTS = {
    "employees": {
        "collection": "employees",
        "description": "Find an employee by employee code",
        "filter": {"emp_code": "EMP1001"},
        "sort": None,
        "hint": "unique_employee_code",
    },
    "attendance": {
        "collection": "attendance_logs",
        "description": "Find attendance for an employee and date",
        "filter": {
            "emp_code": "EMP1001",
            "date": "2026-10-15",
        },
        "sort": None,
        "hint": "unique_employee_attendance_date",
    },
    "employee-monthly": {
        "collection": "attendance_logs",
        "description": "Find an employee's attendance for a month",
        "filter": {
            "emp_code": "EMP1001",
            "date": {
                "$gte": "2026-10-01",
                "$lte": "2026-10-31",
            },
        },
        "sort": {"date": 1},
        "hint": "unique_employee_attendance_date",
    },
    "department-summary": {
        "collection": "employees",
        "description": "Find employees in a department",
        "filter": {"department": "Engineering"},
        "sort": None,
        "hint": "department_lookup",
    },
    "leaderboard-late": {
        "collection": "attendance_logs",
        "description": "Find late attendance records for a month",
        "filter": {
            "date": {
                "$gte": "2026-10-01",
                "$lte": "2026-10-31",
            },
            "late_minutes": {"$gt": 0},
        },
        "sort": {"late_minutes": -1},
        "hint": "late_minutes_desc",
    },
}


def collect_plan_details(node, indexes, stages):
    """Collect stage names and index names from a MongoDB query plan."""
    if isinstance(node, dict):
        stage = node.get("stage")
        if stage:
            stages.append(stage)

        index_name = node.get("indexName")
        if index_name:
            indexes.add(index_name)

        for value in node.values():
            collect_plan_details(value, indexes, stages)

    elif isinstance(node, list):
        for item in node:
            collect_plan_details(item, indexes, stages)


@router.get("/admin/explain/{endpoint}")
def explain_endpoint(
    endpoint: str,
    execution_stats: bool = Query(
        False,
        description="Include execution statistics when true",
    ),
):
    """Explain the query plan for a supported MongoDB operation."""

    config = SUPPORTED_ENDPOINTS.get(endpoint)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Unsupported endpoint.",
                "supported_endpoints": list(SUPPORTED_ENDPOINTS.keys()),
            },
        )

    collection = (
        employees_collection
        if config["collection"] == "employees"
        else attendance_logs_collection
    )

    find_command = {
        "find": collection.name,
        "filter": config["filter"],
        "sort": config["sort"] or {},
        "hint": config["hint"],
    }

    verbosity = "executionStats" if execution_stats else "queryPlanner"

    try:
        explain = collection.database.command(
            "explain",
            find_command,
            verbosity=verbosity,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to explain query. Check that the required index "
                f"'{config['hint']}' exists. Details: {str(exc)}"
            ),
        )

    query_planner = explain.get("queryPlanner", {})
    winning_plan = query_planner.get("winningPlan", {})

    indexes = set()
    stages = []

    collect_plan_details(winning_plan, indexes, stages)

    response = {
        "endpoint": endpoint,
        "description": config["description"],
        "collection": config["collection"],
        "filter": config["filter"],
        "sort": config["sort"],
        "indexes_used": sorted(indexes),
        "stages": stages,
        "collection_scan_detected": "COLLSCAN" in stages,
        "winning_plan": winning_plan,
    }

    if execution_stats:
        response["execution_stats"] = explain.get("executionStats", {})

    return response
