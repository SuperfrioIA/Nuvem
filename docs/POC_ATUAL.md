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
| **P2.1** | Link do arquivo pro SharePoint (`web_url` + `id` no inventário) | **feito** (29/jul/2026) |
| **P2.2** | Escape de conteúdo externo no painel do DataHub | **feito** (29/jul/2026) |
| **P3** | Leitura controlada de uma planilha (`ENTRADA_MERCADORIAS`) | **feito** (29/jul/2026) |
| **P4** | KPIs da POC (`backend/services/kpis_poc.py`) | **feito** (29/jul/2026) |
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
- **P2.2** — endurecer a renderização do painel do DataHub: helper `escaparHtml()`
  (ou `textContent`/`createElement`, padrão que o `admin.html` já usa em outro
  ponto) nos valores que vêm do SharePoint, e validação de esquema (só `http`/
  `https`) antes de pôr a `web_url` num `href`. Curto e independente dos outros
  lotes. Ver a decisão técnica sobre escape.
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
  - **Escape obrigatório** (ver decisões técnicas): a lista de arquivos e a prévia
    de 100 linhas são conteúdo vindo do SharePoint — nada disso entra por
    `innerHTML` sem escapar.
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
  apresentação. Os quatro caminhos possíveis para quando acender — regra fixa de
  cobertura/publicação, variação vs competência anterior, motor de scores sobre as
  fontes do DW, detectores de regra de negócio — estão descritos em `docs/PLANO.md`,
  nota de 29/jul/2026 no **Lote 5**. **Nenhum autorizado**; a escolha é conversa à
  parte, fora do escopo da POC.
- **Conteúdo do SharePoint nunca entra por `innerHTML` sem escapar** (29/jul/2026):
  nome de arquivo, caminho, `web_url` e — no P5.5 — as células da prévia de 100 linhas
  são texto controlado por quem publica na biblioteca do DataHub, não pelo projeto. Um
  arquivo nomeado com HTML executaria script dentro do painel autenticado, com a
  sessão do admin. Probabilidade baixa (exige ator interno com acesso de escrita
  nomeando arquivo de propósito), mas a superfície cresce muito no P5.5, onde a prévia
  são milhares de células externas. Regra: escapar (helper `escaparHtml()`) ou montar
  via `textContent`/`createElement`; e validar esquema (`http`/`https`) antes de usar
  URL externa em `href`. O padrão de `innerHTML` com template string é anterior ao
  P2.1 — não é regressão dele; o P2.2 corrige o painel atual e o P5.5 nasce já com a
  regra.
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

29/jul/2026 — **P2.1 fechado**: `backend/services/inventario_datahub.py` carrega
`id` e `web_url` de cada item de arquivo direto do `children` do Graph (campos
`id`/`webUrl`, já vinham na resposta — confirmado ao vivo, nenhuma chamada nova).
`frontend/admin.html`: nome do arquivo na tabela de recentes vira link
(`target="_blank" rel="noopener"`) pro `web_url`, com fallback pro texto simples se
faltar. `id` fica salvo no resumo como o `item_id` que o P3 vai usar pro download.
Teste novo (`test_arquivo_inclui_id_e_web_url`) confirma que os dois campos
sobrevivem do item bruto do Graph até o resumo. Suíte: **89 passed**.

29/jul/2026 — **P2.2 fechado**: `frontend/admin.html` ganha helper `escaparHtml()`
aplicado em `nome`, `caminho` e `extensao` nas duas tabelas do painel DataHub
(extensões e arquivos recentes) — os três campos derivam de nome de arquivo cru do
SharePoint e entravam por `innerHTML` sem escape. `web_url` só vira `<a href>` se
passar validação de esquema (`^https?://`); fora isso, mostra o nome como texto
puro, sem link. Sem mudança de backend, sem endpoint novo. Validado pela Maria ao
vivo: rebuild da imagem (`docker compose up -d --build` — `frontend/` é `COPY` no
Dockerfile, não volume) e injeção de payload malicioso via console do navegador
(sem alterar dado real no SharePoint), sem disparo de script e sem link para nome
malicioso. Suíte Python inalterada (nenhum arquivo `.py` tocado).

29/jul/2026 — **P3 fechado**: `backend/services/entrada_mercadorias.py` (novo) le
e valida a familia `ENTRADA_MERCADORIAS`. Guarda de seguranca: item_id so e aceito
se aparecer na ultima sincronizacao (`inventario_datahub.py` ganhou a chave
`arquivos` -- lista completa dos itens, nao so os 10 recentes -- vira a lista de
permissao). Nome tem que bater `ENTRADA_MERCADORIAS_{filial}_{AAMM}.xlsx`, extensao
`.xlsx`, aba `SLIN`. Decisao de 29/jul/2026: as 20 colunas do export sao
obrigatorias no cabecalho (nao so as 6 dos KPIs do P4), mas so as 6 numericas
(Volume, Peso Líquido, Peso Bruto, Vlr. Unitário, Vlr. Total, Qtde UA) recebem
validacao de valor -- aceita numero nativo do openpyxl ou texto no formato BR
(ponto de milhar, virgula decimal), descarta a linha se nao converter. Filial fica
crua (codigo numerico do nome do arquivo) -- de-para pra sigla WMS continua
pendencia humana (§6 do FONTES_DATAHUB), pela inconsistencia ja documentada do
`GUIAS_ENTRADA_001`. `graph_datahub.py` ganha `baixar_item()`: streaming com corte
de tamanho (reaproveita `UPLOAD_MAX_MB`, sem variavel nova), timeout proprio de
60s, segue redirect do Graph. `backend/routers/datahub.py` ganha `POST /ler` (def
comum), devolve metadados + ate 100 linhas (arquivo real tem milhares). Validado
pela Maria ao vivo contra o SharePoint real via console do navegador (chamada
autenticada com a sessao do admin). Suite: **115 passed** (89 + 26 novos).

29/jul/2026 — **P4 fechado**: `backend/services/kpis_poc.py` (novo) calcula 5 dos 7
KPIs candidatos da especificação (decisão de 29/jul/2026: quantidade de registros,
quantidade de clientes, volume total, peso bruto total, valor total movimentado —
peso líquido e quantidade de UAs ficaram de fora por redundância pra esse demo).
Cada KPI leva auditoria (coluna/regra, unidade, registros válidos, fonte) e há um
agrupamento por cliente ordenado por valor total. `entrada_mercadorias.py` ganha
`item_mais_recente()` — a tela não deixa escolher entre os até 20 arquivos da
família, sempre usa o mais recente sincronizado. `backend/routers/datahub.py`
ganha `GET /kpis` (sem cache próprio, recalcula a cada chamada — o botão
"Atualizar" da tela é só uma nova chamada). `frontend/admin.html` ganha a aba
"KPIs da POC": dados do arquivo, cards de KPI, gráfico de barras simples (valor por
cliente, top 10) e tabela por cliente — carrega ao abrir a aba, escapa todo
conteúdo vindo do SharePoint (nome de cliente, arquivo) via `escaparHtml()`.
Validado pela Maria ao vivo contra o SharePoint real. Suíte: **126 passed**
(115 + 11 novos).

Achado à parte, fora do código do app: o ambiente local de validação (WSL2,
Ubuntu-24.04, dockerd nativo sem Docker Desktop) desliga a distro por
ociosidade entre comandos, derrubando o Docker e reiniciando os containers —
pareceu bug do app, mas era o WSL. Sem `.wslconfig` (`vmIdleTimeout`) hoje;
contornado nesta sessão mantendo um processo (`sleep infinity`) na distro.
Ajuste permanente (criar `.wslconfig` com `vmIdleTimeout` maior) fica como
decisão da Maria, não foi aplicado.

## Próximo lote autorizado

**P5.5 registrado na fila, não autorizado a começar**: depende do P4 (precisa dos KPIs
para o drill-down da família integrada), então roda depois do P5 e antes do P6.

P3, P4, P5, P5.5 e P6 só começam após validação explícita da Maria, um por vez.
