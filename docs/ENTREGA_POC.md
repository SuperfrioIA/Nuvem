# Entrega da POC — Nuvem IA + SharePoint DataHub

Lote P6, fechado em 30/jul/2026. Este documento é o **balanço da POC**: o que foi
provado, com que evidência, o que ficou de fora e que risco sobra. Serve para quem
vai decidir o próximo passo e para quem pegar o código depois.

Escopo, decisões e status por lote: `docs/POC_ATUAL.md` (dono único).
Roteiro de apresentação: `docs/DEMO_POC.md`.
Inventário e armadilhas das fontes: `docs/FONTES_DATAHUB.md`.

---

## 1. Objetivo comprovado

A pergunta da POC era: **a aplicação consegue ler o SharePoint DataHub sozinha e
tirar número auditável de lá, sem ninguém abrir planilha na mão?**

Sim. Provado de ponta a ponta contra o SharePoint real, não contra mock:

| O que foi provado | Evidência |
|---|---|
| Conexão só-leitura com o DataHub | Client Credentials + `Sites.Selected`; conectado em 29/jul/2026 |
| Varredura recursiva da biblioteca | **249 arquivos, 31 pastas** em ~40s (228 xlsx, 19 pdf, 1 json, 1 lock) |
| Alteração no SharePoint aparece na tela | arquivo subido ao vivo apareceu na recontagem após "Sincronizar agora" |
| Leitura e validação de planilha real | família `ENTRADA_MERCADORIAS`, aba `SLIN`, 20 colunas conferidas no cabeçalho |
| KPIs batem com conferência manual | 5 KPIs recalculados **fora do backend**, com download próprio do Graph |
| Resumo textual sem IA | template determinístico, 2 parágrafos, a partir dos KPIs já calculados |
| Mapa das 8 famílias | grafo de bolinhas com 3 junções de dado conferidas no arquivo |
| Nada quebrou no que já existia | **150 testes verdes**, Postgres real, porta 8002, upload manual intactos |

Número de referência da validação (filial 016, competência 2026-07): 8.411 linhas,
R$ 36.649.308,72, 4.281.727 kg, 1.571.339 volumes. A conferência independente do
valor cruzou os itens contra as guias concluídas por `GEM` e fechou em **−1,76%**,
diferença residual de arredondamento.

### Critérios de aceite — status

| Critério | Status |
|---|---|
| Alteração no SharePoint aparece após sincronização manual | **atendido** (validado ao vivo) |
| Lê arquivo real e devolve dados validados | **atendido** (validado ao vivo) |
| KPIs batem com conferência manual | **atendido** (recálculo independente) |
| Demonstração roda em ~5 minutos | **parcial** — roteiro está em ~6 min com o passo da nuvem; não foi cronometrado ao vivo |
| Testes continuam verdes | **atendido** — 150 passed |
| Compatibilidade preservada (porta, Docker, migrations, upload) | **atendido** — a POC entrou ao lado, não substituiu nada |

---

## 2. O que foi entregue

Onze lotes: P0, P1, P1.1, P1.2, P2, P2.1, P2.2, P3, P4, P5, P5.5 e este P6.

**Backend** (tudo aditivo — nenhum arquivo pré-existente foi movido):

- `backend/config.py` — leitura preguiçosa das 5 variáveis `GRAPH_*`
- `backend/services/graph_datahub.py` — cliente Graph só-leitura, cache de token,
  resolução de site por ID, paginação, download com corte de tamanho
- `backend/services/inventario_datahub.py` — inventário em cache de processo
- `backend/services/entrada_mercadorias.py` — leitura e validação da família
- `backend/services/kpis_poc.py` — 5 KPIs auditáveis
- `backend/services/resumo_poc.py` — resumo executivo por template
- `backend/services/nuvem_datahub.py` — bolinhas por família
- `backend/routers/datahub.py` — 5 endpoints, todos exigindo login

**Frontend** (vanilla, sem framework, sem build step): painel DataHub e aba "KPIs da
POC" no `admin.html`; página própria `nuvem.html`; `comum.js` com o que as duas
telas compartilham.

**Testes**: 7 arquivos novos, tudo mockado — nenhum teste toca o SharePoint real.

**Endpoints** (todos sob `/api/admin/datahub/`, todos autenticados): `GET /status`,
`POST /sincronizar`, `POST /ler`, `GET /kpis`, `GET /nuvem`. Páginas: `/admin` e
`/nuvem`.

---

## 3. Limitações declaradas

O que a POC **não** faz. Nada aqui é defeito — é escopo cortado de propósito.

1. **Lê 1 família de 8.** Só `ENTRADA_MERCADORIAS`. As outras 7 estão **mapeadas**
   (sabemos colunas, tamanho, competências), não lidas. Mapeada não é lida.
2. **Um arquivo por vez, sempre o mais recente.** Não há escolha de arquivo na tela
   nem série histórica. Comparar meses ou ver o ano não é possível hoje.
3. **Nada do DataHub é persistido.** O inventário vive em cache de processo: reinício
   do container zera, e a tela volta a pedir "Sincronizar agora". Nenhum dado bruto
   de planilha entra no banco.
4. **Sincronização é manual.** Sem scheduler, sem fila, sem worker — cortado do
   escopo por decisão.
5. **Sem IA em nenhuma etapa.** Cortada em 29/jul/2026. O resumo é template.
6. **Bolinhas não acendem.** O grafo é mapa do que existe, não semáforo de risco —
   decisão de produto, reforçada pela estatística (só 7 competências publicadas
   contra 6 exigidas pelo motor de score).
7. **Filial fica como código numérico** no que a leitura devolve. O de-para para
   sigla WMS está resolvido para `001`/`015`/`016`, mas **`002` segue pendente**.
8. **Prévia limitada a 100 linhas.** O arquivo real tem milhares; devolver tudo em
   JSON só infla a resposta.
9. **Autenticação é senha única de admin**, não SSO corporativo. A página da nuvem
   fica atrás da mesma sessão justamente porque mostra grão fino (cliente, peso,
   valor).
10. **Somente leitura.** O app nunca escreve no SharePoint. O link do arquivo abre
    com as credenciais de **quem clicou** — quem não tem acesso ao site vê o "acesso
    negado" do próprio SharePoint. O app não empresta acesso a ninguém.

### Uma definição em aberto, relevante para apresentação

O card **"Valor total movimentado"** soma entrada **e devolução**. Na 016/2607 são
2.246 linhas de `DEVOLUCAO DE MERCADORIAS (SEM NF-E)` valendo R$ 573.506,14 — 1,6%
do total. Além disso o rótulo pode ser lido como faturamento SuperFrio, quando é o
valor da mercadoria declarado nas notas dos clientes. **Decisão pendente da Maria**
(entra ou não no card, e se o rótulo muda) — ver `memory/concentracao-sapore-016.md`.
O P6 não alterou cálculo nem rótulo.

---

## 4. Obstáculos do dado — leitura obrigatória para quem continuar

Descobertos conferindo os arquivos reais, não inferidos. Detalhe completo em
`docs/FONTES_DATAHUB.md`, seções 5 e 5.1.

1. **Cabeçalho não está na linha 1** e varia por família (1, 2, 3, 5 ou 6). Em
   `SAIDA_MERCADORIAS` está na **linha 6**, não na 5.
2. **Nomes de coluna repetidos.** `EMB` aparece duas vezes em `ENTRADA_MERCADORIAS`;
   em `SAIDA_MERCADORIAS` os 6 rótulos de medida se repetem 3 vezes — peso e volume
   dessa família **só saem por posição**, exceção explícita à regra "coluna por nome".
3. **Contagem de nota fiscal não é construível.** `NF Entrada` é truncada em 10
   caracteres; `NF GEM` é concatenação cortada em 99. A chave confiável é o **`GEM`**.
   Nunca prometer KPI de "quantidade de notas" com o export atual do SLIN.
4. **Guia cancelada não tem linha de item.** Quem usar `GUIAS_ENTRADA` sozinho
   precisa filtrar `Status`, senão infla ~26%.
5. **`DADOS_GERAIS` está com export quebrado:** `_f1` e `_f2` são o mesmo conteúdo,
   linha a linha, nas três competências testadas. Metade de cada competência **não
   está publicada** e concatenar as partes duplica tudo. Ler só o `_f1` e tratar a
   família como meia competência. O defeito é só dessa família.
6. **`GSM` é série por empresa** — a junção `DADOS_GERAIS`↔`GUIAS_SAIDA` só vale
   filtrando `EMP GSM` pela filial do arquivo (98,97% com filtro, 55,23% sem).
7. **711 MB no total** — o conector durável tem que ser incremental, por
   `lastModifiedDateTime` ou competência, nunca baixar tudo a cada rodada.
8. **`PALLETS EXCEDENTES` são 17 PDFs** — sem extração de tabela de PDF, ficam fora.

---

## 5. Riscos

| Risco | Efeito | Mitigação hoje |
|---|---|---|
| Inventário em cache de processo | reinício do container zera; a primeira tela mostra "sincronize primeiro" e **parece quebrado** | sincronizar antes de qualquer apresentação (está no checklist do `DEMO_POC.md`) |
| Client secret do Graph expira | sincronização passa a falhar com 401, sem aviso prévio | nenhuma — **não há processo de rotação definido**; risco aberto |
| Permissão `Sites.Selected` revogada no tenant | app para de ler o DataHub | nenhuma; depende de governança de TI |
| Conteúdo do SharePoint é entrada não confiável | nome de arquivo com HTML executaria script na sessão do admin | escape aplicado em todas as telas; **regra vale para qualquer tela nova** |
| Publicação incompleta do `DADOS_GERAIS` | qualquer KPI de SLA de entrega nasce com metade do mês faltando | limitação declarada; pendência humana aberta com quem publica |
| WSL desliga por ociosidade no ambiente local | Docker cai, containers reiniciam, **parece bug do app** | manter processo ativo na distro; `.wslconfig` com `vmIdleTimeout` não foi aplicado |
| Concentração de 1 cliente (SAPORE ~81% na 016) | número assusta quem vê pela primeira vez e vira discussão | já conferido do zero e documentado; é real, não reabrir |

---

## 6. Pendências abertas ao fechar o P6

**Do projeto (não são código):**

1. **Validação ao vivo do P5.5** — a página da nuvem não foi validada contra o
   SharePoint real pela Maria. Todos os lotes anteriores têm esse registro; este
   não. É o primeiro passo antes de apresentar.
2. **Deploy do P5/P5.5 na VM** — a VM (`172.31.49.141:8002`) está em
   `0004_catalogo_metricas (head)` com os `GRAPH_*` configurados e sincronização
   confirmada, mas o código das telas do P5/P5.5 ainda não subiu. Runbook em
   `docs/DEPLOY.md`, passo 4.1.
3. **Decidir devolução/rótulo no card de valor** (seção 3).
4. **Pendências humanas das fontes** (`docs/FONTES_DATAHUB.md`, seção 6): de-para da
   filial `002`, cadência de publicação, atualizar as 5 fontes do DW, e cobrar a
   republicação do `DADOS_GERAIS`.

**Dívida técnica conhecida, deixada de propósito:**

- O painel **"KPIs da POC" existe duas vezes** — no `admin.html` e no `nuvem.html`,
  cada um com seu próprio render. Decisão de 30/jul/2026: **manter as duas** nesta
  entrega, porque a aba do admin é plano B se a página da nuvem falhar ao vivo.
  Consolidar (mover o render pro `comum.js` ou tirar do admin) é trabalho de quem
  continuar.

---

## 7. O que vem depois

**Nada autorizado.** Os caminhos desenhados e não construídos, para a conversa de
priorização:

- **IA narradora** — trocar o template do resumo por IA que interpreta os KPIs já
  calculados. Salvaguardas já registradas; a IA nunca calcularia número.
- **Integração durável das famílias do DataHub** na camada fina: cabeçalho
  configurável, mapeamento por posição, concatenação `_f1/_f2/_f3`. Depende dos
  obstáculos da seção 4.
- **Série histórica multi-competência** (Lote 11 do `docs/PLANO.md`) — viável, a
  tabela de medidas já é temporal; a trava é a POC ler 1 arquivo e não persistir.
- **Bolinha que acende** (Lote 5 do `docs/PLANO.md`) — quatro caminhos descritos,
  nenhum escolhido. Exige mais competências publicadas para o score ser estável.
- **Nuvem verdadeiramente pública** (só agregados e scores, sem prévia de arquivo).
