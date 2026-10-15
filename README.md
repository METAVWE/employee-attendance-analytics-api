# Employee Attendance & Analytics API

A REST API built with FastAPI and MongoDB for employee management, attendance tracking, and workforce analytics.

## Features

- Create and list employees, with department filtering and pagination.
- Record employee punch-in and punch-out.
- Calculate attendance metrics, including late arrivals and work hours.
- View monthly and department analytics.
- Inspect database query plans and indexes.

## Tech Stack

Python, FastAPI, Pydantic, MongoDB, PyMongo.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a local `.env` file and configure the MongoDB connection settings expected by `app/database.py`. Never commit this file.
4. Start the API:

   ```bash
   uvicorn app.main:app --reload
   ```

5. Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Project Status

This is a partial submission. The API implementation is in progress. Automated test coverage, authentication and authorization, and production deployment remain future improvements. Verify database connectivity and endpoint behavior in your own environment before relying on the results.

See [REVIEW.md](REVIEW.md) for known limitations and [DECISIONS.md](DECISIONS.md) for implementation choices.
