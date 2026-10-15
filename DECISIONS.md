# Technical Decisions

## FastAPI

FastAPI was selected to build HTTP API endpoints and provide automatic OpenAPI documentation and request validation.

## MongoDB and PyMongo

MongoDB stores employee and attendance records. PyMongo provides database access and supports indexes and aggregation queries.

## Pydantic Validation

Pydantic models validate incoming employee data, including employee codes, email format, dates, and shift times.

## Modular Application Structure

The application separates employee management, attendance, analytics, administration, and database setup into different modules. This improves readability and maintainability.

## Attendance Dates and Time

The attendance implementation uses date-based records and timezone-aware datetime handling. India Standard Time is relevant to attendance calculations. Timestamp conventions should remain consistent across storage, API responses, and analytics.

## Indexes and Query Performance

Database indexes support frequent lookups and help enforce uniqueness where configured. Query plans can be inspected to evaluate index usage.

## Configuration and Secrets

Database connection settings are loaded from environment configuration. Credentials and `.env` files must not be committed to the public repository.

## Current Trade-offs

Authentication, automated testing, and production deployment are not yet implemented. These are acknowledged limitations rather than completed features.
