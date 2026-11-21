# syntax=docker/dockerfile:1
# ---------- base: dependency runtime (tanpa pytest) ----------
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY kosanhub ./kosanhub
COPY migrations ./migrations
COPY wsgi.py worker.py ./

# ---------- test: build GAGAL bila ada test yang gagal ----------
FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY tests ./tests
RUN python -m pytest -q && touch /tmp/tests-passed

# ---------- production: image yang di-push ke Docker Hub ----------
FROM base AS production
# Menyalin penanda dari stage test memaksa test ikut berjalan di setiap build production.
COPY --from=test /tmp/tests-passed /etc/tests-passed
RUN useradd --create-home --uid 10001 appuser
RUN mkdir -p /app/kosanhub/static/images/rooms && chown -R appuser:appuser /app/kosanhub/static/images/rooms
USER appuser
ENV FLASK_APP=wsgi.py
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "wsgi:app"]
