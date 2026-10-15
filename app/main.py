
from contextlib import asynccontextmanager
from app.employees import router as employees_router
from app.attendance import router as attendance_router
from app.analytics import router as analytics_router
from app.admin import router as admin_router
from fastapi import FastAPI

from app.database import (
    client,
    check_database_connection,
    create_database_indexes,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_connection()
    print("MongoDB connection successful!")

    create_database_indexes()
    print("MongoDB indexes created successfully!")

    try:
        yield
    finally:
        client.close()
        print("MongoDB connection closed.")


app = FastAPI(
    title="Employee Attendance & Analytics API",
    description="Employee management, attendance tracking, and analytics.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(employees_router)
app.include_router(attendance_router)
app.include_router(analytics_router)
app.include_router(admin_router)
@app.get("/")
def root():
    return {
        "message": "Employee Attendance & Analytics API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "connected",
    }
