---
name: cortes-produtos-export-quebrado
description: CORTES_PRODUTOS 2604–2606 são cópias idênticas do export de janeiro/26 — só o 2607 tem dado novo (jun parcial + jul); abr e mai não têm leitura de corte
metadata:
  type: project
---

Conferido no dado em 14/08/2026 (leitura GET-only via Graph, histograma de meses por
arquivo): nos galhos `RMSPII/SAIDA/CORTES PRODUTOS`, os arquivos das competências
**2604, 2605 e 2606 têm conteúdo idêntico entre si e igual ao export de janeiro/26**
— 11.409 linhas na filial 001 e 4.920 na 016, sempre com `Data Solicitação` só de
jan/26. Apenas o **2607** traz dado novo: jun/26 parcial (405 linhas na 001, 1.141 na
016) + jul/26 completo.

Mesmo gênero do defeito do `DADOS_GERAIS` (obstáculo 8 do FONTES_DATAHUB): o nome do
arquivo promete uma competência que o conteúdo não entrega.

**Why:** quem somar cortes por arquivo triplica janeiro e inventa corte onde não há;
quem fatiar por `Data Solicitação` descobre que abr e mai/26 simplesmente não têm
leitura de corte na fonte. A família também só existe na RMSPII (001 e 016) — CWB3 e
SANCA não publicam cortes; a perda visível lá é a diferença solicitado × separado da
`SAIDA_MERCADORIAS`.

**How to apply:** para ler cortes, usar o arquivo de competência mais alta e fatiar
pelos meses reais do conteúdo, nunca concatenar arquivos da família. Antes de
prometer série de cortes num painel, rodar o histograma de meses por arquivo (o
padrão de verificação está em `scratchpad/extrair.py` da sessão de 14/08). Pendência
humana: perguntar a quem publica por que 2604–2606 são cópias de janeiro — junto com
a republicação do `DADOS_GERAIS` ([[historico-datahub-por-familia]]).
