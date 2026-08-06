---
name: layout-entrada-por-unidade
description: Conferido no dado em 06/ago/2026 — CWB3 e SANCA têm as 20 colunas da ENTRADA_MERCADORIAS, a RJ tem 18 (sem Cliente/Cliente CNPJ)
metadata:
  type: project
---

Conferência somente leitura pelo Graph em 06/08/2026, arquivo por arquivo, antes de
abrir o lote V2.1:

| Origem | Colunas na linha 1 | Bate com as 20 esperadas |
|---|---:|---|
| `CWB3/001` | 20 | sim, rótulo a rótulo |
| `SANCA/025` | 20 | sim, rótulo a rótulo |
| `RJ/004-003` | **18** | não — faltam `Cliente` e `Cliente CNPJ` |

A RJ tem 8 arquivos (2601–2608), todos `004-003`, aba `SLIN`, cabeçalho na linha 1.
Os arquivos da SANCA de 2601 a 2605 têm ~30 KB — pouquíssima linha, e isso é a fonte,
não defeito.

**Why:** a `docs/proposta_v3_volumetria.md` seção 6 afirmava que a `004-003` era a de
20 colunas e que a variante sem `Cliente` "fica para quando aparecer". Está errado — o
`docs/FONTES_DATAHUB.md` estava certo desde 02/ago. Se o de-para da RJ entrasse no V2.1
sem essa conferência, os 8 arquivos dela sairiam de pendência limpa para erro de
leitura, que é exatamente o que o lote de identidade de 02/ago evitou. Ver
[[volumetria-v2-decisoes]] e [[filiais-catering-poc]].

**How to apply:** no V2.1 entram só `CWB3/001 → CWBIII` e `SANCA/025 → RMSPV`. A RJ
entra no V2.3, junto do leitor da variante de 18 colunas — e nessa hora a decisão
pendente é de produto, não técnica: sem coluna de cliente, **toda a RMRJ cai no balde
"sem cliente identificado"**; peso e valor aparecem, decomposição por cliente não.
