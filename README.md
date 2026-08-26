# HelixHealth

OpenHIS-UNLaM educational hospital information system.

## Run locally with Docker Compose

Requirements: Docker Desktop or Docker Engine with Docker Compose.

Create your local environment file and start the application and PostgreSQL:

### PowerShell

```powershell
Copy-Item .env.example .env
docker compose up --build
```

### Bash

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000> in your browser. The initial scaffold displays
Django's default start page.

Press `Ctrl+C` to stop the foreground processes, then remove the stopped
containers and network:

```text
docker compose down
```

The PostgreSQL data remains in its Docker volume. To intentionally reset the
local database as well, run `docker compose down --volumes`.
