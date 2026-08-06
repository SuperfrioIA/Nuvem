# Proposta V3 — Volumetria integrada e Cockpit visual

**Projeto:** Nuvem IA
**Data:** 06/08/2026
**Substitui:** `docs/proposta_v2_volumetria_cockpit_laboratorio.md` (05/08/2026)
**Status:** decisões fechadas com a Maria em 06/08/2026. Nenhum lote autorizado a
construir — a autorização é por lote.

---

## 1. Por que existe uma V3

A V2 foi escrita antes de olhar a fonte. Ao cruzar cada premissa dela com o código e
com o SharePoint em 06/08/2026, cinco pontos mudaram o suficiente para reordenar o
plano:

1. a entrada por item só existe em 2026 — mas `SAIDA_MERCADORIAS` tem série desde
   out/2021, então a saída não é só "a direção que falta", é a única volumetria com
   histórico;
2. metade dos arquivos processados está em pendência de de-para, e resolver isso é
   cadastro, não código — é o lote mais barato e o que mais muda a tela;
3. `Operação` não é temperatura, é tipo de movimento, e hoje devolução entra somada
   como entrada;
4. `fato_volumetria_mensal` seria uma cópia de `medidas`, que já é o agregado mensal —
   o que falta em `medidas` é índice;
5. a matriz e o visual não exigem framework novo; exigem uma biblioteca de tabela.

O detalhe do levantamento está na seção 4. As decisões estão na 3.

---

## 2. Objetivo da V2 (inalterado)

Uma camada analítica visual capaz de responder, com número auditável até o arquivo de
origem:

```text
quanto entrou · quanto saiu · total movimentado · saldo
como evoluiu no mês e no acumulado
quais unidades e quais clientes puxaram o resultado
como se distribui por tipo de estoque
o que está pendente ou fora de cobertura
```

Frase-guia, mantida da V2:

> Primeiro uma camada visual confiável de volumetria integrada. Depois o Laboratório
> explorando em cima dessa base já governada.

---

## 3. Decisões fechadas (06/08/2026)

| # | Tema | Decisão |
|---|---|---|
| 1 | **Direção** | **Métricas separadas.** `peso_bruto_entrada` / `peso_bruto_saida`, e equivalentes para valor e registros. Não entra coluna `direcao`. |
| 2 | **Agregação** | **Não criar `fato_volumetria_mensal`.** `medidas` já é o agregado mensal; entram índices. |
| 3 | **`movimento_logistico`** | Não criar. |
| 4 | **Fonte de saída** | **`SAIDA_MERCADORIAS`**, banda **Separado Fisicamente**. `GUIAS_SAIDA` fica para produtividade, depois. |
| 5 | **Tipo de estoque** | Entra como dimensão, **4 valores**: `CONGELADO`, `SECO`, `HORTIFRUTI`, `UTENSILIOS`. |
| 6 | **`Operação`** | **Soma tudo**, como hoje. Não filtra devolução, transferência interna nem acerto de estoque. Vira diferença documentada na conciliação. |
| 7 | **Histórico / ano anterior** | **Só 2026.** Família `ENTRADA_MERCADORIAS (UA)` fica fora. DW fica fora. Comparativo da tela é mês anterior, não ano anterior. |
| 8 | **Budget** | Fora da V2. |
| 9 | **De-para** | `CWB3/001 → CWBIII`, `SANCA/025 → RMSPV`, `RJ/004-003 → RMRJ`. |
| 10 | **Cockpit** | Evoluir `/cockpit` no lugar. Sem rota nova. |
| 11 | **Frontend** | Sem framework. ECharts (já presente) + **Tabulator via CDN** para a matriz. |
| 12 | **Visual** | Referência aprovada: protótipo de 06/08/2026 (paleta e tipografia da marca, tema claro e escuro). |
| 13 | **Matriz** | Um nível de drill-down (unidade → cliente), meses nas colunas, ordenação, heatmap leve, exportar CSV. |

### 3.1. Consequências que essas decisões trazem

**A decisão 1 resolve um bloqueador de graça.** `_remover_celulas_orfas`
(`backend/services/processamento_datahub.py:182-206`) apaga, no escopo
`(metrica_id, armazem_id, competencia)`, toda célula que o processamento atual não
emitiu — e o comentário nas linhas 190-193 já avisa que isso só é seguro com produtor
único. Se entrada e saída compartilhassem a métrica, uma apagaria a outra a cada
rodada. Com métricas separadas os escopos não se encontram.

**Custo da decisão 1:** seis conceitos canônicos novos precisam ser criados e
aprovados em `conceitos_canonicos`, porque a ingestão exige conceito aprovado com
unidade (`processamento_datahub.py:135-153`). E `peso_bruto_total` e
`saldo_peso_bruto` passam a ser derivados na consulta, não persistidos.

**A decisão 6 é uma diferença conhecida, não um esquecimento.** Na amostra de
`ENTRADA_MERCADORIAS_016_2601`, devolução é 39% das linhas e transferência interna
mais 9%. Se o Power BI de volumetria não conta esses movimentos como entrada, a Nuvem
vai aparecer maior. Isso precisa estar escrito na conciliação (lote V2.6) antes de
alguém comparar os dois números.

**A decisão 7 tira `variacao_vs_ano_anterior` do escopo.** Os critérios de aceite que
falavam de ano anterior na V2 saem. O comparativo é mês anterior.

**A decisão 5 fica sem o cruzamento com capacidade.** Tipo de estoque entra como
recorte da volumetria, mas ocupação por temperatura exigiria a capacidade das câmaras,
que vem do DW — fora do escopo pela decisão 7. Fica registrado como o próximo ganho
possível depois da V2.

---

## 4. Levantamento de 06/08/2026 (evidência)

Feito com script somente-leitura sobre o Graph, usando `backend/services/graph_datahub.py`.
Inventário completo: **810 arquivos** (770 `.xlsx`) em 61 pastas — mais que o dobro dos
367 registrados em 31/07/2026 em `docs/FONTES_DATAHUB.md:77`, porque o histórico de
`SAIDA_MERCADORIAS` e de `ENTRADA_MERCADORIAS (UA)` desde out/2021 entrou na fonte.

### 4.1. Cobertura temporal por família

| Unidade | Família | Competências | Filiais |
|---|---|---|---|
| RMSPII | `ENTRADA_MERCADORIAS` | 2026-01 .. 2026-08 (8) | 001, 015, 016 |
| RMSPII | `ENTRADA_MERCADORIAS_UA` | **2021-10 .. 2026-08 (50)** | 001, 015, 016 |
| RMSPII | `SAIDA_MERCADORIAS` | **2021-10 .. 2026-08 (50)** | 001, 015, 016 |
| RMSPII | `GUIAS_ENTRADA` / `GUIAS_SAIDA` / `CORTES_PRODUTOS` | 2026-01 .. 2026-08 | 001, 016 |
| CWB3 | `ENTRADA_MERCADORIAS`, `SAIDA_MERCADORIAS` | 2026-01 .. 2026-08 | 001 |
| RJ | `ENTRADA_MERCADORIAS`, `SAIDA_MERCADORIAS` | 2026-01 .. 2026-08 | 004-003 |
| SANCA | `ENTRADA_MERCADORIAS` | 2026-01 .. 2026-08 | 025 |
| SANCA | `SAIDA_MERCADORIAS` | 2026-06 .. 2026-08 | 025 |

Dois pontos operacionais: **existe competência 2608** (a V1 processou até 2607), e a
estrutura de pastas continua `{unidade}/{ÁREA}/{PASTA}/` — não mudou, apesar da
impressão em contrário.

### 4.2. O de-para é 1:1

Nas famílias de volumetria cada unidade tem **um** código de filial. Os códigos `002`,
`004-001` e `005-001` só aparecem em `DADOS_GERAIS` e `OCORRENCIAS_ENTREGAS`, que não
estão integradas. Portanto não há consolidação N:1 e a guarda de colisão de
`processamento_datahub.py:435-443` não é acionada pelo de-para.

As três linhas a criar em `depara_armazem`, conector `sharepoint_datahub`:

```text
CWB3/001    -> CWBIII   (São José dos Pinhais/PR, 001029)
SANCA/025   -> RMSPV    (008009, CNPJ 06.975.242/0009-34)
RJ/004-003  -> RMRJ     (Duque de Caxias/RJ, 008004)
```

As três siglas já existem e estão ativas em `backend/seed_depara.py:97,106,136`.

> **Correção de 06/08/2026 (conferido no dado, somente leitura):** só **duas** das
> três entram no V2.1. `CWB3/001` e `SANCA/025` têm as 20 colunas que o leitor
> exige, rótulo a rótulo; `RJ/004-003` tem **18** (faltam `Cliente` e
> `Cliente CNPJ`). Dar de-para pra RJ antes do leitor da variante tiraria os 8
> arquivos dela de pendência limpa e os colocaria em erro de leitura. A linha da
> RJ passa para o V2.3.

### 4.3. `Operação` é tipo de movimento

`ENTRADA_MERCADORIAS_016_2601`, 4.000 linhas amostradas:

```text
2026  NÃO TROCA NOTA DE ARMAZENAGEM
1557  DEVOLUCAO DE MERCADORIAS (SEM NF-E)
 357  ENTRADA - TRANSF INTERNA
  43  ENTRADA NORMAL/NF ARMAZENAGEM
  10  ACERTO DE ESTOQUE S/ CUSTO
   7  ENTRADA/ DEV.NF ARMAZENAGEM
```

`SAIDA_MERCADORIAS` e `GUIAS_SAIDA` têm o equivalente do lado da saída, com
`SAIDA NORMAL` em 91% das linhas, mais complementos, descarte por avaria e vencimento,
transferência interna e acerto de estoque.

### 4.4. Tipo de estoque vem de `Nome Estoque` / `Estoque`

Nove valores distintos observados, cobertos por quatro palavras-chave:

```text
SECO_RMSPII · SECO · SECO-2023 · SECO - 2015 · SECO FLV (CUCINARE) · LC SECO - GRUPO GR - RMSPII  -> SECO
HORT-FRUTTI · HORTIFRUTI · HORTI_RMSPII                                                          -> HORTIFRUTI
CONGELADO                                                                                        -> CONGELADO
LC UTENSILIOS - GRUPO GR - RMSPII                                                                -> UTENSILIOS
```

`Código Estoque` é mais limpo (`001`, `002`, `005`) mas é **escopado por filial** — o
`001` da filial 016 não é o `001` da filial 001. Não serve como chave global.

### 4.5. `SAIDA_MERCADORIAS`: layout

Aba `SLIN`. **Cabeçalho em dois níveis:** linha 5 traz as bandas, linha 6 traz os 36
rótulos reais.

```text
linha 5:  [0] GSM   [9] Produto   [14] Solicitado pelo Cliente
          [20] Atendido pelo Estoque   [26] Separado Fisicamente   [32] Dados de Separação

linha 6:  [0] Cliente        [1] Cliente CNPJ   [2] Estoque      [3] Empresa
          [4] GSM            [5] Operação       [6] Data Solicitação  [7] Data Saída
          [8] Status Separação  [9] Item         [10] Código      [11] Descrição
          [12] Pedido        [13] Destinatário
          [14..19] Volume · EMB · Fração · EMB · Peso Liquido · Peso Bruto   <- Solicitado
          [20..25] idem                                                      <- Atendido
          [26..31] idem                                                      <- Separado Fisicamente
          [32] Corte Físico  [33] Início  [34] Final  [35] Separador
```

Os rótulos repetidos (`Volume` 3x, `EMB` 6x, `Fração` 3x, `Peso Liquido` 3x,
`Peso Bruto` 3x) deixam de ser ambíguos porque as bandas são de seis colunas em
posição fixa. **A banda oficial é Separado Fisicamente: `Peso Bruto` na coluna 31.**

Diferença entre as bandas na amostra de 8.000 linhas: `101.816` / `101.792` /
`101.577` kg — **0,23%** entre o solicitado e o separado. Isso é nível de atendimento
disponível sem custo adicional, e vale registrar como métrica futura.

Custo: **33 MB por filial/competência**, partido em `_f1` + `_f2`. Os dois arquivos
casam na mesma `(codigo_origem, competencia)`, então acionam
`_abortar_se_origens_colidem` (`processamento_datahub.py:368-388`). Concatenar antes de
gravar é pré-requisito, não melhoria.

### 4.6. `GUIAS_SAIDA` não serve para volumetria

Cabeçalho na linha 2, 31 colunas, sem rótulo repetido, 0,2 MB. Mas **não tem
`Peso Bruto`** (só `Peso Líq.`) e **não tem CNPJ do cliente** — só o nome. Grão de
guia, não de item. É fonte de produtividade e lead time (`Status Separação`,
`Separação Início`/`Final`, `SKUs`, `Itens`, `Pedidos`), não de volumetria.

### 4.7. `medidas` não tem índice

Nenhum `CREATE INDEX` sobre `medidas` em nenhuma das 11 migrations. O único índice
servindo os `WHERE metrica_id = %s` das consultas do Cockpit é o da UNIQUE
`medidas_celula_unica` (`alembic/versions/0006_persistencia_datahub.py:47-52`).

### 4.8. O gargalo do Cockpit não é SQL

Um load da tela dispara **6 requests HTTP**, cada um abrindo **conexão nova** ao
Postgres (`backend/database.py:26-40`, sem pool), num deploy de **1 worker uvicorn**
(`Dockerfile:19`). Com `medidas` na ordem de dezenas de milhares de linhas, o `GROUP BY`
indexado é irrelevante ao lado disso.

---

## 5. Lotes

### V2.1 — Cobertura e base

> Dobrar o dado disponível e indexar, sem tocar em leitor nem em tela.

- criar as três linhas de de-para da seção 4.2 em `backend/seed_datahub.py`;
- índices em `medidas`: `(metrica_id, competencia)`,
  `(metrica_id, armazem_id, competencia)`, `(metrica_id, cliente_id, competencia)`;
- pool de conexão no `backend/database.py`;
- sincronizar e processar, incluindo a competência 2608;
- script readonly de verificação em produção: alembic em head, UNIQUE de `item_id`,
  de-para sem código nu, contagem por unidade, pendências visíveis, nenhum
  processamento com unidade NULL fora da raiz.

**Aceite:** CWB3, SANCA e RJ saem de pendência e aparecem no ranking de unidades; a
contagem de `processamentos_datahub` com status `ok` sobe de 21 para o total dos
arquivos de entrada de 2026; consultas do Cockpit passam a usar índice; o script
readonly roda na VM sem gravar nada.

### V2.2 — Tipo de estoque

> Introduzir a dimensão na entrada, antes de existir saída.

- migration: coluna `tipo_estoque` em `medidas` e `medidas_recebidas`, nova UNIQUE
  incluindo a coluna, e o escopo do prune de órfãs acompanhando;
- derivação por palavra-chave em `Nome Estoque` (seção 4.4), com pendência visível para
  o que não casar — mesmo padrão de `depara_pendencias`;
- agregação da entrada passa a agrupar por `(cliente, tipo_estoque)`;
- reprocesso com `forcar=True`.

**Aceite:** os quatro tipos aparecem na consulta; valor não casado vira pendência
visível e não some; total por competência antes e depois do lote é o mesmo.

### V2.3 — Saída

> A direção que falta, na fonte e na banda decididas.

- seis conceitos canônicos e seis métricas novas (entrada e saída para peso, valor e
  registros), com os nomes atuais migrados para o par de entrada;
- leitor de `SAIDA_MERCADORIAS`: valida as bandas da linha 5 **e** os rótulos da linha
  6, lê a banda Separado Fisicamente por posição, filtra `Status Separação = Cancelado`;
- concatenação de `_f1`/`_f2` antes de gravar;
- processamento incremental e fora do request HTTP (33 MB por filial/competência);
- testes com fixtures gerando o cabeçalho de dois níveis.

**Aceite:** saída grava na mesma semântica da entrada; arquivo partido não aciona a
guarda de colisão; banda errada é rejeitada com erro claro; saída não contamina
entrada; reprocessar duas vezes não duplica.

### V2.4 — Consultas de volumetria

> Os números que a tela vai consumir, sob `/cockpit/`.

- `GET /api/admin/cockpit/volumetria/resumo`, `/evolucao`, `/ranking`, `/matriz`;
- reaproveitar `backend/services/serie_datahub.py`: `resolver_filial` (que já aceita
  sigla e código qualificado), `parse_competencia`, `exigir_metrica_aditiva`,
  `filtros_sql`;
- `total` e `saldo` derivados na consulta a partir do par de métricas;
- filtro de `tipo_estoque` em todos;
- mover `/datahub/serie` para `/cockpit/volumetria/evolucao` — o frontend é o único
  consumidor.

**Aceite:** entrada, saída, total e saldo por mês; acumulado; ranking por unidade e por
cliente com participação; matriz com meses nas colunas e paginação; limitações
declaradas na resposta.

### V2.5 — Cockpit visual

> A tela do protótipo, na rota que já existe.

- aplicar o desenho aprovado: paleta e tipografia da marca, tema claro e escuro,
  cards, evolução com entrada × saída e saldo, dois rankings, tipo de estoque;
- Tabulator via CDN para a matriz: agrupamento por unidade com um nível de abertura
  para cliente, ordenação, heatmap leve, exportar CSV;
- estado visual para unidade sem movimento no período (a RMSPIII encerrou operação e
  hoje a tela não distingue "zero" de "não opera");
- corrigir `frontend/cockpit.html:470` — `dados.ranking.length` avaliado sem proteção
  quando `limite` é falsy;
- ligar a faixa de indicadores aprovados no Laboratório, hoje fixa em vazio
  (`cockpit.html:389-390`).

**Aceite:** filtros globais afetam todos os visuais; nenhuma leitura de Excel em
endpoint de dashboard; a tela responde com o histórico real de 2026 completo.

### V2.6 — Conciliação com o Power BI

> Explicar as diferenças antes que alguém as descubra.

- escolher período de referência e comparar total mensal, acumulado e os dois rankings;
- registrar as diferenças já conhecidas: `Operação` somando devolução e transferência
  (decisão 6), famílias não integradas, cliente sem cadastro caindo no balde
  "Sem cliente identificado", banda escolhida na saída;
- entregável: `docs/CONCILIACAO_POWERBI_V2.md`.

**Aceite:** existe tabela Nuvem × Power BI; toda diferença relevante tem explicação ou
vira pendência registrada; os números não precisam bater, precisam ser rastreáveis.

### V2.7 — Escala e operação

- cache de consulta com TTL curto e invalidação após processamento;
- top N com bucket, paginação da matriz, limites de resposta;
- log de consulta lenta;
- backup/restore com evidência.

### V2.8 — Laboratório com gráficos

- contrato de visualização validado no backend, extensão do padrão que já funciona em
  `backend/services/insight_aprovado.py`;
- tipos permitidos no início: linha temporal, ranking, entrada × saída, matriz, Pareto;
- ECharts no `laboratorio.html`;
- fixar e abrir no Cockpit.

**Aceite:** IA não inventa número; visualização inválida é recusada; gráfico do
Laboratório abre no Cockpit.

---

## 6. Fora da V2, com motivo

| Item | Motivo |
|---|---|
| Comparação com ano anterior | A entrada por item só existe em 2026 (decisão 7). |
| Família `ENTRADA_MERCADORIAS (UA)` | Grão de UA, não de item; seria degrau falso na série. |
| Volumetria do DW (2021→hoje) | Segunda fonte não conciliável, em toneladas e grão filial × mês. |
| Budget | Não existe fonte. |
| `Operação` como dimensão | Decisão 6: soma tudo. |
| Ocupação por temperatura | Depende da capacidade das câmaras, que vem do DW. |
| Drill-down além de um nível | Custo de frontend sem ganho proporcional. |
| `RMSPII/002`, `RJ/004-001`, `RJ/005-001` | Só existem em `DADOS_GERAIS` e `OCORRENCIAS_ENTREGAS`, famílias não integradas. |
| Variante da RJ de 18 colunas | **Corrigido em 06/08/2026:** a `ENTRADA_MERCADORIAS` da RJ que existe é a `004-003` **e ela É a variante de 18 colunas** — conferido no dado, sem `Cliente` nem `Cliente CNPJ`. Fica fora do V2.1 (o de-para dela geraria erro de leitura em 8 arquivos) e entra no V2.3 com o leitor da variante. Ver `docs/V2_PLANO.md`, "Diagnóstico de partida". |
| `GUIAS_SAIDA`, `CORTES_PRODUTOS`, `ESTOQUE_POR_LOTE`, `PALLETS_EXCEDENTES` | Outras perguntas de negócio. `GUIAS_SAIDA` vira produtividade depois. |

---

## 7. Riscos conhecidos

1. **Volume da saída.** 33 MB por filial/competência. Só 2026 já é da ordem de 1 GB.
   Sem processamento incremental e fora do request, a rodada trava o worker único.
2. **Diferença com o Power BI pela decisão 6.** Devolução é 39% das linhas da amostra.
   Se a comparação acontecer antes da V2.6, a ferramenta vai parecer errada.
3. **Conceitos canônicos novos.** Seis, com aprovação obrigatória antes de qualquer
   ingestão gravar. Se ficarem em rascunho, o processamento falha por design.
4. **Reprocesso da V2.2.** Muda o grão das células da entrada. O prune de órfãs precisa
   estar com o escopo certo antes, ou apaga o que não deve.
5. **Dependência de CDN.** ECharts e Tabulator vêm de `cdn.jsdelivr.net`. Funciona hoje,
   mas é dependência externa numa ferramenta interna — vale servir local em algum ponto.
