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

# A V3 (V3.6). App PROPRIA (`catering/app.py`), servida por outro servico do
# compose a partir desta MESMA imagem -- nao ha router da V3 dentro do
# `backend/`, e `backend/` nao e alterado. Uma imagem so porque as duas
# aplicacoes tem as mesmas dependencias e a mesma cadeia de migrations; duas
# imagens dobrariam o build para separar o que ja esta separado no processo.
COPY catering/ catering/
# O script da carga agendada roda `docker compose run --rm` DESTA imagem, entao
# ele precisa estar nela. Sem este COPY, o script falha alto -- de proposito,
# desde o V3.5 -- listando os servicos existentes.
COPY scripts/carga_catering.sh scripts/carga_catering.sh

EXPOSE 8000

# --no-access-log (Bloco G / G2): o access log padrao do uvicorn loga a URL
# completa, com query string -- e onde cliente/filial vazavam em claro nos
# logs. O middleware de backend/main.py loga metodo+path (sem query string)
# no lugar dele.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
