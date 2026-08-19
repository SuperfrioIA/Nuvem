---
name: layout-entrada-por-unidade
description: Conferido no dado — na ENTRADA_MERCADORIAS CWB3/SANCA têm 20 colunas e a RJ 18; na família (UA) RMSPII/CWB3 têm 27, SANCA 28 e a RJ 25 — a RJ é sem cliente nas DUAS famílias
metadata:
  type: project
---

## Família `ENTRADA_MERCADORIAS (UA)` — conferido em 17/ago/2026

Lido pelo Graph, somente leitura, ao virar a análise para o UA:

| Unidade | Colunas (aba `SLIN`) | Cliente |
|---|---:|---|
| `RMSPII/001,015,016` | 27 | sim (`Cliente`, `Cliente CNPJ`) |
| `CWB3/001` | 27 | sim |
| `SANCA/025` | **28** | sim — tem `Data Confirmação` a mais |
| `RJ/004-003` | **25** | **não** — confirmado em 2601, 2606 e 2608 |

**O `docs/FONTES_DATAHUB.md` (linha ~93) está errado nisto:** afirma que a
família `(UA)` está presente nas quatro unidades "com `Cliente` e
`Cliente CNPJ`". Vale para três — a RJ não tem, igual à entrada por item. **A
RJ é sem cliente nas duas famílias**, então trocar de família não resolve a
decisão de produto pendente: peso e valor aparecem, decomposição por cliente
não.

**A série histórica do UA serve:** a RMSPII tem 121 arquivos, 50 competências
de `2110` a `2608`, e o cabeçalho de out/2021 é **idêntico** ao de 2026 (27
colunas, com cliente) — conferido em 2110, 2301, 2401, 2501. Mas a série tem
buracos: 2110→2608 são 59 meses e só 50 existem (`2201` não existe). Contar
meses antes de prometer série contínua; ver [[nao-ler-mes-parcial]].

**Duas armadilhas de leitura que a entrada por item não tem:** o arquivo de
2110 tem 4 abas (`Painel`, `Planilha2`, `SLIN`, `Planilha4`) e a **primeira não
é a `SLIN`** — ler "a primeira aba" devolve vazio, sem erro. E o `016_2608` tem
`SLIN` + `Apoio` + `Dashboard`, onde a `Apoio` é derivada, de grão diferente e
com colunas de duplicidade (`Chave Duplicidade`, `Duplicada`) — somar junto
duplica. Endereçar a aba `SLIN` explicitamente, sempre.

---

## Família `ENTRADA_MERCADORIAS` (grão de item) — conferido em 06/ago/2026

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
