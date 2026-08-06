---
name: historico-datahub-por-familia
description: A entrada por item só tem 2026; SAIDA_MERCADORIAS e ENTRADA_MERCADORIAS (UA) têm série desde out/2021 — e o inventário dobrou para 810 arquivos
metadata:
  type: project
---

Inventário completo lido do Graph em 06/08/2026: **810 arquivos** (770 `.xlsx`) em 61
pastas — mais que o dobro dos 367 registrados em 31/07 ([[reestruturacao-datahub-4-unidades]]).
O que cresceu foi histórico.

| Unidade | Família | Competências | Filiais |
|---|---|---|---|
| RMSPII | `ENTRADA_MERCADORIAS` | 2026-01 .. 2026-08 (8) | 001, 015, 016 |
| RMSPII | `ENTRADA_MERCADORIAS_UA` | **2021-10 .. 2026-08 (50)** | 001, 015, 016 |
| RMSPII | `SAIDA_MERCADORIAS` | **2021-10 .. 2026-08 (50)** | 001, 015, 016 |
| CWB3 | entrada e saída | 2026-01 .. 2026-08 | 001 |
| RJ | entrada e saída | 2026-01 .. 2026-08 | 004-003 |
| SANCA | entrada | 2026-01 .. 2026-08 | 025 |
| SANCA | saída | 2026-06 .. 2026-08 | 025 |

**Nas famílias de volumetria cada unidade tem um único código de filial.** Os códigos
`002`, `004-001` e `005-001` só aparecem em `DADOS_GERAIS` e `OCORRENCIAS_ENTREGAS`, que
não estão integradas — então o de-para novo é 1:1 e a guarda de colisão de
`processamento_datahub.py:435-443` não é acionada por ele.

A estrutura de pastas **continua** `{unidade}/{ÁREA}/{PASTA}/` — não mudou, apesar da
impressão em contrário ao olhar o SharePoint.

**Why:** a proposta V2 tratava a saída como "a direção que falta". Ela é também a única
volumetria com histórico profundo, o que inverte a prioridade do lote. E a assimetria
explica por que a comparação 2025 vs 2026 não é de graça: os arquivos de 2025 que
existem são de `SAIDA_MERCADORIAS` e da família `(UA)`, que é grão de UA e não de item —
concatenar com a entrada por item criaria um degrau falso na virada do ano. A decisão em
06/08 foi ficar só em 2026 ([[volumetria-v2-decisoes]]).

**How to apply:** ao planejar histórico ou comparação anual, checar a família antes de
prometer a série — `ENTRADA_MERCADORIAS` não tem 2025. E o padrão de nome da ingestão
(`^ENTRADA_MERCADORIAS_(\d+(?:-\d+)*)_(\d{2})(\d{2})\.xlsx$`) rejeita tanto
`ENTRADA_MERCADORIAS_UA_001_2502.xlsx` quanto os partidos `_f1`/`_f2`: eles aparecem no
Laboratório (que classifica por prefixo) e somem no processamento, sem erro. Existe
competência **2608** desde 06/08 — a V1 processou até 2607.
