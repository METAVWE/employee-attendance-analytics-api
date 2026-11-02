# Employee Attendance & Analytics API

A REST API built with Python, FastAPI, and MongoDB for employee management, attendance tracking, and attendance analytics.

## Features

- Employee listing and lookup
- Attendance record retrieval
- Employee monthly attendance analytics
- Department attendance summary
- Late-arrival leaderboard
- Department attendance trends
- MongoDB indexes for query optimization
- Query execution plan inspection through an admin endpoint
- Paginated employee listing

## Technology Stack

- **Language:** Python
- **API Framework:** FastAPI
- **Database:** MongoDB Atlas
- **Database Driver:** PyMongo
- **API Documentation:** Swagger UI
- **Version Control:** Git and GitHub

## Project Structure

```text
employee-attendance/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── employees.py
│   ├── attendance.py
│   ├── analytics.py
│   └── admin.py
├── .env
├── .gitignore
├── requirements.txt
├── README.md
└── REVIEW.md
```

The structure above describes the expected core files. Additional files may exist in the project.

## Prerequisites

- Python 3.11 or another compatible Python version
- A MongoDB Atlas database or accessible MongoDB instance
- Git (optional, for cloning the repository)

## Installation

### 1. Clone the repository

Replace the placeholder below with the actual URL of your GitHub repository.

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd employee-attendance
```

Alternatively, download the repository and open its folder in VS Code.

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
MONGO_URI=your_mongodb_connection_string
MONGO_DB=employee_attendance
```

Replace the placeholder with your actual MongoDB connection string. Never commit real database credentials to GitHub.

### 5. Start the API

Run this command from the project root:

```powershell
python -m uvicorn app.main:app --reload
```

## API Documentation

After starting the server, open:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **Health endpoint:** http://127.0.0.1:8000/health

Use Swagger UI to inspect available endpoints, provide request parameters, submit requests, and review responses.

## Main API Operations

| Operation | Purpose |
|---|---|
| `GET /health` | Check API health |
| `POST /employees` | Create an employee |
| `GET /employees` | List or filter employees |
| `POST /attendance/punch-in` | Record employee punch-in |
| `POST /attendance/punch-out` | Record employee punch-out |
| `GET /attendance` | Retrieve attendance records |
| `PATCH /attendance/{emp_code}/{date}` | Correct an attendance record |
| `GET /analytics/employees/{emp_code}/monthly` | Retrieve monthly employee analytics |
| `GET /analytics/departments/summary` | Retrieve department analytics |
| `GET /analytics/leaderboard/late` | Retrieve the late-arrival leaderboard |
| `GET /analytics/departments/{department}/trend` | Retrieve department attendance trends |
| `GET /admin/explain/{endpoint}` | Inspect configured query execution plans |

Check Swagger UI for the exact request parameters and schemas supported by each endpoint.

## Database Indexing and Query Analysis

The project configures indexes for employee lookup, department filtering, employee attendance by date, and late-minute sorting.

The admin explain endpoint was tested for five operations:

- `employees`
- `attendance`
- `employee-monthly`
- `department-summary`
- `leaderboard-late`

The tested winning plans reported index scans and no detected collection scans. The leaderboard query's date filtering and index efficiency should be benchmarked further with larger datasets.

## Testing

The following checks have been performed:

- API health and database connectivity check
- Employee listing and pagination
- Monthly employee analytics
- Department summary analytics
- Late-arrival leaderboard
- Department attendance trend
- Query execution plan checks for five operations
- Performance dataset containing 100,000 attendance records

Concurrency, validation edge cases, audit history, and all performance targets should be verified before claiming complete test coverage.

## Project Review

See [`REVIEW.md`](REVIEW.md) for the code-review summary, configured indexes, explain-plan results, and remaining verification tasks.

## Security

- Store database credentials in environment variables.
- Do not commit `.env` or other files containing secrets.
- Restrict database access through appropriate MongoDB Atlas network and database-user settings.

## Current Status

The API and several analytics operations have been tested. Further functional, concurrency, validation, and performance verification is required before the project can be considered fully tested.

## Author

**Soumyaranjan Samal**