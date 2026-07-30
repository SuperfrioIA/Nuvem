---
name: juncoes-familias-datahub
description: As famílias do DataHub se juntam por GSM (saída) e por Pedido+NF (entregas) — três junções conferidas com dado real, mais o defeito do export do DADOS_GERAIS
metadata:
  type: reference
---

Conferido em 30/jul/2026 baixando os xlsx reais da 016/2607 pelo Graph e cruzando fora
do backend (mesmo método usado no [[chaves-nf-entrada-datahub]]).

- **`SAIDA_MERCADORIAS.GSM` = `GUIAS_SAIDA.Número` — 100%** (847 de 847 chaves, 266.910
  de 266.910 linhas de item). É o espelho exato do `GEM` da entrada. Formatos diferentes,
  mesma numeração: `GSM` = `NNNN/AAAA` (`4971/2026`), `Número` = 10 dígitos zero-padded.
  Normalizar pela parte antes da `/`, sem zeros à esquerda. Só contra o arquivo de julho
  dá 95,87% — os 35 faltantes são guias de junho com saída em 01/07 e estão todos no
  arquivo de junho (borda de competência, não falha de chave).
- **`OCORRENCIAS_ENTREGAS.(Pedido, NF)` = `DADOS_GERAIS.(Pedido, NF)` — 100%** na janela
  que o `DADOS_GERAIS` cobre (12.015 de 12.015 pares). Cliente e `Peso Bruto` idênticos
  nos casados: é o mesmo evento nas duas famílias.
- **`DADOS_GERAIS.GSM` = `GUIAS_SAIDA.Número` — 98,97%**, mas **só filtrando
  `EMP GSM` = filial do arquivo**. O `GSM` é série **por empresa**; sem o filtro cai
  para 55% e engana. Liga ENTREGAS a SAIDA.
- **Guia cortada ou cancelada não tem item**, igual à entrada: das 11 guias de saída
  concluídas sem item, 10 têm `Corte Contábil = 1` com volume/peso zero.
- **Defeito do export: `DADOS_GERAIS_*_f1` e `_f2` são idênticos** linha a linha (60
  colunas) em `016_2607`, `016_2606` e `002_2607`. Metade da competência não está
  publicada (o 016/2607 só cobre 01–15/07) e concatenar as partes duplica tudo. Ler só
  o `_f1`. As partes de `OCORRENCIAS_ENTREGAS` e `SAIDA_MERCADORIAS` são fatias reais e
  disjuntas — o defeito é só dessa família.
- **`SAIDA_MERCADORIAS` tem cabeçalho na linha 6**, não na 5 (a 5 é faixa de
  agrupamento). Os 6 rótulos de medida se repetem 3× (solicitado / atendido / separado)
  — nessa família, peso e volume só saem por posição.

**Why:** o grafo do P5.5 só desenhava aresta por domínio de negócio; a Maria pediu para
verificar, com o rigor do `GEM`, se havia junção real de dado entre famílias antes de
desenhar qualquer linha nova. Havia — e a investigação achou de quebra o export
quebrado do `DADOS_GERAIS`.
**How to apply:** junção não listada acima não foi verificada — não desenhar nem
prometer. Qualquer KPI de entrega precisa declarar que o `DADOS_GERAIS` é meia
competência. Detalhamento completo em `docs/FONTES_DATAHUB.md`, seção 5.1 e obstáculo 8.
