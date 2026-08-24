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

**Rodando de dentro de um agente sem `docker` no PATH do Bash/PowerShell**
(achado em 07/ago/2026, sessão sem acesso direto a Docker): o comando `docker`
pode não existir nos shells do Windows mesmo com o container de teste de pé —
mas `wsl -d Ubuntu-24.04 -e docker ps` funciona, porque o Docker Desktop
expõe o daemon só dentro do WSL. Esse WSL **não tem** `pip`/`pytest`
instalados (bare, só `python3` e `docker`). Caminho que funcionou, sem tocar
no ambiente da Maria de forma permanente (container efêmero, `--rm`):

```
wsl -d Ubuntu-24.04 -e bash -c "docker run --rm \
  --network nuvem-teste \
  -v /mnt/c/Users/maria.watanabe/Documents/nuvem-ia:/app -w /app \
  -e TEST_DATABASE_URL=postgresql://nuvem:teste@nuvem-teste-db:5432/nuvem_teste \
  -e ADMIN_PASSWORD=senha-teste \
  python:3.11-slim \
  bash -c 'pip install --quiet -r requirements-dev.txt && python -m pytest -q'"
```

Peças que importam: `--network nuvem-teste` (a rede Docker do container do
banco — `docker network ls`/`docker inspect nuvem-teste-db` confirmam o
nome), `nuvem-teste-db:5432` (nome DNS do container + porta INTERNA, não a
5433 mapeada pro host), e o volume mount do projeto direto do Windows via
`/mnt/c/...`. `python:3.11-slim` já estava puxado localmente (cache de builds
anteriores), então não precisou de download de imagem nova.

**Why:** sem isso, a suíte só rodava contra Postgres mockado/ausente
(287+ erros de conexão recusada) e boa parte do trabalho de banco (migrations,
motor de processamento, catálogo semântico) ficava "escrito e revisado, nunca
executado" — rodar de verdade achou 7 falhas reais que a leitura estática não
pegou (contagens hardcoded desatualizadas, `SELECT` sem `WHERE` que passou a
pegar a linha errada depois que uma migration nova populou a tabela, um typo
de maiúscula/minúscula na correção de um achado da revisão independente).
**How to apply:** antes de reportar "não dá pra verificar contra banco real"
num ambiente sem Docker direto, testar `wsl -d <distro> -e docker ps` — pode
existir um container de teste já de pé que só não está no caminho óbvio.

## Como impedir o container de cair no meio (24/ago/2026)

Em 24/ago/2026 o `nuvem-teste-db` foi parado pelo Docker Desktop **tres vezes**
durante uma rodada da suite -- `docker inspect` mostrou `exit=0`, `oom=false`,
`restarts=0`, isto e, parada graciosa, nao falta de memoria (havia 7,2 GB
livres). O resultado foram **315 erros de conexao** numa rodada de 15min32 que
nao tinha nenhuma regressao.

O que resolveu foi manter a distro WSL ocupada durante a execucao, num processo
a parte iniciado ANTES do pytest:

```
wsl -d Ubuntu-24.04 -e bash -c "for i in \$(seq 1 1800); do   docker exec nuvem-teste-db pg_isready -U nuvem -d nuvem_teste > /dev/null 2>&1; sleep 1; done"
```

Com o keep-alive: **6min32, zero erro de conexao**. Sem ele: 15min32 e 315
erros. Encerrar o keep-alive junto com o container no fim.

Detalhe que custou tempo: depois de dias parado, o container faz `fsync` do
diretorio de dados inteiro na subida (80 s medidos, por causa de um
`Exited (137)` anterior) e recusa conexao com "the database system is starting
up". Esperar `pg_isready` responder `accepting connections` em vez de dormir um
tempo fixo.

### Duas armadilhas descobertas em 24/ago/2026

**1. O keep-alive tem que ser um `wsl.exe` que continue vivo.** `nohup ... &`
de dentro de um `wsl -d Ubuntu-24.04 -e bash -c "..."` morre junto com o
`wsl.exe` que o lancou -- medido: rodada seguinte voltou a dar 330 erros. O que
funciona e deixar o proprio `wsl -e bash -c "for ... sleep 1 ..."` rodando em
segundo plano no lado Windows, pelo tempo da suite.

**2. Matar o pytest no meio deixa o banco SEM o schema `public`.** A fixture
`banco_vazio` faz `DROP SCHEMA public CASCADE` e depois `CREATE SCHEMA`; se o
processo morrer entre as duas (o VS Code fechou no meio de uma rodada), a
rodada seguinte falha instantaneamente com `InvalidSchemaName: schema "public"
does not exist` em centenas de testes. Parece catastrofe e e so isso -- repara
em um comando:

```
wsl -d Ubuntu-24.04 -e docker exec nuvem-teste-db psql -U nuvem -d nuvem_teste   -c "CREATE SCHEMA IF NOT EXISTS public; GRANT ALL ON SCHEMA public TO nuvem;"
```

Como distinguir os tres modos de falha em massa, todos de ambiente:
- `OperationalError: connection refused` -> container caiu (keep-alive)
- `OperationalError: ... starting up` -> container subindo, faz fsync longo
- `InvalidSchemaName: schema "public" does not exist` -> schema orfao, repara
