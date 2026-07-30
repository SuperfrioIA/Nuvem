---
name: chaves-nf-entrada-datahub
description: Nas famílias ENTRADA do DataHub, GEM é a única chave confiável — as colunas de NF são truncadas e não permitem contar notas fiscais
metadata:
  type: reference
---

Conferido em 30/jul/2026 lendo o xlsx cru de `ENTRADA_MERCADORIAS_016_2607` e
`GUIAS_ENTRADA_016_2607` (8.411 e 1.392 linhas).

- **`GEM` (ENTRADA_MERCADORIAS, posição 2) = `Número` (GUIAS_ENTRADA, posição 0)** —
  10 dígitos zero-padded, sem truncamento. É a chave de join entre as duas famílias e
  casou 100% (1.275 de 1.275 GEM presentes nas guias). Use essa para contar entradas.
- **`NF Entrada` (ENTRADA_MERCADORIAS) está truncada em 10 caracteres.** 308 valores
  terminam em `-` cortados no meio, e 10 valores nem são nota — `FATURADO`, `SECO 1235-`,
  `HORTI 02.0`, `CAIXA-0`, `DEV-0`, `AJUSTEDEPA`, `RETIRADA-0` (581 linhas, R$ 494.784).
- **`NF GEM` (GUIAS_ENTRADA) é uma concatenação de várias notas separadas por `/`,
  cortada em 99 caracteres** — perde as notas além da 10ª.
- As duas colunas de NF só coincidem em 310 de 1.484 valores: são espaços de numeração
  diferentes, **não dá para unir e contar** (a união infla). Contagem exata de notas
  fiscais não sai desses exports — só ordem de grandeza. Precisaria de campo novo no
  export do SLIN.
- **Guias canceladas existem e não têm linha de item.** Na 016/2607: 115 canceladas
  valendo R$ 9,8 mi, com zero interseção com o arquivo de mercadorias. KPI somado sobre
  os itens já exclui cancelado — mas filtrar `Status` ao usar GUIAS_ENTRADA sozinho.
- **`Vlr. Total` (itens) é total de linha, não da nota**: igual a `Vlr. Unitário` ×
  `Volume` em 8.409 de 8.411 linhas. Somar linha a linha está correto, não duplica.

**Why:** a Maria pediu conferência do KPI de valor da POC (a SAPORE parecia grande
demais). O número estava certo, mas a investigação revelou que "quantidade de notas"
não é um KPI construível com o que o SLIN publica hoje.
**How to apply:** ao montar qualquer KPI ou join sobre as famílias de ENTRADA, agregar
por `GEM`. Nunca prometer contagem de NF. Para validar valor de forma independente,
cruzar a soma dos itens contra `Vlr. Total NF` das guias concluídas — na 016/2607 fecham
em −1,76% (R$ 36.649.308,72 contra R$ 37.305.066,49). Ver [[concentracao-sapore-016]] e
`docs/FONTES_DATAHUB.md` (a ressalva de truncamento ainda não está lá).
