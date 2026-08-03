---
name: suite-testes-local
description: Como rodar a suíte pytest na máquina da Maria — sem venv, `python -m pytest`, e o Postgres de teste num container que o Docker Desktop desliga sozinho
metadata:
  type: feedback
---

Receita que funciona na máquina Windows da Maria (não há venv — o Python global
**é** o ambiente do projeto):

1. **Subir/acordar o Postgres de teste** (o `conftest` espera `localhost:5433`):
   `wsl -d Ubuntu-24.04 -e docker ps --filter name=nuvem-teste-db`. O `docker` só
   existe **dentro do WSL**, não nos shells do Windows.
2. **Segurar a sessão WSL aberta** durante a execução, com um processo em
   background que faz `docker ps` a cada poucos segundos. Sem isso o Docker
   Desktop derruba o container no meio da suíte.
3. **Esperar o banco aceitar conexão** antes de disparar o pytest — logo depois de
   acordar, ele responde `FATAL: the database system is starting up` por ~15s.
4. Rodar com **`python -m pytest`**: o `pytest` não está no PATH.

Suíte completa leva ~2–3 min (330 testes em 03/ago/2026) e usa Postgres real,
nunca mock; cada teste zera o schema.

**Why:** três execuções da suíte falharam com ~130 erros de `OperationalError`
que **pareciam defeito no código** e eram só o container desligado — uma delas
demorou 9 minutos só somando timeouts de conexão. Diagnosticar isso do zero
custa caro, e o sintoma engana: os erros aparecem espalhados por todos os
arquivos de teste que usam banco. Além disso o `alembic` (declarado em
`requirements.txt`) não estava instalado, e o erro que ele dá é enganoso —
`cannot import name 'command' from 'alembic' (unknown location)`, porque a pasta
`alembic/` do próprio repositório vira namespace package quando o pacote real
não existe.

**How to apply:** antes de anunciar falha de teste, confirmar que o banco está
de pé — `OperationalError`/`connection refused` em massa é ambiente, não
regressão. Ver [[vm-nuvem-ia]] para o ambiente de produção, que é outro (VM
Linux com Docker Compose, runbook em `docs/DEPLOY.md`).
