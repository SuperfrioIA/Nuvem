# V2.3 — Saída: plano de execução

**Autorizado pela Maria em 06/ago/2026.** Status do lote: `docs/V2_PLANO.md`.
Especificação de origem: `docs/proposta_v3_volumetria.md`, seção 5, "V2.3 — Saída"
— **este documento a corrige em quatro pontos** (seção 1), com evidência.

Este documento existe para ser executado sem re-derivar nada. Quem executa deve
ler, nesta ordem: `docs/V2_PLANO.md` (status e diagnóstico de partida),
`docs/proposta_v3_volumetria.md` (decisões fechadas) e este arquivo.

> Regra que vale o lote inteiro: **nada é alterado no SharePoint do DataHub.** O
> cliente Graph é somente leitura por construção, e a regra vale também para
> escrita pelo sistema de arquivos — nunca rodar com o diretório de trabalho
> dentro da pasta sincronizada do DataHub.

---

## 1. Conferência da fonte em 06/ago/2026 (o que mudou)

Feita pelo Graph, somente leitura, perfilando 10 arquivos de `SAIDA_MERCADORIAS`
das quatro unidades. Quatro premissas da proposta caíram.

### 1.1. Não existe coluna de valor na saída

Os 36 rótulos da linha 6 terminam em `Corte Físico / Início / Final / Separador`.
Não há `Vlr. Total`, `Vlr. Unitário` nem qualquer coluna monetária, **em nenhuma
das quatro unidades**.

A proposta pede "seis métricas (entrada e saída para peso, valor e registros)".
O dado sustenta **cinco**. `valor_mercadoria_saida` não tem produtor possível e
**não será criada** (decisão D1 da Maria): métrica sem produtor é uma promessa
que o dado não paga, e no V2.4 alguém somaria zero como se fosse valor.

### 1.2. A SANCA tem 34 colunas na saída — e a banda inteira desloca

| Unidade | Colunas | `Cliente`/`Cliente CNPJ` | Banda *Separado Fisicamente* | `Peso Bruto` |
|---|---:|---|---:|---:|
| RMSPII, CWB3, RJ | 36 | sim | col 26 | **col 31** |
| SANCA | 34 | **não** | col 24 | **col 29** |

Estável nas três competências que a SANCA tem (2606, 2607, 2608).

`memory/layout-saida-mercadorias.md` afirmava "Peso Bruto na coluna 31" sem
qualificar — vale só para o layout de 36. **Ler a coluna 31 num arquivo da SANCA
leria `Início`, um timestamp, como peso.** A memória foi corrigida em
06/ago/2026.

**Consequência de desenho, não negociável:** o leitor localiza a banda pela
**linha 5** e conta o deslocamento a partir dela (`Peso Bruto` = início da banda
+ 5). Posição chumbada não serve, e validar só a linha 6 também não — os rótulos
são idênticos nos dois layouts, só as posições mudam.

### 1.3. Quem não tem cliente na saída é a RMSPV, não a RMRJ

A RJ **tem** `Cliente`/`Cliente CNPJ` na saída (36 colunas). Falta na *entrada*
dela (18 colunas, já conhecido desde o V2.1). Quem não tem coluna de cliente na
saída é a **SANCA/RMSPV** (34 colunas).

São dois casos distintos, os dois tratados neste lote:

| Direção | Unidade | Layout | Efeito |
|---|---|---|---|
| entrada | RMRJ (`RJ/004-003`) | 18 colunas | toda a unidade cai no balde sem cliente |
| saída | RMSPV (`SANCA/025`) | 34 colunas | toda a unidade cai no balde sem cliente |

### 1.4. Escopo real da fonte

- **248 arquivos, 2,60 GB**, competências `2110`..`2608` (50 distintas).
- **Só 2026: 72 arquivos, 616 MB.**

### 1.5. Confirmado (premissas que se sustentaram)

- **`_f1`/`_f2` são disjuntos**, ao contrário do `DADOS_GERAIS` (onde `_f2` é
  cópia do `_f1`). RMSPII/001 2607: 43.526 + 38.082 linhas, interseção **zero**
  em `(GSM, Item, Pedido)`; SANCA/025 2606: interseção zero. Concatenar é seguro
  — e continua sendo pré-requisito, porque as partes casam na mesma
  `(codigo_origem, competencia)`.
- **A CWB3 publica sem sufixo** (`SAIDA_MERCADORIAS_001_2601.xlsx`). Das 130
  competências da fonte, 118 têm duas partes e **12 têm parte única**. O padrão
  de nome tem que aceitar 1..N partes, com e sem `_fN`.
- **`Status Separação` = `Concluído` em 296.586 linhas**, 6 arquivos, 4 unidades.
  **Nenhum `Cancelado`.** O filtro pedido pela proposta entra assim mesmo, como
  defesa, mas **não muda número nenhum hoje** e isso vai declarado — filtro que
  não filtra nada não pode ser apresentado como saneamento.
- **`Estoque` na saída traz valores novos.** Na RMSPII/001 2608: `CONGELADO_RMSPII`,
  `CONGELADO`, `NOVO-CONGELADO`, `LC CONGELADO - GRUPO GR - RMSPII`,
  `CONG FLV (CUCINARE)`, `CONGELADO - 10591`, `SECO`. `NOVO-CONGELADO` e
  `CONGELADO - 10591` classificam certo; **`CONG FLV (CUCINARE)` vira pendência**
  (`CONG` não casa com `CONGELADO`, e `FLV` sugere hortifruti — ambiguidade real,
  nunca desempatada por chute). `tipo_estoque.py` já prevê `Estoque` no docstring
  e **não precisa ser alterado**.
- **`Operação` na saída** (RMSPII/001 2608): `SAIDA NORMAL` 14.837, descarte por
  avaria 76, vencidos 24, complementos 21, transferência 2. Fora do `SAIDA NORMAL`
  são **0,8% das linhas** — muito abaixo dos 39% de devolução da entrada. Soma
  tudo (decisão 6) e vira linha da conciliação no V2.6.

---

## 2. Decisões da Maria (06/ago/2026)

| # | Tema | Decisão |
|---|---|---|
| **D1** | Valor na saída | **Cinco métricas, não seis.** `valor_mercadoria_saida` não é criada — não tem fonte. |
| **D2** | Sem cliente na fonte | Linhas caem no balde `cliente_id NULL` existente, **sem** criar pendência de cliente (não há CNPJ para cadastrar; pendência ali seria tarefa impossível no painel — o erro que o V2.1.1 corrigiu). A limitação distingue "não cadastrado" de "sem coluna na fonte". |
| **D3** | Escopo temporal | **Só 2026** (decisão 7 da proposta). 72 arquivos, 616 MB. O histórico até 2110 fica **declarado** como disponível e deliberadamente fora. |
| **D4** | Onde roda | **Script de linha de comando na VM.** Sem fila, sem thread, sem botão. O botão é conteúdo do V2.7 ("escala e operação") — construir a interface antes de a ingestão ter rodado uma vez seria desenhar sem saber quanto demora nem onde quebra. |
| **D5** | `clientes_atendidos` | **Continua contando só a entrada**, com o driver explícito e declarado na tela. A união das duas direções entra no V2.4, onde dá para mostrar lado a lado em vez de trocar um número por outro em silêncio. |
| **D5.1** | Balde sem cliente visível | **Acrescentado pela Maria.** O volume do balde "sem cliente identificado" passa a ser exibido como número, separado por causa. Detalhado na seção 3.9. |

---

## 3. Escopo, em ordem de execução

A ordem importa: o rename (passos 1 e 2) é o item mais perigoso do lote e tem que
estar de pé e varrido **antes de qualquer ingestão de saída gravar**.

### 3.1. Métricas e conceitos — migration `0015_metricas_direcionais`

Estado final, cinco métricas:

| Antes | Depois | Origem |
|---|---|---|
| `peso_bruto_movimentado` | `peso_bruto_entrada` | renomeada |
| `valor_mercadoria_movimentada` | `valor_mercadoria_entrada` | renomeada |
| `registros_movimentacao` | `registros_entrada` | renomeada |
| — | `peso_bruto_saida` | nova |
| — | `registros_saida` | nova |

**Renomear em lugar, nunca inserir nome novo.** `UPDATE metricas SET nome = ...`
preserva o `metrica_id`, então as células de `medidas` continuam ligadas.
Inserir um nome novo deixaria a métrica nova com **zero** medidas e as históricas
presas ao id antigo, órfão: o cockpit mostraria **0 t sem erro nenhum** até
alguém reprocessar com forçar. Esta é a falha mais grave possível deste lote.

O mesmo vale em `conceitos_canonicos` (`UPDATE ... SET chave`). O
`catalogo_campos` referencia conceito por **id**, então o rename da chave não o
afeta.

A migration também atualiza `nome`, `nome_executivo` e `descricao` das três
renomeadas para o vocabulário de entrada. Sem isso, banco novo (que nasce do seed
corrigido) e banco existente (que passa pela migration) divergiriam no texto —
classe de bug que este projeto persegue.

Conceitos que **não** são renomeados, de propósito: `peso_liquido_movimentado`,
`quantidade_uas`, `volumes_declarados` e `clientes_atendidos`. Nenhum deles ganha
gêmeo de saída neste lote, e renomear expandiria o raio de explosão sem ganho.
Motivo registrado na migration.

Os dois conceitos novos entram com `unidade_canonica` preenchida (`kg` e `un`) e
`status` aprovado — sem isso `_unidades_dos_conceitos` recusa o processamento por
desenho (risco 3 da proposta). Como o default da coluna `status` é `'aprovado'`
(`0005_catalogo_semantico.py:81`), o INSERT sem a coluna já nasce aprovado; o
teste tem que provar isso em vez de assumir.

As duas métricas novas nascem com `agregacao_padrao = 'soma'` — sem isso,
`exigir_metrica_aditiva` as recusa no cockpit com HTTP 400.

**Downgrade:** desfaz os três renames e remove as duas métricas de saída junto
com a linhagem e as células delas (`medida_linhagem` → `medidas` →
`medidas_recebidas`, nessa ordem, por causa de `medidas.medida_recebida_id`).
Mesma política destrutiva-só-no-que-o-lote-criou da `0014`.

**Seeds** (`backend/seed_semantico.py`, `backend/seed_metricas.py`,
`backend/seed_datahub.py`) passam a listar os cinco nomes. Teste obrigatório:
banco novo semeado e banco existente migrado terminam **idênticos** nas cinco
linhas de `metricas` e `conceitos_canonicos`.

### 3.2. Varredura dos consumidores do nome

A parte que mais quebra em silêncio. Cada item abaixo foi localizado no código;
nenhum pode ficar de fora.

| Arquivo | O que muda | Se esquecer |
|---|---|---|
| `frontend/cockpit.html` — `KPI_FORMATO` | chaves novas | **peso volta a aparecer em kg cru no lugar de toneladas**, e valor em reais cheios no lugar de milhões. Sem erro nenhum na tela. |
| `frontend/cockpit.html` — `find(k => k.chave === "peso_bruto_movimentado")` | chave nova | a linha "Peso bruto (detalhado)" **some** do painel de qualidade |
| `frontend/cockpit.html` — `<option>` do seletor de métrica | as cinco | métrica nova não é selecionável |
| `frontend/cockpit.html` — frase da participação | chave nova | imprime o identificador cru na frase |
| `frontend/linhagem.html` — `<option>` e o default chumbado | chaves novas | **HTTP 400 ao abrir a tela** |
| `backend/services/cockpit.py` — `_METRICAS_CARDS`, `_METRICA_PARTICIPACAO` | apontam para o par de **entrada** | cockpit inteiro em 400 |
| `backend/services/cockpit.py` — `_LIMITACAO_OPERACOES` | texto cita `registros_movimentacao` | texto mentindo na tela |
| `backend/services/serie_datahub.py` — `_METRICA_DRIVER_CLIENTES` | vira `registros_entrada` (D5) | contagem de clientes pela metade, com o rótulo antigo |
| `backend/services/processamento_datahub.py` — `_METRICAS` | par de entrada | erro de configuração no processamento |
| `scripts/verificar_v2.py` — duas listas `IN (...)` | resolver do banco | **check passa por vacuidade**: consulta vazia cai no ramo de sucesso e aprova um banco inteiro em grão antigo |
| `scripts/totais_competencia.py` — `_METRICAS_DATAHUB` e a consulta | resolver do banco | `antes.txt` e `depois.txt` saem vazios, o `diff` dá zero e o lote é aprovado sem nada ter sido verificado |

**Endurecimento obrigatório nos dois scripts:** a lista de métricas passa a ser
resolvida contra `metricas` e **falha** se não resolver nenhuma. Hoje os dois
tratam "consulta vazia" como "está tudo certo".

Os cards do cockpit **continuam apontando para o par de entrada**, de propósito:
o V2.3 é lote de ingestão, e a tela tem que exibir exatamente os mesmos números
de antes do lote. Saída na tela é V2.4/V2.5.

### 3.3. Leitor `backend/services/saida_mercadorias.py` (novo)

Módulo novo, no molde do `entrada_mercadorias.py`, com quatro diferenças de
fundo:

1. **Cabeçalho em dois níveis.** Valida a **linha 5** (as seis bandas, na ordem
   esperada) **e** a **linha 6** (os rótulos). Validar só uma das duas deixa
   passar arquivo com banda reordenada; validar só a linha 6 não distingue os
   dois layouts, porque os rótulos são iguais.
2. **Banda por deslocamento, nunca por posição chumbada.** Localiza
   `Separado Fisicamente` na linha 5 e lê `Peso Bruto` em `início + 5`. Confere
   que o rótulo naquela posição é mesmo `Peso Bruto` antes de ler qualquer linha
   — se não for, erro claro, nunca leitura silenciosa.
3. **Dois layouts aceitos** (36 com cliente, 34 sem), e a leitura **declara qual
   leu**. Layout que não seja nenhum dos dois é erro.
4. **Agregação em streaming.** Um arquivo tem 99.628 linhas
   (`SAIDA_MERCADORIAS_025_2607_f1`). O `ler()` da entrada devolve todas as
   linhas em memória; aqui isso não escala. O leitor expõe um iterador de linhas
   normalizadas e o processamento agrega enquanto consome — a lista completa
   nunca existe.

Padrão de nome, aceitando 1..N partes, com e sem sufixo:

```text
^SAIDA_MERCADORIAS_(\d+(?:-\d+)*)_(\d{2})(\d{2})(?:_f(\d+))?\.xlsx$
```

Filtro `Status Separação = Cancelado`, normalizado (sem acento, sem caixa), com
**contagem das linhas filtradas** exposta no relatório. Zero é o valor esperado
hoje, e zero declarado é diferente de zero silencioso.

Campos que o leitor entrega por linha: CNPJ do cliente (ou ausente, no layout de
34), `Estoque`, `Peso Bruto` da banda oficial, `Status Separação`. `Operação` não
é usada (decisão 6) e não é lida.

`sem_dado` segue a mesma semântica do V2.1.1: cabeçalho válido e zero linha é
estado terminal, não erro.

### 3.4. Variante de 18 colunas da entrada — `entrada_mercadorias.py`

`entrada_mercadorias` passa a reconhecer os dois layouts **pelo cabeçalho, nunca
pela unidade**: um de-para novo não pode mudar como um arquivo é lido. No layout
de 18, a leitura é marcada como sem coluna de cliente e todas as linhas vão para
o balde `cliente_id NULL`, **sem** registrar pendência de cliente (D2).

### 3.5. De-para da RJ — migration `0016_depara_rj`

`RJ/004-003 → RMRJ` entra em `filiais_datahub.SIGLA_POR_CODIGO` e como migration
que insere o de-para e apaga a pendência correspondente — mesmo padrão da `0012`,
que é a lição de 03/ago (correção de cadastro entra como migration, não como SQL
manual no runbook). O comentário atual em `filiais_datahub.py:31-36`, que explica
por que a RJ estava fora, é substituído pelo motivo de ela entrar agora.

**A mesma linha habilita entrada e saída da RJ** — por isso o passo 3.4 e este
têm que andar juntos. Liberar o de-para sem o leitor da variante transformaria os
8 arquivos de entrada da RJ em 8 erros de leitura, exatamente o que o V2.1 evitou.

`RMSPII/002`, `RJ/004-001` e `RJ/005-001` seguem fora, por decisão de 02/ago.

### 3.6. Layout lido — migration `0017_layout_lido`

Coluna `layout_lido` em `processamentos_datahub`, preenchida pelo processamento
com o layout que o leitor de fato detectou. É a base da atribuição de causa da
seção 3.9: a causa vem **do que foi lido**, não de uma lista escrita à mão que
alguém esquece de atualizar quando a fonte muda.

### 3.7. Partição, guarda de colisão e processamento

**A unidade de processamento deixa de ser o arquivo e passa a ser a partição:**
`(família, origem qualificada, competência)`, com 1..N partes ordenadas pelo
índice do sufixo (sem sufixo = parte única).

Ajustes na guarda de colisão (`_abortar_se_origens_colidem`):

- as partes de uma mesma partição **não** são colisão — é o caso normal;
- **é** colisão: duas partes com o mesmo índice, ou a mesma partição aparecendo
  em dois caminhos diferentes;
- a chave ganha a **família**. Sem isso, a entrada e a saída da mesma
  filial/competência se acusariam de colidir, e a rodada abortaria sempre.

Isto cumpre a regra já registrada no `V2_PLANO.md`: *processamento por arquivo
isolado só pode existir passando pela guarda de colisão.*

`processamentos_datahub` continua chaveado por `item_id`, com **uma linha por
parte** — as duas partes precisam aparecer no painel. O frescor é avaliado na
**partição inteira**: parte alterada reprocessa a competência toda, senão
metade do mês ficaria com dado velho.

`processamento_datahub.py` deixa de ser específico da entrada e passa a receber o
produtor (família, leitor, métricas, fonte lógica). Dois pontos críticos:

- **`_remover_celulas_orfas` recebe só os `metrica_id` daquele produtor.** É isso,
  e só isso, que impede a saída de apagar as células da entrada e vice-versa.
  A separação de métricas (decisão 1) torna os escopos disjuntos; o código tem
  que tornar isso estrutural, não acidental. **Teste obrigatório nos dois
  sentidos.**
- **`medidas_recebidas.arquivo_origem` nomeia todas as partes** da competência —
  o valor veio da união delas, e a linhagem tem que dizer isso.

Filtro de escopo temporal (D3): constante explícita com a competência mínima
(`2026-01`) e o motivo. Os 176 arquivos fora do recorte **não podem ficar em
silêncio** — aparecem como "fora de escopo por decisão", que é o vocabulário de
cobertura que o V2.1 criou.

### 3.8. `scripts/processar_saida.py` (novo) — D4

Somente ele grava; roda na VM por `docker compose exec`. Incremental (pula
partição inalterada), **uma competência por transação** (uma falha não derruba as
outras), progresso em stdout por competência, resumo ao final. Nada de fila, nada
de thread.

### 3.9. Balde "sem cliente identificado" visível — D5.1

Hoje o balde é invisível como número: o card conta os clientes cadastrados e o
sistema só escreve "há movimentação sem cliente identificado no recorte", sem
dizer se é 1% ou 40%. Este lote faz esse balde **crescer** (a RMRJ inteira entra
nele na entrada), então soltar o crescimento sem mostrar o tamanho seria
apresentar número parcial como completo.

**O que passa a ser exibido:** peso (t), valor (R$), registros e — o que de fato
informa — **a participação no total do recorte**.

**Separado por causa**, porque os destinos são diferentes:

| Causa | Resolve? | Como o sistema sabe |
|---|---|---|
| cliente não cadastrado | sim — cadastra e o valor migra no próximo processamento | tem CNPJ na fonte; já aparece em `cliente_pendencias` |
| unidade sem coluna de cliente na fonte | **não** — não há CNPJ para cadastrar | `layout_lido` do processamento (seção 3.6) |

Somar os dois num número só mandaria alguém caçar um cadastro que não existe —
mesmo defeito dos cinco erros permanentes da SANCA que o V2.1.1 corrigiu.

**Onde:** bloco novo na resposta de `clientes_atendidos`
(`serie_datahub._serie_clientes_atendidos`, ao lado de `limitacoes`) e uma linha
abaixo do número no card do cockpit.

**Limite declarado:** como o card fica em entrada (D5), o balde equivalente da
**saída** — a RMSPV — só é exibido no V2.4. A resposta declara que ele existe e
que ainda não está sendo mostrado. Não pode ficar escondido.

### 3.10. Cobertura e catálogo semântico

- `nuvem_datahub._FAMILIAS`: `SAIDA_MERCADORIAS` passa de `nao_integrada` para
  `integrada`. A bolinha tem que dizer que **176 dos 248 arquivos estão fora de
  escopo por decisão** (D3) — família integrada com três quartos dos arquivos em
  silêncio é pior do que família não integrada.
- `backend/seed_semantico.py`: os 36 campos da saída entram em `catalogo_campos`.
  **Só o `Peso Bruto` da banda *Separado Fisicamente* fica `aprovado`** e ligado
  ao conceito; os das outras duas bandas ficam `rascunho` com observação nomeando
  a banda. É isso que impede o Laboratório e o `perfil_dados` de somarem a banda
  errada. `catalogo_fontes` já tem `datahub_saida_mercadorias`
  (`seed_semantico.py:116`) — não precisa criar.
- O campo do catálogo tem que registrar as **duas** posições possíveis (36 e 34
  colunas) ou a posição perde sentido como identidade. Decidir na execução se
  isso vira duas fontes lógicas ou uma observação; **não deixar implícito**.

### 3.11. `scripts/verificar_v2.py`

Além do endurecimento da seção 3.2:

- as cinco métricas existem, com conceito aprovado e unidade definida;
- nenhuma célula de métrica de saída em armazém sem de-para;
- todas as partes de uma partição com status terminal (nunca metade ok, metade
  pendente);
- **RMRJ na entrada** e **RMSPV na saída** com zero célula de cliente não nulo —
  se aparecer uma, o leitor casou o layout errado;
- nenhuma célula de saída em competência anterior a 2026 (prova do recorte D3);
- contagem de arquivos de saída processados batendo com os 72 esperados.

---

## 4. Aceite

Da proposta, mantidos: saída grava na mesma semântica da entrada; arquivo partido
não aciona a guarda de colisão; banda errada é rejeitada com erro claro; saída
não contamina entrada; reprocessar duas vezes não duplica.

Acrescentados por este plano:

1. **O rename não move um único número.** `scripts/totais_competencia.py` rodado
   antes do deploy e depois: a coluna do total da entrada bate **linha a linha**.
   É a prova central do lote.
2. **O leitor acerta os dois layouts.** Teste com fixture de 34 e de 36 colunas,
   e a de 34 provando que o peso sai da coluna 29, não da 31.
3. **Partição de 1, 2 e N partes**, com e sem sufixo `_fN`, sem acionar colisão.
4. **Prune isolado nos dois sentidos**: processar saída não apaga célula de
   entrada, e vice-versa.
5. **RMRJ e RMSPV sem cliente**, sem pendência fantasma de cliente.
6. **Balde sem cliente com número e causa** na resposta e na tela.
7. Migrations `0015`, `0016` e `0017` validadas nos dois sentidos contra banco com
   dado real, via `alembic` CLI direto, independente da suíte.

**Conferência contra o dado real na VM.** Valores medidos em 06/ago/2026, somando
o `Peso Bruto` da banda *Separado Fisicamente* de **todas as linhas não vazias,
sem descarte por validação**:

| Arquivo | Colunas | Linhas | Peso separado (kg) |
|---|---:|---:|---:|
| `RMSPII/001_2607_f1` | 36 | 43.526 | 1.670.063,1 |
| `RMSPII/001_2607_f2` | 36 | 38.082 | 1.928.910,8 |
| **`RMSPII/001` 2607 (partição)** | 36 | **81.608** | **3.598.973,9** |
| `RMSPII/001_2608_f1` | 36 | 14.960 | 578.032,7 |
| `SANCA/025_2607_f1` | **34** | 99.628 | 2.885.648,3 |
| `CWB3/001_2601` (sem sufixo) | 36 | 34.666 | 1.054.464,4 |
| `RJ/004-003_2608_f1` | 36 | 22.409 | 631.952,2 |

O número do sistema pode ficar **um pouco abaixo** destes, porque o leitor
descarta linha com peso não numérico e estes totais não descartam nada.
Diferença pequena é esperada e **tem que ser explicada**, nunca ignorada; sistema
acima do total medido é defeito.

---

## 5. Fora do lote (declarado)

| Item | Onde vai |
|---|---|
| `valor_mercadoria_saida` | **não existe** — a fonte não tem coluna de valor (1.1) |
| Histórico anterior a 2026 (176 arquivos, ~2 GB) | fora por decisão 7 / D3 |
| Botão de processar saída no painel | V2.7 (escala e operação) — D4 |
| `clientes_atendidos` somando as duas direções | V2.4 — D5 |
| Balde sem cliente da **saída** (RMSPV) exibido | V2.4 — D5.1 |
| Consultas de volumetria (`resumo`, `evolução`, `ranking`, `matriz`) | V2.4 |
| Cockpit visual, entrada × saída, saldo, Tabulator | V2.5 |
| Conciliação com o Power BI (inclui a decisão 6 e a banda escolhida) | V2.6 |
| Nível de atendimento (as três bandas diferem em ~0,2%) | métrica futura, fora da V2 |
| `GUIAS_SAIDA` como produtividade | depois da V2 |

---

## 6. Riscos

1. **O rename é a parte perigosa do lote, não o leitor.** Quase todo consumidor
   falha em silêncio: kg no lugar de tonelada, check de deploy passando vazio,
   `diff` de conciliação aprovando sem comparar nada. Por isso ele é o passo 1 e
   2, varrido inteiro antes de qualquer ingestão de saída gravar.
2. **Banda por posição chumbada** — o erro que a SANCA quase provocou (1.2).
   Mitigado por localizar a banda na linha 5, conferir o rótulo na posição
   calculada, e testar com fixture de 34 colunas.
3. **Memória.** Um arquivo de 18 MB abre em memória e o pico chega a ~2× no
   download (`graph_datahub.baixar_item` junta os pedaços num `bytes` só). Ler
   **uma parte por vez** e agregar em streaming; nunca as duas juntas.
4. **`statement_timeout` de 30 s** vale para toda query do pool
   (`database.py:23`). Uma competência por transação, com escritas em lote, tem
   que caber nisso — se não couber, aparece aqui antes de aparecer em produção.
5. **A saída não filtra `Operação`** (decisão 6). Na amostra são 0,8% das linhas,
   bem menos que os 39% da entrada. Vai para a conciliação (V2.6).
6. **A RMSPIII (015) está encerrando**: 2 linhas na saída de 2607. Não é
   `sem_dado` (tem dado), mas o V2.5 vai precisar distinguir "zero" de "não
   opera" — já previsto lá.
7. **`_f1`/`_f2` disjuntos foi verificado em dois pares, não nos 118.** A
   verificação por amostra vale para o desenho; se um par vier duplicado como no
   `DADOS_GERAIS`, o peso daquela competência dobra. Vale um check de sanidade no
   processamento (partes com interseção de chave) ou, no mínimo, o risco
   registrado aqui e conferido na primeira rodada real.

---

## 7. Fechamento do lote

Mesmo ritual dos anteriores, sem atalho:

1. suíte completa (baseline: **514 passed** no fim do V2.2; nenhum teste
   removido);
2. migrations `0015`, `0016` e `0017` validadas nos dois sentidos, contra banco
   com dado, via `alembic` CLI direto — independente da suíte;
3. `node --check` nas telas alteradas;
4. `docs/V2_PLANO.md` atualizado (status do lote, o que foi entregue, o que a
   verificação achou);
5. `memory/layout-saida-mercadorias.md` já corrigido em 06/ago (a coluna 31 não é
   universal); rever se a execução muda mais alguma memória;
6. commit isolado, **sem** co-autor Anthropic;
7. **verificação independente por agente separado, antes do commit**;
8. **aguardar autorização da Maria antes do V2.4.**
