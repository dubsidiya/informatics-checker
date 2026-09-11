FROM python:3.12-slim-bookworm

WORKDIR /app
COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser
ENV HOST=0.0.0.0 \
    PORT=8765 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8765
CMD ["python", "app.py"]
