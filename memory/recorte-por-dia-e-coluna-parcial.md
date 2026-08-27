---
name: recorte-por-dia-e-coluna-parcial
description: V3.7 (26/ago/2026) — o recorte da tela é por dia e tem filtro de dia do mês; coluna que deixou de ser o mês inteiro é declarada, e o piso da carga não é a abertura da tela
metadata:
  type: project
---

O recorte da V3 passou a ser por **dia** (`AAAA-MM-DD`, inclusivo nas duas
pontas), e ganhou um segundo filtro que não substitui o primeiro:

- **período** (`de`/`ate`): intervalo de datas — `03/08/2026 a 05/09/2026`;
- **dia do mês** (`dias`): multi-seleção 01..31 que corta **dentro de todo mês
  do período** — jan a ago tirando os dias 1, 2 e 3 exclui esses dias nos oito
  meses. É a semântica do slicer "Dia" do Power BI, que foi a referência pedida.
  É dia **do mês**, não da semana.

A coluna da Matriz **continua mensal** (decisão da Maria: "pra mostrar na matriz
faz o que você falou mesmo"). Consequência que vale mais que o recorte em si:

> **Coluna que deixou de ser o mês inteiro tem que ser declarada onde ela é
> lida.** Ponta do período cabe no cabeçalho (`2026-08 (03-31)`); filtro de dia
> do mês não cabe, porque corta em todas as colunas — vira aviso, com os dias
> resumidos em faixas. Mês inteiro sai **sem** marcador: anotar o óbvio treina a
> pessoa a ignorar a anotação.

**Why:** um total rotulado como o mês que não é o mês é o número que alguém copia
para um relatório, e o custo já foi medido em
[[nao-ler-mes-parcial]] — 3 de 18 leituras por cliente trocaram de sinal entre
julho pela metade e julho fechado. Recorte que corta errado não estoura: devolve
um número menor, plausível, e ninguém vê.

**How to apply:** três coisas que se confundem e não são a mesma:

1. `DW_ANO_MINIMO` é o piso da **carga** (o que o banco guarda);
2. `CAT_ABERTURA_DE` (padrão `ano-corrente`) é o primeiro dia do recorte com que
   a **tela abre** — janeiro do ano corrente até **hoje**. Filtrar para trás
   sempre funcionou: o campo de data não tem mínimo, e o alcance real do dado
   aparece como dica ao lado dos filtros;
3. "hoje" vem do **Postgres**, no fuso de exibição — o container roda em UTC, e
   às 21h de Brasília ele já está no dia seguinte.

Não travar a abertura no primeiro dia com dado: essa versão foi construída e
desfeita no mesmo dia, porque marcava um janeiro inteiro como parcial só porque o
dado começa no dia 02. Ver [[pagina-mostra-numero-nao-texto]] e
[[validar-tela-no-navegador]] — foi o navegador que achou.
