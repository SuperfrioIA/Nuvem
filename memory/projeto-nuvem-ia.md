---
name: projeto-nuvem-ia
description: Camada de insights SuperFrio — junta silos numa camada fina e mostra nuvem de métricas que acendem fora do padrão
metadata:
  type: project
---

Nuvem IA junta dados de sistemas (futuramente via Pentaho) e controles manuais
(SharePoint/upload) numa camada fina (de-para + agregados + scores) e mostra uma nuvem
de bolinhas-métricas que acendem quando fogem do próprio padrão histórico, por contexto
(filial × mês). **POC fechada em 21/jul/2026: catering na família RMSP**
(docs/PILOTO.md refeito) — ocupação + contratos take-or-pay + volumetria, com grão
cliente mínimo (Lote 9.5) e perdas fora por ora. Fase atual: construção em lotes (ver
docs/PLANO.md) — Lotes 1 (esqueleto, banco, upload manual), 3 (motor de scores) e 7
(de-para oficial das 32 filiais SF) feitos; **primeiro deploy na VM real validado em
20/jul/2026** (só o admin, na 8002, rede interna — runbook em docs/DEPLOY.md). Lote 0
quase fechado (filiais escolhidas em 21/jul; falta Entra ID, donos do dado e pedidos ao
DW); próximos: Lote 7.1 (RMSPV + lista catering no de-para) e Lote 8 (relatórios reais
como fonte, recorte RMSP). Base analítica da POC: `docs/Analise/saida/`
(analise_rmsp.xlsx + analise-rmsp/ + mapa-dados com tabelas por nó e filtro por
filial). Dona: Maria Watanabe (CSC).

**Why:** hoje há milhares de BIs individuais e o cruzamento mora na cabeça das pessoas.
**How to apply:** o motor de cruzamento é o valor; o grafo é a embalagem. Máquina tria,
humano valida. Nunca copiar dado bruto pra dentro — só resumos. Ver [[decisoes-fechadas]].
