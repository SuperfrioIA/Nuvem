FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 8000

# --no-access-log (Bloco G / G2): o access log padrao do uvicorn loga a URL
# completa, com query string -- e onde cliente/filial vazavam em claro nos
# logs. O middleware de backend/main.py loga metodo+path (sem query string)
# no lugar dele.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
