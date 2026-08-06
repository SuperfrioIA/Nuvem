---
name: operacao-e-tipo-estoque
description: A coluna Operação é tipo de movimento (devolução é 39% das linhas), não temperatura — o tipo de estoque vem de Nome Estoque por palavra-chave, implementado no V2.2
metadata:
  type: project
---

Perfilado em 06/08/2026 lendo `ENTRADA_MERCADORIAS_016_2601.xlsx` (4.000 linhas) e
`SAIDA_MERCADORIAS_016_2606_f1.xlsx`.

**`Operação` é tipo de movimento, não temperatura.** Valores na entrada:

```text
2026  NÃO TROCA NOTA DE ARMAZENAGEM
1557  DEVOLUCAO DE MERCADORIAS (SEM NF-E)
 357  ENTRADA - TRANSF INTERNA
  43  ENTRADA NORMAL/NF ARMAZENAGEM
  10  ACERTO DE ESTOQUE S/ CUSTO
   7  ENTRADA/ DEV.NF ARMAZENAGEM
```

Na saída o equivalente tem `SAIDA NORMAL` em 91% das linhas, mais complementos, descarte
por avaria e vencimento, transferência interna e acerto de estoque.

**O tipo de estoque vem de `Nome Estoque` (entrada) / `Estoque` (saída), por palavra-chave.**
Nove valores distintos observados, cobertos por quatro categorias:

```text
SECO_RMSPII · SECO · SECO-2023 · SECO - 2015 · SECO FLV (CUCINARE)
  · LC SECO - GRUPO GR - RMSPII                                      -> SECO
HORT-FRUTTI · HORTIFRUTI · HORTI_RMSPII                              -> HORTIFRUTI
CONGELADO                                                            -> CONGELADO
LC UTENSILIOS - GRUPO GR - RMSPII                                    -> UTENSILIOS
```

**`Código Estoque` é escopado por filial** — o `001` da filial 016 não é o `001` da
filial 001. É mais limpo (`001`/`002`/`005`) mas não serve como chave global.

**Why:** a suposição inicial era que `Operação` trazia congelado/seco. Não traz, e isso
tem duas consequências. Primeira: o `peso_bruto_movimentado` da V1 soma devolução,
transferência interna e acerto de estoque como entrada — **devolução sozinha é 39% das
linhas**. Se o Power BI de volumetria separa esses movimentos, a Nuvem aparece maior, e
essa é a explicação mais provável de divergência na conciliação. Segunda: `UTENSILIOS`
mostra que a dimensão não é só temperatura — tem linha de serviço ali dentro, por isso a
decisão foi chamar de "tipo de estoque" e manter os 4 valores em vez de jogar num balde.

**How to apply:** o leitor já lê `Operação`, `Nome Estoque` e `Código Estoque` — as três
estão em `_COLUNAS_ESPERADAS` e são lidas linha a linha. A decisão de somar tudo em
`Operação` está registrada em [[volumetria-v2-decisoes]] e precisa aparecer na
conciliação.

**Implementado no V2.2 (06/ago/2026)**, ver `docs/V2_PLANO.md`: `backend/services/
tipo_estoque.py` classifica por palavra-chave (`classificar()`), com o sentinela
`NAO_CLASSIFICADO` para valor vazio, sem palavra-chave, ou ambíguo (casa com mais de
uma) — nunca desempatado por ordem da lista. `NAO_CLASSIFICADO` é diferente de NULL:
NULL é "dimensão não se aplica" (célula anterior ao lote, upload manual, medida
derivada); o sentinela é "valor da fonte existe mas não classificou", com pendência
visível em `tipo_estoque_pendencias` (mesmo padrão de `depara_pendencias`/
`cliente_pendencias`). A agregação em `processamento_datahub.py` passou a agrupar por
`(cliente_id, tipo_estoque)` — a UNIQUE de `medidas` (migration `0014`) ganhou a
coluna, e o prune de órfãs continua varrendo o recorte inteiro (métrica, armazém,
competência) sem filtrar por tipo, para não deixar célula do grão antigo sobreviver
ao lado da nova.
