# Support Ticket Service

Backend for customer support tickets. Customers create tickets, agents move them through a status workflow, and a background worker summarizes each new ticket, checks it for spam, suggests a priority and routes it to a department.

FastAPI, PostgreSQL, Celery + Redis, Docker Compose.

## Running it

```bash
docker compose up --build
```

Migrations and sample data are applied on startup.

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

`docker compose down -v` wipes the database.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/v1/tickets` | Create a ticket |
| GET | `/api/v1/tickets` | List tickets (`status`, `priority`, `category`, `page`, `page_size`) |
| GET | `/api/v1/tickets/{id}` | Ticket with its processing result |
| PATCH | `/api/v1/tickets/{id}/status` | Change status |
| GET | `/api/v1/tickets/{id}/events` | Audit log |
| GET | `/api/v1/tickets/{id}/history` | History with time spent in each status |

Allowed status changes:

```
OPEN        -> IN_PROGRESS, CLOSED
IN_PROGRESS -> OPEN, RESOLVED
RESOLVED    -> IN_PROGRESS, CLOSED
CLOSED      -> (final)
```

Anything else returns `409`. All errors use the same format: `{"error": {"code", "message", "details", "request_id"}}`.

Example:

```bash
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{"customer_name": "Jane Doe", "customer_email": "jane@example.com",
       "subject": "Charged twice", "description": "I was charged twice this month.",
       "category": "BILLING"}'
```

The response shows `processing.status: PENDING`; a second later the ticket is `COMPLETED` with a summary, spam score, suggested priority and department.

## Sample data

`scripts/seed.py` adds 3 agents and 15 tickets covering every status, priority and category. It only runs when the database is empty. Ticket ids are fixed, so for example `850173ef-2c23-565d-91a0-198d0362fa19` always has a history that was reopened once, and `3357200e-6d6b-5ecb-bf43-face98ce3efa` is a spam ticket.

## Design notes

More detail, with an architecture diagram, in [docs/design-notes.md](docs/design-notes.md).

- **Layers:** routes → services → repositories → models. Routes only handle HTTP; services hold the business rules and are the only place that commits.
- **Sync SQLAlchemy:** routes are plain `def` and run in FastAPI's thread pool. Simpler than async, and the API and worker share the same code.
- **Tables:** `tickets`, `ticket_events` (append-only history), `ticket_processing` (one row per ticket), `agents`. Fixed values are Postgres enums. Indexes match the list queries: `created_at DESC` and `(status, priority, created_at)`.
- **Background jobs:** the ticket is committed first, then its id is queued. The worker uses a thread pool and holds no DB connection while analyzing, so it would cope with a slow LLM call. Failures are retried 3 times with backoff, then marked `FAILED`. Running the same job twice is safe.
- **Analysis** is keyword-based for now (`app/services/processing.py`), behind a `TicketAnalyzer` interface so it can be swapped.
- Every request gets an `X-Request-ID` that shows up in API and worker logs.

## Configuration

Copy `.env.example` to `.env` to change anything; all values have defaults.

| Variable | Default | |
|---|---|---|
| `APP_ENV` | `local` | `production` switches to JSON logs |
| `LOG_LEVEL` | `INFO` | |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `tickets` | |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `10` | |
| `SEED_ON_START` | `true` | |
| `CORS_ORIGINS` | empty | Leave empty if a proxy handles CORS |
| `WORKER_CONCURRENCY` | `16` | |
| `PROCESSING_TIMEOUT_SECONDS` | `30` | |
| `PROCESSING_SIMULATED_LATENCY_MS` | `0` | Fake delay to test worker concurrency |

## Checks

```bash
docker compose exec api sh -c "ruff check . && ruff format --check . && mypy app"
```

## Tradeoffs

- No auth: the `actor` on status changes is whatever the client sends.
- Analysis is keyword rules, so it's predictable but easy to fool.
- Processing results are suggestions only; the worker never changes a ticket's status or priority.
- If Redis is down when a ticket is created, the ticket is saved but stays `PENDING`.
- Offset pagination is fine at this size but not for very large tables.

## Future improvements

- Authentication and roles, with `actor` taken from the token.
- Outbox pattern so a saved ticket always gets its job queued.
- `Idempotency-Key` header on ticket creation so retries don't create duplicates.
- An LLM-based `TicketAnalyzer`.
- SQS as an alternative to Redis, via the `JobPublisher` interface.
- Cursor pagination.
- Endpoints for assigning tickets and managing agents.
- Metrics, tracing and CI.
