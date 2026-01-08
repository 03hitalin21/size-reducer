# Size Reducer

Production-ready MVP for a Telegram + web video compression service. Telegram and web uploads go into a shared SQLite job queue and are processed by a worker using FFmpeg.

## Project tree

```
app/
  __init__.py
  config.py
  db.py
  jobs.py
  logging.py
  media.py
  utils.py
bot/
  __init__.py
  main.py
webapi/
  __init__.py
  main.py
  rate_limit.py
  static/
    app.js
    index.html
worker/
  __init__.py
  main.py
storage/
  uploads/
  outputs/
db/
  jobs.sqlite
scripts/
  init_db.py
  init_db.sql
  nginx_fastapi.conf
  systemd/
    bot.service
    webapi.service
    worker.service
Dockerfile
docker-compose.yml
requirements.txt
.env.example
README.md
tests/
  test_db.py
  test_media.py
```

## Requirements

- Python 3.11+
- FFmpeg + FFprobe installed on the server
- Telegram bot token

## Configuration

Copy `.env.example` to `.env` and fill values.

Key variables:

- `TELEGRAM_BOT_TOKEN` (required for bot)
- `TELEGRAM_WEBHOOK_URL` (optional, enables webhook mode)
- `BASE_URL` (used for download links)
- `SQLITE_PATH`
- `STORAGE_PATH`
- `MAX_UPLOAD_MB`
- `MAX_DURATION_SECONDS`
- `MAX_TELEGRAM_SEND_MB`

## Non-docker setup

1) Install FFmpeg (Ubuntu example)

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

2) Create virtualenv and install deps

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3) Initialize database

```bash
python scripts/init_db.py
```

4) Run web API

```bash
uvicorn webapi.main:app --host 0.0.0.0 --port 8000
```

5) Run worker

```bash
python -m worker.main
```

6) Run Telegram bot

Webhook (default): set `TELEGRAM_WEBHOOK_URL` to a public URL that routes to the bot service.

```bash
python -m bot.main
```

Polling fallback: leave `TELEGRAM_WEBHOOK_URL` empty and run the same command.

## Docker Compose (optional)

1) Build and initialize database

```bash
docker compose build
docker compose run --rm webapi python scripts/init_db.py
```

2) Start services

```bash
docker compose up -d
```

## API endpoints

- `POST /api/upload` (multipart: `file`, `profile`)
- `GET /api/status/{job_id}`
- `GET /api/download/{job_id}?token=...`

Static web UI is at `/web/`.

## Systemd unit files

Sample units are in `scripts/systemd/`. Update `User`, `WorkingDirectory`, and venv path:

- `scripts/systemd/webapi.service`
- `scripts/systemd/worker.service`
- `scripts/systemd/bot.service`

## Nginx reverse proxy

Example snippet for the FastAPI web service: `scripts/nginx_fastapi.conf`.

## Notes

- FFmpeg runs with H.264 + AAC and writes MP4 outputs to `storage/outputs/`.
- Jobs are queued in SQLite and locked atomically via `UPDATE ... RETURNING`.
- Telegram jobs will receive the compressed file directly when possible, otherwise a download link.