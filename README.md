# HelixHealth

OpenHIS-UNLaM educational hospital information system built with Python 3.13,
Django 5.2 LTS, Django REST Framework, HTMX, Bootstrap 5, and PostgreSQL 18.

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/) 0.12.5 or a compatible release
- Docker Desktop or Docker Engine with Docker Compose
- Git, when using the pre-commit hooks

## Fresh local setup

Clone the repository, open a terminal in its root, and create the local
environment file.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Bash:

```bash
cp .env.example .env
```

Replace the placeholder `DB_PASSWORD` in `.env` before starting PostgreSQL for
the first time. PostgreSQL applies that initialization password only when the
`postgres_data` volume is empty; changing `.env` later does not change the
password stored by an existing database cluster.

Install the exact locked Python environment and the browser used by the smoke
tests:

```text
uv sync --frozen
uv run playwright install chromium
```

Validate the Compose configuration, start PostgreSQL, and wait for its health
check:

```text
docker compose config
docker compose up -d --wait db
```

Apply every Django migration and run the system checks:

```text
uv run python manage.py migrate --noinput
uv run python manage.py check
```

`manage.py` uses the development environment and loads `.env`. When commands
run on the host, the database host defaults to `localhost`; the Compose `web`
service uses the internal hostname `db`.

Start the development server and open <http://localhost:8000>:

```text
uv run python manage.py runserver
```

## Seed data

Seed data is versioned as reversible Django data migrations. Running
`migrate` inserts the administrative and medical-professional role groups plus
the initial specialties and hospital services. No separate seed command is
required.

Apply any pending seed migrations:

```text
uv run python manage.py migrate --noinput
```

Confirm the reference records are available:

```text
uv run python manage.py shell -c "from professionals.models import HospitalService, Specialty; print('specialties:', Specialty.objects.count()); print('hospital services:', HospitalService.objects.count())"
```

A fresh database should report six specialties and five hospital services.

## Run with the application container

To run both Django and PostgreSQL through Compose:

```text
docker compose build
docker compose up -d --wait db
docker compose run --rm web python manage.py migrate --noinput
docker compose up web
```

Open <http://localhost:8000>. Press `Ctrl+C` to stop the foreground web
service.

## Tests

Start PostgreSQL before running the test suite. Tests use PostgreSQL, never
SQLite.

```text
docker compose up -d --wait db
uv run pytest
```

Run only the non-browser tests when Chromium is not installed:

```text
uv run pytest -m "not browser"
```

## Quality checks

Run the same formatting, linting, and type checks enforced by CI:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy
```

Run every configured pre-commit hook manually:

```text
uv run pre-commit run --all-files
```

Install the hooks into the current Git checkout if desired:

```text
uv run pre-commit install
```

## Database and container lifecycle

Inspect service health or PostgreSQL logs:

```text
docker compose ps
docker compose logs db
```

Stop services while preserving the PostgreSQL volume:

```text
docker compose down
```

Permanently delete the local database and its contents only when an intentional
reset is required:

```text
docker compose down --volumes
```

After a reset, the next `docker compose up -d --wait db` initializes a new
database using the current values in `.env`.
