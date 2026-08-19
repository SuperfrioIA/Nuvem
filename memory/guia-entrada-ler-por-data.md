---
name: guia-entrada-ler-por-data
description: GUIAS_ENTRADA tem que ser lida por data de Solicitação varrendo todos os arquivos, não pela competência do nome — e o DW usa Solicitação, não Confirmação (testado, 90× melhor)
metadata:
  type: reference
---

Medido em 17/ago/2026 fechando julho/2026 contra o Power BI (RMSPII,
Recebimento, peso bruto).

### A guia não mora no arquivo da sua competência

Guia com `Solicitação` em julho aparece também nos arquivos `_2606` e `_2608`.
Só na SAPORE são **78,4 t** de guia cancelada de julho fora do arquivo de
julho. Ler apenas a competência 2607 inflava o resíduo da conciliação de
**0,10% para 0,9%** — parecia um resíduo inexplicado e era erro de leitura.
Vale o mesmo padrão já visto na `ENTRADA_MERCADORIAS (UA)` da SANCA, cujo
arquivo de agosto traz 251 linhas de 31/07.

### O DW usa Solicitação, não Confirmação

A `GUIAS_ENTRADA` tem três colunas de data: `Data NF`, `Solicitação` e
`Confirmação`. Testado dia a dia contra o fato, em julho, na SAPORE:

| Agregando por | Erro absoluto somado no mês |
|---|---:|
| `Solicitação` | **9,3 t** |
| `Confirmação` | 838,4 t |

Noventa vezes pior. O deslocamento é real (sex→dom, seg→ter…), mas o DW **não**
o segue. Usar `Solicitação`, que é a mesma base da entrada por item e por UA.

### O quadro que fecha (jul/2026, RMSPII, peso bruto)

| Camada | t |
|---|---:|
| BI / fato do DW | 9.638,1 |
| Itens publicados | 8.306,7 |
| Guia CANCELADA (183 guias) | 1.321,5 |
| Itens + cancelada | 9.628,2 |
| **Resíduo** | **9,9 (0,10%)** |

O que sobra é da própria fonte, não da leitura: a soma dos itens de uma guia
concluída pesa **0,14%** menos que o cabeçalho dela, e o cabeçalho das guias
pesa **0,23%** mais que o fato. É diferença de balança entre documento e item.

**Why:** eu tinha dado 0,9% como "resíduo em aberto" e a Maria voltou dizendo
que ainda não batia — estava certa, e a causa era minha leitura por arquivo.

**How to apply:** em qualquer conciliação com o BI, varrer **todos** os arquivos
da família e filtrar pela data, nunca pela competência do nome; e agregar por
`Solicitação`. A filial 015 não publica guia nenhuma, então lá não há como medir
cancelamento. Ver [[conciliacao-rmspii-primeira-passada]],
[[nivel-unidade-vs-filial-e-cliente-cnpj]] e [[fato-volumetria-dw]].
