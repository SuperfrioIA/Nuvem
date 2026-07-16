---
name: projeto-nuvem-ia
description: Camada de insights SuperFrio — junta silos numa camada fina e mostra nuvem de métricas que acendem fora do padrão
metadata:
  type: project
---

Nuvem IA junta dados de sistemas (futuramente via Pentaho) e controles manuais
(SharePoint/upload) numa camada fina (de-para + agregados + scores) e mostra uma nuvem
de bolinhas-métricas que acendem quando fogem do próprio padrão histórico, por contexto
(filial × mês). Piloto: Perdas × Volumetria × Ocupação (docs/PILOTO.md). Fase atual
(16/jul/2026): construção em lotes (ver docs/PLANO.md) — Lote 1 (esqueleto, banco,
upload manual) e Lote 3 (motor de scores) feitos, validados localmente; Lote 0 (TI/Entra
ID) e Lote 2 (conectores completos/SharePoint) pendentes. Dona: Maria Watanabe (CSC).

**Why:** hoje há milhares de BIs individuais e o cruzamento mora na cabeça das pessoas.
**How to apply:** o motor de cruzamento é o valor; o grafo é a embalagem. Máquina tria,
humano valida. Nunca copiar dado bruto pra dentro — só resumos. Ver [[decisoes-fechadas]].
