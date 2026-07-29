# POC atual — Nuvem IA + SharePoint DataHub

**Este documento é o dono único do escopo ativo, do status dos lotes P0–P6 e do
próximo lote autorizado** (decisão de 29/jul/2026 — ver `memory/decisoes-fechadas.md`).
Nenhum outro arquivo mantém status desses lotes. Origem completa da especificação:
`docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md` (marcado como superado nesta data — fica
no lugar como referência técnica detalhada de cada lote P1–P6, não como fonte de
status).

Para o histórico de produto (Lotes 0–10, R0–R3), continue usando `docs/PLANO.md` —
este documento não o substitui.

---

## Objetivo

Provar, de ponta a ponta, que a aplicação consegue: conectar-se ao SharePoint
DataHub, listar arquivos/pastas de uma pasta configurada, atualizar esse inventário
sob demanda ("Sincronizar agora"), ler uma planilha real selecionada, calcular
poucos KPIs auditáveis e gerar um resumo textual determinístico (sem IA) sobre eles.

## Como isso se encaixa no projeto

Existe **uma** POC: catering na família RMSP (`docs/PILOTO.md`), alimentada por
**dois canais de fonte** que convergem na mesma camada fina:

1. **SharePoint DataHub** — exports do WMS SLIN (228 arquivos/711 MB, 8 famílias —
   inventário completo em `docs/FONTES_DATAHUB.md`), justamente os clientes de
   catering da POC;
2. **Arquivos locais do Pentaho/DW** — os 5 modelos de importação já construídos
   (Lotes 8/R1.1), via upload manual.

Os Lotes P0–P6 são o marco que prova o canal DataHub de ponta a ponta com um KPI de
amostra. Não substituem a integração durável das famílias do DataHub na camada fina
(cabeçalho configurável, mapeamento por posição, concatenação `_f1/_f2/_f3`) — isso
vem depois, como incremento do caminho dos modelos de importação.

## Fluxo da demonstração

1. A tela mostra a conexão ativa com o DataHub.
2. A quantidade atual de pastas e arquivos é exibida.
3. Uma nova pasta/arquivo é adicionada manualmente no SharePoint.
4. Clica em **Sincronizar agora**.
5. A nova pasta/arquivo aparece na contagem.
6. Abre a tela de KPIs.
7. A aplicação mostra indicadores calculados com dados reais de uma planilha.
8. Um resumo textual curto (template determinístico) explica o que foi encontrado.

## Escopo incluído

- Cliente Graph somente leitura (Client Credentials, `Sites.Selected` + `read`);
- Tela DataHub com sincronização manual (sem scheduler);
- Leitura controlada de uma única família de planilha (`ENTRADA_MERCADORIAS`,
  preferencialmente — cabeçalho na linha 1, sem partes `_f1/_f2/_f3`);
- 3 a 5 KPIs determinísticos, auditáveis (coluna/regra, unidade, nº de registros
  válidos, fonte);
- Resumo textual por template (sem IA).

## Escopo excluído (não construir nesta POC)

Scheduler, sincronização automática recorrente, Celery, Redis, filas, workers
adicionais, banco vetorial, RAG, chatbot, agentes, IA para redigir o resumo
(decisão de 29/jul/2026 — candidata a incremento pós-demo), leitura genérica de
qualquer planilha, processamento das 8 famílias do DataHub de uma vez, leitura de
PDFs, "nuvem de bolinhas" completa, motor genérico de insights, autenticação
corporativa completa, novo data lake, cópia integral do DataHub pro Postgres,
reescrita do backend, framework abstrato de conectores, arquitetura de
microsserviços.

## Princípio central

A IA não calcula números nem interpreta a planilha bruta livremente:

```
SharePoint → leitura/validação determinística → metadados → KPIs em código
→ resumo estruturado → resumo textual por template (determinístico)
```

## Ambiente da demo

- **Fase 1 (a demo):** máquina da Maria (Docker/WSL), `.env` local com os `GRAPH_*`.
  Nada precisa subir pra VM antes da apresentação.
- **Fase 2 (pós-demo):** subir pra VM (porta 8002). Pendências: aplicar as
  migrations 0002–0004 (R1–R3 ainda não deployados lá), repassar os `GRAPH_*` no
  compose/`.env` da VM, confirmar saída HTTPS da VM pros endpoints da Microsoft.

## Lotes e status

| Lote | Objetivo | Status |
|---|---|---|
| P0 | Diagnóstico e organização segura do repositório | **feito** (29/jul/2026) |
| **P1** | Configuração + cliente mínimo do Microsoft Graph (`backend/config.py`, `backend/services/graph_datahub.py`) | **feito** (29/jul/2026) |
| **P1.1** | Correções do P1 achadas em revisão: cache de token, URL de subpasta, erro de configuração na hierarquia `GraphError` | **feito** (29/jul/2026) |
| **P2** | Tela DataHub + sincronização manual (`backend/routers/datahub.py`) | **feito** (29/jul/2026) |
| **P1.2** | Correção achada testando o P2 ao vivo: endereçamento por site ID no cliente Graph | **feito** (29/jul/2026) |
| P2.1 | Link do arquivo pro SharePoint (`web_url` + `id` no inventário) | a fazer |
| P3 | Leitura controlada de uma planilha (`ENTRADA_MERCADORIAS`) | a fazer |
| P4 | KPIs da POC (`backend/services/kpis_poc.py`) | a fazer |
| P5 | Resumo textual (template) + acabamento da demo | a fazer |
| P5.5 | Nuvem do DataHub: grafo de bolinhas por família, com drill-down | a fazer |
| P6 | Revisão final e limpeza pós-POC | a fazer |

Especificação técnica completa de cada lote (endpoints, requisitos de segurança,
casos de teste, critério de aceite detalhado): `docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md`,
seção 8. Resumo de cada um:

- **P1** — `obter_token()` / `testar_conexao()` / `listar_itens()` via `httpx`,
  Client Credentials; nunca logar segredo; tratar 401/403/404/429/timeout;
  paginação por `@odata.nextLink`; testes com mocks de HTTP (sem SharePoint real).
- **P2** — `GET /api/admin/datahub/status`, `POST /api/admin/datahub/sincronizar`,
  `GET /api/admin/datahub/resumo`; listagem recursiva; inventário em cache de
  processo (não criar tabela salvo necessidade clara); tela com status/contadores/
  lista de pastas e arquivos recentes. O cliente Graph é síncrono (`httpx.get`) —
  declarar os endpoints como `def` comum, **não** `async def`, senão a
  sincronização bloqueia o event loop do FastAPI durante toda a varredura.
- **P2.1** — o `children` do Graph já devolve `webUrl` e `id` por item, e o
  inventário do P2 descarta os dois. Carregar ambos no dicionário de arquivo
  (`backend/services/inventario_datahub.py`) e transformar o nome do arquivo em
  link (`target="_blank"`) na lista do painel. O `id` é o `item_id` que o P3 vai
  precisar pro download — entra na mesma alteração pra poupar retrabalho. Nenhuma
  chamada nova ao Graph, nenhuma permissão nova. O link abre o SharePoint **como a
  pessoa que clicou**, com as credenciais dela: quem não tem acesso ao site DataHub
  vê o "acesso negado" do próprio SharePoint (comportamento aceito em 29/jul/2026 —
  o app não empresta acesso a ninguém).
- **P3** — download por `item_id` (nunca URL arbitrária), validação de
  nome/extensão/tamanho, leitura com `openpyxl`, metadados obrigatórios (arquivo,
  competência/filial inferidas, linhas lidas/válidas/descartadas, % qualidade).
  Colunas localizadas **por nome**, via dicionário cabeçalho→índice montado na
  leitura — nunca índice chumbado (ver decisões técnicas). O timeout de 10 s do
  cliente Graph serve pra listar, não pra baixar arquivo: usar timeout próprio,
  maior, no download.
- **P4** — 3 a 5 KPIs entre os candidatos (registros, clientes, volume, peso
  líquido/bruto, UAs, valor movimentado); tela "KPIs da POC" com auditoria por KPI.
- **P5** — template determinístico do resumo; `docs/DEMO_POC.md` com roteiro e
  checklist de preparação.
- **P5.5** — **Nuvem do DataHub** (decisão de 29/jul/2026). Página **própria**
  (`frontend/nuvem.html`), fora do `admin.html` — o admin é ferramenta de
  administração, a nuvem é o produto. Fica **atrás da mesma sessão/senha** enquanto
  mostrar grão fino (ver decisões técnicas). Escopo:
  - **Bolinha = família do DataHub** (as 8 do inventário, agrupadas nas 4 áreas:
    ENTRADA, SAIDA, ENTREGAS, ESTOQUE). Tamanho por nº de arquivos ou MB; estado
    visual: integrada / mapeada mas não lida / só PDF.
  - Nenhuma leitura nova de arquivo pra desenhar o grafo — usa o inventário que o
    P2 já mantém em cache.
  - **Clique na bolinha → área de baixo**: lista de arquivos daquela família (nome
    com link pro SharePoint via `web_url` do P2.1, competência, filial, tamanho,
    última modificação).
  - **Só na família integrada** (`ENTRADA_MERCADORIAS`): além da lista, os cards de
    KPI do P4 e **prévia de ~100 linhas** validadas, renderizadas na hora, sem
    persistir nada (respeita "nada de dado bruto na camada fina"). Nas outras
    bolinhas, metadado só — arquivos de SAIDA/ESTOQUE têm vários MB e a prévia
    exigiria streaming com cuidado.
  - **Sem bolinha acendendo** nesta versão (ver decisões técnicas). A bolinha é
    mapa do que existe, não semáforo de risco.
  - Frontend vanilla (HTML/JS/SVG), padrão do `mapa-dados` já validado em
    21/jul/2026 — sem framework novo.
- **P6** — limpeza de código temporário/prints/endpoints inseguros; suíte
  completa; `docs/ENTREGA_POC.md` com objetivo comprovado, limitações e riscos.

## Critérios de aceite gerais

- Uma alteração no SharePoint aparece na tela após sincronização manual;
- A aplicação lê um arquivo real selecionado no DataHub e devolve dados validados;
- Os KPIs batem com conferência manual;
- A demonstração completa roda em ~5 minutos;
- Testes existentes (44, Postgres real via Docker/WSL) continuam verdes em cada lote;
- Compatibilidade preservada: porta 8002, Docker Compose, Postgres, migrations,
  upload manual, endpoints e admin atuais — a POC entra ao lado, não quebra o fluxo.

## Decisões técnicas fixadas

- IA cortada da POC (29/jul/2026): resumo só por template determinístico; camada de
  IA narradora é candidata a primeiro incremento pós-demo (salvaguardas já registradas
  em `docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md`, seção "IA no resumo — cortada da POC").
  Ver `memory/decisoes-fechadas.md`.
- Cliente Graph (`backend/services/graph_datahub.py`) é serviço de infraestrutura —
  **não** implementa a interface `Conector` de `backend/conectores/base.py`. O
  conector `sharepoint_excel` real (formato canônico + modelos de importação) fica
  para depois da POC.
- Estrutura de pastas é aditiva: nada do que existe hoje é movido para "bater" com o
  desenho novo (`backend/services/`, `backend/routers/` entram como pastas novas
  para o código novo).
- Não criar tabela nova para o inventário do DataHub salvo necessidade clara
  (comparação entre sincronizações, rastreabilidade) — decisão fica para o P2.
- **Nuvem em página própria, mas autenticada** (29/jul/2026): a decisão antiga do
  projeto é "senha só no `/admin`, nuvem aberta na rede interna" — mas ela foi tomada
  quando a nuvem mostraria só agregados e scores. O P5.5 exibe prévia de planilha com
  nome de cliente, CNPJ, pesos e valores; numa página sem senha isso ficaria aberto a
  qualquer pessoa da rede interna. Então: página separada do admin (organização), com
  senha (exposição de dado). Bônus prático: os endpoints já vivem em
  `/api/admin/datahub/*` e são reaproveitados sem criar endpoint público novo. A nuvem
  verdadeiramente aberta continua sendo o Lote 5 do `docs/PLANO.md` — só agregados e
  scores, sem prévia de arquivo.
- **Bolinhas não acendem no P5.5** (29/jul/2026, decisão da Maria — "agora é pra
  mostrar que temos os dados; só depois começar a dizer que algo está anormal"). Além
  da razão de produto, a estatística não sustentaria: o motor exige 6 competências
  anteriores à analisada, e o DataHub tem 7 (jan–jul/2026) — só jul/2026 seria
  avaliável, com desvio-padrão tirado de 6 pontos (instável: `|z| >= 2` dispararia
  quase por sorteio). As outras 6 competências cairiam em `historico_curto`. Se a
  bolinha parecesse detector de anomalia sem ser, viraria pergunta difícil na
  apresentação. Caminhos registrados para quando acender (nenhum autorizado):
  regra fixa de cobertura/publicação (não precisa de histórico), variação vs
  competência anterior (precisa de 2), motor de scores sobre as fontes do **DW**
  (volumetria tem série 2021→hoje, histórico de verdade) e detectores de regra de
  negócio (Lote 9/9.5 do `docs/PLANO.md`).
- **Leitura de planilha por nome de coluna, não por posição** (29/jul/2026): o P3
  monta um dicionário cabeçalho→índice ao ler o arquivo e busca cada coluna que os
  KPIs precisam pelo rótulo. Motivo: se alguém acrescentar coluna na planilha
  amanhã, a leitura continua funcionando (coluna não mapeada simplesmente não entra
  — mesma regra do parser dos modelos de importação, Lote 1). Índice chumbado
  quebraria a cada coluna nova. Posição só entra para desempatar rótulo duplicado
  (`EMB` aparece duas vezes em `ENTRADA_MERCADORIAS`) — e nenhum KPI candidato do P4
  usa essas colunas. Coluna mapeada ausente ou renomeada deve **falhar com mensagem
  clara** ("coluna 'Peso Bruto' não encontrada"), nunca produzir número errado.

## Status atualizado

29/jul/2026 — **P0 fechado** (organização segura do repositório, sem alterar
comportamento). **P1 fechado**: `backend/config.py` (leitura preguiçosa das
variáveis `GRAPH_*`) e `backend/services/graph_datahub.py` (cliente somente
leitura — `obter_token`/`testar_conexao`/`listar_itens`, Client Credentials,
paginação por `@odata.nextLink`, trata 401/403/404/429/timeout/falha de
rede/resposta inválida, nunca loga segredo ou token); `tests/test_graph_datahub.py`
cobre os 8 cenários pedidos + 404/429/falha de rede, tudo mockado. `requirements.txt`
ganhou `httpx`; `docker-compose.yml` repassa os 5 `GRAPH_*` ao `nuvem-app` (default
vazio — não quebra quem ainda não configurou). Nenhum endpoint/rota criado ainda
(fica pro P2). Suíte: 64 passed (44 + 20 novos, Docker/WSL, Postgres real).

29/jul/2026 — **P1.1 fechado** (correções de revisão do P1, sem escopo novo):

- **Cache de token de processo** (`obter_token`): o token vale ~1h e era pedido a
  cada `listar_itens()`. Na listagem recursiva do P2 isso seria uma autenticação
  por pasta (a árvore do DataHub passa de 20 com as subpastas por cliente) —
  lentidão visível e risco de 429. Renovação com margem de 5 min; 401 do Graph
  descarta o cache pra próxima chamada reautenticar.
- **URL de subpasta corrigida**: faltava o `:` que fecha o caminho do site antes do
  sub-recurso (`.../sites/DataHub:/drive/items/{id}/children`). Sem ele o Graph lê
  `/sites/DataHub/drive/...` como caminho do site e responde 400/404 — quebraria na
  primeira subpasta da listagem recursiva do P2.
- **Falta de configuração entrou na hierarquia `GraphError`**: `config.py` levanta
  `ConfiguracaoGraphIncompletaError` (subclasse de `RuntimeError`, compatível) e o
  serviço traduz pra `GraphConfiguracaoIncompletaError`. Antes, `.env` sem os
  `GRAPH_*` fazia `testar_conexao()` estourar exceção — contra a própria promessa da
  função — e viraria erro 500 no painel do P2 em vez de "faltam as variáveis: …".

Suíte: **70 passed** (64 + 6 novos: config fora da hierarquia, URL de subpasta,
reaproveitamento/renovação/invalidação de token, `testar_conexao` sem configuração).

29/jul/2026 — **P2 fechado**: `backend/services/inventario_datahub.py` (cache em
memória do processo, reconstruído só em `sincronizar()` — `status()` nunca chama o
Graph); percorre a pasta configurada **recursivamente** (desce em cada `item_id` de
pasta retornado pelo próprio Graph, nunca por caminho digitado) e monta total de
arquivos/pastas, contagem por extensão, lista de pastas e os 10 arquivos mais
recentes. Falha de sincronização preserva o último resumo bom no cache.
`backend/routers/datahub.py`: **2 endpoints** (`GET /status`, `POST /sincronizar`,
ambos `def` comum) em vez dos 3 do desenho original — o resumo já vai dentro da
resposta, sem endpoint `/resumo` separado. `backend/main.py` registra o router.
`frontend/admin.html` ganhou o painel "DataHub" (mesmo padrão dos painéis de
Catálogo/Métricas): status da conexão, pasta configurada, última sincronização,
cards de contagem, extensões, pastas e arquivos recentes, botão "Sincronizar agora"
com estado de carregamento. Nenhuma tabela nova no banco; nenhum arquivo do P1/P1.1
alterado. Suíte: **86 passed** (70 + 16 novos, `tests/test_inventario_datahub.py` e
`tests/test_datahub_router.py`, tudo mockado — nenhuma chamada real ao SharePoint).

29/jul/2026 — **P1.2 fechado** (bug achado testando o P2 ao vivo, pela Maria, contra
o SharePoint real): o primeiro clique em "Sincronizar agora" voltou
`resposta inesperada do Graph (HTTP 400)`. Causa raiz confirmada chamando o Graph
real: `listar_itens()` endereçava a pasta encadeando **dois** segmentos de caminho
com `:` numa URL só (`/sites/{host}:{caminho}:/drive/root:/{pasta}:/children`) — o
Graph não aceita isso e respondia
`"Resource not found for the segment 'root:'."`. Correção: `graph_datahub.py` ganha
`_resolver_site_id()` (resolve o site pelo caminho — um só `:` — e cacheia o ID
retornado, sem `:`, reaproveitado entre chamadas); `listar_itens()` passa a
endereçar a pasta e as subpastas pelo ID do site, nunca mais encadeando dois `:`.
`tests/test_graph_datahub.py`: testes de listagem com sucesso ajustados pra
responder a chamada extra de resolução do site (helper `_mock_get`); os testes de
erro (403/404/429/timeout/rede/resposta malformada) não precisaram mudar — o mesmo
tipo de exceção é levantado não importa em qual das duas chamadas o erro
aconteça; 2 testes novos (site ID reaproveitado entre chamadas, resposta sem campo
`id`). Suíte: **88 passed**. Validado ao vivo contra o SharePoint real após a
correção: sincronização completa em ~40s, **249 arquivos, 31 pastas** (228 xlsx, 19
pdf, 1 json, 1 lock), sem erro.

## Próximo lote autorizado

**P2.1 autorizado** (29/jul/2026) — curto, independente do P3, pode rodar já.

**P5.5 registrado na fila, não autorizado a começar**: depende do P4 (precisa dos KPIs
para o drill-down da família integrada), então roda depois do P5 e antes do P6.

P3, P4, P5, P5.5 e P6 só começam após validação explícita da Maria, um por vez.
