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
| **P0** | Diagnóstico e organização segura do repositório (este lote) | **em andamento** |
| P1 | Configuração + cliente mínimo do Microsoft Graph (`backend/config.py`, `backend/services/graph_datahub.py`) | a fazer |
| P2 | Tela DataHub + sincronização manual (`backend/routers/datahub.py`) | a fazer |
| P3 | Leitura controlada de uma planilha (`ENTRADA_MERCADORIAS`) | a fazer |
| P4 | KPIs da POC (`backend/services/kpis_poc.py`) | a fazer |
| P5 | Resumo textual (template) + acabamento da demo | a fazer |
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
  lista de pastas e arquivos recentes.
- **P3** — download por `item_id` (nunca URL arbitrária), validação de
  nome/extensão/tamanho, leitura com `openpyxl`, metadados obrigatórios (arquivo,
  competência/filial inferidas, linhas lidas/válidas/descartadas, % qualidade).
- **P4** — 3 a 5 KPIs entre os candidatos (registros, clientes, volume, peso
  líquido/bruto, UAs, valor movimentado); tela "KPIs da POC" com auditoria por KPI.
- **P5** — template determinístico do resumo; `docs/DEMO_POC.md` com roteiro e
  checklist de preparação.
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

## Status atualizado

29/jul/2026 — Lote P0 em andamento: criação deste documento, do inventário do
repositório e organização/atualização de referências. Nenhum lote de código (P1+)
começou.

## Próximo lote autorizado

Nenhum lote de código foi autorizado ainda. **P1 só começa após validação explícita
da Maria ao final do P0.**
