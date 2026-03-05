# Documentation

This directory contains all project documentation for RailBook. Each subdirectory groups related documents by topic.

## Table of Contents

### API

- **[API Reference](api/API_REFERENCE.md)** -- Complete endpoint documentation for all routes (auth, trains, bookings, payments, demo, admin). Includes request/response schemas, status codes, and example payloads.
- **[Error Codes](api/ERROR_CODES.md)** -- Catalog of all error responses with HTTP status codes, error formats, and troubleshooting guidance.

### Architecture

- **[System Architecture](architecture/ARCHITECTURE.md)** -- High-level overview of how RailBook is structured: FastAPI backend, PostgreSQL with row-level locking, Redis rate limiting, React frontend, and the booking lifecycle (reserve -> pay -> confirm).
- **[Concurrency](architecture/CONCURRENCY.md)** -- Deep dive into the 5 concurrency problems in ticket booking (double booking, lost updates, phantom reads, stale reservations, overlapping journeys) and how RailBook solves each at the database level.
- **[Database Schema](architecture/DATABASE.md)** -- All 8 tables documented: columns, types, indexes, unique constraints, and relationships. Covers the SQLAlchemy 2.0 model definitions.

### Guides

- **[Developer Guide](guides/DEVELOPER_GUIDE.md)** -- Setup instructions, local development workflow, project conventions, and how to add new features.
- **[User Guide](guides/USER_GUIDE.md)** -- End-user walkthrough of the application, from account creation to booking and refunds.
- **[Deployment Guide](guides/DEPLOYMENT_GUIDE.md)** -- Docker Compose deployment, environment variable configuration, and production hardening recommendations.
- **[Load Testing Guide](guides/LOAD_TESTING_GUIDE.md)** -- Locust personas, running load tests, and verifying database integrity after a run.

### Postman

- **[Postman Collection](postman/)** -- Importable Postman collection and environment for interactive API testing. See `postman/README.md` for usage instructions.

### Other Files

- **[railbook-plan.md](railbook-plan.md)** -- Original project planning document.
- **[railbook-excalidraw.json](railbook-excalidraw.json)** -- Architecture diagram source file (open with [Excalidraw](https://excalidraw.com/)).
