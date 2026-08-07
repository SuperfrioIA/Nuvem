FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY alembic.ini .
COPY alembic/ alembic/
# scripts/processar_saida.py roda DENTRO do container (V2.3, decisao D4) --
# e o unico de scripts/ que chama o motor de ingestao (psycopg2, GRAPH_*),
# ao contrario de verificar_v2.py/totais_competencia.py, que ficam no host e
# so fazem SELECT via `psql` do container do banco.
COPY scripts/processar_saida.py scripts/processar_saida.py

EXPOSE 8000

# --no-access-log (Bloco G / G2): o access log padrao do uvicorn loga a URL
# completa, com query string -- e onde cliente/filial vazavam em claro nos
# logs. O middleware de backend/main.py loga metodo+path (sem query string)
# no lugar dele.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
