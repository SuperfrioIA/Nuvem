---
name: layout-saida-mercadorias
description: SAIDA_MERCADORIAS tem cabeçalho em dois níveis e três bandas de medida repetidas — a banda oficial é Separado Fisicamente, Peso Bruto na coluna 31
metadata:
  type: project
---

Perfilado em 06/08/2026 lendo `SAIDA_MERCADORIAS_016_2606_f1.xlsx` (16,3 MB) direto do
Graph. Aba `SLIN`.

**Cabeçalho em dois níveis.** Linha 5 traz as bandas, linha 6 traz os 36 rótulos reais:

```text
linha 5:  [0] GSM  [9] Produto  [14] Solicitado pelo Cliente
          [20] Atendido pelo Estoque  [26] Separado Fisicamente  [32] Dados de Separação

linha 6:  [0] Cliente  [1] Cliente CNPJ  [2] Estoque  [3] Empresa  [4] GSM
          [5] Operação  [6] Data Solicitação  [7] Data Saída  [8] Status Separação
          [9] Item  [10] Código  [11] Descrição  [12] Pedido  [13] Destinatário
          [14..19] Volume · EMB · Fração · EMB · Peso Liquido · Peso Bruto  <- Solicitado
          [20..25] idem                                                     <- Atendido
          [26..31] idem                                                     <- Separado
          [32] Corte Físico  [33] Início  [34] Final  [35] Separador
```

Os rótulos repetidos (`Volume` 3x, `EMB` 6x, `Fração` 3x, `Peso Liquido` 3x,
`Peso Bruto` 3x) **não são ambiguidade** — são três bandas de seis colunas em posição
fixa. **Banda oficial: Separado Fisicamente, `Peso Bruto` na coluna 31.**

As três bandas somaram `101.816` / `101.792` / `101.577` kg em 8.000 linhas — 0,23% entre
o que o cliente pediu e o que saiu. É nível de atendimento de graça, métrica futura.

**`GUIAS_SAIDA` não serve para volumetria.** Cabeçalho na linha 2, 31 colunas, só 0,2 MB
— mas **não tem `Peso Bruto`** (só `Peso Líq.`) e **não tem CNPJ do cliente**, só o nome.
Grão de guia. Serve para produtividade de separação (`Status Separação`,
`Separação Início`/`Final`, `SKUs`, `Itens`, `Pedidos`), não para volumetria.

**Why:** `SAIDA_MERCADORIAS` foi escolhida por ser o espelho real da entrada — mesmo grão
de item, mesmo `Peso Bruto`, e `Cliente CNPJ` permite resolver cliente pela raiz do CNPJ
igual à entrada. O leitor atual de `ENTRADA_MERCADORIAS` busca coluna **por nome** com
"primeira ocorrência ganha" (`backend/services/entrada_mercadorias.py:135`), o que nesta
família leria a banda errada em silêncio.

**How to apply:** o leitor de saída valida as bandas da linha 5 **e** os rótulos da linha
6 antes de ler por posição — validar só uma das duas linhas deixa passar arquivo com
banda reordenada. Filtrar `Status Separação = Cancelado`. E são **33 MB por
filial/competência, partidos em `_f1` + `_f2`**: os dois casam na mesma
`(codigo_origem, competencia)` e acionam `_abortar_se_origens_colidem`
(`processamento_datahub.py:368-388`), então concatenar antes de gravar é pré-requisito.
Só 2026 é da ordem de 1 GB — processar fora do request HTTP.
