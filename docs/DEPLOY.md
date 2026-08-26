# Runbook de deploy na VM — Nuvem IA

Primeira subida na VM real (mesma do Conciliador porta 80 e do Hub porta 8001).
Escopo desta subida: **só o admin** (`/` redireciona pra `/admin`; a nuvem/index.html
é o Lote 5, ainda não construída). Você roda os passos na VM; me manda a saída de cada
um antes de seguir pro próximo.

Todos os comandos são pra rodar **na VM** (Linux), no shell dela — não na sua máquina
Windows. Onde aparece `SUA_...`, troque pelo valor real.

---

## Pré-requisitos

- Docker + Docker Compose já instalados na VM (usados por Conciliador/Hub).
- Chave SSH da VM autorizada no repo privado `SuperfrioIA/Nuvem` (passo 2).
- Pasta do projeto: `/home/ubuntu/nuvemIA`, na home junto do Conciliador
  (`/home/ubuntu/conciliadorEstoque`) e do Hub (`/home/ubuntu/apps/hub`).

---

## Passo 1 — Pré-voo: Docker e portas

Checagens só de leitura, antes de mexer em qualquer coisa. Se algo aqui não bater,
a gente resolve antes de clonar.

```bash
docker compose version
sudo ss -tlnp | grep LISTEN          # panorama: deve aparecer :80 (Conciliador) e :8001 (Hub)
sudo ss -tlnp | grep ':8002' || echo "8002 livre"
```

Esperado: uma versão de Compose; `80` e `8001` ocupados (os outros apps); e **8002
livre**.

A porta 8002 não é escolhida agora — já está fixada na arquitetura (Conciliador=80,
Hub=8001, Nuvem IA=8002) e no `docker-compose.yml`. Este passo só **confirma** que ela
está de fato livre. Se 8002 já estiver ocupada, **para aqui** e me manda o que apareceu:
aí vira decisão (trocar a porta no compose + realinhar o pedido da Valcann).

---

## Passo 1.1 — Escopo dos comandos de container (medido em 25/ago/2026)

**A VM roda quatro projetos, de times diferentes, no mesmo Docker.** Levantado com
`docker ps` em 25/ago/2026:

| projeto | containers |
|---|---|
| Nuvem IA (este) | `nuvemia-nuvem-app-1`, `nuvemia-nuvem-db-1` |
| Conciliador | `conciliador_frontend`, `conciliador_backend`, `conciliador_db` |
| Hub | `superfrio-hub`, `superfrio-db` |

**O nome do projeto Compose na VM é `nuvemia`**, não `nuvem-ia` — ele vem do nome do
diretório (`/home/ubuntu/nuvemIA`), e é diferente do nome local. Todo filtro por nome
tem que usar o da VM.

### Comandos que derrubam sistema de outro time

Não é hipótese: um único comando amplo alcança os sete containers. Os cinco abaixo são
os que aparecem em receita de internet e em memória muscular:

| comando | o que ele realmente faz aqui |
|---|---|
| `docker stop $(docker ps -q)` | para **os sete** — Conciliador e Hub caem junto |
| `docker system prune -a` | apaga imagem de todo container **parado**; o projeto do outro time não volta sem rebuild/pull |
| `docker system prune --volumes` | apaga **volume** — é o banco do Conciliador e do Hub, sem backup no caminho |
| `docker compose down` no diretório errado | Compose age sobre o projeto do **diretório atual**. Em `~/conciliador`, derruba o Conciliador |
| `docker stop $(docker ps -q --filter name=db)` | casa com `nuvemia-nuvem-db-1`, `conciliador_db` **e** `superfrio-db` — três bancos, três projetos |

E um que não atinge outro time, mas destrói dado nosso: **`docker compose down -v`**
apaga o volume `nuvem_db_data`, que é o Postgres de produção da Nuvem IA.

### A forma segura

```bash
pwd                                    # SEMPRE antes de qualquer comando compose
docker ps --filter label=com.docker.compose.project=nuvemia   # só o nosso
docker compose ps                      # do diretório certo, só este projeto
```

- Nunca `prune`, em nenhuma variante. Se faltar disco, resolver por nome, item a item.
- Nunca parar/remover container por padrão genérico de nome.
- `down -v` só com autorização explícita da Duda e backup confirmado.
- **No V3.6**, ao acrescentar o serviço da V3 ao compose, subir **nomeando o serviço**
  (`docker compose up -d <servico-novo>`) em vez de um `up -d` seco: o `up` recria
  serviço cuja configuração mudou, e pode recriar o app da V2 sem necessidade.

## Passo 1.2 — A VM alcança o DW Oracle (verificado em 25/ago/2026)

Pré-requisito do V3.5/V3.6, verificado pela Maria **antes** de existir código que dependa
dele — descobrir isso no dia do deploy travaria a subida:

```bash
getent hosts oracleprd-aws.superfrio.com.br
timeout 5 bash -c "cat < /dev/null > /dev/tcp/oracleprd-aws.superfrio.com.br/1521"   && echo "PORTA 1521 ABRE" || echo "FALHOU"
docker exec nuvemia-nuvem-app-1 python -c "import socket; s=socket.create_connection(('oracleprd-aws.superfrio.com.br',1521),5); print('ABRE DE DENTRO DO CONTAINER'); s.close()"
```

Resultado: **abre nos dois** — host e container. O nome resolve para **`172.31.80.11`**
(host real `l001porcdb.superfrio.com.br`), e a VM é `172.31.49.141`: **mesma faixa
`172.31.x.x`**, ou seja, tráfego interno da VPC, sem NAT nem gateway externo no caminho.

Os dois testes existem porque são perguntas diferentes: o host pode alcançar e o
container não (DNS do Docker é servidor embutido, e rede de container pode ter rota
própria). Quem vai conectar é o processo da aplicação, então o teste que decide é o de
dentro do container.

Isto **não** prova que o listener do Oracle aceita sessão — prova que a rede chega. O
handshake em modo thin já foi provado da máquina da Maria (Oracle 12.2, `service_name`,
sem Instant Client).

---

## Passo 2 — Deploy key do repo Nuvem

A VM usa **uma deploy key por repo, com apelido de host** no `~/.ssh/config`
(`github.com` → Conciliador; `github-hub` → Hub). A chave default só enxerga o
Conciliador, então o Nuvem precisa da própria — criada no mesmo molde, com apelido
`github-nuvem`.

> **Cole um bloco de cada vez** (não os três grudados). Se o `ssh-keygen` perguntar
> `Overwrite (y/n)?`, a chave já existe de uma tentativa anterior — responda `n` e pule.
> Se o `~/.ssh/config` ficar inválido, o ssh para de ler o arquivo pra **todos** os
> hosts (Conciliador/Hub inclusive); valide com `ssh -G github-nuvem >/dev/null && echo OK`.

```bash
# 1) gerar o par de chaves do Nuvem (sem passphrase, como as outras)
ssh-keygen -t ed25519 -C "nuvem-ia-deploy" -f ~/.ssh/nuvem_deploy -N ""

# 2) registrar o apelido github-nuvem no ~/.ssh/config
cat >> ~/.ssh/config <<'EOF'

Host github-nuvem
  HostName github.com
  User git
  IdentityFile ~/.ssh/nuvem_deploy
  IdentitiesOnly yes
EOF

# 3) mostrar a chave PÚBLICA (pra colar no GitHub)
cat ~/.ssh/nuvem_deploy.pub
```

**No GitHub** (precisa de admin no repo): `SuperfrioIA/Nuvem` → Settings → Deploy keys →
Add deploy key. Título `vm-deploy`, cole a chave pública do passo 3 e **deixe "Allow
write access" desmarcado** (a VM só lê o repo — clona/atualiza, nunca dá push).

Testar pelo apelido novo:

```bash
ssh -T git@github-nuvem
```

Esperado: `Hi SuperfrioIA/Nuvem! You've successfully authenticated...`. O "código 1" e o
"does not provide shell access" são normais. Se vier `conciliadorEstoque` ou
`Permission denied`, para aqui e me manda a saída.

---

## Passo 3 — Clonar o repo

```bash
cd /home/ubuntu
git clone git@github-nuvem:SuperfrioIA/Nuvem.git nuvemIA
cd nuvemIA
```

Repare no `git@github-nuvem:` — é o apelido criado no Passo 2, que roteia pra deploy key
do Nuvem. `git@github.com:` cairia na chave do Conciliador e falharia. O `nuvemIA` no fim
é o nome da pasta de destino: o `docker-compose.yml` fica direto em
`/home/ubuntu/nuvemIA/` (padrão do Conciliador/Hub), sem uma pasta `Nuvem` dobrada.

Me manda: a saída do clone e o resultado de `ls` dentro de `nuvemIA` (pra eu confirmar
que veio `docker-compose.yml`, `Dockerfile`, `backend/`, `frontend/`, `.env.example`).

---

## Passo 4 — Criar o `.env` de produção

**Nunca commitar** este arquivo. Gere segredos novos (não reusar os de teste local).

```bash
# ainda dentro de /home/ubuntu/nuvemIA
cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 16)
ADMIN_PASSWORD=TROQUE_POR_UMA_SENHA_FORTE
SECRET_KEY=$(openssl rand -hex 32)
UPLOADS_HOST_PATH=/home/ubuntu/nuvemIA/data/uploads
EOF
chmod 600 .env
```

Depois **edite o `ADMIN_PASSWORD`** (é a senha que você vai digitar pra logar no
`/admin` — escolha algo forte e que você guarde):

```bash
nano .env      # troca só a linha ADMIN_PASSWORD=
```

Crie a pasta de uploads (fora do container, persistente):

```bash
mkdir -p /home/ubuntu/nuvemIA/data/uploads
```

Confirme o `.env` (sem me mandar os valores — só que as 4 chaves existem):

```bash
cut -d= -f1 .env
```

Esperado: `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `SECRET_KEY`, `UPLOADS_HOST_PATH`.
Não me mande o conteúdo dos segredos.

---

## Passo 4.1 — Variáveis do Microsoft Graph (DataHub)

*Acrescentado em 30/jul/2026, depois de executado na VM real. Necessário desde o Lote
P1 (leitura do SharePoint DataHub); o `.env` criado no Passo 4 acima é anterior a ele
e só tem as 4 chaves. Se o painel do DataHub acusar "configuração do Graph incompleta
— faltam as variáveis: …", é isto que está faltando.*

São 5 variáveis. **Três saem do próprio repositório**, não precisa entrar no Azure:

| Variável | Valor | Fonte |
|---|---|---|
| `GRAPH_CLIENT_ID` | `7324ef4d-54e4-4fc9-9179-00a5c95b8855` | docs/FONTES_DATAHUB.md §1 |
| `GRAPH_SITE_PATH` | `superfrioarmazens.sharepoint.com:/sites/DataHub` | `.env.example` |
| `GRAPH_PASTA` | `00.Dados/00.Bronze/00.Dados_Sistemicos` | `.env.example` |
| `GRAPH_TENANT_ID` | — | `.env` de outra máquina já configurada, ou Azure → app `nuvem-ia` → Directory (tenant) ID |
| `GRAPH_CLIENT_SECRET` | — | `.env` de outra máquina já configurada (é o **Value**, nunca o Secret ID) |

**O client secret não é recuperável do Azure** — aparece uma única vez, na criação. Se
a única cópia se perder, alguém com direito no app registration precisa gerar um novo.
Guarde uma cópia em gerenciador de senhas. Ele **expira em 12 meses**; essa é a única
manutenção periódica do vínculo.

**Validade e rotação** (registrado no Bloco G / G1, 03/ago/2026): o secret atual foi
criado em **15/jul/2026**, expira em **15/jul/2027**. Pra rotacionar antes disso vencer:

1. Entra ID → App registrations → `nuvem-ia` → Certificates & secrets → **New client
   secret**;
2. copiar o **Value** assim que ele aparecer (nunca o Secret ID — é o mesmo erro do
   passo acima);
3. na VM: `nano .env` (nunca heredoc/echo, pra não sobrar no `bash_history`) e trocar
   só a linha `GRAPH_CLIENT_SECRET=`;
4. `docker compose up -d` (**nunca** `restart` — mesma armadilha do passo 4.1: `restart`
   reaproveita o ambiente antigo e a troca não pega);
5. confirmar no painel do DataHub (Sincronizar agora) e só então apagar o secret
   antigo no Azure.

Ver também `memory/graph-secret-rotacao.md`.

```bash
cd /home/ubuntu/nuvemIA
nano .env          # acrescenta as 5 linhas no fim
chmod 600 .env
docker compose up -d
```

Use o **nano**, não `echo`/heredoc: assim o secret não fica no `~/.bash_history`.

**`up -d`, nunca `restart`** — este é o erro que mais engana: `docker compose restart`
reinicia o mesmo container com o mesmo ambiente e a mensagem de "faltam as variáveis"
continua idêntica. Só `up -d` recria o container lendo o `.env` novo.

Conferir que chegaram no container, sem imprimir valor nenhum:

```bash
docker compose exec nuvem-app env | grep '^GRAPH_' | cut -d= -f1
```

Depois: `/admin` → painel DataHub → **Sincronizar agora**.

---

## Passo 4.2 — Variável da IA (chat do Laboratório)

*Acrescentado no Bloco G / G1 (03/ago/2026): até aqui o `docker-compose.yml` não
passava `ANTHROPIC_API_KEY`/`IA_MODELO`/`IA_EFFORT` pro container — o chat do
Laboratório (Bloco E / V1.5) ficava sempre no ramo de erro em produção, mesmo com a
chave no `.env`, porque o compose não usa `env_file:` (mapeia variável por variável).*

```bash
cd /home/ubuntu/nuvemIA
nano .env          # acrescenta ANTHROPIC_API_KEY=... no fim
chmod 600 .env
docker compose up -d --build
```

`IA_MODELO` (default `claude-sonnet-5`) e `IA_EFFORT` (default `medium`) são
opcionais — só entram no `.env` se quiser trocar o padrão, sem precisar mexer em
código. Conferir sem imprimir a chave:

```bash
docker compose exec nuvem-app env | grep -E '^(ANTHROPIC_API_KEY|IA_MODELO|IA_EFFORT)' | cut -d= -f1
```

### Se falhar, a mensagem diz a camada

- **"timeout / falha de rede ao autenticar no Graph"** → saída HTTPS da VM. Testar:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration
curl -s -o /dev/null -w '%{http_code}\n' https://graph.microsoft.com/v1.0/
```

  Esperado `200` e `401` — **401 é boa notícia**: a rede chega e o Graph só recusa por
  falta de token. Travando ou `000`, abrir chamado com a Valcann (mesmo caminho da
  porta 8001 do Hub). *Em 30/jul/2026 a VM real não precisou de chamado: a saída
  HTTPS já estava liberada, como aconteceu com a porta 8002.*
- **"credencial do Graph rejeitada (HTTP 400/401)"** → secret errado ou vencido. O
  clássico é ter copiado o Secret ID (GUID de 36 caracteres) em vez do Value.
- **"acesso negado (HTTP 403)"** → concessão `read` no site DataHub (ver
  docs/FONTES_DATAHUB.md §1).
- **"faltam as variáveis" de novo** → foi `restart` em vez de `up -d`.

---

## Passo 5 — Subir

```bash
docker compose up -d --build
docker compose ps
```

Esperado em `ps`: `nuvem-db` e `nuvem-app` como `healthy` (desde o Bloco G / G1, o
`nuvem-app` também tem healthcheck — `GET /health`, que confere o banco). Nos
primeiros ~15s depois de subir é normal aparecer `health: starting`; espere um
pouco e rode `docker compose ps` de novo antes de desconfiar. Me manda a saída do
`ps`.

---

## Passo 6 — Validar na própria VM (antes de qualquer rede)

```bash
# 1) logs sem erro de conexão com o Postgres
docker compose logs nuvem-app | tail -30

# 2) o admin responde (GET, espera 200) — não usar -I/HEAD: a rota só aceita GET (dá 405)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8002/admin

# 3) login guardando o cookie (espera 200)
curl -s -c /tmp/nuvem.cookie -X POST http://localhost:8002/api/admin/login \
  -F "senha=SUA_ADMIN_PASSWORD" -o /dev/null -w "%{http_code}\n"

# 4) armazéns ativos (espera 31 — 35 semeados; MRS, RMSPIII, CWBI e RPIII inativas)
curl -s -b /tmp/nuvem.cookie http://localhost:8002/api/admin/armazens \
  | grep -o '"sigla"' | wc -l
```

Critério de sucesso desta subida:
- logs sem `connection refused`/erro de Postgres;
- `/admin` = **200**;
- login = **200**;
- armazéns ativos = **31** (35 semeados; inativas: MRS, RMSPIII, CWBI e RPIII). A conta
  passou por duas revisões: no Lote 7.1 a RMSPV entrou; em 03/ago/2026 a CWBIV entrou e
  CWBI e RPIII saíram dos ativos (`memory/filiais-catering-poc.md`). **A contagem não
  detecta o `ativo` trocado entre RMSPIII e RMSPIV** — dá o mesmo número nos dois casos;
  pra isso, consultar as duas siglas:
  `SELECT sigla, ativo FROM armazens WHERE sigla IN ('RMSPIII','RMSPIV');`
  (esperado `f` e `t`).

Me manda as 4 saídas. Se as 4 baterem, o app está **rodando e validado na VM**.

**Checklist automatizado (Bloco G / G3):** `scripts/verificar_v1.py` cobre em
um comando só boa parte do que os passos acima fazem à mão desde o Bloco A —
`/health`, login (certo/errado), gate das rotas e páginas com e sem sessão,
`/frontend/*.html` bloqueado, `/docs` fechado, header `X-Request-Id`. Não
substitui a contagem de armazéns acima (isso é dado específico da VM) — é
complemento, não troca:

```bash
ADMIN_PASSWORD=SUA_ADMIN_PASSWORD python scripts/verificar_v1.py http://localhost:8002
```

---

## Passo 7 — Abrir pra rede

Testa de outra máquina (o endereço que você usa pro Hub, trocando a porta):
`http://IP_DA_VM:8002/admin`.

- **Se abrir o login do admin:** a porta já está acessível na rede — nada a fazer. Foi o
  que aconteceu em 20/jul/2026 com a 8002 (a VM é uma EC2; o Security Group aparentemente
  libera uma faixa de portas, e a 8002 caiu junto com a 8001 do Hub).
- **Se der timeout:** abrir chamado com a **Valcann** pra liberar a porta na rede interna
  dessa VM (mesmo processo que liberou a 8001 do Hub), e testar de novo depois.

Lembrete de postura: com a porta acessível na rede, quem protege o console é a
`ADMIN_PASSWORD` — mantenha-a forte. A nuvem (Lote 5) é aberta na rede interna por desenho.

---

## Migrations (Alembic) — desde o Lote R0

O schema do banco é gerenciado pelo **Alembic** (pasta `alembic/` + `alembic.ini`,
assados na imagem). O `init_db()` só semeia dados de cadastro; quem cria e evolui
tabela é migration. Tudo acontece **sozinho no startup** do `nuvem-app`
(`backend/migracao.py`), em três caminhos:

| Estado do banco | O que o startup faz |
|---|---|
| **Gerenciado** (tabela `alembic_version` existe) | aplica migrations pendentes (`upgrade head`) — caso normal de toda atualização |
| **Novo** (vazio) | cria o schema inteiro pela baseline |
| **Legado** (tabelas do `init_db` antigo, sem `alembic_version`) | **valida o schema** (12 tabelas + colunas obrigatórias) e, só se bater com a baseline, marca `alembic_version = 0001_baseline` (stamp) e segue. **Se algo divergir, não altera nada**: o app para de subir com o erro no log |

Ou seja: a atualização da VM continua `git pull && docker compose up -d --build`.
Na primeira subida pós-R0, o banco existente é validado e "adotado" pelo Alembic
automaticamente (aconteceu validado no ambiente local em 22/jul/2026: dados
preservados, stamp aplicado, restart idempotente).

### Contingência — o startup abortou com "schema legado divergente"

O log (`docker compose logs nuvem-app`) lista exatamente o que divergiu
(ex.: `tabela ausente: clientes` ou `colunas ausentes em medidas: ...`). Nada foi
alterado no banco. Casos:

1. **VM rodando código anterior aos Lotes 7.1/8.5** (faltam `clientes`,
   `catalogo_fontes`, `catalogo_colunas`): suba uma vez a versão anterior ao R0
   (`git checkout 387c674 && docker compose up -d --build` — o `init_db` antigo cria
   as tabelas que faltam), volte pra main (`git checkout main`) e rode o
   `up -d --build` de novo.
2. **Divergência inesperada** (coluna faltando, tabela mexida na mão): não force.
   Confira o log, ajuste o banco manualmente até bater com a baseline
   (`alembic/versions/0001_baseline.py` é a referência) e reinicie. Só depois de
   entender a causa, se tiver certeza de que o schema é equivalente, o stamp manual
   é: `docker compose exec nuvem-app alembic stamp 0001_baseline`.

### Rollback

*Reescrito no Bloco G / G1 (03/ago/2026): a VM usa uma deploy key **só de leitura**
(Passo 2) — não dá pra `git tag && git push` de lá. O rollback de código é por SHA
registrado localmente, e agora existe de fato um pg_dump pra restaurar (seção
"Backup e restauração" abaixo); antes do G1 esse passo dependia de um dump que não
existia.*

**Antes de cada deploy** (`git pull && docker compose up -d --build`), registrar o
SHA que está rodando e tirar um dump de segurança:

```bash
cd /home/ubuntu/nuvemIA
echo "$(date -Iseconds) $(git rev-parse HEAD)" >> deploy-historico.log
./scripts/backup.sh
git pull && docker compose up -d --build
```

**Se o deploy sair ruim:**

1. Código: `git checkout <SHA-anterior-do-deploy-historico.log> && docker compose up
   -d --build`; voltar pra `main` só depois de confirmar que estabilizou.
2. Banco, se alguma migration nova mexeu em schema: `./scripts/restore.sh
   backups/nuvem_<carimbo-do-dump-pre-deploy>.sql.gz` (destrutivo — confirmação
   pedida na hora). Sem mudança de schema, o `checkout` sozinho resolve.
3. Alternativa pontual, quando existir `downgrade` na migration em questão:
   `docker compose exec nuvem-app alembic downgrade -1`. O `downgrade` da
   **baseline** apaga todas as tabelas — só faz sentido em dev.
4. Conferir a versão aplicada: `docker compose exec nuvem-app alembic current`.

### Backup e restauração

*Criado no Bloco G / G1 (03/ago/2026). Mecanismo local, testado (backup → restauração
→ contagem de linhas conferida). **Cópia pra fora da VM é pendência declarada** —
decisão da Maria: pensar no destino externo depois, combinar com a TI; até lá, o
dump fica só no disco da VM, sujeito ao mesmo risco de perda que o resto do
`/home/ubuntu/nuvemIA` (ex.: disco corrompido leva app e backup junto).*

`scripts/backup.sh`: `pg_dump` do Postgres (via `docker compose exec`) + `tar` da
pasta de uploads retidos, ambos comprimidos e carimbados com data/hora em
`backups/` (fora do git — `.gitignore`); apaga backups com mais de
`RETENCAO_DIAS` (padrão 14, variável de ambiente do próprio script).

`scripts/restore.sh <arquivo.sql.gz>`: **destrutivo** — zera o schema `public`
(mesmo padrão da suíte de testes: `DROP SCHEMA ... CASCADE` + `CREATE SCHEMA`) e
restaura o dump informado. Pede confirmação explícita (digitar `restaurar`) antes
de rodar.

> ### ⚠ Medido em 26/ago/2026: esta linha NUNCA foi instalada
>
> Durante o deploy do V3.6, o `crontab -l` da VM mostrou **apenas** o backup do
> **Conciliador** (`conciliadorEstoque/infra/backup/backup-db.sh`, 04h UTC), que
> é de outro projeto. A linha abaixo, documentada desde o Bloco G1 (03/ago/2026),
> não estava lá.
>
> Consequência: **o banco da Nuvem IA não tem cópia automática** — e ele agora
> guarda a V3 em produção, além das tabelas da V1/V2. O único dump existente é o
> avulso de 26/ago 16h30, feito à mão no passo 2 do deploy.
>
> Instalar não colide com nada: 03h UTC fica antes do backup do Conciliador (04h)
> e longe das cargas (10h05 e 18h05 UTC).
>
> **Lição do episódio:** documentar "rodar diariamente" não faz rodar. Passo de
> instalação que não tem verificação depois vira passo que ninguém sabe se foi
> dado. Por isso a seção do V3.6 acima confere o `crontab -l` em vez de mandar
> instalar e seguir.

**Rodar diariamente na VM** (crontab do usuário que roda o compose):

```bash
crontab -e
# adicionar a linha:
0 3 * * * cd /home/ubuntu/nuvemIA && mkdir -p backups && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Restaurar (ex.: depois de um deploy ruim, ou pra testar em outro ambiente):

```bash
cd /home/ubuntu/nuvemIA
ls backups/                       # escolher o dump certo pelo carimbo
./scripts/restore.sh backups/nuvem_AAAAMMDD_HHMMSS.sql.gz
```

Os xlsx retidos do upload manual ficam no `.tar.gz` irmão do mesmo carimbo
(`backups/uploads_AAAAMMDD_HHMMSS.tar.gz`); restaurar é descomprimir por cima de
`UPLOADS_HOST_PATH` manualmente (não é automático — são arquivos, não banco).

### Testes (desenvolvimento, WSL)

Suíte pytest com Postgres real (nunca mock). Uma vez:
`docker run -d --name nuvem-teste-db --restart unless-stopped -e POSTGRES_USER=nuvem -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=nuvem_teste postgres:16`
e uma rede comum (`docker network create nuvem-teste && docker network connect nuvem-teste nuvem-teste-db`). Rodar:

```bash
docker run --rm --network nuvem-teste \
  -e TEST_DATABASE_URL=postgresql://nuvem:teste@nuvem-teste-db:5432/nuvem_teste \
  -v "$PWD":/app -v nuvem-pip-cache:/root/.cache/pip -w /app \
  python:3.11-slim bash -c "pip install -q -r requirements-dev.txt && pytest -q"
```

O banco de teste é **zerado** a cada teste — nunca aponte `TEST_DATABASE_URL` pro
banco de verdade.

## V3.6 — Subir a V3 e desligar a V2 (procedimento)

*Escrito em 26/ago/2026. **A ordem é a segurança** — os passos estão numerados
porque dois deles não têm volta, e o que vem antes de cada um existe para poder
desistir.*

### O que muda, em uma frase

A V3 entra no ar na porta 8003 e a V2 sai do ar inteira — decisão da Maria em
26/ago/2026: nenhuma das telas dela era usada por ninguém.

**O que sai do ar junto:** `/admin`, `/nuvem`, `/cockpit`, `/laboratorio`,
`/linhagem` e a ingestão do DataHub (o "Sincronizar agora" daquela tela).

**O que NÃO é tocado:** `backend/` e `frontend/` (o código fica, intacto), o
volume `nuvem_db_data`, as tabelas da V1/V2 dentro dele, o backup diário das 3h
(`scripts/backup.sh` fala com o `nuvem-db`, que fica) e — principalmente — o
Conciliador e o Hub.

**Reativar o laboratório**, se um dia voltar a fazer sentido: descomentar o
bloco `nuvem-app` no `docker-compose.yml` e `docker compose up -d`. É por isso
que ele está comentado e não deletado.

### Por que as migrations rodam à mão, e não pelo startup

Até o V3.5, as migrations da V3 (0019–0023) entrariam em produção **de carona no
startup da V2**: o `Dockerfile` copia `alembic/` e `backend/main.py` chama
`migracao.migrar()` ao subir. Consequência: uma migration da V3 com defeito
derrubaria a **V2**.

Como a V2 não vai mais subir, isso deixou de ser necessário — e a troca é boa em
si. Em produção o `migrar()` cai no caminho *gerenciado* (a `alembic_version`
existe), que é literalmente `upgrade head`: o comando explícito faz o mesmo, no
momento escolhido, sem acoplar a V3 ao ciclo de vida de um app que está saindo.

### Pré-requisitos, antes de abrir a janela

- [ ] `.env` da VM com **`CAT_SECRET_KEY`** (obrigatória, própria da V3 — sem
      ela o app sobe, o `/health` responde 200 e o **login estoura**),
      `DW_USER`, `DW_SENHA`. Ver `.env.example`;
- [ ] suíte completa verde na máquina de desenvolvimento (não só a do lote);
- [ ] saber que a porta 8003 está livre na VM (`sudo ss -tlnp | grep 8003`).

### O procedimento

```bash
cd /home/ubuntu/nuvemIA
```

**1. Trazer o código e registrar o que subiu.**

```bash
git pull
git rev-parse --short HEAD          # anote: é o que você vai comparar num rollback
```

**2. Backup. Antes do ponto sem volta.**

```bash
./scripts/backup.sh
ls -lh backups/ | tail -3
```

**3. Conferir de onde a cadeia parte** (esperado: `0018...`, o que confirma o
caminho *gerenciado* do Alembic):

```bash
docker compose exec -T nuvem-db psql -U nuvem -d nuvem -c   "SELECT version_num FROM alembic_version"
```

**4. Construir a imagem.** Ainda não serve nada — dá para parar aqui sem efeito.

```bash
docker compose build
```

**5. ⚠ NÃO-RETORNO 1 — aplicar as migrations da V3.**

```bash
docker compose run --rm nuvem-cat alembic upgrade head
```

Se isto falhar, **pare**. Não tente o passo seguinte: o backup do passo 2 é o
caminho de volta, e a seção "Rollback" abaixo tem o procedimento.

**6. Conferir o que a migration criou.**

```bash
docker compose exec -T nuvem-db psql -U nuvem -d nuvem -c   "SELECT version_num FROM alembic_version"          # esperado: 0023_identidade_ano_solic
docker compose exec -T nuvem-db psql -U nuvem -d nuvem -c   "SELECT tablename FROM pg_tables WHERE tablename LIKE 'cat_%' ORDER BY 1"
```

Esperado: `cat_auditoria`, `cat_cargas`, `cat_clientes`, `cat_fato_expedicao`,
`cat_fato_recebimento`, `cat_tipos_estoque`, `cat_unidades`, `cat_usuarios`.

**7. Subir a V3.**

```bash
docker compose up -d nuvem-cat
docker compose ps
```

**8. Validar na própria VM, antes de qualquer rede.**

```bash
curl -s localhost:8003/health          # esperado: {"ok":true,"banco":"ok",...}
```

**9. Criar o primeiro usuário.** Pelo CLI, e não por variável no `.env` — a
senha é pedida por `getpass` e não fica em arquivo nem no histórico do shell:

```bash
docker compose run --rm nuvem-cat python -m catering.seguranca criar   --login maria.watanabe --papel admin
```

**10. Carga inicial** (cerca de 79 mil linhas, uns 30 segundos):

```bash
MODO=completa ./scripts/carga_catering.sh
tail -20 logs/carga_catering.log
```

**11. Abrir a tela e conferir com dado real.** A Matriz com jan–ago/2026, o
rodapé "De quando é o dado" dizendo `oracle` **e com a hora certa** (o fuso de
exibição é o V3.5.1 — se aparecer três horas adiantado, `CAT_FUSO_EXIBICAO` não
chegou no container).

**Até aqui, a V2 ainda está no ar.** Se algo estiver errado, o rollback é
`docker compose stop nuvem-cat` e nada foi perdido.

**12. ⚠ NÃO-RETORNO 2 — desligar a V2.** Só depois do 11 passar.

```bash
docker stop nuvemia-nuvem-app-1
docker rm nuvemia-nuvem-app-1
```

**Por nome, e não com `docker compose up -d --remove-orphans`.** As duas formas
funcionam, e a pergunta da Maria na execução de 26/ago/2026 — *"não vai remover
nada das outras aplicações, né?"* — é a razão de a documentada ser esta.

`--remove-orphans` age por **exclusão**: remove o que não está no arquivo, dentro
do projeto `nuvemia`. É seguro por construção (os containers do Conciliador e do
Hub têm outro `com.docker.compose.project`), e ainda assim é a forma errada de
documentar uma operação em VM compartilhada: ela exige que quem executa confie
num filtro invisível. O comando por nome age por **inclusão** — um container,
nomeado, sem padrão e sem "o que sobrou". É a mesma postura da tabela do Passo
1.1: *resolver por nome, item a item*.

Para provar o escopo antes, se der vontade (não muda nada):

```bash
docker ps -a --filter "label=com.docker.compose.project=nuvemia"   --format '{{.Names}}  [{{.Label "com.docker.compose.service"}}]'
```

`docker rm` remove o **container**, não a imagem nem o volume. E como o serviço
já não existe no compose, ele não volta: `restart: unless-stopped` não se aplica
a container removido.

**13. Conferir que o vizinho não foi afetado.** Este passo existe porque é a
pergunta que dá medo, e medo se responde com evidência:

```bash
docker ps --format '{{.Names}}	{{.Status}}'
curl -s -o /dev/null -w '%{http_code}
' localhost:80       # Conciliador
curl -s -o /dev/null -w '%{http_code}
' localhost:8001     # Hub
```

Esperado: os containers do Conciliador (3) e do Hub (2) de pé, e os dois
respondendo.

**14. Ligar o agendamento.** As duas linhas em UTC — ver a seção da carga
agendada abaixo, e o aviso de não "corrigir" os horários.

### Se der errado

| sintoma | o que fazer |
|---|---|
| passo 5 falhou (migration) | **pare**. Restaurar do backup do passo 2 (seção "Backup e restauração") |
| a V3 não sobe no passo 7 | `docker compose logs nuvem-cat`. A V2 ainda está no ar — não há pressa |
| `/health` responde mas o login estoura | `CAT_SECRET_KEY` não chegou no container: `docker compose exec nuvem-cat printenv CAT_SECRET_KEY` |
| a carga falha no passo 10 | a mensagem nomeia a camada (credencial, DNS, contrato). `cat_cargas` guarda o motivo |
| a hora do rodapé está adiantada | `CAT_FUSO_EXIBICAO` não chegou. É exibição, não dado — o banco está certo |
| preciso a V2 de volta | descomentar o bloco `nuvem-app` no compose e `docker compose up -d` |

**Nada disso pede os comandos da tabela do Passo 1.1.** `docker stop $(docker ps
-q)`, `docker system prune --volumes` e `docker compose down` no diretório errado
continuam proibidos — o risco para o Conciliador e o Hub nunca esteve no deploy,
está no comando de emergência digitado com pressa.

---

## Carga agendada da V3 — construída no V3.5, **ligada no V3.6**

`scripts/carga_catering.sh` já existe e funciona. **Não instale o crontab
agora**: faltam duas coisas que só o V3.6 resolve, e ligar antes disso produz
uma carga que falha todo dia às 07h05 ou, pior, uma que roda no horário errado
sem ninguém notar.

### Pendência 1 — FECHADA no V3.6: o serviço `nuvem-cat` existe

O `Dockerfile` passou a copiar `catering/` e `scripts/carga_catering.sh`, e o
compose ganhou o serviço **`nuvem-cat`** na porta **8003** — o nome que o script
já esperava (`SERVICO_CATERING`, padrão `nuvem-cat`).

Enquanto isso não existia, o script falhava alto listando os serviços presentes,
de propósito: numa VM com quatro projetos, a mensagem crua do Compose manda quem
estiver de plantão para o lugar errado.

A credencial do DW chega no container **por variável de ambiente do Compose**,
nunca como argumento de linha de comando — argumento aparece em `ps`, em log de
shell e no histórico.

### Pendência 2 — DECIDIDA: o cron é escrito em UTC (26/ago/2026)

O contrato diz **07h05 e 15h05**, 30 minutos depois das rodadas do processo do
DW (que roda a cada 2h, de 6h35 a 23h35). Se a VM estiver em UTC, `5 7 * * *`
dispara às **04h05 locais** — antes da primeira rodada do DW do dia — e a carga
leria sempre a véspera, entregando número velho com cara de número novo.

Havia duas saídas, e a decisão da Maria foi a segunda:

| saída | por que não / por que sim |
|---|---|
| ajustar o fuso da VM para `America/Sao_Paulo` | mais limpo de ler, e **afeta os outros três projetos da VM** — deixa de ser decisão de um time só, e o ganho não paga a negociação |
| **escrever o cron em UTC** | escolhida. Não toca em nada de ninguém. O preço é ficar escrito, e está escrito aqui |

Confira o fuso antes de colar as linhas — a decisão pressupõe VM em UTC, que é
o padrão de servidor, mas pressuposto não conferido é o começo de um incidente:

```bash
timedatectl                 # esperado aqui: Time zone: Etc/UTC
date -Iseconds
```

> ### ⚠ Os horários do crontab estão em UTC, e é de propósito
>
> `5 10` é **07h05 de Brasília** e `5 18` é **15h05 de Brasília**.
>
> **Não "corrija" para `5 7` e `5 15`.** Parece errado e não é: em UTC, `5 7`
> dispararia às 04h05 locais, antes da primeira rodada do DW do dia, e a carga
> passaria a ler sempre a véspera — todo dia, no horário errado, sem ninguém
> notar. É pior que uma carga que falha, porque falha aparece.
>
> Se o fuso da VM mudar algum dia, **estas duas linhas mudam junto.** Quem
> mexer no fuso da VM tem que passar por aqui.
>
> Horário de verão: o Brasil não observa desde 2019. Se voltar, `America/Sao_Paulo`
> passa a oscilar entre UTC-3 e UTC-2 e estas linhas precisam de revisão — o
> cron em UTC não acompanha DST sozinho. É a fraqueza conhecida desta escolha.

### As duas linhas, quando as duas pendências estiverem fechadas

```bash
crontab -e
# adicionar -- horarios em UTC: 5 10 = 07h05 BRT, 5 18 = 15h05 BRT.
# NAO trocar por 5 7 / 5 15 (ver o aviso acima).
5 10 * * * cd /home/ubuntu/nuvemIA && ./scripts/carga_catering.sh >> logs/carga_catering.log 2>&1
5 18 * * * cd /home/ubuntu/nuvemIA && ./scripts/carga_catering.sh >> logs/carga_catering.log 2>&1
```

Antes: `mkdir -p /home/ubuntu/nuvemIA/logs`.

Como conferir depois de ligar, sem abrir a tela:

```bash
tail -20 logs/carga_catering.log
docker compose exec -T nuvem-db psql -U nuvem -d nuvem -c \
  "SELECT id, tabela_origem, fonte, status, linhas_lidas, linhas_inseridas, linhas_atualizadas, terminada_em, erro FROM cat_cargas ORDER BY id DESC LIMIT 6"
```

O que cada status significa: `ok` carregou; `sem_dado` é o desfecho **normal**
do incremental (nada mudou no DW desde a marca d'água); `erro` tem o motivo na
coluna `erro`, e o script saiu com código diferente de zero. Rodada `rodando`
que não terminou é rodada morta no meio — o processo caiu sem passar pelo
tratamento.

Rodada manual, fora do horário (por exemplo depois de arrumar uma falha):

```bash
cd /home/ubuntu/nuvemIA && ./scripts/carga_catering.sh                  # incremental
cd /home/ubuntu/nuvemIA && MODO=completa ./scripts/carga_catering.sh    # recarga cheia
```

Duas rodadas nunca correm juntas: o script usa `flock` e a segunda desiste
registrando `PULADA` no log. Isso é proteção contra rodada que atrasou além da
próxima, não contra rodada travada — `PULADA` aparecendo duas vezes seguidas é
sinal de rodada presa, e aí é olhar `docker ps` e o log.

## Comandos úteis / rollback

```bash
docker compose logs -f nuvem-app      # acompanhar logs ao vivo
docker compose restart nuvem-app      # reiniciar só o app
docker compose down                   # derruba os containers (o volume do banco fica)
docker compose down -v                # derruba E apaga o banco — CUIDADO, perde dados
git pull && docker compose up -d --build   # atualizar após novo commit
curl localhost:8002/health            # sonda rapida (Bloco G / G1): 200 = banco ok
./scripts/backup.sh                   # dump avulso, fora do horario do cron
```

O volume `nuvem_db_data` guarda o banco entre `up`/`down`. `down -v` apaga tudo — só
usar se quiser começar do zero.
