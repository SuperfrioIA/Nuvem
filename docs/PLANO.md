# Plano de construção — Nuvem IA

Plano em lotes (agrupados por módulo tocado, não por prioridade). **Um lote por vez;
aguardar validação antes do próximo.** Gatilho pra começar: a Maria diz "vamos pro
Lote N". Ao fechar um lote, marcar o check e **commitar** — este arquivo é a verdade
compartilhada entre sessões.

Status possíveis por lote: `a fazer` · `em andamento` · `feito` · `bloqueado`.

## Como escolher o modelo

- **Fable 5** — pensar/decidir: design denso, estatística, ambiguidade.
- **Opus 4.8** — capacidade máxima quando o problema trava (viz difícil, bug cabeludo).
- **Sonnet 5** — cavalo de batalha: construir código bem-especificado.
- **Haiku 4.5** — tarefas pequenas, mecânicas, spec fechada (scripts, glue).

O desenho já está fechado nos docs, então quase tudo é construção → Sonnet. Fable/Opus
só onde há julgamento (o motor).

---

## Lote 0 — Destravar o mundo externo

**Status: a fazer** · não é código; começa já e roda em paralelo a tudo.
**Modelo:** — (coordenação humana; redigir pedido/contrato = Sonnet 5).

- [ ] Pedido à TI: app registration no Entra ID, permissão `Sites.Selected` — concessão
      de acesso ao site precisa ser **leitura e escrita** (write), não só leitura: além
      de ler a planilha de ocupação, o app vai gravar arquivos de backup do
      `upload_manual` lá (caminho mais longo)
- [ ] Congelar o contrato da planilha de ocupação (aba + colunas fixas + quem preenche)
- [ ] Escolher as 1–2 filiais do piloto
- [ ] Definir o dono de cada dado (perdas / volumetria / ocupação)
- [ ] Confirmar se ocupação tem histórico retroativo (se não, começa a acumular agora)
- [ ] Combinar com a TI o destino do `pg_dump` fora da VM

**Check de conclusão:** pedido protocolado; contrato escrito e combinado; filiais escolhidas.

## Lote 1 — Esqueleto + primeiro dado real

**Status: feito** (15/jul/2026) · infra + banco + admin upload. **Modelo:** Sonnet 5.

- [x] `docker-compose`, `Dockerfile`, `.env` (porta 8002, 2 containers, worker único)
- [x] Esqueleto FastAPI (API + estáticos)
- [x] `database.py`: 9 tabelas (inclui `modelos_importacao`) + `init_db` idempotente
- [x] Conector `upload_manual` com modelos de importação: mapeamento de colunas
      (armazém/competência fixos ou por coluna; métrica por soma ou razão
      numerador/denominador; cliente reconhecido mas não persistido), salvo e
      reutilizável por relatório — ver docs/ARQUITETURA.md
- [x] Retenção do arquivo original do upload (pasta local na VM, plugável pra
      SharePoint depois) + referência na execução — drill-down manual dessa fonte
- [x] `admin.html` mínimo: upload xlsx (com tela de mapeamento/escolha de modelo),
      CRUD de-para, log de execuções
- [x] Auth: senha única no `/admin`

**Check de conclusão:** validado rodando os containers de verdade (WSL/Docker local —
não tem Docker Desktop; a distro WSL já tem Docker Engine + Compose, dispensa
Docker Desktop). Sobe limpo na 8002 com `--build`; upload sem de-para grava 0 e vira
pendência; de-para resolve; reprocesso com modelo salvo grava em `medidas`; execução
aparece no log com o arquivo original referenciado. **Ainda falta validar na VM real**
(SuperFrio) — o teste até aqui foi só local.

Bug de infra achado e corrigido no processo: `nuvem-app` tentava conectar no Postgres
antes dele aceitar conexão (caía e reiniciava sozinho, disfarçado pelo
`restart: unless-stopped`). Corrigido com healthcheck (`pg_isready`) + `depends_on:
condition: service_healthy`.

Achado de qualidade de dado (não é código): no arquivo real de ocupação,
`Cap Peso Bruto` vem zerado em 100% das linhas (par inviável) e `Cap Posição`/`Cap
Volume`/`Cap LPN` têm valor sentinela `999999999` (precisa listar em
`ignorar_valores` no modelo, campo já existe). Mesmo filtrando, nenhum par testado deu
um número "limpo" de ocupação — segue pendente a confirmação com o dono do dado (ver
memory/decisoes-fechadas.md / Lote 0).

**Primeiro número real na tela.**

## Lote 2 — Conectores plugáveis completos

**Status: a fazer** · camada de conectores + SharePoint. **Modelo:** Sonnet 5.
Depende do Lote 0 pra testar de verdade.

- [ ] Interface única (`testar` / `buscar` / `detalhar`)
- [ ] Conector `sharepoint_excel` (Microsoft Graph)
- [ ] Registro + toggle no admin

**Check de conclusão:** toggle liga/desliga; `testar()` responde ok/erro; com credencial,
`buscar()` traz ocupação do SharePoint no mesmo formato canônico. Sem credencial, "testar
conexão" acusa erro (esperado) e seguimos no upload manual.

## Lote 3 — Motor + scores

**Status: feito** (16/jul/2026) · motor de scores. **Modelo:** Sonnet 5.

- [x] Decidido: média/desvio-padrão amostral (não mediana/MAD — arquitetura já autorizava
      pro piloto; MAD fica registrado como evolução se o nº de métricas crescer). Janela
      de até 24 competências anteriores (exclui o mês em análise); histórico mínimo de 6
      competências pra ser avaliável (abaixo disso, `historico_curto`); limiar `|z| >= 2`
      pra `fora_padrao`.
- [x] Motor em Python puro (`backend/motor.py`, só stdlib `statistics`)
- [x] Tabela `scores` (já existia no schema do Lote 1) — recalculada por completo
      (delete+insert) a cada rodada, sem recálculo seletivo (volume do piloto é pequeno)
- [x] Disparo pós-ingestão: automático ao fim de `upload/processar`; endpoint manual
      `POST /api/admin/scores/recalcular`; leitura em `GET /api/admin/scores`
- [x] "Sem dado" ≠ "dentro do padrão": ausência de linha em `medidas`/`scores` (o motor
      não grava nada nesse caso) — o Lote 5 (tela) é quem distingue isso de `normal`

**Check de conclusão:** validado local (mesma ressalva do Lote 1 — falta a VM real) com
dataset sintético controlado (perdas+volumetria, 12 meses armazém RPI + 3 meses CGH)
rodando nos containers de verdade: `historico_curto` nos 6 primeiros meses de RPI (e nos
3 meses inteiros de CGH, que nunca atinge o mínimo), `normal` no meio da série, e
`fora_padrao` batendo nas duas métricas juntas em dez/2023 (z=218 perdas, z=-54
volumetria) — reproduz o padrão do cenário conhecido. Recálculo 2x deu o mesmo resultado
(idempotente). **Falta ainda**: rodar sobre os dados reais de perdas/volumetria do Lote 1
pra confirmar que os números batem com o relatório oficial — os três arquivos novos em
`docs/` não servem pra isso (ver nota abaixo).

Achado no processo (não é do Lote 3, não corrigido): o campo `pendencias` da resposta de
`/upload/processar` (`linhas_lidas - linhas_gravadas`) fica negativo quando o modelo tem
mais de uma métrica por linha (cada linha física vira N gravações) — bug do Lote 1,
exposto agora pelo teste com 2 métricas. Fica pendente de decisão.

Nota sobre os arquivos novos em `docs/` (16/jul/2026): nenhum serve pra validar o motor
com dado real agora. `rpt_dw_occupation_detailed_v01 (2).xlsx` é o mesmo snapshot de
ocupação grão-fino do Lote 1 (um dia só, valores zerados/sentinela ainda pendentes com o
dono do dado). `data (2).xlsx` é um export largo (mês nas colunas, jan/26–jul/26) com
linha de subtotal "Total" por cliente somada junto das linhas de cliente — o parser
atual contaria em dobro se subisse como está. `conciliacao_66.csv` é conciliação
SKU×lote, fora do grão do projeto (armazém×mês).

## Lote 4 — Rotina agendada + backup

**Status: a fazer** · **Modelo:** Sonnet 5; script de backup pode ser Haiku 4.5.

- [ ] APScheduler embutido, 1×/dia, worker único
- [ ] Execução manual pelo admin
- [ ] Rebusca das últimas 3 competências
- [ ] Reprocesso = delete + insert por conector × competência
- [ ] `pg_dump` diário copiado pra fora da VM + retenção dos xlsx do upload

**Check de conclusão:** roda sozinha e é idempotente (2× não corrompe); execução manual
funciona; dump gerado e copiado pra fora da VM.

## Lote 5 — A nuvem (tela)

**Status: a fazer** · **Modelo:** Sonnet 5; se a viz travar, escalar pra Opus 4.8.

- [ ] `index.html`: grafo de bolinhas (padrão mapa-ia), lendo só a camada fina
- [ ] Seleção de contexto (filial × período)
- [ ] Estados: aceso / normal / sem-dado

**Check de conclusão:** abre em segundos lendo só a camada fina; contexto filtra; bolinhas
fora do padrão acendem juntas; distingue sem-dado de normal.

## Lote 6 — Confiança e acabamento

**Status: a fazer** · **Modelo:** Sonnet 5 / Haiku 4.5.

- [ ] Painel de cobertura (matriz métrica × armazém × competência presente/ausente)
- [ ] Fila de pendências de de-para no admin
- [ ] Refino visual (skill `superfrio`)
- [ ] Card no Hub (Receita 3, tipo url, nova aba)
- [ ] Tela de ajuda, se precisar

**Check de conclusão:** cobertura mostra os buracos; pendências visíveis e resolvíveis;
visual dentro da identidade; card abre a nuvem numa nova aba do portal.

---

## Fora de escopo (confirmado — degraus seguintes)

Previsão/sazonalidade · padrão por cliente (v2 = tabela-fato `medidas_cliente`) · alertas
/ e-mail · IA narradora · Pentaho (`pentaho_sql`) · drill-down ao vivo (`detalhar()` só
quando existir fonte de grão fino).
