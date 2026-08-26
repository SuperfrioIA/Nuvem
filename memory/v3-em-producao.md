---
name: v3-em-producao
description: A V3 entrou em producao em 26/ago/2026 lendo o DW ao vivo, a V2 saiu do ar, e o banco ficou sem backup automatico
metadata:
  type: project
---

Em **26/ago/2026** a volumetria de catering (V3) entrou em producao na VM,
porta 8003, lendo o **DW Oracle** duas vezes por dia. A V2 saiu do ar no mesmo
deploy. Numeros do aceite: rec **36.893** e exp **42.900** linhas, 6 unidades,
14 clientes, 40 nomes de estoque, periodo de 02/jan a 26/ago/2026.

**A pendencia que importa: o banco de producao NAO tem backup automatico.** O
crontab da VM tem o backup do *Conciliador* (04h UTC, outro projeto) e as duas
cargas da V3 (10h05 e 18h05 UTC), mas **nao** a linha do `scripts/backup.sh` da
Nuvem IA — documentada desde o Bloco G1 em 03/ago/2026 e nunca instalada. Em
26/ago o unico dump existente era o avulso feito a mao antes do deploy.

    0 3 * * * cd /home/ubuntu/nuvemIA && mkdir -p backups && ./scripts/backup.sh >> backups/backup.log 2>&1

Tres coisas que a execucao ensinou e que nenhum teste teria pego:

1. **producao estava duas migrations atras do que se supunha** (`0017`, nao
   `0018`), entao o `upgrade head` aplicou tambem uma migration da **V2**. Ler o
   SQL antes com `alembic upgrade <atual>:head --sql` transformou o passo de ato
   de fe em decisao informada — repetir sempre que o upgrade tocar migration
   alheia;
2. **o `env.py` roda todas as migrations numa transacao so** (sem
   `transaction_per_migration`), e com DDL transacional do Postgres isso as torna
   tudo-ou-nada. Falha no meio nao deixa estado pela metade;
3. **`.env` de producao nao tinha as variaveis novas.** Documentar variavel no
   `.env.example` e o que separa "app sobe quebrado" de "app nao sobe" — sem
   `CAT_SECRET_KEY` o `/health` responde 200 e o login estoura, que engana quem
   confia no healthcheck.

**Why:** este e o marco em que o projeto deixou de ser construcao e passou a ter
usuario, e o momento em que apareceu um risco que nao existia antes — dado de
producao gerado por carga automatica, sem copia automatica.

**How to apply:** ao propor qualquer coisa que toque o banco da VM, checar
primeiro se o backup ja esta no cron; enquanto nao estiver, tratar toda operacao
destrutiva como irreversivel de fato. Ver [[vm-nuvem-ia]] para o endereco e a
postura na VM, [[fato-volumetria-dw]] para o comportamento da fonte (o DW revisa
o passado, nos dois sentidos) e [[nao-conectar-no-dw]] para o limite da IA.
