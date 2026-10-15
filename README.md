# Employee Attendance & Analytics API

A REST API developed using Python, FastAPI, and MongoDB to manage employee records, track attendance, and generate workforce analytics.

## Features

- Create and list employee records.
- Filter and paginate employee lists.
- Record employee punch-in and punch-out.
- Calculate late arrivals and working hours.
- Generate monthly attendance and department analytics.
- Inspect database indexes and query execution plans.

## Technology Stack

- Python
- FastAPI
- MongoDB
- PyMongo
- Pydantic
- Uvicorn

## Project Structure

```text
employee-attendance/
├── app/
│   ├── main.py
│   ├── employees.py
│   ├── attendance.py
│   ├── analytics.py
│   ├── admin.py
│   ├── database.py
│   ├── config.py
│   └── models.py
├── performance_test.py
├── requirements.txt
├── README.md
├── REVIEW.md
├── DECISIONS.md
└── .gitignore
```

## How to Run

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. Install dependencies:

   `pip install -r requirements.txt`

4. Configure your MongoDB connection using a local `.env` file. Follow the environment variable names expected by the application.
5. Start the API:

   `uvicorn app.main:app --reload`

6. Open `http://127.0.0.1:8000/docs` to explore the API endpoints.

Never upload `.env` files, database passwords, or other secrets to GitHub.

## Current Project Status

This is a partial submission. The main API modules and performance test script are included in the repository.

The following work remains incomplete or needs further verification:

- Comprehensive automated unit and integration tests.
- Authentication and role-based authorization.
- A health endpoint that checks actual database connectivity.
- Additional validation and error handling for attendance edge cases.
- Production deployment, monitoring, and rate limiting.
- Testing the complete application in a clean environment.

The API is intended for development and evaluation, not production use with sensitive employee data without appropriate security controls.

## Documentation

- `REVIEW.md` describes known issues and recommended improvements.
- `DECISIONS.md` explains the main technical decisions and trade-offs.

## License

No license has been added yet.

## Incomplete Features and Future Improvements

This project is a partial implementation of an Employee Attendance & Analytics API. The core employee management, attendance tracking, and analytics modules have been developed. The following improvements remain incomplete or require further verification:

1. **Automated Testing:** Comprehensive unit and integration tests are still needed to verify API behavior, attendance calculations, and error handling.

2. **Authentication and Authorization:** Proper user authentication and role-based access control are not implemented. These are required before exposing employee data in a production environment.

3. **Database Health Monitoring:** The health endpoint needs to verify actual MongoDB connectivity instead of relying on a fixed status.

4. **Attendance Validation:** Additional testing and validation are needed for duplicate punch-ins, punch-outs without a corresponding punch-in, invalid timestamps, and other attendance edge cases.

5. **Analytics Verification:** Monthly attendance totals, department summaries, late arrivals, and working-hour calculations need to be validated against known test data.

6. **Performance Testing:** The performance test script is included, but performance results and behavior under concurrent requests need to be verified and documented.

7. **Production Readiness:** Deployment, monitoring, rate limiting, and production configuration are not yet completed.

These limitations are acknowledged as future improvements. The current project is intended for development and evaluation and should not be used to process sensitive employee data in production without appropriate security and reliability controls.