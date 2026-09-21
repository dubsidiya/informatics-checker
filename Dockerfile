FROM python:3.13.2-slim-bookworm

WORKDIR /app
COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /var/data \
    && chown -R appuser:appuser /app /var/data

USER appuser
ENV HOST=0.0.0.0 \
    PORT=8765 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHECKER_ENV=production \
    CHECKER_RUNNER=judge0 \
    CHECKER_DB=/var/data/checker.sqlite3

EXPOSE 8765
CMD ["python", "app.py"]
