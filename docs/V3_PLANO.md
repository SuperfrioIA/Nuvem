# V3 — Plano e status

**Este documento é a fonte única do status da V3.** Criado em 24/ago/2026, na
decisão de migrar o artefato de análise para aplicação lendo o DW.

**Autorizados e feitos até agora: V3.0, V3.1, V3.2 e V3.3** (24/ago/2026), **V3.4
e V3.5** (25/ago/2026), **V3.5.1, V3.6 e V3.7** (26/ago/2026) **e V3.8 e V3.8.1**
(27/ago/2026 — os dois **executados na VM**: o histórico completo, 2023–2026, está
em produção nas duas tabelas, 202.087 linhas no recebimento e 232.089 na
expedição; ver "Aceite do V3.8.1"). Do V3.9 em diante a divisão em lotes na seção
final é proposta, não plano em execução — autorização é por lote, como na V1 e na
V2.

**V3.7.1** (filtros com caixas de seleção), **V3.7.2** (os dois movimentos na
mesma matriz, com o pai somando "movimentação") **e V3.7.3** (desmarcar tudo)
**foram feitos e validados no navegador em 27/ago/2026**, os três. A validação do
V3.7.1 foi o que gerou o V3.7.3, que conserta um defeito de interação introduzido
pelo próprio V3.7.1 — o ciclo está registrado na seção dele.

> **O V3.5 está construído e testado, e a leitura real do DW é a evidência que
> falta.** A IA não conecta no DW; o aceite é a rodada da Maria
> (`python -m catering.carga --fonte oracle --sondar`, e depois a carga). Ver
> "Aceite" na seção do V3.5.

> **Cuidado com o nome:** `docs/proposta_v3_volumetria.md` **não** é deste
> documento — é a especificação da **V2**, e se chama "v3" por acidente
> histórico. O status da V2 continua em `docs/V2_PLANO.md`.

---

## O que a V3 é

Uma aplicação enxuta que lê volumetria de catering direto do **DW Oracle**, com
carga agendada, e entrega **filtros + Matriz + planilha**. O desenho da tela foi
acordado e validado no artefato de análise publicado em 21/ago/2026
(`Documents/analises/radar_recebimento.html` + kit de build em
`_build_radar`).

**A visão foi acordada antes de codar** — a V1 e a V2 foram escritas descobrindo
regra no caminho, e é daí que vem a maior parte do retrabalho delas.

> **O artefato não existe mais em disco** (a Maria apagou a pasta `analises` em
> 24/ago/2026). A partir daqui **a especificação de registro é este documento**:
> o "Contrato fechado" abaixo, mais `memory/medida-repetida-vira-linha.md` (as 3
> faixas da saída abrem como **linhas** dentro do cliente, não como colunas),
> `memory/pagina-mostra-numero-nao-texto.md` e
> `memory/radar-recebimento-fonte-dw.md`. Foi exatamente por isso que essas
> decisões foram escritas em vez de ficarem só no HTML.
>
> Duas consequências práticas: (1) **o aceite do V3.2 não muda**, porque a
> referência sempre foi os CSVs agregados por `nk_calendario`, não o artefato
> — e os CSVs seguem em `docs/Analise/`; (2) **não existe mais lado a lado**,
> então a validação visual é humana, no navegador, como manda
> `memory/validar-tela-no-navegador.md`.

Não há mais vínculo com o SharePoint DataHub na V3. A fonte é o DW.

---

## Por que recomeçar em vez de refatorar

A pergunta foi levantada pela Maria em 24/ago/2026 ("queria apagar tudo e fazer
do zero... quero evitar gambiarra, frankenstein, código antigo"). A resposta
inicial foi "reaproveita", e mudou depois de medir o que existe. Os dois
argumentos são técnicos, não estéticos:

### 1. O grão da tabela de fato está errado para a visão de hoje

O fato publicado da V1/V2 é livro-caixa mensal em formato longo:

```sql
medidas_recebidas (armazem_id, cliente_id, metrica_id,
                   competencia DATE, valor NUMERIC, dimensoes JSONB)
medidas           (metrica_id, armazem_id, competencia, valor,
                   UNIQUE (metrica_id, armazem_id, competencia))
```

Uma linha por medida, por mês, com o resto empurrado para JSONB. Era o desenho
certo para "uma planilha por mês por armazém com meia dúzia de números".

O artefato precisa do oposto: **grão de dia**, 13 medidas na mesma linha de
fato, seis dimensões (dia, unidade, filial, cliente, operação, tipo de estoque).
Uma linha do artefato viraria ~7 linhas ali, e toda consulta viraria pivô sobre
JSONB. Serviço, teste e consulta do cockpit todos se apoiam nesse grão —
refatorar é trocar a fundação com a casa em cima.

### 2. A arquitetura responde uma pergunta que deixou de existir

Conector plugável, de-para de nome de filial, `item_id` como identidade, máquina
de estado por arquivo (`ok`/`erro`/`sem_dado`), leitor de variante de layout (18
colunas da RJ), três tabelas de pendência — tudo isso existe porque a fonte era
uma pasta de planilhas inconsistentes no SharePoint.

O DW entrega coluna tipada, PK, esquema estável, sigla pronta em
`NK_WMS_FILIAL`, todas as unidades juntas. Manter essa maquinaria é carregar
defesa contra um inimigo que saiu da sala.

### Medido em 24/ago/2026

| camada | tamanho | acoplamento ao DataHub |
|---|---|---|
| backend | 11.245 linhas / 54 arquivos | 33 dos 54 arquivos citam `datahub`/`sharepoint`/`graph`/`item_id`; 2.847 linhas em arquivos com "datahub" no nome |
| testes | 10.879 linhas / 43 arquivos | **8.570 linhas (79%)** |
| frontend | 4.786 linhas / 5 páginas | cockpit, nuvem, laboratório, admin, linhagem |
| schema | 25 tabelas / 18 migrations | 5 migrations são cicatriz de de-para (`0012_depara_cwb3_sanca`, `0016_depara_rj`, `0018_corrige_sigla_rmspii`) |
| conexão com o DW | **nenhuma** | `requirements.txt` só tem `psycopg2`; tudo do DW veio como CSV até hoje |

### O que isso NÃO autoriza

**Não apagar nada agora.** O código da V2 continua no repo e continua sendo a
implementação de referência de regras que vão precisar de releitura. O antigo
sai quando o novo provar o mesmo número, não antes.

---

## Contrato fechado (Maria, 21–24/ago/2026)

| item | decisão |
|---|---|
| **Fonte** | Oracle `pdwgener` (`oracleprd-aws.superfrio.com.br:1521`, `service_name`, cliente `oracledb` em modo thin) — **`DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`** + **`DM_VOLUMETRIA.FATO_VOL_EXP_CAT_V01`** (nome confirmado pela Maria em 25/ago/2026; o registrado antes, `FATO_VOL_REC_CAT`, estava sem o schema e sem o sufixo `_V01`, e por isso a sondagem levou `ORA-00942`); `FATO_VOLUMETRIA` só para conciliação. ~~São **tabelas inteiras**, sem filtro de extração~~ — **corrigido em 25/ago/2026:** o DW reconstruiu as duas tabelas com histórico desde 02/jan/2023 (434 mil linhas), e a Maria recortou o escopo: **a V3 lê de 2026 para frente**, por `nk_calendario`, com o piso em configuração (`DW_ANO_MINIMO`, padrão 2026) porque comparar 2025 com 2026 é caso de uso previsto. Ver a seção do V3.5 |
| **Escopo** | **catering = instâncias SLIN**. Volume de outras instâncias (`DISTROMAQ_PRD`, `MDLZ_PRD`, `DISTRO_PRD`, `SEEDS_PRD`, `ATIVA_*`) é outro negócio e está corretamente fora. Declarar na tela; guardar a instância como coluna de procedência |
| **Carga** | 2× ao dia: **07h05 e 15h05**. O processo do DW (`catering_to_dw_volumetry_v01`) roda a cada 2h, de 6h35 a 23h35 — lemos 30 min depois, nunca no horário |
| **Incremento** | por **`DW_DATA_ALTERACAO`**, não só `DW_DATA_INCLUSAO` (linha muda entre extrações). Idempotente pela PK. **O DW insere e altera, nunca apaga** — **confirmado com o time do DW pela Maria em 25/ago/2026**, e nao mais heranca sem fonte: o processo so insere e atualiza, **so guia confirmada entra na tabela**, e **nao existe desconfirmar**. Logo uma linha que entrou nao tem por onde sair, e nao precisa de varredura de PKs para detectar remocao. Consequencia: o alarme de contagem que se discutiu para o V3.5 **nao sera construido** — vigiaria uma condicao sem mecanismo. O gatilho que o traria de volta e o WMS passar a permitir cancelar guia ja confirmada. Fica tambem registrado um caso estreito **conhecido e nao tratado**: se o `nk_instancia` de um movimento mudasse de `SLIN_*` para outra instancia, o DW nao teria apagado nada mas a linha sairia do nosso escopo, e a nossa copia ficaria com ela — nao tratado porque significaria o volume passar a pertencer a outro negocio, o que nao e correcao plausivel de cadastro|
| **Tela** | barra de filtros + **Matriz** + planilha aberta (100 linhas) + download do recorte. **Só isso** — o resto do artefato não entra na V3 |
| **Matriz** | **unidade > cliente > tipo de entrada**, um mês por coluna, 12 unidades por página — igual ao artefato |
| **Data que agrega** | **`nk_calendario`** (Maria, 24/ago/2026) — a data do **movimento**, não a da solicitação. Guia pedida em 31/jan e expedida em 02/fev conta em **fevereiro**. É a data que o calendário do DW usa, e a que fecha melhor contra o `fato.csv`. `data_solic` continua guardada, para conciliação |
| **Medidas** | as 5 lentes do artefato: peso líquido, peso bruto, pallets, volumes, valor. Expedição nas 3 faixas: solicitado, atendido, separado |
| **Guia** | **fora da Matriz** — contagem distinta não soma por linha. Sem `COUNT(DISTINCT)` na tela principal |
| **Pallet** | só existe na **entrada**. Nenhuma das 3 faixas da expedição tem pallet — escolher Pallets mostra entrada com número e saída vazia. É a fonte, não defeito |
| **Dado sensível** | **nada mascarado**, R$ visível para todos |
| **Auditoria** | **só login e download** (Maria, 24/ago/2026) — quem entrou, e quem baixou o quê com qual recorte. Consulta a consulta, não: gera volume e não se lê |
| **Login** | admin + visualizador; desenhado para o AD entrar depois sem reescrita (papel separado de identidade) |
| **Download** | sempre no recorte dos filtros da tela; streaming, nunca montado em memória; CSV como padrão, xlsx só sob teto |
| **Admin / linhagem** | **os dois morrem** (Maria, 24/ago/2026): parqueados no repo agora, sem alteração de código; saem da VM **só depois** da tela nova de pé |
| **Laboratório** | lote posterior, **refeito** olhando o dado do DW — não é porte das 850 linhas atuais |

### Volume medido (dimensiona banco e download)

| | medido nos CSVs de 21/ago/2026 |
|---|---|
| linhas, jan–ago/26, 6 unidades | **78.768** (36.300 recebimento + 42.468 expedição) |
| projeção por ano, grão de item | ~120.000 |
| tamanho bruto dos 8 meses | 34,6 MB |
| por carga (2×/dia, incremental) | ~10.000 linhas |

Isso é pequeno para Postgres. Não justifica cubo, pré-agregação nem
materialização — a Matriz agrega ao vivo.

---

### Sondagem do DW em 25/ago/2026 (o que a conexao real provou)

Executada pela Maria em dois blocos somente leitura. O que **mudou** em relacao ao
que o projeto assumia:

| assunto | o que se assumia | o que a conexao provou |
|---|---|---|
| nome do objeto | `FATO_VOL_REC_CAT` | **`DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`** — outro schema e sufixo de versao |
| tabela ou view | indefinido (o `_V01` sugeria view) | **TABLE** nas duas. View pesada teria custo no `extrair()`; tabela nao tem |
| `NUMBER` no Python | `Decimal` | **`float`** — `fetch_decimals` e `False` por padrao no `oracledb 4.0.2`. Ver a correcao na secao do V3.1 |
| cliente Oracle na VM | incognita | **nao precisa** — modo thin conecta em 12.2 |
| senha do usuario | incognita | **`OPEN`, sem expiracao** — agendamento nao morre por senha vencida |
| contrato de colunas | medido nos CSVs, nao verificado na fonte | **bate coluna por coluna**: 36 e 46, unica diferenca e o `pk_dw` renomeado de proposito |

**Volume e marca d'agua, em 25/ago:**

| | linhas no DW | CSV de 21/ago | `nk_calendario` | `dw_data_alteracao` |
|---|---|---|---|---|
| recebimento | 36.592 | 36.300 (+292) | 02/jan/2026 a 24/ago/2026 | 20/ago 15:26 a 24/ago 17:46 |
| expedicao | 42.789 | 42.468 (+321) | 31/dez/2025 a 24/ago/2026 | 20/ago 15:40 a 24/ago 17:47 |

A diferenca contra o CSV e pequena e coerente com dias novos — a premissa "tabelas inteiras, sem filtro de extracao" **se sustenta**.

**O que a marca d'agua mostra, e o que ela ainda nao prova.** O `last_ddl_time` das duas tabelas e **20/ago 15:24**, e o menor `dw_data_alteracao` e **20/ago 15:26** — dois minutos depois. Ou seja: as tabelas nasceram em 20/ago, foram carregadas inteiras naquele momento (e por isso linha de dez/2025 tambem carrega 20/ago na alteracao), e **desde entao nao houve DDL** — nos quatro dias seguintes elas foram atualizadas no lugar, com alteracao subindo ate 24/ago. Isso confirma duas coisas do V3.0: `dw_data_alteracao` e **tempo de processamento do DW**, nao data de negocio (que e o que serve para marca d'agua), e a decisao de nao usar a PK como identidade estava certa. O que **quatro dias nao provam** e o comportamento no mes: se um dia o DW recriar a tabela, todo `dw_data_alteracao` sobe junto e a rodada "incremental" vira carga cheia. Isso e **seguro** (o upsert nao apaga nada, e a chave natural sobrevive a rebuild), mas nao e incremental — e vale saber antes de prometer 07h05/15h05 rapidos.

**O risco que o upsert nao cobre:** linha **removida** na fonte nao e removida no nosso Postgres, porque a carga so insere e atualiza. Em 20/ago isso era teoria; agora sabemos que a tabela e reconstruida em algum momento (o proprio `_V01` e o `FATO_VOLUMETRIA_V04` mostram versionamento ativo), entao e cenario real.

**Decidido no V3.5:** nao ha varredura de PKs, porque o time do DW confirmou que o processo so insere e atualiza, so guia confirmada entra e nao existe desconfirmar — linha que entrou nao tem por onde sair (ver a linha "Incremento" do contrato fechado). O que o V3.5 construiu no lugar foi a guarda contra o cenario **oposto e observavel**: carga completa que le zero linha e `erro`, nunca `sem_dado`. Se um dia o WMS passar a permitir cancelar guia confirmada, a varredura volta a pauta — e o gatilho esta escrito.

## O que sobrevive da V1/V2

Reaproveitar por leitura e cópia, com teste novo — nunca por `import` do código
antigo:

- **Infra que funciona e está deployada:** Docker, compose, alembic, pytest,
  `auth.py`, `database.py` (pool), `logging_config.py`, `main.py`, e o método de
  deploy na VM.
- **Regra pura, sem acoplamento de fonte:** `services/tipo_estoque.py` (53
  linhas — já reimplementada no loader do artefato),
  `services/mascaramento.py`, `services/compatibilidade_medidas.py`.
- **O conhecimento, que é o ativo caro:** `docs/`, `memory/`, o histórico de
  decisão do `V2_PLANO.md`. Sobrevive intacto.
- **As cicatrizes:** as 8.570 linhas de teste acoplado não são portadas, mas são
  catálogo de bug real já encontrado (`sem_dado`, de-para de CWB3/Sanca,
  correção da sigla da RMSPII). Ler a cicatriz, não herdar o tecido.

---

## Limitações herdadas, que a V3 não resolve

Trocar de fonte muda o alvo da conciliação, não elimina ela. Dois fatos medidos
em 21/ago/2026 e confirmados pela Maria em 24/ago:

1. **A `FATO_VOL_REC_CAT` não tem guia de recebimento cancelada.** 1 linha em
   36.300 (guia `0000000609`, RMSPII, 15/jan/2026), com peso, volume e valor
   vazios. As 36.300 linhas têm `DTHR_CONFIRM` preenchida — a tabela só carrega
   guia confirmada, e guia cancelada em geral nunca foi confirmada. **Não é
   filtro de extração: é característica da tabela.** Isso explica 86,7% do gap
   contra o BI na RMSPII (12.925,2 t de gap contra 11.204,8 t de cancelada
   medida, jan–jun/26). Fechar depende de quem mantém o
   `catering_to_dw_volumetry_v01`, não da V3.
2. **A expedição tem cancelada, com peso só no solicitado.** 974 linhas / 927
   guias / 4.530,9 t líquido, e **0,0 t** em atendido e separado. Consequência
   de tela: na faixa *solicitado* (padrão), ~3% do número de expedição é pedido
   cancelado que não saiu. Trocar para *atendido* ou *separado* zera isso.

Nenhum dos dois é defeito da V3. Os dois precisam estar **declarados na tela**.

---

## Decisões abertas

| # | pergunta | de quem |
|---|---|---|
| A-1 | ~~O `linhagem` morre junto com o admin?~~ — **sim** (Maria, 24/ago/2026). Mesmo tratamento do admin: parqueado no repo agora, sai da VM só depois da tela nova de pé | fechada |
| A-2 | ~~Auditoria de acesso: só login, ou toda consulta?~~ — **só login e download** (Maria, 24/ago/2026) | fechada |
| A-3 | ~~As quatro incognitas do acesso ao DW~~ — **fechadas em 25/ago/2026**, com dois blocos somente leitura executados pela Maria (a IA nao conecta no DW). Oracle **12.2.0.1.0**; `service_name=pdwgener`; **`oracledb` em modo thin conecta, entao a VM NAO precisa do Instant Client**; usuario `INTEGRACAO_DADOS_CATERING` (criado em 24/ago), **senha `OPEN` e sem data de expiracao** — o agendamento do V3.5 nao morre por senha vencida; objetos reais **`DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`** e **`DM_VOLUMETRIA.FATO_VOL_EXP_CAT_V01`**, que sao **TABLE** e nao view; leitura confirmada (36.592 e 42.789 linhas); e o **contrato do V3.0 bateu coluna por coluna** (36 e 46, com a unica diferenca sendo o `pk_dw`, renomeado de proposito e ja documentado no `contrato.py`). Licao registrada: o `ORA-00942` da primeira sondagem **nao era falta de GRANT** — era o nome, que o plano guardava sem o schema e sem o sufixo `_V01` | fechada |
| A-4 | ~~Nome do pacote novo no repo~~ — **decidido em 24/ago/2026: `catering/`**, pelo escopo do negócio e não pela métrica (já existe dado de ocupação e capacidade no projeto, que um dia pode entrar como outra métrica do mesmo escopo) | fechada |
| A-5 | ~~Qual data a Matriz agrega~~ — **`nk_calendario`** (Maria, 24/ago/2026): *"conta como expedida em fevereiro. Calendário."* A data que vale é a do **movimento**, não a do pedido | fechada |
| A-6 | **Parcialmente fechada** (Maria, 24/ago/2026): `CONG` conta como congelado, `RESFRIADO` é classe nova, `AGUA / CARVAO` é seco — implementado, e o não-classificado caiu de 3,2% para **1,3%** do peso. **Segue aberto:** `CONSOLIDADOR` e `CONSOLIDADOR - 14025`, **3.872,5 t**, que são 97% do que restou e não foram perguntados | Maria |
| A-7 | ~~O nome da tabela tem versao, e versao sobe~~ — **respondido pela Maria em 25/ago/2026: fica so a `_V01`, sem programacao para criar outra versao por enquanto.** Entao o V3.5 escreve `DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01` e segue. Duas coisas do desenho ficam de pe **mesmo assim**, porque "sem programacao por enquanto" e ausencia de plano e nao garantia: o nome da tabela vive em **configuracao**, nao como constante enterrada em tres arquivos, e **tabela ausente falha alto** — a carga nunca pode reportar `ok` com zero linha. O contexto que justifica: a `FATO_VOLUMETRIA` do mesmo schema ja esta em `_V04`, entao versao subir e o comportamento normal daquele time, so nao esta agendado agora | fechada |
| A-8 | ~~Duas tabelas de catering desconhecidas~~ — **respondido pela Maria em 25/ago/2026: `FATO_VOL_EST_CAT_V01` e ESTOQUE e `FATO_VOL_TRN_CAT_V01` e TRANSPORTE. Nao entram agora, mas entram no futuro.** Fora do escopo do V3.5 (recebimento + expedicao). Quando entrarem, **nao e ajuste, e lote proprio**, por tres razoes concretas: (1) `movimento` tem CHECK `('rec','exp')` na migration 0019, e ampliar CHECK e migration; (2) cada movimento novo tem contrato de colunas **proprio** — a expedicao ja tem 46 colunas contra 36 do recebimento, entao estoque e transporte nao vao ser copias; (3) estoque provavelmente e **saldo** (foto num instante) e nao **fluxo** (soma no periodo) — se for, ele nao se soma por mes como a Matriz faz hoje, e isso e decisao de produto antes de ser codigo | fechada, com trabalho futuro registrado |

**O A-3 esta fechado** e nao bloqueia mais nada: as quatro incognitas foram respondidas em 25/ago e o contrato medido nos CSVs bateu coluna por coluna contra as tabelas reais. O que a sondagem trouxe de novo virou A-7 e A-8, **as duas fechadas pela Maria no mesmo dia**: fica so a `_V01`, e as tabelas de estoque e transporte existem mas nao entram agora.

> **Consequencia no codigo — FEITA no V3.5:** `catering/contrato.py` tinha `TABELA_REC = "FATO_VOL_REC_CAT"` / `TABELA_EXP = "FATO_VOL_EXP_CAT"`, nomes **incompletos** (sem schema, sem `_V01`), e esses valores viram `cat_cargas.tabela_origem`, que e **chave da marca d'agua** (`destino.marca_dagua()` filtra por ela). O V3.5 trocou para o nome qualificado e o pos em **configuracao** (`contrato.tabela()`, lendo `DW_TABELA_REC`/`DW_TABELA_EXP`), invalidando a marca d'agua das rodadas por CSV de proposito: a primeira rodada contra o Oracle e completa. Foi feito agora exatamente porque hoje nao custa nada, e depois do V3.6 custaria uma carga cheia em producao.
>
> **Efeito colateral que o lote descobriu:** `RENOMEADAS` montava o nome da coluna da PK como `"PK_" + TABELA_REC`. A tabela ganhou schema e sufixo de versao; a coluna, nao — derivar um identificador do outro produziria `PK_DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`, que nao existe. Agora sao constantes separadas, e o teste que ja existia no `test_catering_dominio.py` e a trava.

---

## Divisão em lotes (proposta, nada autorizado)

Ordem deliberadamente invertida em relação ao normal: o acesso ao DW é o
**último** passo técnico, não o primeiro. Os dois CSVs de 21/ago já são o
contrato de colunas do DW, então quase tudo se constrói antes do acesso existir.
Isso remove o impedimento do caminho crítico.

A costura que permite isso:

```text
extrair()                   <- a única parte que conhece a fonte (CSV hoje, SQL depois)
transformar() + carregar()  <- idêntico nos dois casos
```

| lote | o quê | depende do DW? |
|---|---|---|
| **V3.0** | Contrato e schema: fato no grão do DW, migrations, sem carga — **feito em 24/ago/2026**, ver seção abaixo | não |
| **V3.1** | Carregador contra os CSVs, idempotente pela **chave natural** (não pela PK do DW — ver V3.0), com registro de rodada; suíte nova — **feito em 24/ago/2026**, ver seção abaixo | não |
| **V3.2** | Filtros + Matriz, com aceite célula por célula contra os CSVs agregados por `nk_calendario` — **feito em 24/ago/2026**, ver seção abaixo | não |
| **V3.3** | Planilha aberta + download em streaming e auditoria — **feito em 24/ago/2026**, ver seção abaixo | não |
| **V3.4** | Login e papéis (admin/visualizador) + auditoria de acesso — **feito em 25/ago/2026**, ver seção abaixo | não |
| **V3.5** | Troca de `extrair()` para Oracle + agendamento construído e desligado — **feito em 25/ago/2026**, ver seção abaixo | **sim** |
| **V3.6** | Deploy na VM; a V2 sai do ar inteira — **EXECUTADO em 26/ago/2026**, a V3 está em produção na porta 8003 | **sim** |
| **V3.7** | Recorte por dia, filtro de dia do mês e abertura da tela — **feito em 26/ago/2026**, ver seção abaixo | não |
| **V3.7.1** | Filtros com caixas de seleção e "Selecionar tudo" — **feito em 27/ago/2026**, ver seção abaixo | não |
| **V3.7.2** | Os dois movimentos na mesma matriz, com o pai somando "movimentação" — **feito em 27/ago/2026**, ver seção abaixo | não |
| **V3.7.3** | Desmarcar tudo: "Selecionar tudo" alterna, e "nenhum marcado" é estado que não pode ser aplicado — **feito em 27/ago/2026**, ver seção abaixo | não |
| **V3.8** | Histórico completo do DW (piso 2023) + recarga cheia — **executado em 27/ago/2026**, e entrou metade: o conserto é o V3.8.1 | não |
| **V3.8.1** | A linha sem cliente (migration 0024) e o `--sondar` medindo preenchimento — **executado em 27/ago/2026**, histórico completo em produção | não |
| **V3.9** | Conciliação contra `FATO_VOLUMETRIA`, com as duas limitações declaradas | não |
| **V3.10** | Laboratório novo, sobre o dado do DW | não autorizado |

**Renumeração (26/ago/2026):** conciliação e laboratório andaram dois números
para frente, para o recorte por dia e o histórico completo entrarem na ordem em
que foram pedidos. O que era "V3.7 conciliação" agora é **V3.9**.

**Ressalva sobre o V3.2 — o aceite nunca foi o artefato.** O artefato agregava
por `data_solic`; a aplicação agrega por `nk_calendario` (A-5). Comparar os dois
direto acusaria diferença onde não há erro nenhum. Então a referência do aceite
é **os mesmos CSVs de `docs/Analise/`, agregados por `nk_calendario`, célula por
célula** — e essa referência **sobreviveu** ao apagamento do artefato, porque
são os CSVs, não o HTML.

Como a comparação é contra o dado e não contra a tela antiga, os dois casos que
antes precisavam ser distinguidos (diferença no meio do período = bug;
diferença na borda = a própria decisão A-5, com dez/2025 em 1.408,8 t por
solicitação contra 133,9 t por calendário) deixam de existir como ressalva: a
agregação dos dois lados passa a ser a mesma. Os números da borda ficam
registrados aqui só como memória de por que a A-5 foi decidida.

**A visão ainda muda** — palavra do time em 21/ago, "vai mudar todo dia". Por
isso o V3.2 para e é apresentado antes de qualquer tela adicional. Construir
cinco páginas de uma vez é repetir exatamente o erro que gerou a bagunça que a
V3 está corrigindo.

---

## Lote V3.0 — Contrato e schema (feito, 24/ago/2026)

Autorizado pela Maria em 24/ago/2026. Entregou o pacote `catering/`, o contrato
de colunas medido e a migration `0019_catering_fato_dw`. **Sem carregador, sem
tela, sem login, sem DW** — e sem tocar em `backend/`, `frontend/` ou nas
migrations antigas.

### O que a medição do contrato descobriu

Perfilei as duas extrações coluna por coluna antes de escrever o DDL, para o
schema não ser chute. Quatro achados mudaram o desenho:

1. **`PK_FATO_VOL_*_CAT` não serve de identidade.** Vem `1..N` sem buraco, com
   `N` igual à contagem de linhas, e **todas** as linhas têm `DW_DATA_INCLUSAO`
   em 20 ou 21/ago/2026 — as duas tabelas foram criadas inteiras naquele dia.
   Não há evidência de como o processo se comporta ao longo do tempo; se ele
   reconstruir a tabela, a PK deixa de ser estável. A PK entra como
   procedência (`pk_dw`) e a identidade passa a ser a chave natural
   `(nk_instancia, nk_wms_filial, num_gem, nome_estoque, descr_oper_wms,
   nk_cliente)` — **única em 36.300/36.300 e 42.468/42.468** linhas medidas.
   Menos que isso não serve: sem `nk_cliente` sobra 1 duplicata no recebimento
   e 65 na expedição; sem `descr_oper_wms`, 202 e 93.

2. **Identificador com zero à esquerda é texto, nunca número.** `NUM_GEM` vem
   `'0000000001'`, `NK_FILIAL` `'02060862000569'`, `NK_CLIENTE` `'01838723'`,
   `NK_SLIN_EMPRESA`/`FILIAL` `'001'`. Como inteiro perdem o zero e deixam de
   casar com a fonte. Está no contrato e tem teste.

3. **Existem duas datas, e elas divergem** — A-5. `NK_CALENDARIO` (a data do
   calendário do fato) e `DATA_SOLIC` (quando a guia foi solicitada) diferem em
   **11,5%** das linhas do recebimento e em **62,4%** das da expedição. No
   total do mês a diferença é pequena (≤1,2% de jan a jul), mas nas bordas do
   período é grande — dez/2025 tem 1.408,8 t por solicitação contra 133,9 t por
   calendário. Medido contra o `fato.csv`, o **calendário encaixa melhor** na
   expedição: RMSPII jan–jun **−0,32%** por calendário contra **−0,60%** por
   solicitação, e junho **−2,48%** contra **−5,44%**. O artefato usa
   `data_solic`. Isso **não contradiz** a medição anterior do artefato, que
   comparou `DATA_SOLIC` contra `DTHR_CONFIRM`, não contra `NK_CALENDARIO`. O
   schema guarda as duas; qual é o padrão da tela é decisão da Maria.

4. **A regra de tipo de estoque não cobria o vocabulário do DW** — A-6. Dos 40
   nomes distintos de `NOME_ESTOQUE`, **13 não casavam com nenhuma das quatro
   palavras-chave** e caíam em `NAO_CLASSIFICADO`: 3.571 linhas, **10.317,4 t,
   3,2% do peso líquido**.

   A Maria decidiu três coisas em 24/ago/2026, e estão implementadas:

   | decisão | efeito |
   |---|---|
   | `CONG` conta como congelado | `CONG FLV (CUCINARE)`, 350,4 t |
   | `RESFRIADO` é **classe nova** (a quinta) | `RESFRIADO - PR`, 0,6 t |
   | `AGUA / CARVAO` é seco, por de-para de **nome exato** | 5.962,2 t |

   Com isso o não-classificado caiu para **875 linhas, 4.004,1 t, 1,3%**.
   `CONG` foi conferido contra os 40 nomes antes de entrar: pega os 10 de
   congelado e não colide com nenhum outro tipo (`CONSOLIDADOR` tem `CONS`,
   não `CONG`). `AGUA / CARVAO` entrou como nome exato de propósito — `AGUA`
   como palavra-chave pegaria coisa demais.

   **Segue aberto:** `CONSOLIDADOR` e `CONSOLIDADOR - 14025` somam **3.872,5 t**
   — 97% do que restou — e não estavam entre as três perguntas. Os outros oito
   (`RETAIL`, `QUÍM/DESC/LIMP`, `CROSS DOCKING`, `EPI`, `REAJUSTE`, `PAP`,
   `MAQUINARIO`, `AJUSTE DE TARIFA`) somam 131,6 t.

   Nada é classificado por conta própria: a disciplina do projeto é que
   ambiguidade vira sentinela visível, nunca chute silencioso. O comportamento
   está fixado em teste para que mudar seja deliberado.

   Consequência: `catering/dominio/tipo_estoque.py` **divergiu de propósito**
   da regra do V2.2. O `backend/services/tipo_estoque.py` **não** foi alterado
   — ele serve a ingestão do DataHub, que a V3 não usa. As duas não devem mais
   ser comparadas por igualdade.

### Decisões de desenho

- **Dois fatos, não um.** 6 medidas no recebimento contra 16 na expedição; num
  fato único ~10 colunas ficariam eternamente vazias. Espelhar mantém a
  invariante que torna a carga auditável: uma linha aqui é uma linha lá. A
  visão conjunta sai de `UNION ALL` na consulta — não criada aqui porque o
  formato exato é do V3.2.
- **O fato espelha o DW; as dimensões guardam as nossas decisões.**
  `cat_unidades` (sigla exibida, com a exceção RMSPV→RMSPIV), `cat_clientes`
  (razão social canonizada) e `cat_tipos_estoque` (classificação e a regra que
  decidiu). Isso torna todo de-para auditável: dá para mostrar "o DW diz X, a
  tela mostra Y, e a linha que decidiu foi essa".
- **Sem FK do fato para as dimensões**, deliberado. Unidade nova, cliente novo
  ou nome de estoque novo entram sozinhos com o padrão de identidade, em vez de
  derrubar a carga — bloquear exigiria a maquinaria de pendência da V2, que
  existia porque a fonte era planilha suja.
- **Um índice por fato**, `(nk_calendario, nk_wms_filial)`: serve o filtro só
  de período e também período+unidade. Índice que não serve consulta nenhuma
  custa escrita e engana quem lê o schema — mesma disciplina do V2.1.
- **Cadeia de migration continuada** (0019) no **mesmo banco**: a V2 segue
  rodando em produção enquanto a V3 é construída.
- **Regra reaproveitada entra por cópia com teste próprio**, nunca por
  `import` do `backend/`. `tipo_estoque` é a terceira cópia da mesma regra (V2,
  artefato, V3) — o teste é o que impede as três de derivarem em silêncio.

### Arquivos

- `catering/__init__.py`, `catering/contrato.py`
- `catering/dominio/{__init__,tipo_estoque,unidades,clientes}.py`
- `alembic/versions/0019_catering_fato_dw.py`
- `tests/test_catering_dominio.py`, `tests/test_catering_schema.py`

### Suíte

**648 passed, 2 failed** (`python -m pytest -q`, Postgres real em
`localhost:5433`, 8min51). Os 52 testes novos passam; `test_migracao.py` passa
inteiro (28), então a 0019 não quebra a cadeia existente.

**As 2 falhas são pré-existentes, não deste lote** — provado removendo a 0019
do diretório de migrations e reexecutando: falham igual, com `head` na 0018.
São consequência do último commit do repo (`e5805b3`, migration
`0018_corrige_sigla_rmspii`), que passou a exibir 015 e 016 como `RMSPII`
enquanto os dois testes ainda esperam as siglas antigas:

| teste | erro |
|---|---|
| `test_volumetria.py::test_ranking_unidade_declara_quem_ficou_fora_e_por_que` | `KeyError: 'RMSPIII'` |
| `test_volumetria_router.py::test_evolucao_devolve_serie_da_filial` | `assert 'RMSPII' == 'RMSPIV'` |

Não corrigidos aqui: são código da V2 e estão fora do escopo deste lote.
Merecem um lote de correção próprio, autorizado à parte.

### Nota de ambiente

O container `nuvem-teste-db` foi parado pelo Docker Desktop **três vezes** no
meio da suíte (`exit=0`, `oom=false` — parada graciosa, não falta de memória),
produzindo 315 erros de conexão numa rodada inteira que **não eram regressão**.
O que resolveu foi manter a distro WSL ocupada durante a execução:

```
wsl -d Ubuntu-24.04 -e bash -c "for i in \$(seq 1 1800); do \
  docker exec nuvem-teste-db pg_isready -U nuvem -d nuvem_teste > /dev/null 2>&1; sleep 1; done"
```

Com isso a suíte completa sem um único erro de conexão, contra 15min32 e 315
erros sem ele. **O keep-alive tem que ser um processo `wsl.exe` que continue
vivo** — `nohup ... &` de dentro de um `wsl -e bash -c` morre junto com o
`wsl.exe` que o lançou, e nesse caso não protege nada.

Segunda armadilha, descoberta quando o VS Code fechou no meio de uma rodada: a
fixture faz `DROP SCHEMA public CASCADE` e depois `CREATE SCHEMA`. Matar o
pytest entre as duas deixa o banco de teste **sem o schema `public`**, e a
rodada seguinte falha instantaneamente com `InvalidSchemaName` em centenas de
testes — que parece catástrofe e é só isso. Conserto:

```
wsl -d Ubuntu-24.04 -e docker exec nuvem-teste-db psql -U nuvem -d nuvem_teste   -c "CREATE SCHEMA IF NOT EXISTS public; GRANT ALL ON SCHEMA public TO nuvem;"
```

Os dois achados estão em `memory/suite-testes-local.md`.

---

## Lote V3.1 — O carregador (feito, 24/ago/2026)

Autorizado pela Maria em 24/ago/2026. Entregou o pacote `catering/carga/`, a
migration `0020_cat_cargas_fonte` e a suíte própria. **Sem Oracle, sem
agendamento, sem tela, sem login** — e sem tocar em `backend/`, `frontend/`
nem nas migrations antigas.

### A costura, que é o ponto do lote

```text
extrair(movimento, desde)   <- fonte_csv.py     (o ÚNICO que conhece a fonte)
transformar(linha)          <- transformacao.py (não sabe de onde veio)
gravar(cur, lote)           <- destino.py       (não sabe de onde veio)
```

Duas coisas fazem a troca do V3.5 ser adaptador de verdade, e não promessa:

1. **O `desde` já está na assinatura.** No CSV filtra em Python por
   `DW_DATA_ALTERACAO`; no Oracle vira `WHERE`. Se o parâmetro só aparecesse
   no V3.5, a troca mexeria na assinatura de todos e deixaria de ser adaptador.
2. **`extrair()` devolve a linha crua** e a coerção aceita **texto e valor
   nativo** — o CSV entrega `'25290.217'` e o `oracledb` entrega valor
   tipado, e os dois passam pelo mesmo funil.
   **Correção de 25/ago/2026:** este item dizia que o `oracledb` entrega
   `Decimal`. **Entrega `float`.** Medido: `oracledb 4.0.2`,
   `defaults.fetch_decimals = False` por padrão, e `NUMBER` vira `float`
   (ou `int` quando escala 0). Peso em kg com 3 decimais passando por
   ponto flutuante binário perde precisão contra a coluna `NUMERIC` do
   Postgres — então o V3.5 tem que ligar
   `oracledb.defaults.fetch_decimals = True` (ou um output type handler).
   A coerção já aceita os dois, então isto é uma linha de configuração,
   não retrabalho — mas é uma linha que, faltando, corrompe número em
   silêncio. Se a fonte já entregasse tipado, cada
   adaptador teria sua própria cópia da coerção, que é exatamente o que
   afunda a promessa. Há teste passando os dois lados
   (`test_coercao_aceita_texto_e_valor_nativo`).

A `FonteFalsa` da suíte é a segunda prova: ela tem a mesma interface e alimenta
os testes de banco. Se `transformar` ou `gravar` espiassem a fonte, ela não
funcionaria.

### O que rodou de verdade

Carga completa das duas extrações de 21/ago/2026, em Postgres real:

| rodada | resultado |
|---|---|
| 1ª | rec **36.300 inseridas**, exp **42.468 inseridas** — 18s no total |
| 2ª (mesma fonte) | **0 inseridas, 0 atualizadas**, 78.768 iguais, `carga_id` intocado |
| 3ª (`--incremental`) | `sem_dado` nos dois — nada com `dw_data_alteracao` acima da marca d'água |
| dimensões | 6 unidades, 40 nomes de estoque, 14 raízes de cliente (7 com mais de uma grafia) |

### Decisões deste lote

- **Falha derruba a rodada inteira, com rollback** (Maria, 24/ago/2026).
  Rollback é barato aqui: o upsert não apaga nada, então o dado da rodada
  anterior continua no banco e na tela — o custo máximo de uma falha é meio dia
  de frescor. Carga **parcial** custaria um furo silencioso permanente: a
  Matriz mostraria um número quase certo e ninguém saberia quais linhas faltam.
- **Fora de escopo não é malformado.** Instância não-SLIN é outro negócio: é
  pulada, contada e logada, sem derrubar nada. Medido: **zero** linha nessa
  situação nos dois CSVs (as 4 instâncias são SLIN), então a guarda é tripwire.
- **Update só quando o conteúdo mudou** — `DO UPDATE ... WHERE (colunas do
  contrato) IS DISTINCT FROM (EXCLUDED...)`, com a lista gerada de
  `contrato.colunas()`. Update incondicional reescreveria 78 mil linhas por
  rodada e reportaria "36.300 atualizadas" sempre, número que esconde mudança
  real em vez de mostrar.
- **A comparação inclui a procedência** (`pk_dw`, `dw_data_*`). Consequência
  que vale saber de antemão: se o processo do DW **reconstruir** a tabela, a
  `PK_FATO_VOL_*_CAT` muda para toda linha e a rodada reporta tudo como
  atualizado. Isso é o alarme que o `contrato.py` pediu ao registrar que a PK
  do DW não é identidade estável — ignorar a procedência na comparação
  guardaria uma `pk_dw` velha afirmando que nada mudou.
- **`carga_id` = a última rodada que escreveu a linha.** A 0019 tem uma coluna
  só; entre "quem inseriu" e "quem atualizou por último", a segunda responde a
  pergunta da tela: *de quando é esse número?*
- **`linhas_lidas` conta o que entrou na carga** (dentro do escopo), para que
  `lidas − inseridas − atualizadas` continue sendo exatamente as linhas que a
  fonte reapresentou sem mudança. O total que a fonte entregou fica no log.
- **`janela_de`/`janela_ate` ficam NULL na carga por CSV.** A coluna significa
  "o recorte pedido ao Oracle", e no CSV nada foi pedido — preenchê-la com o
  período observado mudaria o sentido da coluna. ~~O V3.5 a preenche.~~
  **Corrigido em 25/ago/2026:** o V3.5 **não** as preenche, e a promessa acima
  estava errada. As duas colunas são `DATE` e a 0019 as descreve como janela de
  data de **negócio** relida; o incremento é por `dw_data_alteracao`, que é
  timestamp de processamento e já está inteiro em `max_dw_data_alteracao`. Ver a
  seção do V3.5.
- **`cat_cargas` é escrito em conexão própria**, para o registro da falha
  sobreviver ao rollback do lote. Rodada que morreu fica no histórico com
  `status='erro'` e a mensagem nomeando linha e coluna.
- **Dimensões recalculadas do banco, não do lote**, uma vez, depois dos dois
  fatos. A canonização do cliente escolhe a razão social pela grafia de maior
  peso: olhando só o delta da rodada, o rótulo trocaria conforme o que veio no
  dia. Não geram linha em `cat_cargas` — os contadores da tabela descrevem
  leitura de fato, e forçar encaixe poluiria o histórico.
- **Nada é apagado nas dimensões.** O DW insere e altera, nunca apaga, então
  desaparecimento significaria erro nosso, e apagar destruiria a evidência.
- **Sem `statement_timeout` na conexão do carregador.** O app web usa 30s
  porque request presa trava tela; interromper carga em lote no meio só
  transforma rodada lenta em rodada perdida. É uma das razões de não reusar o
  pool do app.
- **Número inválido é erro, nunca zero.** O `num()` do loader do artefato
  devolve `0.0` — atalho aceitável em laboratório, inaceitável num carregador,
  porque viraria peso faltando sem ninguém notar.
- **Medida vazia é NULL, nunca zero.** Mantém a guia cancelada distinguível de
  "pesou zero" — é uma das duas limitações que a tela tem que declarar.

### Migration 0020

Uma coluna: `cat_cargas.fonte TEXT NOT NULL DEFAULT 'csv'`, com CHECK
aceitando `csv` e `oracle`. `tabela_origem` diz `FATO_VOL_REC_CAT` tanto vindo
do CSV quanto do Oracle, e a partir do V3.5 as duas coisas convivem no mesmo
histórico — sem a coluna, olhar `cat_cargas` não responde "esse número veio do
banco de verdade ou do CSV que usamos pra construir?". O CHECK já aceita
`oracle`, então o V3.5 não precisa de migration para isso.

### Como rodar

```
python -m catering.carga --de docs/Analise
python -m catering.carga --de docs/Analise --incremental
python -m catering.carga --de docs/Analise --movimento rec
```

Sai com código 1 quando a rodada falha — agendador que não vê falha não serve
de agendador.

### Arquivos

- `catering/carga/{__init__,fonte_csv,transformacao,destino,dimensoes,__main__}.py`
- `alembic/versions/0020_cat_cargas_fonte.py`
- `tests/test_catering_carga.py` (18 testes)

### Nota sobre a suíte: um teste que pula de propósito

`docs/Analise/` é gitignored — dado real de operação não vai pro Git. Então os
três testes que leem as extrações de verdade (`@tem_extracao`) **pulam** onde o
arquivo não existe, dizendo por quê. Falhar por dado ausente transformaria a
suíte em alarme falso na VM e em qualquer outra máquina; os outros 15 testes
não dependem do arquivo e cobrem a lógica inteira com fonte sintética.

### O que este lote NÃO fez

Oracle, agendamento, consulta, Matriz, tela, endpoint, login, deploy. E nada da
V1/V2 foi apagado ou alterado.

---

## Lote V3.2 — Filtros + Matriz (feito, 24/ago/2026)

Autorizado pela Maria em 24/ago/2026. Entregou a agregação, o app próprio da V3
e a tela. **Sem planilha aberta, sem download, sem login, sem Oracle, sem
deploy** — e sem tocar em `backend/` ou `frontend/`.

### App separado, e não router dentro do `backend/main.py`

Decisão da Maria: *"V3 é um projeto totalmente diferente"*. Um router no
`backend/main.py` deixaria `backend/` "intocado exceto uma linha", que não é
intocado. Com app própria (`catering/app.py`, porta 8003 local):

- `backend/` fica intacto de verdade;
- a V3 sobe, cai e faz rollback sem encostar no que serve a operação hoje;
- o desmonte do V3.6 é remover um serviço, não editar código da V2.

O **banco é o mesmo** — as migrations seguem na mesma cadeia. Separar o dado
exigiria segundo Postgres, backup próprio e conciliação entre os dois, sem
ganho. `tests/test_catering_app.py::test_app_da_v3_nao_depende_do_app_da_v2`
confere os **imports** do módulo e falha se alguém importar do `backend/` —
"separado" precisa ser verificável, não prometido.

### A Matriz

```text
entrada:  unidade → cliente → operação
saída:    unidade → cliente → faixa → operação
```

- **Coluna é do tempo; medida que se repete vira linha** — as 3 faixas da saída
  abrem dentro do cliente ("se não fica indo pro lado", 18/ago). Confirmado no
  navegador: sem rolagem horizontal.
- **Cada faixa leva os próprios filhos.** Expandir *Atendido pelo estoque*
  mostra as operações daquela faixa, não as da faixa do botão.
- **O nível de cima mostra a faixa escolhida**, e a tela declara que as três
  **não somam entre si**.
- `operação` é o `descr_oper_wms` (12 valores distintos na entrada, 74% em
  `NÃO TROCA NOTA DE ARMAZENAGEM`). **Leitura do contrato escrito, não do
  artefato** — que já não existe. Por isso `matriz.HIERARQUIA` é tupla
  configurável: trocar o 3º nível é uma linha, não uma reescrita. **Falta a
  Maria confirmar olhando a tela.**
- **Duas matrizes, não uma.** O `V3_PLANO` deixava o formato da visão conjunta
  para este lote; a resposta é que não existe: as hierarquias diferem (a saída
  tem `faixa`) e as medidas não são comparáveis linha a linha.
- Agrega ao vivo. Sem cubo, sem materialização — o índice
  `(nk_calendario, nk_wms_filial)` da 0019 serve exatamente este filtro.

### O aceite

`test_aceite_celula_por_celula_contra_os_csvs` calcula a Matriz **duas vezes por
caminhos independentes** — em Python puro lendo os CSVs, e pelo SQL — e compara
**cada célula**, em 4 combinações (rec/liq, rec/pal, exp/liq, exp/val). O
caminho de Python não importa `matriz.py`, não usa o carregador e reimplementa
o de-para da sigla como dict literal; se compartilhasse, os dois erros seriam o
mesmo erro. Isso substitui o lado a lado com o artefato que se perdeu.

### Defeitos que só o navegador achou

Confirma `memory/validar-tela-no-navegador.md` — lote de tela não fecha por
leitura:

1. **`#corpo` deixava de existir** depois do primeiro desenho, então o segundo
   `carrega()` quebrava com `TypeError` ao trocar de movimento. A referência
   estável é `.rolagem`.
2. **Um byte nulo** tinha entrado como separador de caminho da árvore — o
   arquivo virava binário para `grep` e `file`. Trocado pelo *unit
   separator* (`\u001f`), que não aparece em sigla,
   CNPJ nem descrição de operação — e por isso não pode colidir com chave.
3. Rótulos de tela sem acento (`Peso liquido`, os dois avisos, a trilha de
   níveis na seção de método). `contrato.LENTES[...]["nome"]` é texto de tela e
   passou a ir acentuado, diferente do resto do módulo, que é ASCII por
   convenção de código.

### Decisões de tela

- **Página é número.** Uma linha por elemento; método, procedência, de-para e
  limitações ficam numa seção "Fontes & método" só deles
  (`memory/pagina-mostra-numero-nao-texto.md`).
- **Aviso só quando o caso ocorre.** Pallets na saída mostra coluna vazia com a
  razão; nas outras lentes nenhum aviso aparece.
- **Pallets fica visível e desabilitado** na saída, não escondido: esconder
  faria parecer que a medida não existe, quando ela não existe *ali*.
- **Mês vazio é coluna vazia, não coluna ausente** — coluna que desaparece faz
  as outras deslizarem e a comparação passa a mentir.
- **A tela não soma nada.** Todo total vem do backend, inclusive o de cada nó
  (lição do V2.1). Há teste conferindo que o nó de cima é a soma dos filhos.
- **Número vai como texto no JSON.** Peso e R$ não passam pelo float do
  JavaScript; a conversão kg→t é da tela.
- **Opções de filtro saem do dado**, não de lista fixa: unidade, cliente e
  operação novos aparecem sozinhos.
- **Sem FK, então `LEFT JOIN` com queda para a fonte.** Unidade ou cliente que
  ainda não entrou na dimensão aparece com o rótulo cru — desaparecer em
  silêncio deixaria o número menor sem ninguém ver. Tem teste.

### Como rodar local

```
python -m uvicorn catering.app:app --host 127.0.0.1 --port 8003
```

Porta 8003 para não colidir com a V2 (8002). **Não há serviço no compose ainda,
de propósito:** o app não tem login (V3.4), e criar o serviço agora deixaria uma
tela sem autenticação a um `docker compose up` da VM. O compose é V3.6, depois
do login.

### Arquivos

- `catering/consulta/{__init__,matriz}.py`, `catering/app.py`
- `catering/web/matriz.html`, `catering/web/logo.png`
- `tests/test_catering_matriz.py` (11 testes), `tests/test_catering_app.py` (9)
- `catering/contrato.py`: só o rótulo acentuado da lente

### O que este lote NÃO fez

Planilha aberta e download (V3.3), login (V3.4), Oracle e agendamento (V3.5),
deploy e compose (V3.6). O `CONSOLIDADOR` da A-6 aparece na tela como
`NAO_CLASSIFICADO` até ser decidido.

---

## Lote V3.3 — Planilha aberta, download e auditoria (feito, 24/ago/2026)

Autorizado pela Maria em 24/ago/2026. Entregou a planilha paginada no servidor,
o download do recorte em CSV (streaming) e xlsx (sob teto), e a auditoria de
download. **Sem login** (V3.4), sem Oracle (V3.5), sem deploy (V3.6).

### Uma definição de recorte, não três

O lote começou extraindo `catering/consulta/recorte.py` — filtros, período e o
`WHERE`. A Matriz, a planilha e o download **leem o mesmo `de_para_where()`**.
Se cada uma montasse o seu, o dia em que um filtro mudasse de comportamento numa
e não na outra a tela mostraria um número e baixaria outro, e ninguém
descobriria por um bom tempo, porque os dois parecem plausíveis sozinhos.

A refatoração foi verificada preservando comportamento: os 20 testes do V3.2
passaram sem alteração.

### A planilha

- **100 linhas por página, paginação no servidor** (contrato).
- **Ordenação determinística.** `ORDER BY nk_calendario DESC` sozinho **não**
  basta: em empate o Postgres não promete ordem estável entre execuções, e a
  página 2 poderia repetir linha da 1 e omitir outra **sem erro nenhum**. A
  ordenação termina na chave natural, que é única por construção (V3.0).
- **Estreita na tela, completa no arquivo.** A tela mostra dia, unidade,
  cliente, guia, operação, tipo de estoque e a lente escolhida (na saída, as 3
  faixas dela). As 16 medidas da expedição seriam o "indo pro lado" de novo.
- **A guia aparece aqui**, e não na Matriz: lá seria `COUNT(DISTINCT)` num pivô;
  aqui é coluna de uma linha.

### O download

- **Streaming nos dois lados.** `StreamingResponse` resolve metade; a outra
  metade é o banco — com cursor comum o psycopg2 traz tudo para a memória antes
  de a primeira linha sair, e o "nunca montado em memória" do contrato vira só
  aparência. Usa **cursor nomeado** (server-side) com `itersize`. Consequência
  de desenho: o gerador **é dono da conexão**, porque o corpo dele roda depois
  de a resposta começar, quando um `with` do chamador já teria fechado.
- **Sempre o recorte inteiro.** `pagina` não entra: baixar uma página só não é
  baixar o recorte. Tem teste.
- **A linha inteira, com procedência:** as colunas derivadas (dia, unidade
  exibida, cliente canonizado, tipo de estoque) **e** todas as do contrato,
  cruas — 40 colunas na entrada, 50 na saída. Parece redundante e não é: é o que
  permite conferir "o DW diz `RMSPV`, a tela mostra `RMSPIV`" sem abrir o banco.
- **Formato Excel-first:** `;`, **UTF-8 com BOM**, decimal com vírgula, data
  `DD/MM/AAAA`. Sem o BOM o Excel estraga os acentos no duplo clique — e duplo
  clique é como o arquivo vai ser aberto.

#### O zero à esquerda, que o CSV não consegue proteger

`num_gem` é `0000000609`. O Excel **come o zero à esquerda** ao abrir CSV, e não
há aspas nem truque de CSV que impeça isso de forma confiável — e a política do
projeto proíbe exportação que deforme identificador. A saída honesta:

- o **CSV** leva o valor correto, e a tela avisa, **no próprio controle de
  download**, que o Excel vai truncar identificador no duplo clique;
- o **xlsx** escreve essas colunas como **texto** (`number_format='@'`), e é a
  opção certa quando o que importa é a guia. Verificado: `num_gem` volta como
  `str`, e a medida continua número para o Excel poder somar.

A lista de colunas protegidas sai de `contrato.IDENTIFICADORES_TEXTO`, que existe
desde o V3.0 exatamente por isso — não é lista escrita à mão.

**Teto do xlsx: 150.000 linhas.** xlsx não streama nem em `write_only`. O
período medido hoje tem 78.768 e um ano projeta ~120.000, então cobre um ano com
margem; acima disso a mensagem manda para o CSV, em vez de o servidor morrer sem
explicação.

### A auditoria (migration 0021)

`cat_auditoria (criado_em, terminado_em, evento, usuario, recorte JSONB,
formato, linhas, ip, status, erro)`.

- **Tabela própria, não a `eventos_auditoria` da V2.** A V2 está congelada; o
  dia em que ela sair da VM, a auditoria da V3 sairia junto.
- **`usuario` nulável, e fica nulo neste lote.** Login é o V3.4. Não se inventa
  `'anonimo'`: isso criaria um ator que não existe, e depois ninguém
  distinguiria "antes do login" de "usuário apagado".
- **Registra no início, fecha no fim**, em conexão própria — o mesmo padrão do
  `cat_cargas`, pela mesma razão: o stream pode morrer no meio, e download
  interrompido não pode aparecer como concluído. Tem teste que força a falha e
  confere `status='erro'` com mensagem.
- Verificado com dado real: 4 downloads, recorte exato (`unidades: ["CWBIII"]`,
  `2026-02`), 202 linhas cada, `usuario` nulo.

### Aceite

`test_planilha_somada_bate_com_a_matriz`: somando **todas as páginas** da
planilha, o total dá exatamente o que a Matriz agrega no mesmo recorte — é onde
erro de paginação, de `LIMIT/OFFSET` e de `JOIN` duplicando linha apareceria.
`test_download_bate_com_o_csv_de_origem`: o arquivo baixado somado contra o CSV
do DW, no mesmo recorte.

### Defeito que só o navegador achou

**A coluna do número estava fora da tela.** `Cliente` e `Operação` são largas
(`NÃO TROCA NOTA DE ARMAZENAGEM`) e empurravam a medida para fora do viewport —
numa tela cujo princípio é *mostrar o número*, isso é grave. Duas causas: as
colunas de texto sem teto, e a primeira coluna reusando a classe `.rotulo` da
Matriz, que carrega `min-width: 320px` (dimensionada para nome de cliente com
hierarquia, não para uma data). Corrigido com classe própria da planilha e teto
com reticências nas colunas de texto — o texto inteiro fica no `title`, porque
cortar na tela não pode esconder dado.

### Arquivos

- `catering/consulta/{recorte,planilha,download}.py`, `catering/auditoria.py`
- `alembic/versions/0021_cat_auditoria.py`
- `catering/app.py` (`/api/planilha`, `/api/download`, e `_filtros()` comum aos três)
- `catering/consulta/matriz.py` (passa a ler o recorte compartilhado)
- `catering/web/matriz.html` (visão Matriz/Planilha e os botões de download)
- `tests/test_catering_planilha.py` (12), `tests/test_catering_app.py` (+5)

---

## Lote V3.4 — Login e papéis (feito, 25/ago/2026)

Autorizado pela Maria em 25/ago/2026. Entregou autenticação por pessoa, dois
papéis (`admin` / `visualizador`), auditoria de acesso preenchendo `usuario`, e
uma tela de administração. Sem Oracle (V3.5) e sem deploy (V3.6) — que é a ordem
de propósito: **nada sem autenticação chega à VM**.

### A costura que o contrato exige: papel separado de identidade

O contrato pede "desenhado para o AD entrar depois sem reescrita". Isso não é
organização de código, é o schema:

```text
identidade  -> QUEM você é.     Hoje: senha local. Depois: AD.
papel       -> O QUE você pode. Sempre nosso, sempre no nosso banco.
```

Na `cat_usuarios` (migration 0022) isso aparece como uma decisão concreta:
**`senha_hash` é NULÁVEL**. Uma pessoa do AD tem linha aqui — com papel, nome e
`ativo` — e nenhuma senha local. No dia do AD, `identidade.autenticar()` passa a
consultar o diretório e a autorização não muda uma linha, porque nunca dependeu
de a senha existir.

Se a coluna fosse `NOT NULL`, "AD depois" exigiria migration mais uma senha falsa
por pessoa — e alguém acabaria guardando um hash inútil só para satisfazer a
restrição. O teste `test_usuario_sem_senha_local_tem_papel_mas_nao_entra` fixa
isso: se alguém tornar a coluna obrigatória, ele quebra.

Uma decisão de fronteira que vem junto: **pessoa autenticada no AD sem linha
nossa não entra**. Senão, no dia da virada, o domínio inteiro da SuperFrio
passaria a ter acesso à volumetria de catering.

### O papel vem do banco a cada request, nunca do cookie

O cookie carrega **quem** (login e validade, assinados). O que a pessoa pode é
consultado na `cat_usuarios` em cada request.

Essa é a diferença entre revogar acesso **agora** e revogar acesso "em até 12
horas". Com o papel dentro do cookie — o atalho barato, que economiza uma
consulta — rebaixar um admin ou desativar quem saiu da empresa só faria efeito
quando o cookie expirasse: o crachá continuaria valendo depois do desligamento.

Custa uma consulta curta por request autenticado. Numa ferramenta interna de CSC
isso é barato; se um dia deixar de ser, a resposta é cache com invalidação — e
não mover o papel para dentro do cookie. Dois testes cuidam disso
(`test_papel_vem_do_banco_e_nao_do_cookie`,
`test_desativar_corta_o_acesso_no_request_seguinte`).

### scrypt da stdlib, e nenhuma dependência nova

O `requirements.txt` não tem bcrypt, passlib nem argon2. `hashlib.scrypt` é
stdlib e é **memory-hard** — subir o custo de quebra exige memória, não só CPU,
que é o que derruba ataque em GPU. Medido nesta máquina: **~51 ms** por hash em
n=2^14. Caro para força bruta, imperceptível num login.

O que não serve, e por quê:

- **SHA-256 cru** — rápido de propósito, bilhões de tentativas por segundo;
- **`compare_digest(senha, SENHA_DO_ENV)`**, que é o que a V2 faz — funciona para
  *uma* senha compartilhada, onde não há nada guardado. Com identidade por pessoa
  existe hash guardado, e guardar senha reversível de várias pessoas é uma classe
  de incidente inteira;
- **PBKDF2** — aceitável, mas só CPU-hard.

O valor guardado leva os parâmetros dentro dele
(`scrypt$16384$8$1$<sal>$<hash>`), e não numa constante do módulo: sem isso,
subir o custo no futuro invalidaria toda senha já cadastrada, porque a
verificação usaria um custo diferente do da gravação e **ninguém entraria**.

### O que o login recusa, e o que ele não conta

- **Mensagem e código iguais** para senha errada e login inexistente. Diferenciar
  entregaria *quem tem conta* a quem está adivinhando, sem acertar senha nenhuma.
  O motivo real vai para o log e para a auditoria, que são nossos.
- **Login inexistente também paga um scrypt**, num hash descartável. Sem isso a
  resposta voltaria em ~0 ms para quem não existe e ~51 ms para quem existe com
  senha errada — e essa diferença é um oráculo de enumeração.
- **Freio por login E por IP.** A V2 freava só por IP porque não havia identidade
  por pessoa; o próprio comentário dela registra o custo — o CSC atrás do mesmo
  IP trava inteiro quando uma pessoa erra a senha. Com identidade, a chave certa
  é o **login**: quem erra trava a si mesmo. 5 falhas em 10 min → 10 min. O freio
  por IP fica, mais frouxo (30 em 10 min), para o caso que o outro não pega:
  varredura de logins diferentes da mesma origem. Em memória, como na V2 —
  proporcional a uma ferramenta interna, e não defesa contra atacante
  determinado.

### A auditoria de acesso, sem migration nova

A `cat_auditoria` do V3.3 já tinha `evento IN ('download','login')` e `usuario`
nulável. O V3.4 **só passou a usar**: sucesso vira `status='ok'`, falha vira
`status='erro'` com o motivo, e a tentativa barrada pelo freio também entra —
que é justamente a que interessa ver. A senha nunca entra em coluna nenhuma
(`test_a_senha_nunca_chega_a_auditoria`).

Login grava **numa escrita só** (`registrar_login`), e não no par
`abrir`/`fechar` do download: download é um stream que pode morrer no meio, login
não tem meio. Duas escritas por tentativa custariam duas idas ao banco inclusive
nas erradas, que são as que podem vir em rajada.

O download passou a preencher `usuario` — uma linha, como o V3.3 previu.

### Duas formas de recusar, porque quem recebe é diferente

- rota de **página** (`/`, `/administracao`) sem sessão → **303 para `/login`**.
  Responder 401 numa navegação mostraria `{"detail": ...}` cru no navegador, que é
  o servidor falando com uma pessoa em formato de máquina;
- rota de **API** sem sessão → **401**, que é o que o `fetch` da tela trata
  (redireciona para `/login`);
- visualizador em rota de admin → **403**, e não 401: 401 o mandaria para a tela
  de login, onde ele entraria de novo para ser recusado de novo.

Abertos, por decisão declarada: `/health` (o healthcheck do V3.6 depende, e não
expõe dado), `/logo.png` (a própria tela de login usa) e `/login`.

### A fraqueza que fica declarada: cookie sem `secure`

**A VM serve HTTP puro hoje** (porta 8002, sem TLS). Com `secure=True` o
navegador não devolveria o cookie e o login simplesmente não funcionaria em
produção. Então o padrão é desligado, controlado por `CAT_COOKIE_SECURE`.

Isto é uma fraqueza real, não um detalhe: em HTTP, quem estiver no caminho da
rede lê o cookie de sessão. É aceitável porque a rede é interna e o dado não é
credencial de terceiros, e **fica registrado como pendência** — no dia em que
houver HTTPS, liga a variável. `httponly` e `samesite=lax` ficam ligados sempre,
porque não dependem de TLS.

### O primeiro admin, e a guarda contra ficar sem nenhum

Sistema com login precisa de uma forma de o primeiro acesso existir. As duas
saídas ruins: usuário fixo no código (que vai para o Git e para produção) e
endpoint público de cadastro (que qualquer um usa antes de você).

A saída daqui: no startup, `garantir_primeiro_admin()` cria o admin **só se a
tabela estiver vazia**, lendo `CAT_ADMIN_LOGIN`/`CAT_ADMIN_SENHA` do ambiente.
Com um usuário cadastrado a função não faz nada — então variável esquecida no
`.env` não recria nem sobrescreve ninguém, e trocar o valor depois não muda a
senha de quem existe.

No outro extremo, `usuarios.UltimoAdmin` recusa a alteração que deixaria o
sistema **sem nenhum admin ativo**. O modo de falha que isso impede é definitivo:
o único admin se desativa por engano e ninguém mais cadastra usuário nem lê
auditoria. São três caminhos para o mesmo buraco, e os três estão fechados:
rebaixar, desativar e **remover a senha local** — o terceiro tranca igual
enquanto não existe AD, porque a pessoa mantém o papel e deixa de ter qualquer
forma de entrar. A guarda vive em `usuarios.py`, e não no `app.py`, para valer também
para o CLI — e não fecha a saída de recuperação, porque criar outro admin antes
continua funcionando.

### Chave de sessão própria, e lida no uso

`CAT_SECRET_KEY`, e não a `SECRET_KEY` da V2: chave compartilhada significa que
um vazamento da V2 (congelada, e um dia removida da VM) passaria a permitir
forjar sessão da V3.

Ela é lida **no uso**, não no import. Com erro no import o app não subiria, o
`/health` morreria junto e o sintoma chegaria como "container não fica de pé",
sem dizer o que falta. Com erro no uso o `/health` responde e o erro no log nomeia
a variável ausente (`test_sem_chave_o_health_continua_de_pe`).

### Variáveis de ambiente novas

| variável | para quê | obrigatória |
|---|---|---|
| `CAT_SECRET_KEY` | assina o cookie de sessão da V3 | **sim** |
| `CAT_COOKIE_SECURE` | `1` só quando houver HTTPS (ver acima) | não (padrão `0`) |
| `CAT_ADMIN_LOGIN` / `CAT_ADMIN_SENHA` | primeiro admin, se a tabela estiver vazia | não |
| `CAT_ADMIN_NOME` | nome de exibição do primeiro admin | não |

Vão no `.env` (gitignored) — **nunca no chat, nunca em commit**.

### CLI de recuperação

```
python -m catering.seguranca listar
python -m catering.seguranca criar --login joao.silva --nome "João" --papel visualizador
python -m catering.seguranca criar --login do.ad --nome "Do AD" --papel admin --sem-senha
python -m catering.seguranca senha --login joao.silva
python -m catering.seguranca papel --login joao.silva --papel admin
python -m catering.seguranca desativar --login joao.silva
```

A senha vem por `getpass`, e **não existe flag para passá-la na linha de
comando**: iria para o histórico do shell, para o `ps` de quem estiver na máquina
e para qualquer terminal gravado.

### A tela

`/login` (marca, sem barra de filtros) e `/administracao` (usuários + últimas
linhas da auditoria, só admin). O cabeçalho da Matriz passou a mostrar quem está
logado, o papel, o botão de sair, e o link da administração **só para admin** —
visualizador que clicasse seria devolvido pelo próprio servidor.

A rota da tela de administração é `/administracao`, e não `/admin`: `/admin` é
rota da V2, e `test_app_da_v3_nao_depende_do_app_da_v2` proíbe rota da V2 dentro
deste app. Renomear manteve a guarda intacta em vez de afrouxá-la.

### Defeitos que só o navegador achou

A regra do projeto — lote com tela não fecha por leitura — pagou três vezes aqui.
Nenhum dos três apareceria na suíte como ela estava, porque os três são
comportamento do navegador, não do servidor.

**1. Página atrás de sessão servida do cache.** Depois de sair de um admin e
entrar como visualizador, `GET /administracao` **não chegou ao servidor** — o
`FileResponse` manda `ETag`/`Last-Modified`, o Chrome devolveu o HTML guardado, e
o desvio para a Matriz nunca teve chance de rodar. Não houve vazamento de dado
(as APIs responderam 403 e as tabelas ficaram vazias), mas a tela errada abrir é
defeito por si — e num computador compartilhado a página do colega voltaria pelo
botão de voltar.

Correção: `Cache-Control: no-store` nas páginas protegidas (`_pagina()` no
`app.py`). O `/logo.png` continua cacheável de propósito — é estático, público, e
são 147 KB em toda navegação. Fixado em
`test_pagina_atras_de_sessao_nao_pode_ficar_no_cache`.

Detalhe honesto da verificação: depois da correção, o navegador **continuou**
mostrando a tela antiga — `no-store` impede guardar, não apaga o que já estava
guardado. A prova de que a correção funciona veio de uma URL sem entrada no
cache: duas navegações seguidas, as duas chegando ao servidor com 303 para a
Matriz.

**2. Campo de senha ilegível com autofill.** No primeiro carregamento da tela de
login, com senha salva no Chrome, o campo preenchido pelo autofill virou
**branco** — e o texto branco da tela escura ficou ilegível. O navegador sobrepõe
o `background` com um estilo interno que só `-webkit-box-shadow` inset cobre.
Corrigido no `login.html`. Ressalva honesta: a correção segue o padrão conhecido
para `:-webkit-autofill`, mas **não foi reproduzida no Playwright** — o autofill
depende da senha salva no perfil do Chrome, e o teste automatizado digita o
campo, então nunca dispara a pseudo-classe.

**3. 403 caindo como `TypeError`.** O `busca()` da tela de administração só
tratava 401. Quando o papel muda com a tela aberta, o 403 chegava como
`TypeError: lista is not iterable` — que manda quem está depurando olhar o JSON
em vez da autorização. Agora 403 devolve a pessoa para a Matriz, o mesmo desvio
que o servidor faz numa navegação.

O fluxo do rebaixamento foi exercitado no navegador de ponta a ponta: com a tela
de admin aberta, o papel foi trocado no banco e o clique seguinte já foi recusado
— o cabeçalho passou a dizer VISUALIZADOR e o link de Administração desapareceu,
com o **mesmo cookie**.

### Aceite

`python -m pytest tests/test_catering_*.py tests/test_migracao.py` — **188
passando** (25/ago/2026), dos quais 53 são o `test_catering_seguranca.py` novo.
Suíte completa: **754 passando + 2 xfailed** (os dois conhecidos da V2), 13min29.

Três testes são afirmação de contrato, e não detalhe de implementação:

1. `test_usuario_sem_senha_local_tem_papel_mas_nao_entra` — a costura do AD;
2. `test_papel_vem_do_banco_e_nao_do_cookie` — revogação vale no request seguinte;
3. `test_recusa_nao_distingue_login_inexistente_de_senha_errada` — sem oráculo de
   enumeração.

A `cliente_v3` de `test_catering_app.py` passou a entrar logada como admin. A
exigência de sessão em si ficou no arquivo novo, de propósito: se a autenticação
quebrar, o sinal tem que chegar como falha de segurança, e não como catorze
falhas de Matriz apontando para o lugar errado.

### Arquivos

- `alembic/versions/0022_cat_usuarios.py`
- `catering/seguranca/{__init__,__main__,senha,usuarios,identidade,sessao}.py`
- `catering/auditoria.py` (`registrar_login`)
- `catering/app.py` (`/login`, `/logout`, `/api/eu`, `/api/usuarios`,
  `/api/auditoria`, `/administracao`, e `Depends(exigir_login)` nas rotas de dado)
- `catering/web/login.html`, `catering/web/administracao.html`,
  `catering/web/matriz.html` (cabeçalho de sessão e desvio de 401)
- `tests/test_catering_seguranca.py` (53), `tests/test_catering_app.py` (fixture
  autenticada), `tests/conftest.py` (`CAT_SECRET_KEY`)

### O que este lote NÃO fez

- **AD de verdade** — só o desenho que o permite (`senha_hash` nulável e a
  autenticação isolada em um módulo).
- **HTTPS**, e por isso o cookie vai sem `secure`. Declarado acima.
- **Expirar sessão na troca de senha.** Quem já está logado continua logado
  depois de um reset; a alavanca que corta acesso na hora é `ativo = false`, que
  é a que importa operacionalmente.
- **Persistir o freio de tentativas** — ele mora em memória e zera num restart do
  container, como na V2.
- Oracle (V3.5), deploy (V3.6).

---

## Lote V3.5 — A fonte passa a ser o Oracle (feito, 25/ago/2026)

Autorizado pela Maria em 25/ago/2026. Entregou `catering/carga/fonte_oracle.py`,
o comando de carga sob demanda, o `--sondar` e o script do agendamento **pronto e
desligado**. Começou **sem migration** — o CHECK da 0020 já aceitava `fonte='oracle'` desde
o V3.1 — e ganhou uma, a **0023**, quando a primeira carga real derrubou a chave
natural. Essa é a história do lote, e está contada abaixo.

**Limite que definiu o lote: a IA não conectou no DW.** O DW é produção, e a
política do projeto é que a IA não conecta nele. Todo o código foi escrito e
testado contra driver falso; a leitura real é a rodada que a Maria executa, e a
saída dela é o aceite (abaixo).

### O adaptador cobrou a promessa do V3.1

```text
extrair(movimento, desde)   <- fonte_csv.py  |  fonte_oracle.py
transformar(linha)          <- NÃO mudou uma linha
gravar(cur, lote)           <- NÃO mudou uma linha
```

O que o V3.1 pagou adiantado se provou certo: o `desde` já estar na assinatura, e
a coerção aceitar texto **e** valor nativo. O carregador (`carga/__init__.py`) só
ganhou uma guarda nova (carga vazia, abaixo) — nada mais nele soube que a fonte
mudou.

### O nome do objeto, e a marca d'água invalidada de propósito

`contrato.TABELA_REC/EXP` passaram a levar o nome qualificado
(`DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`), e o nome vive em `contrato.tabela()`, que
lê `DW_TABELA_REC`/`DW_TABELA_EXP` do ambiente. A A-7 diz que fica só a `_V01` e
não há outra versão programada — mas "não programada" é ausência de plano, não
garantia, e a `FATO_VOLUMETRIA` do mesmo schema já está em `_V04`. Trocar de
versão é uma variável de ambiente, não um commit.

Como `tabela_origem` é a **chave da marca d'água**, mudar o nome invalida a marca
d'água das rodadas por CSV: a primeira rodada contra o Oracle é completa. Era o
esperado e foi autorizado — hoje custa uma rodada, depois do V3.6 custaria carga
cheia em produção.

`destino.TABELA_ORIGEM` virou a função `destino.tabela_origem()` pelo mesmo
motivo: dicionário montado no import congelaria o valor de quando o módulo foi
carregado, e uma carga gravando um nome com o incremento seguinte procurando
outro é recarga completa silenciosa em toda rodada.

### A armadilha que o lote desarmou: a PK derivava do nome da tabela

`RENOMEADAS` montava o nome da coluna da PK como `"PK_" + TABELA_REC`. Isso
funcionava **só enquanto os dois andavam juntos**. Com a tabela qualificada,
produziria `PK_DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`, que não existe: a tabela
ganhou schema e sufixo de versão, a coluna não. Agora é constante medida
(`contrato.PK_DW`), e o teste que já existia no `test_catering_dominio.py` virou
a trava — ele reprovaria a concatenação sem ninguém precisar lembrar do risco.

### `fetch_decimals`, a linha que corrompe número em silêncio

Medido: `oracledb 4.0.2` traz `defaults.fetch_decimals = False`, e com isso todo
`NUMBER` chega como **float**. Peso em kg com 3 decimais passando por ponto
flutuante binário não volta a ser o que era contra a coluna `NUMERIC(18,3)`.

A opção é ligada dentro de `conectar()`, **não no import**: efeito de import
mudaria o comportamento global do driver para quem só importou o módulo. A
alternativa considerada foi um `outputtypehandler` por conexão, mais cirúrgico —
ficou de fora porque ele decide coluna por coluna, e coluna nova cair no ramo
errado é exatamente o silêncio que se está tentando evitar.

### Duas consultas por movimento, e o motivo de cada uma

| consulta | para quê |
|---|---|
| `SELECT * FROM <tabela> WHERE 1=0` | o `description` do cursor passa pela **mesma** `conferir_colunas()` que o CSV usa. É o que enxerga coluna **nova** no DW — a lista explícita passaria por cima dela em silêncio. Não lê bloco nenhum |
| `SELECT <colunas do contrato> FROM <tabela> [WHERE DW_DATA_ALTERACAO > :desde]` | o dado. Lista explícita, gerada de `contrato.colunas()`: coluna removida ou renomeada dá `ORA-00904` **nomeando a coluna**, no primeiro `execute`, em vez de erro de tipo trinta mil linhas adiante |

O `desde` vai por **bind**, nunca concatenado. E não há teto do outro lado: o
Oracle dá consistência de leitura no nível do statement, e a marca d'água da
rodada é o `max` do que efetivamente entrou — então linha que chegue durante a
leitura entra na rodada seguinte, sem furo. Um teto com o relógio da nossa
máquina compraria diferença de relógio contra o do DW sem resolver nada.

### `janela_de`/`janela_ate` ficam nulas — a nota do V3.1 estava errada

O V3.1 registrou que "o V3.5 as preenche". Ao implementar, as duas colunas se
mostraram **DATE**, e a 0019 as descreve como a janela de **data de negócio**
relida. O incremento daqui é por `dw_data_alteracao`, que é timestamp de
processamento e já está inteiro em `max_dw_data_alteracao`. Preenchê-las com a
data truncada do `desde` misturaria dois sentidos na mesma coluna, e truncando.
O `desde` de uma rodada é exatamente o `max_dw_data_alteracao` da rodada `ok`
anterior, então nada se perde em auditoria. A alternativa — migration mudando as
duas para TIMESTAMP — não responderia nada que a coluna existente não responda.

### Carga completa que lê zero linha é `erro`, não `sem_dado`

A A-7 pede que a carga nunca reporte desfecho normal com zero linha, e esta é a
implementação. `sem_dado` continua **certo** no incremental (nada mudou no DW
desde a marca d'água) e passou a ser **errado** numa carga completa, onde
significa a fonte inteira vindo vazia — com a tela seguindo em frente com o dado
velho e ninguém avisado.

Tabela ausente já derrubava sozinha (`ORA-00942`). O que a guarda cobre é o caso
pior, que a sondagem tornou concreto: a tabela **existe** e vem vazia, porque
aquele time versiona e reconstrói objeto. Custa nada — rollback de rodada vazia
não desfaz nada, e o upsert nunca apaga.

As duas causas produzem mensagens diferentes de propósito: "a fonte não devolveu
linha nenhuma" é problema no DW ou no acesso; "todas fora do escopo do catering"
é a instância ter mudado, que é problema de negócio. Um teste existente mudou de
expectativa por causa disso — o que era um teste só virou dois, um por caso.

### A carga real derrubou a chave natural — e a 0023 é a resposta

**Isto é o achado central do lote, e ele veio da rodada da Maria, não da suíte.**
O `--sondar` passou em tudo; a carga recusou:

```
ON CONFLICT DO UPDATE command cannot affect row a second time
```

O que aconteceu no DW entre 24 e 25/ago, medido às 16h31:

| | 25/ago 09h (sondagem 2) | 25/ago 16h (primeira carga) |
|---|---|---|
| recebimento | 36.592 linhas, desde jan/2026 | **201.848**, desde **02/jan/2023** |
| expedição | 42.789 linhas, desde dez/2025 | **231.886**, desde **02/jan/2023** |
| `dw_data_alteracao` mínimo | 20/ago 15:26 | **25/ago 10:31** — toda linha reescrita |

O DW **reconstruiu as duas tabelas com 3,6 anos de histórico**. O V3.0 tinha
registrado isso como hipótese ("se um dia o DW recriar a tabela"); aconteceu um
dia depois de a hipótese ser escrita.

E com o histórico veio o defeito real: **`num_gem` se recicla por ano.** As
colisões aparecem **4x** — 2023, 2024, 2025, 2026 — e em datas próximas dentro
do ano (gem `0000000020` em 03/jan/2023 e 05/jan/2026). A chave natural de seis
colunas repetia em **27.834 de 201.848** linhas no recebimento (13,8%) e
**44.187 de 231.886** na expedição (19,1%).

**A falha foi de raciocínio, não de código.** A chave foi medida única em
36.300/36.300 e 42.468/42.468 linhas — e essas linhas eram de **um ano só**.
Generalizar unicidade de uma amostra de um ano para a série inteira é o erro, e
ele vale escrever com essas palavras porque é do tipo que se repete. O que
funcionou foi a disciplina em volta: o upsert **recusou alto**, com rollback,
em vez de duplicar em silêncio — exatamente o que o V3.0 desenhou ao registrar
que a PK do DW não serve de identidade.

#### Por que `ano_solic`, e não uma das duas datas

Quatro candidatos ficaram únicos. Três medições escolheram entre eles:

| candidato | recebimento | expedição |
|---|---|---|
| chave de hoje (6 colunas) | repete em 27.834 | repete em 44.187 |
| **+ `ano_solic`** | **única** | **única** |
| + ano de `data_solic` | única | única |
| + ano de `nk_calendario` | **repete em 12** | **repete em 79** |
| + `data_solic` | única | única |
| + `nk_calendario` | única | única |

1. **O espaço de numeração é o ano do PEDIDO, não o do movimento.** É o que as
   12 e 79 linhas provam: são as viradas de ano — guia pedida em dezembro e
   movimentada em janeiro pertence à sequência do ano anterior.
2. **A identidade certa é a mais GROSSA que ainda seja única**, porque
   identidade fina transforma correção em `INSERT` duplicado: qualquer conserto
   na coluna extra deixa de ser update e a linha antiga sobrevive ao lado.
   `ano_solic` (SMALLINT) é a mais grossa das quatro.
3. **`data_solic` tem lixo, e `ano_solic` não.** Nas 16 linhas da expedição em
   que as duas discordam, `data_solic` traz **2105-04-29**, `2002-04-29` e
   `2005-05-07`, com `nk_calendario` são em 2024/2025 — quem está errada é a
   data. No recebimento são 15 linhas do caso benigno (`ano_solic` 2025 com
   `data_solic` em 04/jan/2026, virada de ano).

O item 3 é o que fecha a decisão, e não é preferência estética: **existe defeito
visível na fonte que alguém vai corrigir um dia.** Com `data_solic` na chave,
corrigir `2105` → `2025` mudaria a identidade da linha e duplicaria o número em
silêncio. Com `ano_solic` na chave, a mesma correção é um `UPDATE`.

A identidade passou a ser, na migration **0023**:

```
(nk_instancia, nk_wms_filial, num_gem, ano_solic, nome_estoque,
 descr_oper_wms, nk_cliente)
```

`ano_solic` fica depois do `num_gem` porque qualifica o número da guia — a chave
se lê como *"o GEM é único dentro do ano do pedido"*.

**O upsert não precisou de uma linha de mudança**: ele é gerado de
`contrato.CHAVE_NATURAL`, então acrescentar a coluna ao contrato bastou, e
`ano_solic` saiu do `SET` sozinho. É o desenho do V3.1 pagando de novo.

**A 0023 descobre o nome da restrição no catálogo** em vez de escrevê-lo: a 0019
criou o `UNIQUE` sem nome, e o nome que o Postgres gerou foi truncado em 63
caracteres — e ficou **diferente** nas duas tabelas (`..._num_gem_nome__key` e
`..._num_gem_nom_key`), porque a truncagem depende do tamanho do nome da tabela.
A restrição nova é nomeada, para a próxima migration não repetir esse trabalho.
O `downgrade` volta para seis colunas e **falha de propósito** num banco que já
tenha mais de um ano de histórico — a alternativa seria apagar linha para o
passado caber.

#### Um furo do alarme, achado ao escrever o teste da regressão

O `ON CONFLICT` só grita quando as duas linhas do lote **realmente escrevem** na
mesma linha. O `WHERE ... IS DISTINCT FROM` — que existe para
`linhas_atualizadas` significar o que diz — faz uma linha idêntica à do banco
não afetar nada, e aí a companheira divergente escreve sozinha, **sem alarme**, e
vence.

Para o furo aparecer é preciso a conjunção: a fonte publicar a mesma chave duas
vezes com conteúdo diferente **e** uma das duas ser byte a byte igual ao
gravado, `pk_dw` e `dw_data_alteracao` inclusive — ou seja, só com linha que o DW
não tocou desde a nossa última carga.

**Não foi fechado**, e o motivo é custo: fechar exige guardar a chave de cada
linha da rodada em memória (uma página não basta — a repetição pode cair entre
páginas), ~80 MB para 232 mil linhas, ou trocar por hash e aceitar alarme falso.
O estado que sobra é defensável (a linha divergente vence, nenhuma medida se
perde). Fica **fixado em teste**
(`test_o_alarme_de_chave_repetida_tem_um_furo_conhecido`), porque alarme em que
se confia sem saber onde ele não alcança é pior que alarme com limite escrito.

#### O que mais isto muda, e que não é defeito

- **O volume da V3 mudou de escala:** ~434 mil linhas em vez de ~79 mil, e a
  tela passa a mostrar 2023–2026. Segue pequeno para Postgres, e a projeção de
  ~120 mil/ano do contrato estava certa — errada era a profundidade do
  histórico. O aceite célula por célula do V3.2 não fica inválido, fica
  **parcial**: ele cobriu 2026.
- **O rebuild deixou de ser hipótese**, com uma consequência concreta para o
  V3.6: a rodada das 07h05 pode, sem aviso, ter que carregar 434 mil linhas em
  vez de 10 mil.
- **`data_solic` tem data impossível em 16 linhas** (ano 2105, 2002, 2005). Não
  é corrigido nem classificado por conta própria — a disciplina do projeto é que
  ambiguidade vira sentinela visível, nunca chute silencioso. Fica registrado
  aqui, e a Matriz não é afetada porque ela agrega por `nk_calendario` (A-5).
  **Decisão aberta:** se a planilha e o download devem declarar essas linhas.

### A 0023 validada nas duas direções (26/ago/2026)

A regra de trabalho manda validar migration no upgrade **e** no downgrade, e a
0023 é incomum porque o downgrade dela foi escrito para **falhar de propósito**
quando existe mais de um ano de histórico. Isso não tinha teste nem validação
manual; foi exercitado no fechamento do lote, no `nuvem_teste`:

| passo | resultado |
|---|---|
| banco vazio, `downgrade 0022` | cria `uq_cat_fato_rec_identidade_antiga` com **6 colunas**, sem `ano_solic` |
| `upgrade head` | volta para `uq_cat_fato_rec_identidade` com as **7 colunas** |
| duas linhas, mesmo `num_gem`, `ano_solic` 2025 e 2026, `downgrade 0022` | **`UniqueViolation`** — `could not create unique index` |

O terceiro passo é o que importava, e o desfecho é melhor do que o docstring
prometia: além de recusar, **a transação inteira voltou atrás**. A revisão ficou
em `0023`, a restrição de sete colunas continuou no lugar e as duas linhas
continuaram lá. A tabela não passou por nenhum instante sem identidade — o
`DROP` da antiga e o `CREATE` da nova estão na mesma transação, então o
`_trocar()` é atômico. Falhar aqui é o comportamento certo: a alternativa seria
apagar linha do usuário para a chave antiga caber.

O **upgrade** já era coberto indiretamente, e continua: o
`tests/test_catering_schema.py` afirma que o UNIQUE de cada tabela de fato é
exatamente `contrato.CHAVE_NATURAL`, então mudar a chave no contrato sem
migration (ou o contrário) deixa a suíte vermelha.

### O escopo continua sendo filtrado em Python

Não existe `WHERE NK_INSTANCIA LIKE 'SLIN_%'` no SQL, de propósito. O V3.1 conta
e loga linha fora de escopo como tripwire (medido: zero linha nos dois CSVs).
Empurrar o filtro para o banco economizaria tráfego de linha que ninguém tem, ao
preço de nunca mais saber que instância nova apareceu.

### O piso de período: a V3 lê de 2026 para frente

**Decisão da Maria, 25/ago/2026**, depois de ver a reconstrução: *"o certo é a
gente só pegar de 2026 pra frente"*. Isso corrige uma linha do contrato fechado
— "são tabelas inteiras, sem filtro de extração" valeu enquanto a fonte só tinha
o ano corrente.

| | antes do piso | com o piso |
|---|---|---|
| recebimento | 201.848 linhas, desde 02/jan/2023 | o que houver de 2026 em diante |
| expedição | 231.886 linhas, desde 02/jan/2023 | idem |
| CSVs de 21/ago (medido) | 36.300 e 42.468 | **36.300 e 42.318** |

As 150 linhas que a expedição perde são **dez/2025** — 128,7 t solicitadas. O
recebimento não tem nenhuma linha anterior a 2026, então ele não muda. Está
fixado em teste contra o arquivo de verdade, porque é o número que denuncia um
piso mexido sem querer.

**Corta por `nk_calendario`**, a data do movimento — a mesma que a Matriz agrega
(A-5). Guia pedida em dez/2025 e movimentada em jan/2026 **entra**, porque ela
conta em 2026.

**Fica em configuração** (`DW_ANO_MINIMO`, padrão 2026) porque a própria Maria
nomeou o caso de uso ao decidir: *"de acordo, se quiser comparar 2025-2026"*.
Trocar para 2025 é uma variável de ambiente — sem commit, sem migration. O valor
é validado (2000..2100): `26`, `20226` ou `2o26` falham nomeando a variável, em
vez de virar "carrega tudo" ou "carrega nada" em silêncio.

**No SQL, e não em Python.** Aqui a decisão é oposta à do filtro de instância
SLIN, e por um motivo concreto: instância fora de escopo é **tripwire** (queremos
contar e logar se aparecer), período fora da janela é recorte conhecido. Trazer
5x mais linha duas vezes por dia para descartar em Python seria desperdício —
foi exatamente o que a reconstrução tornou palpável.

**A `FonteCSV` aplica o mesmo piso**, ainda que os CSVs sejam 2026. Se as duas
fontes recortassem diferente, comparar uma com a outra deixaria de provar
qualquer coisa.

**A medição de identidade também respeita a janela.** Sem isso, o `--sondar`
acusaria as 27.834 colisões de 2023–2025 num recorte que não lê 2023 — alarme
sobre dado que não entra. Quem quiser saber se a chave aguenta um período maior
baixa o `DW_ANO_MINIMO` e roda o sondar de novo, que é o fluxo certo **antes** de
ampliar a janela.

**O `--sondar` passou a mostrar os dois números** — o que a tabela tem e o que a
janela lê. Sai da mesma varredura, e é o que impede alguém de concluir que o DW
está faltando dado quando o recorte é nosso.

Três consequências que valem estar escritas:

1. **Baixar o piso carrega o passado; subir o piso não apaga nada.** A carga só
   insere e atualiza (decisão do V3.1), então linha que já entrou fica. Voltar
   atrás de um piso mais baixo exige `DELETE` à mão, deliberado.
2. **A 0023 continua necessária.** Com dado só de 2026 a chave de seis colunas
   voltaria a funcionar *hoje* e quebraria em **janeiro de 2027**, quando o GEM
   reiniciar e 2026 e 2027 conviverem na mesma tabela. A reciclagem é fato da
   fonte, não do filtro.
3. **O aceite do V3.2 volta a valer inteiro** — ele foi conferido célula por
   célula contra 2026, que passou a ser exatamente o que a tela mostra. E as 16
   linhas com `data_solic` impossível (2105, 2002, 2005) têm movimento em
   2024/2025: **saem com o piso**. Sobra só o caso benigno de virada de ano no
   recebimento.

### Somente leitura, provado de duas formas

Mesmo par do cliente do Graph, pelo mesmo motivo:

- **estática**, sobre a árvore sintática: nenhum literal do módulo contém palavra
  de escrita (docstring é ignorada — ela fala de escrita para explicar por que
  não há), e nenhuma chamada a `commit`/`rollback`/`executemany`. Pega o código
  que nenhum teste exercitou;
- **de runtime**: o cursor falso recusa qualquer comando que não comece por
  `SELECT`, e os dois caminhos que emitem SQL são exercitados. Pega o comando
  montado por concatenação, que a estática não veria.

### Agendamento: construído, e desligado

`scripts/carga_catering.sh` está pronto e **não está no crontab de ninguém**.

- **`docker compose run --rm`, e não `exec`**: a carga não depende do processo web
  estar saudável. Com `exec`, uma rodada morreria porque a *tela* está fora do
  ar, que é outro problema;
- **`flock` sem espera**: se uma rodada atrasar além da próxima, a nova desiste e
  registra "PULADA" em vez de duas cargas concorrentes disputarem o upsert;
- **falha alto quando o serviço do compose não existe** — que é o caso **hoje**: a
  imagem atual não copia `catering/`, e o serviço da V3 é do V3.6. A mensagem
  lista os serviços que existem, porque numa VM com quatro projetos a mensagem
  crua do Compose manda quem estiver de plantão para o lugar errado;
- **o código de saída sobe**: agendador que não vê falha não serve de agendador.

Duas coisas que só o V3.6 fecha, e estão escritas no `DEPLOY.md`: o **nome do
serviço** e o **fuso da VM** — se ela estiver em UTC, `5 7 * * *` é 04h05 local,
antes da rodada de 06h35 do DW, e a carga leria sempre a véspera.

### Três coisas achadas no fechamento — duas feitas no V3.5.1, uma aberta

Decisão da Maria, 26/ago/2026: fechar o V3.5 com a troca de fonte provada e não
abrir código novo antes do deploy. **Horas depois a decisão foi revista para as
duas primeiras**, que viraram o lote V3.5.1 (branch `v3.5.1-fuso`, seção
própria abaixo) — o gatilho foi perceber que a decisão de fuso já estava tomada,
e decisão tomada que não é escrita volta a ser discutida. A terceira segue
aberta.

O diagnóstico abaixo é o que estava escrito **antes** do conserto, e fica como
registro do que foi medido.

**1. O fuso não fica só no cron — ele vaza para a tela.** Medido no fechamento: a
carga terminou às **09h45** no relógio da máquina e o rodapé "De quando é o dado"
mostra **12h45**, quase três horas no futuro. A causa não é o dado: `terminada_em`
é `timestamptz` e grava UTC corretamente; ninguém converte na hora de exibir, e a
sessão do Postgres está em `Etc/UTC`. São dois pontos:

| onde | linha | o que mostra errado |
|---|---|---|
| rodapé de procedência da Matriz | `catering/app.py:262` | a hora da última carga |
| coluna "quando" da auditoria, em `/administracao` | `catering/app.py:476` | a hora de cada acesso e download |

O segundo é o que incomoda de verdade: **auditoria com hora errada é problema de
rastreabilidade**, não de estética — é o registro que se consulta quando alguém
pergunta quem baixou o quê e quando. `max_dw_data_alteracao` **não** entra nessa
lista: ela é `timestamp without time zone` de propósito, porque é o relógio do DW.

O conserto é `AT TIME ZONE` nos dois `to_char`, com teste. A alternativa mais
correta a longo prazo é mandar ISO-8601 para o front e formatar no fuso do
navegador — melhor se um dia houver operação fora do Brasil, e mais mudança do
que o momento pede. **Fica junto do fuso do cron porque é a mesma decisão de
fundo** (qual é o fuso de referência do sistema), e resolver separado é convidar
a segunda correção a desfazer a primeira.

**2. `DATABASE_URL` ausente falha com uma mensagem que não ajuda.** Ela sai como
`carga falhou: 'DATABASE_URL'` — um `KeyError` cru vazando pelo tratamento
genérico do `__main__`. A ausência da credencial do DW é tratada bem
(`CredencialAusente`, nomeando as duas variáveis); a do Postgres não. Custou dois
tropeços reais no fechamento deste lote, no mesmo lugar.

**3. Ajuste visual da tela.** Nada específico foi levantado na validação de
26/ago. Fica depois do deploy por decisão de risco: mexer na tela agora adiciona
risco ao único caminho já provado ponta a ponta.

### Como rodar

```
python -m catering.carga --de docs/Analise                  # CSV, igual antes
python -m catering.carga --fonte oracle --sondar            # SÓ lê o DW
python -m catering.carga --fonte oracle                     # carga completa
python -m catering.carga --fonte oracle --incremental       # o que o cron roda
```

`--fonte` tem padrão `csv` para que todo comando já documentado continue valendo
como está escrito. `--de` e `--fonte oracle` são mutuamente exclusivos, e
`--sondar` não toca no Postgres — então ele não precisa de `DATABASE_URL` e serve
como primeira prova de acesso numa máquina onde o banco local ainda não existe.

### Aceite

A suíte prova o **statement**, os binds, a conferência de contrato e a coerção de
valor nativo. Ela não prova — e está escrito no próprio arquivo de teste — que o
Oracle honra o `>`, que os nomes reais das colunas são os do contrato, e que o
volume é o esperado. Essas três são a rodada da Maria:

```
python -m catering.carga --fonte oracle --sondar
python -m catering.carga --fonte oracle
python -m catering.carga --fonte oracle
python -m catering.carga --fonte oracle --incremental
```

O que cada uma responde: a 1ª, sessão + GRANT + contrato coluna por coluna +
volume + o tipo que chega; a 2ª, a carga de verdade; a 3ª, idempotência
(`0 inserida, 0 atualizada`, ou o que o DW mexeu no meio, que também é resposta
certa); a 4ª, `sem_dado` ou poucas linhas.

**Executado pela Maria em 25/ago/2026, e o resultado dividiu o aceite em dois.**

**O que a rodada PROVOU (a leitura está fechada):**

| pergunta | resposta da rodada real |
|---|---|
| a sessão abre em modo thin, sem Instant Client | sim, contra o `pdwgener` |
| o GRANT vale | sim — leu as duas tabelas inteiras |
| o contrato bate | **36 e 46 colunas, sem divergência**, conferidas contra o que o cursor descreve |
| o nome da coluna da PK | `PK_FATO_VOL_REC_CAT`, **sem** o `_V01` da tabela — a dúvida que sobrou da sondagem, fechada |
| o número chega tipado | `Decimal('18584.492')` e `Decimal('194.6')` → `NUMERIC(18,3)`, **sem float no caminho** |
| o zero à esquerda sobrevive | `'0000013953'` continua texto |
| `nk_calendario` DATE → `date` | sim, hora descartada |

**O que a rodada REPROVOU:** a chave natural, e o volume presumido. Ver a seção
"A carga real derrubou a chave natural" acima — foi o achado central do lote.

**A carga completa concluiu às 18h02 de 25/ago/2026**, já com a 0023 e o piso
de 2026:

| rodada | resultado |
|---|---|
| `--fonte oracle` (completa) | rec **36.678 lidas / 36.678 inseridas** (12s); exp **42.726 / 42.726** (15s); **0 fora de escopo** nos dois |
| dimensões | 6 unidades, 40 nomes de estoque, 14 clientes (7 canonizados) |
| `--fonte oracle --incremental` | **`sem_dado`** nos dois — a marca d'água (13:48:12 e 13:48:24) é exatamente o teto do que entrou |
| conferência no banco | `cat_cargas` com `fonte='oracle'` e o nome qualificado; **zero linha antes de 2026** nas duas tabelas; `nk_calendario` de 02/jan a 25/ago |

O número da sondagem e o da carga coincidem (42.726 na janela, 42.726 gravadas),
então nada se perdeu entre contar e gravar.

**A segunda carga completa fechou o aceite**, em 26/ago/2026 (09h44 e 09h45):

| movimento | resultado |
|---|---|
| rec | 36.678 lidas, **0 inserida, 0 atualizada, 36.678 iguais**, 0 fora de escopo |
| exp | 42.726 lidas, **0 inserida, 0 atualizada, 42.726 iguais**, 0 fora de escopo |

O contador de **iguais** é a prova, e não o de inseridas: ele leu as 79.404
linhas, comparou coluna por coluna e **não escreveu nada** — é o
`WHERE ... IS DISTINCT FROM` do upsert exercitado contra o driver real, que a
suíte só provava com CSV e com fonte falsa.

Uma rodada intermediária falhou antes disso, e o registro dela também é aceite:
às 09h05 a carga morreu com `[Errno 11001] getaddrinfo failed` — DNS, resolvido
sozinho na tentativa seguinte. A rodada 5 ficou em `cat_cargas` com
`status='erro'` e a mensagem, **as 79.404 linhas continuaram intactas** e a
expedição nem começou (o carregador aborta no primeiro movimento que falha).
Falha de rede virou linha de log, não dado torto.

**A tela foi validada no navegador pela Maria** em 26/ago/2026, com o dado do
Oracle no banco (caminho C, porta 8003) — a regra de que lote que mexe em tela
não fecha por leitura. Aprovada.

### A verificação que a carga real permitiu: Oracle x CSV, célula por célula

Com o dado carregado, comparei o que veio do **Oracle hoje** contra os **CSVs de
21/ago** — mesmo período, mesma agregação por `nk_calendario`. É a verificação
mais forte possível sem tocar no DW, e ela prova a cadeia inteira (leitura,
coerção, upsert, gravação) contra uma referência independente.

**Contagem de linhas: jan–jul bate em zero**, nos dois movimentos. Agosto difere
em +378 (rec) e +408 (exp) — os quatro dias novos entre 21 e 25/ago.

**Medidas, jan–jul/2026 (o período comum), soma exata em `Decimal`:**

| movimento | medidas conferidas | resultado |
|---|---|---|
| recebimento | `qtde_peso2`, `qtde_pbrt2`, `qtde_vlr`, `qtde_vol2`, `qtde_pallet` | **5 de 5 byte a byte idênticas** |
| expedição | `qtde_peso_solicitado`, `qtde_pbrt_atendido`, `qtde_vol_atendido`, `qtde_pedido` | **4 de 4 idênticas** |
| expedição | `qtde_vlr_separado` | **diverge: +391.943,152 (+0,03%)** |

Isso fecha, com número e não com teste, a promessa do `fetch_decimals`:
143.561.956,719 kg somados dos dois lados dão o mesmo `Decimal`. Se houvesse
float no caminho, não daria.

#### A única divergência é a fonte revisando, e ela vale mais que o resto

Investigada linha por linha: **306 linhas de 38.827 (0,79%)** com
`qtde_vlr_separado` diferente, e **zero chave natural sem par** — a identidade
casou 100% entre CSV e DW, o que é uma validação extra da 0023.

Três coisas dizem que é revisão da fonte, e não defeito nosso:

1. **só uma medida mudou**, e é a que amadurece por último (o valor do que foi
   fisicamente separado depende de a separação terminar e ser valorizada). As
   outras nove, mesmas linhas, não mudaram nada;
2. **a distribuição cresce com a proximidade:** jan 9, fev 4, mar 10, abr 42,
   mai 57, jun 86, **jul 98**. Quanto mais recente o mês, mais revisão pendente;
3. **todas carregam `DW_DATA_ALTERACAO` do mesmo instante do rebuild**
   (25/ago 13:47:14), e oito delas saíram de vazio/zero para ter valor.

O que isso prova sobre a decisão de trocar de fonte: **extração em arquivo
envelhece em silêncio.** Quem lê o CSV de 21/ago está com 391.943,15 de valor
separado desatualizado e não tem como saber. Ler o DW ao vivo, com incremento
por `DW_DATA_ALTERACAO`, é o que faz essa revisão chegar — e a rodada de amanhã
às 07h05 a traria sozinha.

Registrado também em `memory/fato-volumetria-dw.md`, que dizia "o DW revisa
número **para baixo**": revisa nos **dois** sentidos, e agora há medida nas
tabelas de catering, não só na `FATO_VOLUMETRIA`.


### Suíte

**234 passed** (`python -m pytest tests/test_catering_*.py tests/test_migracao.py`,
Postgres real em `localhost:5433`, 7min39), com as extrações de 21/ago presentes
na máquina — então os testes `@tem_extracao` rodaram em vez de pular. 34 testes
novos em `tests/test_catering_oracle.py`, mais os três da identidade em
`test_catering_carga.py` (a regressão da carga real, o furo conhecido do alarme
e a carga completa vazia).

O container de teste foi derrubado pelo Docker Desktop no meio de uma rodada, de
novo — o keep-alive de `memory/suite-testes-local.md` resolveu, como nas vezes
anteriores.

### O respaldo da arquitetura, medido em 26/ago/2026

A pergunta "por que não ler o DW ao vivo?" vai aparecer, e agora tem resposta com
número: `docs/ARQUITETURA_FONTE_DE_DADOS.md`. O documento é transversal de
propósito (sem "V3" no nome) — ele vale para qualquer tela nova que leia do DW.

O que foi medido no banco local com a carga real de 2026 dentro:

| medida | valor | como |
|---|---|---|
| disco por linha, com índices | **582 B** (rec) e **589 B** (exp) | `pg_total_relation_size` |
| todo o histórico do DW (433.734 linhas) | **cerca de 242 MB** | extrapolação dos bytes por linha |
| crescimento | **cerca de 120 mil linhas/ano, 70 MB/ano** | duas contas independentes que fecham |
| memória da carga | **3,9 MB, constante** | `tracemalloc` com 5 mil, 20 mil e 42 mil linhas |
| agregação de 6 medidas sobre 36.678 linhas | **21,6 ms**, `shared hit=1721`, zero leitura de disco | `EXPLAIN (ANALYZE, BUFFERS)` |
| Matriz completa | **36,5 ms** (rec) e **62,0 ms** (exp) | a função real da tela, mediana de 5 |

Três consequências que valem para as decisões seguintes:

1. **Volume não é critério aqui.** Trazer 2023 em diante custa 242 MB e uma
   variável de ambiente (`DW_ANO_MINIMO`). O que decide o piso do período é
   produto — quatro anos de coluna na Matriz e as linhas de `data_solic` podre
   voltando para dentro da janela — e não disco;
2. **a memória da carga não cresce com a tabela**, porque o carregador streama em
   lotes de `destino.PAGINA`. Recarga completa do histórico inteiro é tempo
   (cerca de 2,5 min), nunca pressão de memória;
3. **a tela varre a tabela inteira e responde em 22 ms** porque a cópia é local e
   pequena. Com o histórico completo o heap (cerca de 168 MB) passa do
   `shared_buffers` de 128 MB — o dia em que isso incomodar, a saída é índice por
   `nk_calendario` ou partição por ano, no nosso banco, com migration nossa.

O documento também registra o que **não** foi medido: o custo de uma agregação
dentro do DW, que exigiria conectar em produção.

### Arquivos

- `catering/carga/fonte_oracle.py` (novo)
- `alembic/versions/0023_identidade_ano_solic.py` (novo — a identidade de sete
  colunas)
- `catering/contrato.py` (nome qualificado, `tabela()`, `PK_DW` desacoplada,
  `CHAVE_NATURAL` com `ano_solic`, `piso_do_periodo()`)
- `catering/carga/fonte_csv.py` (o mesmo piso, para as duas fontes não
  divergirem)
- `catering/carga/destino.py` (`tabela_origem()` virou função)
- `catering/carga/__init__.py` (`CargaVazia`)
- `catering/carga/__main__.py` (`--fonte`, `--sondar`)
- `catering/web/matriz.html` (procedência e ressalva passam a dizer o nome real)
- `scripts/carga_catering.sh` (novo, **não instalado**)
- `requirements.txt` (`oracledb==4.0.2`), `.env.example` (as variáveis `DW_*`)
- `tests/test_catering_oracle.py` (novo, 29), `tests/test_catering_carga.py`
- `docs/ARQUITETURA_FONTE_DE_DADOS.md` (novo — o respaldo da decisão de
  arquitetura, com as medições de volume, memória e tempo de consulta)

### O que este lote NÃO fez

Deploy e serviço no compose (V3.6), crontab instalado, conciliação (V3.9),
laboratório (V3.10). Nada em `backend/`, `frontend/` ou nas migrations antigas. E
nenhuma conexão da IA com o DW.

---

---

## Lote V3.5.1 — O fuso de exibição, e a mensagem que faltava (feito, 26/ago/2026)

Lote pequeno, em branch própria (`v3.5.1-fuso`) e **não** empilhado no V3.5: o
V3.5 estava pronto para revisão independente, e misturar código novo no mesmo
diff estragaria justamente a revisão do lote que mexeu em contrato e identidade.

### O dado sempre esteve certo; a leitura dele não

`cat_cargas.terminada_em` e `cat_auditoria.criado_em` são `timestamptz` e guardam
UTC — que é o certo, e não mudou. O defeito era o `to_char`, que renderiza no
fuso da **sessão** do Postgres (`Etc/UTC` no container): uma carga das 09h45
aparecia como **12h45**, quase três horas no futuro, no campo que existe para dar
confiança na procedência.

Dois pontos, os dois em `catering/app.py`:

| onde | o que mostrava errado |
|---|---|
| rodapé "De quando é o dado" | a hora da última carga |
| coluna "quando" da auditoria, em `/administracao` | a hora de cada acesso e download |

**O segundo é o que pesou na decisão de não deixar para depois.** Rodapé com hora
esquisita é ruim; registro de auditoria com hora errada é problema de
rastreabilidade — é o que se consulta quando alguém pergunta quem baixou o quê e
quando.

`max_dw_data_alteracao` **não** entrou: ela é `timestamp without time zone` de
propósito, porque é o relógio do DW e não o nosso.

### Configuração, não constante nos dois SQL

`contrato.fuso_exibicao()` lê `CAT_FUSO_EXIBICAO` (padrão `America/Sao_Paulo`),
no mesmo formato de `ano_minimo()` e `tabela()`. Duas razões:

1. **um lugar para mexer** no dia em que a exibição passar a ser no fuso de quem
   lê (ISO-8601 para o front, formatado no navegador). Espalhar
   `'America/Sao_Paulo'` por dois `to_char` é garantir que o terceiro nasça
   esquecido;
2. **valida na leitura, não no uso.** `America/SaoPaulo` (sem o `_`) é o erro que
   de fato se comete, e ele falha nomeando a variável — em vez de o Postgres
   estourar no meio de uma consulta de tela, com mensagem que aponta para o lugar
   errado.

O fuso entra no SQL **por bind** (`AT TIME ZONE %s`), nunca concatenado: ele vem
de variável de ambiente, e variável de ambiente concatenada em SQL é injeção
esperando a vez, mesmo local e mesmo validada antes. Há teste estático para isso,
porque esse caminho não aparece em teste de comportamento — ele aparece na forma
como o statement foi montado.

### A decisão do cron: UTC, escrito em letras grandes

A pendência 2 do `DEPLOY.md` está fechada: o crontab é escrito **em UTC**
(`5 10` e `5 18` para 07h05/15h05 de Brasília), e não se ajusta o fuso da VM.

Ajustar a VM seria mais limpo de ler e **afeta os outros três projetos** que
moram nela — deixa de ser decisão de um time só, e o ganho não paga a
negociação. O preço da escolha é ficar escrito, e ficou: o `DEPLOY.md` tem o
aviso de não "corrigir" para `5 7`, com o efeito explicado (carga lendo a véspera
todo dia, no horário errado, sem ninguém notar — pior que falha, porque falha
aparece).

**A fraqueza conhecida ficou registrada junto:** cron em UTC não acompanha
horário de verão. O Brasil não observa desde 2019; se voltar, as duas linhas
precisam de revisão. Escolha com fraqueza declarada é decisão; sem declarar, é
armadilha.

### `catering/ambiente.py` — a mensagem que o carregador não herdou

O CLI de usuários (V3.4) já tinha resolvido o `KeyError: 'DATABASE_URL'` com uma
mensagem que diz o que fazer. **O carregador não herdou**, e cobrou: duas vezes
na mesma sessão, em 26/ago, a carga morreu com `carga falhou: 'DATABASE_URL'` —
mensagem que não mentia e não ajudava.

Duplicar o texto seria a saída curta e errada: duas cópias de instrução
operacional envelhecem em ritmos diferentes, e a que envelhece é sempre a que
alguém lê no pior momento. O texto passou a morar em `catering/ambiente.py`, e os
dois CLIs importam.

Duas decisões dentro disso:

- **a checagem é na entrada, depois do parse.** A falta é conhecida antes de
  qualquer trabalho, então dá para recusar com a orientação inteira em vez de
  descobrir no meio de uma carga que já abriu sessão no DW e já registrou a
  rodada. `--help` e argumento errado não pagam pedágio, e `--sondar` não pede
  `DATABASE_URL`, porque não toca no Postgres;
- **`DW_USER`/`DW_SENHA` também são exigidos na entrada.** A `FonteOracle` já
  recusava sem eles, mas depois de a rodada estar registrada — a linha ficava em
  `cat_cargas` com `status='erro'` por um motivo que a pessoa poderia ter sabido
  antes de começar.

Um detalhe que um teste pegou e vale escrever: a mensagem **não** pode ser
montada com `str.format`. O corpo carrega um comando PowerShell com
`ForEach-Object { ... }`, e `format` lê essas chaves como campo de formatação —
`KeyError: " $_ -match ..."`. Mensagem de erro que estoura ao ser montada é o
pior lugar possível para um defeito, porque ela só é montada quando algo já deu
errado.

### O que este lote NÃO fez

Não tocou no fuso da VM, não instalou crontab, não mexeu em nada do caminho da
carga — a mudança é de exibição e de mensagem. O terceiro item dos achados
(ajuste visual da tela) segue aberto, sem nada específico levantado.

### Suíte

Nove testes novos. Os cinco do fuso foram verificados contra o defeito: com a
correção revertida, **quatro falham** (o quinto é o do contrato, que não deveria
falhar) — teste que passa antes e depois não prova nada.

---

## Lote V3.6 — Deploy: a V3 sobe, a V2 sai (código pronto, execução pendente)

Autorizado em 26/ago/2026. **O código está pronto e a execução na VM é da
Maria** — o procedimento numerado está em `docs/DEPLOY.md`, seção "V3.6".

### A decisão que mudou o lote: a V2 sai inteira

O plano previa "desmonte do admin e do linhagem", e ao levantar o V3.6 apareceu
um conflito: `/admin` e `/linhagem` **não são um serviço**, são duas rotas dentro
do `backend/main.py` — o mesmo processo que serve `/nuvem`, `/cockpit` e
`/laboratorio`. Tirar só as duas exigiria editar a V2, que está **congelada** por
regra do `CLAUDE.md`. Havia três saídas, e a pergunta que decidia era de negócio:
aquelas telas ainda servem para alguém?

Resposta da Maria: **nenhuma delas serve.** *"Futuramente talvez a gente volte a
usar o laboratório, mas aí a gente reativa e mexe nele."*

Com isso o desmonte volta a ser o que o V3.2 tinha prometido — **remover um
serviço, não editar código** — e `backend/` fica intacto de verdade.

### O ganho que a decisão destravou: as migrations saem do startup

Este é o melhor efeito colateral do lote, e ele resolve um risco que estava no
projeto desde o V3.0 sem estar escrito em lugar nenhum.

As migrations da V3 (0019–0023) entrariam em produção **de carona no startup da
V2**: o `Dockerfile` copia `alembic/` e `backend/main.py` chama
`migracao.migrar()` ao subir. Consequência que ninguém havia decidido: **uma
migration da V3 com defeito derrubaria a V2**, porque `migrar()` roda antes de a
aplicação servir.

Como a V2 não sobe mais, elas passam a ser aplicadas explicitamente
(`docker compose run --rm nuvem-cat alembic upgrade head`). Em produção o
`migrar()` cairia no caminho *gerenciado* — a `alembic_version` existe, então é
literalmente `upgrade head` — logo o comando explícito faz o mesmo, no momento
escolhido, sem acoplar a V3 ao ciclo de vida de um app que está saindo.

Verificado em 26/ago/2026 na produção, antes de decidir: `pg_tables LIKE 'cat_%'`
devolveu só `catalogo_campos`, `catalogo_colunas` e `catalogo_fontes` — que são
da V1/V2. **O schema da V3 não estava em produção**, o que confirma que a V2 não
foi reconstruída desde 24/ago e que o V3.6 cria, não confere.

### O que muda no repositório

| arquivo | mudança |
|---|---|
| `Dockerfile` | `COPY catering/` e `COPY scripts/carga_catering.sh` — sem eles, o script da carga falha alto de propósito |
| `docker-compose.yml` | serviço `nuvem-cat` na porta 8003; o bloco `nuvem-app` fica **comentado, não deletado** |
| `.env.example` | `CAT_SECRET_KEY` documentada (faltava — ver abaixo) e `CAT_COOKIE_SECURE` |
| `docs/DEPLOY.md` | procedimento de 14 passos, com os dois não-retornos marcados; pendências 1 e 2 fechadas |

**Uma imagem só para as duas aplicações**, e não duas: as dependências são as
mesmas e a cadeia de migrations é a mesma. Duas imagens dobrariam o build para
separar o que já está separado no processo.

### `--no-access-log` na V3, por motivo diferente da V2

A V2 desliga o access log porque tem middleware próprio que loga método e path
**sem** query string (Bloco G, onde cliente e filial vazavam em claro). A V3
**não tem middleware nenhum** — então a escolha aqui é entre não ter log de
requisição e ter um que vaza o recorte (`clientes=`, `unidades=` viajam em query
string).

Fica sem, e o substituto é melhor que access log: a V3 audita **em banco**
(`cat_auditoria`, V3.3/V3.4) usuário, evento, recorte, formato, linhas e IP. Log
de requisição morre com o container; auditoria em banco entra no backup.

### Um achado do lote: `CAT_SECRET_KEY` não estava no `.env.example`

O `.env` local da Maria tem a variável desde o V3.4, então o `docker compose
config` validou sem reclamar — e o `.env.example`, que é de onde se monta o
`.env` da VM, não a mencionava.

O modo de falhar é o pior possível: **o app sobe, o `/health` responde 200 e o
login estoura.** Quem olha só o healthcheck conclui que está no ar. Documentada
agora, com o efeito escrito ao lado do nome.

### O que este lote NÃO faz

Não executa o deploy — isso é da Maria, pelo procedimento do `DEPLOY.md`. Não
apaga dado: o volume `nuvem_db_data` e as tabelas da V1/V2 ficam. Não remove
`backend/` nem `frontend/`. Não instala o crontab (passo 14, na VM). Não mexe no
Conciliador nem no Hub.

### Suíte

A **completa**, e não só a do lote — a regra é essa antes de um deploy, porque a
fronteira deixa de ser só o schema.

### Aceite do V3.6 — executado em 26/ago/2026

**A V3 está em produção**, na porta 8003 da VM, servindo dado do DW. Executado
pela Maria, comando por comando, com a saída de cada bloco conferida antes de
liberar o seguinte.

| passo | resultado |
|---|---|
| fuso da VM | **`Etc/UTC`** — confirma a decisão do cron em UTC |
| porta 8003 | livre; e já estava liberada na rede (Security Group) |
| linha de base | 7 containers: 2 da Nuvem, 3 do Conciliador, 2 do Hub |
| backup pré-deploy | `nuvem_20260826_163046.sql.gz`, 456K |
| migrations | `0017` → **`0023`**, seis migrations, numa transação só |
| tabelas criadas | as **8** `cat_*` esperadas |
| carga completa | rec **36.893**, exp **42.900**, `status ok`, 0 fora de escopo |
| dimensões | 6 unidades, 14 clientes, 40 nomes de estoque |
| período | 02/jan a **26/ago/2026** — o piso de 2026 respeitado |
| login e papel | entrou como `ADMIN`; console do navegador **sem erro** |
| download | xlsx completo, registrado em `cat_auditoria` |
| **fuso na tela** | carga das **16h45 UTC** exibida como **13h45** — o V3.5.1 provado em produção |
| V2 desligada | container removido por nome; a 8002 saiu do `ss` |
| vizinhos | Conciliador e Hub **intactos** — uptimes de 6 dias a 7 semanas, nenhum reiniciado |
| agendamento | as duas linhas em UTC (`5 10`, `5 18`) instaladas |
| carga incremental | `sem_dado` nos dois, marca d'água em `2026-08-26 12:43:36` |

**A evidência mais forte de que o desligamento da V2 não afetou ninguém não é o
comando que usamos, e sim os uptimes dos vizinhos depois dele**: 7 semanas nos
bancos do Conciliador e do Hub, 6 e 9 dias nos serviços. Container tocado tem
contador zerado.

### O que a execução ensinou, e que o código não previa

**1. Produção estava em `0017`, não `0018`.** O `upgrade head` aplicou **seis**
migrations, e a primeira delas é **da V2** — a `0018`, que corrige o de-para de
`RMSPII/015` e `RMSPII/016`. Ou seja: a V2 em produção rodou desde 18/ago com o
banco atrás do próprio código, exibindo `RMSPIII`/`RMSPIV` onde o código já
esperava `RMSPII`. Ninguém notou, o que é coerente com as telas não serem usadas.

Antes de liberar, o SQL foi inspecionado em modo offline
(`alembic upgrade 0017_layout_lido:head --sql`) e a 0018 se mostrou segura:
`UPDATE ... FROM` sem constraint nova, que afeta zero linhas se o conector não
existir. **Ler o SQL antes de aplicar transformou o não-retorno em decisão
informada** — vale repetir em qualquer deploy que aplique migration alheia.

**2. O `env.py` roda tudo numa transação só.** Sem `transaction_per_migration`, e
com DDL transacional do Postgres, as seis migrations são tudo-ou-nada: falha na
quarta reverte as três anteriores e o banco fica em `0017`. Isso torna o passo
menos perigoso do que a documentação sugeria — o risco do passo 5 é o sucesso
dele, não a falha.

**3. `CAT_SECRET_KEY`, `DW_USER` e `DW_SENHA` não estavam no `.env` da VM.** O
teste novo (`test_catering_deploy.py`) tinha acabado de fechar essa lacuna no
repositório, e ela se materializou na execução — o Bloco 1 pegou antes de
qualquer build.

**4. O rodapé "De quando é o dado" está dentro de um `<details>` recolhido**, com
o rótulo "Fontes & método". Não é defeito, é o desenho do V3.2 — mas o campo que
sustenta a confiança no número exige um clique e um rótulo que não o anuncia.
Fica na lista de ajustes visuais.

**5. `docker rm` por nome em vez de `--remove-orphans`.** A pergunta da Maria
(*"não vai remover nada das outras aplicações, né?"*) melhorou o procedimento: o
`DEPLOY.md` passou a documentar o comando cirúrgico. Operação em VM compartilhada
não deve exigir que quem executa confie num filtro invisível.

### Pendências abertas depois do deploy

**1. O backup automático do banco NÃO está instalado** — e esta é a única
pendência com risco real. O `crontab -l` da VM tem o backup do **Conciliador**
(04h UTC, outro projeto) e as duas cargas da V3, mas **não** a linha do
`scripts/backup.sh` da Nuvem IA, documentada desde o Bloco G1. O único dump
existente é o avulso de 26/ago 16h30.

```
0 3 * * * cd /home/ubuntu/nuvemIA && mkdir -p backups && ./scripts/backup.sh >> backups/backup.log 2>&1
```

**2. Dez nomes de estoque em `NAO_CLASSIFICADO`**, vistos no log da carga:
`AJUSTE DE TARIFA`, `CONSOLIDADOR`, `CONSOLIDADOR - 14025`, `CROSS DOCKING`,
`EPI`, `MAQUINARIO`, `PAP`, `QUÍM/ DESC/ LIMP`, `REAJUSTE`, `RETAIL`. Vários não
descrevem tipo de estoque — parecem cobrança (`AJUSTE DE TARIFA`, `REAJUSTE`),
material (`EPI`, `MAQUINARIO`) e operação (`CROSS DOCKING`). O tripwire está
funcionando como projetado: aparecem na tela como `NAO_CLASSIFICADO`, visíveis.
Decisão de negócio em aberto.

**3. HTTP sem TLS.** O navegador marca "Não seguro" e avisa no download. É a
fraqueza declarada no V3.4 (cookie de sessão sem `secure`, porque sem HTTPS
ligar a flag impediria qualquer login). `CAT_COOKIE_SECURE=1` quando houver TLS.

**4. A revisão independente** não foi feita em nenhum dos lotes V3.5, V3.5.1 e
V3.6 — a regra de trabalho a exige, e ela ficou de fora nos três.
## Lote V3.7 — Recorte por dia, filtro de dia do mês e abertura da tela (feito, 26/ago/2026)

Autorizado em 26/ago/2026, dentro da conversa que pediu o histórico completo do
DW. **Foi separado do histórico de propósito**, e a ordem importa: este lote é
código e sobe validado contra os dados de 2026 que já estão no banco; o histórico
(V3.8) é operação, e mexe em produção. Se as guardas de recorte largo estiverem
erradas, a hora de descobrir é antes de existirem 434 mil linhas — não depois.

### O que o lote entrega

| | antes | depois |
|---|---|---|
| **Período** | mês fechado, `AAAA-MM`, meio-aberto no fim | **dia**, `AAAA-MM-DD`, **fechado nas duas pontas** |
| **Dia do mês** | não existia | multi-seleção 01..31, recorta dentro de **todo** mês do período |
| **Abertura da tela** | `min..max` do dado | **janeiro do ano corrente até hoje** (`CAT_ABERTURA_DE`) |
| **Coluna parcial** | não declarada | cabeçalho traz a faixa de dias (`2026-08 (03-31)`) |
| **Download grande** | começava calado | a tela pergunta acima de 150 mil linhas |
| **xlsx acima do teto** | 400 do servidor, como página de JSON cru | aviso antes de navegar |

### As duas coisas com a palavra "dia", que não se substituem

O pedido veio com um anexo do Power BI, e ele resolveu a ambiguidade: a tela dele
tem **Ano / Mês / Dia** como filtros separados, com o Dia em caixas de seleção.
Traduzido para o nosso recorte:

- **período** (`de`/`ate`) é um intervalo de datas — `03/08/2026 a 05/09/2026`;
- **dia do mês** (`dias`) é a multi-seleção 01..31, que corta **dentro de cada
  mês do período** — jan a ago tirando os dias 1, 2 e 3 exclui esses dias nos
  oito meses.

É dia **do mês**, não dia da semana. No SQL é uma cláusula só
(`EXTRACT(DAY FROM f.nk_calendario) = ANY(%(dias)s)`), no mesmo padrão dos outros
filtros, e o valor chega ao banco como **lista de inteiros** — o texto da URL não
alcança o SQL.

**O que NÃO entrou do anexo, e é decisão registrada:** os dropdowns separados de
Ano e Mês (o intervalo de datas cobre) e o botão que troca o grão das colunas
entre Ano, Mês e Dia. A coluna continua **mensal** — pedido da Maria: *"pra
mostrar na matriz faz o que você falou mesmo"*.

### O total que passou a poder mentir, e como a tela declara

Com recorte por dia, a coluna `2026-08` pode não ser agosto. São duas
parcialidades diferentes, e cada uma é declarada onde ela é lida:

1. **ponta do período** — cabe no cabeçalho, porque afeta uma coluna só de cada
   lado: `2026-08 (03-31)`. Mês inteiro sai **sem** parênteses, porque anotar o
   óbvio treina a pessoa a ignorar a anotação;
2. **filtro de dia do mês** — **não** cabe no cabeçalho: ele corta em todas as
   colunas, inclusive as do meio. Entra como aviso, com os dias resumidos em
   faixas (`04 a 06, 09, 20, 21`) — aviso que lista 28 números é uma parede que
   ninguém lê.

Um total rotulado como o mês que não é o mês é exatamente o número que alguém
copia para um relatório. É a disciplina do
`memory/pagina-mostra-numero-nao-texto.md` aplicada ao recorte — e o
`memory/nao-ler-mes-parcial.md` já tinha medido o custo de não declarar:
comparando a RMSPII com julho pela metade contra julho fechado, **3 de 18**
leituras por cliente **trocaram de sinal** (CONVIDA aparecia +78,8% e fechou
−22,3%). A conclusão de lá era literalmente "o número de dias tem que viajar
junto com o número, sempre" — o cabeçalho deste lote é isso.

É também o motivo de o marcador **ficar** na coluna do mês corrente na abertura
padrão (`2026-08 (01-26)`): ali ele não é ruído, é o aviso de que agosto ainda
não terminou e não se compara com julho inteiro.

### A abertura da tela: janeiro do ano corrente, e por que fica em configuração

A tela abria em `min(nk_calendario)..max(nk_calendario)`. Isso era certo enquanto
o banco tinha um ano; com o histórico do V3.8 dentro dele, a tela passaria a
abrir em **01/2023, com 44 colunas**, para responder uma pergunta que ninguém
fez.

O pedido da Maria trouxe duas formulações — *"janeiro do ano corrente até o mês
atual"* (rolante) e *"de acordo com a sua recomendação de fixo em
configuração"*. Elas apontam para comportamentos diferentes, e a saída foi a
variável aceitar as duas:

| `CAT_ABERTURA_DE` | efeito |
|---|---|
| `ano-corrente` (**padrão**) | 1º de janeiro do ano de hoje |
| `AAAA-MM-DD` | data fixa, para pinar |

O `ate` é sempre **hoje**. O que o rolante custa está escrito antes de doer: em
01/jan/2027 a tela abre com uma coluna só, e a saída é pinar a data — variável de
ambiente, sem commit.

**`hoje` vem do Postgres, no fuso de exibição, e não do relógio do processo.** O
container roda em UTC, e as 21h de Brasília já são o dia seguinte lá — a tela
abriria com um dia que ainda não começou. É o mesmo defeito que o V3.5.1
corrigiu no rodapé, só que aqui ele mexeria no **recorte**. O Postgres também é
onde a base de fuso é confiável, sem depender de `tzdata` na imagem.

**O alcance real do dado não desapareceu:** virou a dica "Dado disponível
02/01/2026 a 21/08/2026" ao lado dos campos. Quem não sabe que 2023 está no
banco não filtra para trás — e o campo de data não tem mínimo, então filtrar para
trás sempre funcionou.

### A trava que foi construída, medida no navegador e desfeita

A primeira versão abria em `max(abertura, primeiro dia com dado)`, para não abrir
com a ponta esquerda vazia. **O navegador mostrou o preço:** o dado local começa
em 02/jan, então a tela abria em 02/jan e o cabeçalho declarava
`2026-01 (02-31)` — marcando como parcial um **janeiro que está inteiro**.

A marca de mês parcial só vale se ela for rara. Nascer ligada no padrão é o
caminho mais curto para ninguém mais olhar para ela. Coluna vazia à esquerda não
custa nada (ela existe, é completa e vale zero); marcador que mente, custa. A
trava saiu, e ficou apenas a da inversão (`CAT_ABERTURA_DE` pinado no futuro não
pode abrir a tela com "período invertido" na cara de quem entrou).

Isto está fixado em teste, com o motivo escrito — é o tipo de "melhoria" que
volta sozinha na próxima leitura do código.

### Aviso em vez de trava, e por que a Matriz não precisava de guarda

A pergunta da Maria foi direta: *"será que devemos colocar uma trava para
ninguém querer pegar de 2023 a 2026, para não travar o sistema?"* Antes de
responder, foi medido o que de fato pesa num recorte de 3,6 anos (~434 mil
linhas):

| camada | o que acontece |
|---|---|
| Matriz — SQL | um `GROUP BY` sobre o recorte, alguns milhares de linhas agregadas. Postgres resolve em bem menos de 1s |
| Matriz — navegador | **desenha só o nível aberto**: abre com 6-12 linhas × 44 colunas. Não trava |
| Planilha | 100 linhas por página + um `count(*)`. Não muda |
| xlsx | **já tinha teto** de 150 mil linhas, com mensagem mandando para o CSV |
| CSV | streaming, sem teto. ~170 MB e uma espera longa — **o único ponto com peso real** |

Então **trava dura de período não entrou**: ela não protegeria estabilidade
nenhuma e mataria o comparativo 2023×2026, que foi o caso de uso que motivou o
piso configurável no V3.5. O que entrou:

- **confirmação no download acima de 150 mil linhas** (número escolhido pela
  Maria, igual ao teto do xlsx). Constante própria (`TETO_CONFIRMACAO`) e não
  apelido de `TETO_XLSX`: hoje valem o mesmo por decisão, não por dependência —
  uma responde "este formato aguenta?", a outra "você quer mesmo?";
- **aviso antes de navegar quando o xlsx não cabe.** O servidor já recusava com
  400 e uma boa mensagem, mas o download **navega**, então a recusa aparecia como
  uma página de JSON cru. Os dois tetos vêm do Python (`/api/opcoes`), para não
  existir uma segunda cópia deles no JavaScript;
- **o aviso de recorte largo na Matriz foi descartado.** Estava no plano, e a
  medição não o sustentou. Aviso sem medição que o justifique é código a mais e
  ruído na tela.

**A contagem sai de graça.** A Matriz passou a devolver `total_linhas`, somando
`count(*)` dos grupos da consulta que ela já roda — sem consulta extra. Isso deu
um invariante novo, que está em teste: **o `total_linhas` da Matriz tem que ser
igual ao da planilha**, que conta o mesmo recorte por outro caminho. Se
divergirem, a tela avisa sobre um arquivo e baixa outro.

A tela também confere se o número em mãos ainda descreve o recorte pedido
(assinatura dos filtros): quem mexeu nos filtros **sem** apertar Aplicar recebe o
número do recorte que vai realmente sair, buscado na hora. Perguntar "são 434 mil
linhas, continuar?" com o número de outro recorte é pior que não perguntar.

### O aceite: recorte por dia contra o CSV, célula por célula

O mesmo método do aceite do V3.2 — duas implementações independentes, mesmo
número — com o recorte que este lote criou. O caminho em Python puro passou a
cortar **por dia** (antes comparava mês com mês, o que não provava nada sobre
corte no meio do mês) e a aceitar o filtro de dia do mês. Três recortes:

| recorte | o que ele prova |
|---|---|
| `2026-03-03` a `2026-05-05` | pontas parciais nos dois lados |
| `2026-02-01` a `2026-04-30`, dias 1-3 | filtro de dia sobre meses inteiros |
| `2026-06-10` a `2026-07-20`, dias 10-15 | os dois ao mesmo tempo |

Cada um confere o conjunto de células, o valor de cada célula, o cabeçalho
parcial e a presença do aviso. **Por que este é o teste que importa neste lote:**
um recorte que corta errado não estoura — ele devolve um número menor, plausível,
e ninguém vê.

### Duas duplicações que o lote fechou porque iam cobrar

1. **`matriz._eco()` era uma cópia campo a campo de `Filtros.como_dict()`.**
   Acrescentar `dias` em um dos dois e não no outro faria a tela ecoar um recorte
   e a auditoria gravar outro. Agora `_eco` delega.
2. **O `GROUP BY` era contado por subtração** (`len(selecoes) - len(medidas)`),
   o que amarrava o agrupamento a quantos agregados existem — a `count(*)` nova
   teria virado um off-by-one **silencioso**, que num `GROUP BY` não estoura, só
   soma errado. Agora o agrupamento é fechado antes de os agregados entrarem.

### O que muda no repositório

| arquivo | mudança |
|---|---|
| `catering/contrato.py` | `abertura_de(hoje)`, `ABERTURA_ANO_CORRENTE`, `AberturaInvalida` |
| `catering/consulta/recorte.py` | `de`/`ate` em data, `dias`, `data_do_recorte()`, `dias_do_filtro()`, `rotulos_dos_meses()`, `rotulo_dos_dias()`, `aviso_dos_dias()`, `ultimo_dia_do_mes()` |
| `catering/consulta/matriz.py` | `rotulos_meses` e `total_linhas` na resposta, aviso do dia, `_eco` delegado |
| `catering/consulta/planilha.py` | o mesmo aviso do dia |
| `catering/consulta/download.py` | `TETO_CONFIRMACAO`, sufixo `_dias` no nome do arquivo |
| `catering/app.py` | `dia` nos três endpoints, `abertura`/`teto_confirmacao`/`teto_xlsx` em `/api/opcoes`, `hoje` do Postgres |
| `catering/web/matriz.html` | dois `type="date"`, select de dia do mês, dica do alcance, cabeçalho parcial, confirmação do download |
| `docker-compose.yml`, `.env.example` | `CAT_ABERTURA_DE` |
| `tests/` | 5 arquivos: recorte por dia, aceite novo, invariante da contagem, abertura e suas travas, compose |

**Sem migration.** O schema não muda: o recorte é `WHERE`, não coluna.

### Suíte

```
python -m pytest tests/test_catering_*.py tests/test_migracao.py
```

**270 testes, ~6min20, verde** (26/ago/2026). Eram 188 no V3.4.

Duas coisas que a suíte cobrou e valem estar escritas:

- **`_mes` já existia** no `test_catering_matriz.py` (corta
  `2026-01-05 00:00:00.000` em `2026-01`), e o helper novo com o mesmo nome o
  sobrescreveu. O aceite do V3.2 foi quem gritou. O novo virou
  `_pontas_do_mes`;
- **`rotulos` já existia** dentro do laço de linhas da `matriz()` (os rótulos de
  **nível**), e a variável nova com o mesmo nome era sobrescrita a cada linha —
  a resposta saía com uma lista onde a tela esperava um dicionário. Quem achou
  foi o teste do cabeçalho parcial, no primeiro `assert` que olhou o rótulo.

Colisão de nome em módulo de 300 linhas com vocabulário repetido (`mes`,
`rotulos`, `dias`) é a classe de erro deste lote, e as duas apareceram em teste
antes de aparecerem na tela.

### Validação no navegador (26/ago/2026)

Caminho C do `docs/EXECUCAO_LOCAL.md`, porta 8003 local, com os CSVs de
`docs/Analise/` carregados (36.300 + 42.318 linhas). Conferido:

- abre em **01/01/2026 a 26/08/2026**, janeiro limpo e `2026-08 (01-26)` na
  última coluna — agosto não terminou, e a coluna diz isso;
- `03/03` a `05/05` → três colunas, `2026-03 (03-31)`, `2026-04`,
  `2026-05 (01-05)`, com os números caindo de acordo;
- filtro de dia 03-05 → aviso na tela e totais recalculados; na planilha, só
  linhas dos dias 02 e 03 (recorte 02-03) e o mesmo aviso;
- confirmação do download exercitada com os tetos baixados na página: CSV
  pergunta e cancelar **não navega**; xlsx avisa em vez de deixar o servidor
  devolver JSON cru; filtro mexido sem Aplicar rebusca a contagem (1.247 → 36.300);
- **console sem erro nem aviso**, e `node --check` no script da página.

O que **não** foi validado: aparência e experiência são aprovação humana
(`memory/validar-tela-no-navegador.md`), e o volume real de 434 mil linhas só
existe depois do V3.8 — a confirmação do download foi exercitada com o teto
baixado, não com o recorte grande de verdade.

### O que este lote NÃO fez

Não baixou o piso da carga (continua 2026), não rodou recarga, não encostou na
VM. Coluna por dia na Matriz, dropdowns de Ano/Mês e trava dura de período
ficaram **fora por decisão**, não por falta de tempo. Nada em `backend/`,
`frontend/` ou nas migrations.

## Lote V3.7.1 — Filtros com caixas de seleção (feito em 27/ago/2026)

Mapeado mais cedo em 27/ago/2026 (*"só mapeie esse novo lote, fazemos ele
depois"*) e **autorizado no mesmo dia**: *"pode seguir com o próximo lote"*. O
mapeamento foi feito antes da construção de propósito, e as decisões que ele
fixou entraram como estavam — nenhuma foi re-discutida na execução.

### De onde veio

Fechando o V3.7, a pergunta da Maria foi: *"precisa ser Ctrl + clique? Não pode
apenas ser clique em mais de 1?"*

Os cinco filtros de múltipla escolha (unidade, cliente, tipo de estoque,
operação e agora dia do mês) são `<select multiple>` nativos. A **capacidade** de
escolher vários sempre existiu — está medida no V3.7: unidade `RMSPII + CWBIII`
soma 13.153,8 + 944,1 = 14.097,9 t em jan/2026, e filtros diferentes se
estreitam. O que não existe é a **descoberta**: no `select` nativo o clique
simples *substitui* a seleção, e só Ctrl (ou Cmd) acrescenta — comportamento do
navegador, não do nosso código, e que não está escrito em lugar nenhum da tela.

Duas saídas foram apresentadas:

| | o que é | custo |
|---|---|---|
| **A** | clique simples **alterna**: intercepta o `mousedown` na opção, inverte o `selected`, cancela o nativo. Ctrl e Shift continuam valendo | ~10 linhas |
| **B** | **lista de caixas de seleção com "Selecionar tudo"**, como o slicer do Power BI | widget próprio |

**Escolhida a B**, e o motivo é o que importa: *"estamos mais acostumados com a
B"*. É o padrão que a operação já usa no BI — a caixa marcada diz sozinha o que
está selecionado, sem depender de convenção nenhuma. A **A fica registrada como
alternativa viável**, não como ideia descartada: se a B se mostrar grande demais
na hora de fazer, a A entrega o "clique simples em mais de um" por um décimo do
trabalho.

### O desenho que faz isso ser pequeno

O `<select multiple>` **continua no DOM, escondido, como fonte da verdade**. O
painel de caixas só o comanda. Consequência: `parametros()`, `opcoesSelect()` e o
botão Limpar não mudam **uma linha** — a mudança é uma camada de interface sobre
o que já existe, e não uma reescrita do recorte. Nenhum arquivo de backend,
nenhuma migration.

```
CLIENTE
┌──────────────────────────┐
│ Seleções múltiplas    ▾  │   fechado: "Todos" / "SAPORE S.A" / "3 selecionados"
└──────────────────────────┘
   ┌──────────────────────────┐
   │ ☐ Selecionar tudo        │
   │ ─────────────────────────│
   │ ☑ ANGA ALIMENTACAO E ... │
   │ ☐ BRF S.A.               │
   │ ☑ CONVIDA REFEICOES LTDA.│
   └──────────────────────────┘
```

### Três decisões já tomadas, para não serem re-discutidas na execução

1. **"Selecionar tudo" marcado = nenhum filtro na consulta.** Marcar os 14
   clientes e não filtrar dão o mesmo número hoje, e **não são a mesma coisa
   amanhã**: se um cliente novo aparecer na carga, "sem filtro" inclui ele e "os
   14 que eu marquei" não. Manda-se **nada** na URL quando está tudo marcado — é
   o que o "Todos" do BI significa, deixa a auditoria honesta ("sem filtro de
   cliente") e não infla a URL do download.
2. **Sem campo de busca dentro do painel.** As listas hoje têm 6, 14, 6, 12 e 31
   itens; busca nesse tamanho é peso sem ganho. **Gatilho para acrescentar
   depois:** a lista de cliente passar de ~25 itens — o que o V3.8 pode causar,
   ao acordar clientes de 2023 que não operam mais.
3. **Comportamento mínimo, que não precisa ser pedido:** Esc fecha, clique fora
   fecha, Tab e setas navegam, e clicar numa caixa **não** fecha o painel — se
   fechasse, marcar três itens exigiria abrir três vezes, que é o problema do
   Ctrl+clique com outra roupa.

### A decisão que faltava — FECHADA em 27/ago/2026: a barra encurta

**A barra de filtros encurta para uma linha** (Maria, 27/ago/2026). Hoje são cinco
caixas de 64px de altura ocupando duas linhas; viram cinco botões de uma linha que
abrem o painel de caixas. É ganho de espaço real e era mudança visual, então
precisava de aprovação humana (`memory/validar-tela-no-navegador.md`) — está dada.
A alternativa que ficou para trás, e não precisa ser re-perguntada: manter a
altura de hoje, com as caixas dentro do espaço que os selects já ocupam, era
funcionalmente idêntico e só não ganhava espaço.

### O que foi construído, e as três decisões que a execução obrigou a tomar

O desenho previsto sobreviveu: o `<select multiple>` continua no DOM, escondido,
como fonte da verdade, e o painel de caixas só o comanda. `parametros()` e
`opcoesSelect()` **não mudaram uma linha**, como previsto — mas duas outras
mudaram, e a previsão de que nada mais mexeria estava errada:

- `preencheOperacoes()` ganhou uma linha (`atualizaCaixa('#operacao')`). A lista
  de operação é **por movimento**, então trocar Entrada/Saída troca as opções, e
  o painel tem que ser remontado sobre elas. Sem isso, o painel de operação
  mostraria a lista do movimento anterior;
- o **Limpar** ganhou uma linha (`atualizaCaixas()`) e passou a iterar
  `COM_CAIXAS` em vez da lista literal dos cinco seletores. A lista literal
  duplicada era o defeito esperando o sexto filtro: ele entraria numa cópia e
  não na outra, e o Limpar deixaria um filtro em pé sem dizer.

Três decisões que o desenho não tinha respondido, e que a execução não podia
adiar:

1. **Não existe estado "nenhum item marcado".** Com nada selecionado o painel
   mostra **tudo** marcado e o botão diz "Todos" — porque "sem filtro" e "todos"
   são a mesma linha do `WHERE`. A consequência: desmarcar um item em "Todos"
   significa **"todos menos este"**, e desmarcar o último selecionado volta para
   "Todos". A alternativa — deixar o painel vazio e o rótulo dizendo "Todos" —
   seria a tela mentindo sobre o próprio recorte.
2. **"Selecionar tudo" fica desabilitado quando está marcado.** Marcado já *é*
   "sem filtro", então não existe ação para desmarcar. Deixá-lo habilitado e não
   fazer nada pareceria defeito; desabilitado, ele diz que aquele já é o estado.
3. **O select só recebe `.escondido` depois de o painel existir.** As regras de
   `select[multiple]` ficaram no CSS de propósito: se a montagem do widget
   falhasse no meio, a pessoa fica com o campo nativo em vez de nada. Degradação
   por construção, e não por promessa.

### O aceite — e o que ele NÃO cobre

**A máquina de estados foi provada fora do navegador**, contra o código real
extraído do `matriz.html` e rodado com um DOM mínimo em node: 22 asserções nos
nove casos que decidem o que vai na URL — "Todos" inicial, "todos menos este",
remarcar tudo voltando para **URL vazia** (a decisão 1 do desenho), rótulo com
nome único e com contagem, desmarcar o último, "Selecionar tudo", o Limpar
ressincronizando os cinco, lista de um item só, e `selecionados()` continuando a
ler do select. O harness é descartável e **não foi versionado** — o projeto não
tem suíte de JS, e inventar uma neste lote seria escopo que ninguém pediu. O que
ficou versionado é o teste estrutural abaixo.

`node --check` no script: limpo. **Suíte da V3: 277 testes, verdes, 5min02** —
que é o que prova que nada de backend se mexeu.

**Um teste novo, e ele guarda a fiação, não o comportamento:**
`test_todo_filtro_de_multipla_escolha_tem_painel_de_caixas` compara os
`<select multiple>` do HTML servido com a lista `COM_CAIXAS`. O defeito que ele
pega é silencioso: um sexto filtro acrescentado sem entrar na lista fica visível
como select nativo entre os botões, **e o Limpar deixa de zerá-lo** — o recorte
sai com um filtro em pé que a tela não mostra. Nada disso levanta erro; só sai
número de menos.

**O navegador — validado pela Maria em 27/ago/2026** ("validado"), no caminho C
com os CSVs de 21/ago recarregados (36.300 + 42.468 linhas). Isso fecha o que o
harness em node **não** podia provar: que o painel abre no lugar certo, que ele
não fica atrás de outro elemento, e que a barra de uma linha ficou boa de olhar —
aprovação estética é humana por regra
(`memory/validar-tela-no-navegador.md`). Nenhum defeito reportado.

Como a tela foi levantada, porque isso se repete: caminho C do
`docs/EXECUCAO_LOCAL.md`, e **recarregar os CSVs** — o pytest zera o banco local,
e sem isso a tela sobe vazia. O `cat_usuarios` também é zerado, então o primeiro
admin precisa ser recriado pelo bootstrap (`CAT_ADMIN_LOGIN`/`CAT_ADMIN_SENHA`) a
cada rodada de suíte.

### O que o mapeamento previa como prova

**O navegador, e não a suíte.** A página é HTML com JS embutido e o projeto não
tem suíte de JS. Então: marcar, desmarcar, "Selecionar tudo", Limpar, rótulo do
botão fechado e console limpo, nos cinco filtros; `node --check` no script; e a
suíte da V3 verde **para provar que nada de backend se mexeu** (270 testes).

Um detalhe de execução que já se sabe: validar na tela exige subir o caminho C e
**recarregar os CSVs**, porque o pytest zera o banco local.

### O que este lote NÃO faz

Não toca no recorte (período, dia do mês, `WHERE`, auditoria), não mexe em
backend, não tem migration e não substitui o botão Limpar. Não inclui busca no
painel (gatilho acima) nem "Selecionar tudo" com estado intermediário por grupo.

## Lote V3.7.2 — Os dois movimentos na mesma matriz (feito em 27/ago/2026)

Mapeado e **autorizado no mesmo dia**, 27/ago/2026: *"pode seguir com o próximo
lote, para já fazermos tudo junto"*. As cinco decisões que o mapeamento copiou do
artefato entraram como estavam; o que a execução mudou está marcado como correção
mais abaixo, e não reescrito por cima.

### De onde veio, e por que ele reabre uma decisão fechada

Pedido da Maria em 27/ago/2026: *"queria incluir também a visualização das 2
movimentações juntas, entrada e saída"*.

Isso **contraria uma decisão escrita** no V3.2, e o texto ainda está no
`catering/consulta/matriz.py`: *"não existe visão conjunta, porque a hierarquia
das duas é diferente (a saída tem o nível `faixa`) e as medidas não são
comparáveis linha a linha. Unir viraria uma tabela que não responde nenhuma das
duas perguntas."*

Essa decisão não estava errada — estava **incompleta**. Ela mediu o custo de unir
as duas árvores *preservando os dois desenhos inteiros*, e nessa forma a conclusão
continua valendo. O que faltava era a saída que o artefato de 21/ago já tinha
achado: **na visão conjunta a árvore fica MAIS CURTA, e não mais longa.** A
operação sai, a faixa deixa de ser nível, e o que sobra é
`unidade → cliente → movimento` — os mesmos três níveis das outras duas visões.

O que desbloqueou foi evidência, não opinião: a Maria mandou o print do artefato
(27/ago/2026), que é a **única** forma de conferir o formato — o artefato foi
apagado em 24/ago e não existe mais em disco.

### As cinco decisões que o artefato já tomou

Copiadas do print, não re-discutidas.

1. **Hierarquia `unidade → cliente → movimento`.** Dentro do cliente, duas
   linhas: Expedição e Recebimento.
2. **O pai é a soma dos dois, e o nome dele é "movimentação"** — *"que é como o
   BI lê a matriz"*. Confere no print: SAPORE em jan/26 = 3.907,7 (Expedição) +
   3.934,4 (Recebimento) = 7.842,0; e os 26.892,9 da RMSPII comportam os
   13.153,8 t de entrada que o V3.7 mediu no mesmo mês.
3. **A operação NÃO abre nesta visão, e a tela declara isso** — *"Tipo de
   operação não abre aqui: veja num movimento só"*. É esta decisão que dissolve
   o obstáculo do V3.2: o nível desigual **some**, em vez de duas árvores de
   tamanhos diferentes serem reconciliadas.
4. **A faixa deixa de ser nível da árvore e vira botão**, com outro rótulo e
   outra pergunta: *"A expedição entra como: Solicitado / Atendido / Separado"*
   — isto é, **qual das três colunas da expedição entra na soma**. Hoje o rótulo
   é "Faixa da expedição" (`catering/web/matriz.html`) e `faixa` é um nível da
   árvore da saída. O rótulo do artefato é mais preciso e vale adotar.
5. **Terceiro estado no botão de movimento**: `Entrada | Saída | Entrada + saída`.
   Acrescenta, não substitui — as duas visões de hoje ficam como estão.

### O arredondamento, que o print entrega de graça

3.907,7 + 3.934,4 dá 7.842,**1**, e o artefato mostra 7.842,**0**. Ele somou o
**kg cru** e arredondou **uma vez**, no fim. Somar filhos já arredondados faria o
total da tela divergir do download do V3.3 em um dígito — e divergência de um
dígito é justamente a que ninguém investiga. Bate com a regra da V3 ("valor cru
na API, formatação na tela") e entra como teste do lote.

### Três pontos que o artefato não resolvia (resolvidos mais abaixo)

1. **Pallets.** `LENTES["pal"]["exp"] = None` — a expedição não tem pallet. Em
   "Entrada + saída" a soma daria **exatamente a entrada**, rotulada
   "movimentação": número certo com nome errado, que é pior que erro visível.
   **Recomendação:** desabilitar "Entrada + saída" quando a medida é Pallets,
   pelo mesmo mecanismo que já desabilita Pallets na Saída.
2. **O filtro de Operação.** Ele é *por movimento* hoje
   (`OPCOES.operacoes[movimento]`), e as duas listas são diferentes. Numa visão
   conjunta, filtrar por uma operação que só existe na entrada **zeraria a linha
   de Expedição em silêncio**. Ou ele se desabilita junto com o nível, ou vira
   dois filtros.
3. **A soma acumula os dois vieses, em direções opostas.** A entrada não tem guia
   cancelada nenhuma na fonte (faltam 11.204,8 t medidas em jan–jun/26); a
   expedição tem cancelada com peso no solicitado (4.530,9 t, ~3%). As duas
   limitações já estão declaradas separadas na tela — o total "movimentação"
   precisa dizer que carrega as duas.

### Custo, e o que ele não é

Nenhuma migration, nenhuma tabela nova, nenhuma coluna nova. No backend, um
terceiro valor aceito em `movimento` e uma entrada a mais em `HIERARQUIA`; a soma
é feita em **Python**, sobre as duas consultas que já existem, e **não em SQL** —
unir as duas tabelas num `UNION` traria de volta exatamente o problema que a
decisão 3 remove.

> **Correção de duas coisas que este mapeamento errou** (escritas na execução,
> 27/ago/2026, para não parecerem esquecimento):
>
> 1. **A planilha e o download NÃO entram, e a versão anterior deste texto dizia
>    o contrário** ("o lote inclui os três, ou não fecha"). O raciocínio estava
>    invertido. É verdade que os três compartilham o recorte por construção
>    (`recorte.de_para_where()`), mas o que a conjunta muda não é o **recorte** —
>    é de **quantas tabelas** as linhas vêm. E aí a simetria acaba: a Matriz
>    **agrega**, e por isso pode somar; a planilha mostra **linha crua** e o
>    download leva a **linha inteira**. Unir linha crua de 36 colunas com linha
>    crua de 46 não encurta nada — é a união incoerente que o V3.2 recusou, e ela
>    continua recusada. Os dois passam a **recusar com 400** em Entrada + saída,
>    com a mensagem dizendo o que fazer, e a tela desabilita os controles antes
>    de a pessoa clicar.
> 2. **O contador da paginação não ganhou o terceiro termo** (`2 movimentos`, como
>    no print). Ficou de fora por não carregar informação: o número de movimentos
>    é sempre 2 nessa visão. Registrado aqui para a próxima leitura do print não
>    achar que faltou algo.

### As três decisões abertas, resolvidas pelo lado conservador

A Maria autorizou o lote dizendo *"se precisar de alguma decisão deixe pra
depois"*. As três foram então resolvidas pela opção que **não deixa número errado
na tela**, e as três são reversíveis sem retrabalho — o caminho oposto de cada
uma é uma decisão de produto, não uma reescrita.

| ponto | o que ficou | o que a alternativa exigiria |
|---|---|---|
| **Pallets** | Em Entrada + saída, Pallets **recusa** com aviso próprio ("o total seria apenas a entrada com o nome de movimentação"), e o botão fica desabilitado na tela | Mostrar a entrada sozinha rotulada "movimentação" — número certo com nome errado |
| **Filtro de operação** | **Recusado com 400** na conjunta, e o filtro é limpo e desabilitado na tela ao entrar nela | Virar dois filtros (um por movimento), que é decisão de produto |
| **Os dois vieses** | Entram como **aviso na tela**, dizendo que a soma acumula os dois e que eles apontam para lados opostos | Nada — este era o único dos três que já tinha resposta |

O motivo de a operação recusar em vez de simplesmente filtrar: as duas listas de
`descr_oper_wms` não coincidem, então filtrar por uma operação que só existe na
entrada **zeraria a linha de Expedição em silêncio**, com o total da
"movimentação" virando só a entrada. Recusar alto é a única saída honesta.

### O que a execução provou (27/ago/2026)

**O aceite é aritmético, e ele fecha em duas igualdades.**
`test_conjunta_soma_os_dois_e_cada_filha_bate_com_a_visao_de_um_movimento_so`:
para cada (unidade, cliente, mês), o nó pai é **exatamente** a soma das duas
filhas — no cliente, na unidade e no total do recorte — e cada filha é
**idêntica** ao que a visão de um movimento só devolve no mesmo recorte. Se a
primeira falhar, o total mente; se a segunda falhar, a conjunta e a visão simples
discordam sobre o mesmo dado e as duas ficam sem credibilidade.

Os valores do teste são **assimétricos de propósito** (140 na entrada, 100 na
saída): com 100 e 100 uma troca de lado passaria batido. E fevereiro tem só
entrada, porque o mês em que um dos dois lados não existe é onde a soma erra com
mais facilidade.

Os outros sete testes novos: a faixa trocando quem entra na soma (240 / 220 /
210, sem virar nível), a recusa do filtro de operação, a recusa do Pallets, a
trava estrutural do `de_para_where` (que é o que protege planilha e download), o
terceiro movimento **não** estando em `contrato.MOVIMENTOS`, a recusa 400 dos
dois endpoints — incluindo **não deixar registro de auditoria de um download que
não saiu** — e as opções da API declarando os três movimentos.

**Suíte da V3: 285 testes, verdes, 5min23.**

**Um teste existente cobrou uma dívida, e essa é a melhor parte.**
`test_hierarquia_e_configuravel` afirmava que todo nível de `HIERARQUIA` é
`FAIXA` ou está em `NIVEL`. Com o `movimento`, a exceção solta virou **duas** —
então ela deixou de ser exceção e passou a ser lista: `matriz.FORA_DO_SQL`. O
defeito que isso evita é dos piores: nível novo que escape dos dois desalinha os
índices de `chave_0..n` na leitura do resultado, o que **não levanta erro** — só
troca rótulo de lugar.

**A tela foi provada fora do navegador**, com o mesmo harness descartável em node
do V3.7.1: 28 asserções nos limites da visão conjunta — a operação sendo
**limpa** (e não só desabilitada, senão o primeiro pedido sairia com um filtro
que o servidor recusa), a saída forçada da Planilha, os dois botões de download
desabilitados com a nota trocada, o Pallets desabilitado, o rótulo da faixa
mudando de "Faixa da expedição" para "A expedição entra como", e tudo voltando ao
normal ao escolher Entrada de novo.

### O aceite contra dado real, e a lição que ele repetiu

Rodado em 27/ago/2026 contra os CSVs de 21/ago carregados no banco local (36.300
linhas de recebimento e 42.468 de expedição), no recorte jan/26.

**As duas igualdades do aceite fecharam em TODAS as 20 células**
(unidade × cliente) — o pai igual à soma exata das duas filhas, e cada filha
idêntica à visão de um movimento só. E `total_linhas` da conjunta = 10.644 =
4.773 da entrada + 5.871 da saída.

**Os valores absolutos NÃO batem com o print, e eu escrevi antes que eles
deveriam.** Estava errado, e o erro é exatamente o que este documento já avisava
para o V3.2: *"o aceite nunca foi o artefato"*. O artefato agrega por
**`data_solic`** e a aplicação agrega por **`nk_calendario`** (decisão A-5, da
Maria em 24/ago: *"conta como expedida em fevereiro. Calendário."*).

Medido, e é a primeira vez que esse par é medido nesta célula:

| SAPORE S.A, jan/26 | por `nk_calendario` (V3) | por `data_solic` (artefato) | o print mostra |
|---|---|---|---|
| Expedição (solicitado) | 3.995,0 t | **3.907,7 t** | 3.907,7 |
| Recebimento | 3.936,1 t | **3.934,4 t** | 3.934,4 |
| movimentação | 7.931,1 t | **7.842,0 t** | 7.842,0 |
| RMSPII, movimentação | 26.821,2 t | — | 26.892,9 |

Ou seja: **o print bate à casa decimal quando a agregação é a dele.** Isso é mais
forte do que "os números diferem" — prova que é o mesmo dado por baixo e que a
única diferença é a data de agregação, que é decisão fechada e não defeito.

**E o arredondamento se confirmou no dado real.** Os kg crus por `data_solic` são
3.907.660,404 (expedição) e 3.934.384,147 (recebimento):

- arredondando cada filho e somando: **7.842,1** — não é o que o print mostra;
- somando o cru e arredondando uma vez: **7.842,0** — é exatamente o print.

A decisão de somar em kg e deixar a tela arredondar uma vez não era estética:
era a diferença entre reproduzir o artefato e divergir dele num dígito.

**O navegador — validado pela Maria em 27/ago/2026**, na mesma rodada do V3.7.1
e sobre o mesmo dado. Os dois harnesses em node provam a lógica; a tela quem
provou foi ela. Nenhum defeito reportado.

**O que fica declarado mesmo com o aceite:** os números da conjunta na tela local
são os do `nk_calendario`, então **não** conferem com o print do artefato — a
diferença é a A-5, medida na tabela acima. Quem for comparar a tela com o print
depois vai reencontrar essa divergência, e ela não é defeito.

### O que este lote NÃO faz

Não mexe no recorte (período, dia do mês, `WHERE`, auditoria), não tem migration,
não abre operação nem tipo de estoque na visão conjunta, não a leva para a
planilha nem para o download (ver a correção acima), e **não inclui saldo
(`Entrada − Saída`) nem estoque**. Saldo ficou fora **por decisão**: o resultado
não é estoque — falta o saldo inicial, e a subtração herda os dois vieses em
direções opostas, então ela parece um saldo e não é. Estoque é a
`FATO_VOL_EST_CAT_V01`, que pelo A-8 é lote próprio.

## Lote V3.7.3 — Desmarcar tudo (feito em 27/ago/2026)

Autorizado em 27/ago/2026: *"vamos implementar o filtro de selecionar tudo e ficar
tudo desmarcado ou tudo marcado"*.

### De onde veio, e o que eu tinha errado

Olhando a tela do V3.7.1 recém-implantada, a pergunta da Maria foi: *"poderíamos
clicar no selecionar tudo, pra des-selecionar tudo?"*

**Isso não era conveniência faltando, era defeito.** No V3.7.1, para ver **um**
cliente entre 14 era preciso desmarcar 13, um por um — porque desmarcar em "Todos"
significa "todos menos este", e não havia como partir do zero. Com o desmarcar
tudo, o mesmo recorte são **2 cliques**. Eu otimizei a coisa errada.

O que me levou a desabilitar o botão no V3.7.1 estava certo pela metade: no
backend, **"nenhum selecionado" e "todos" são o mesmo estado** — lista de filtro
vazia = nenhuma cláusula no `WHERE`. Então desmarcar tudo mostraria zero caixas e
uma Matriz com tudo dentro: a tela mentindo sobre o próprio recorte. A decisão 2
do V3.7.1 protegia isso.

**O que eu não tinha visto:** o painel não aplica nada na hora. Marcar caixa só
mexe no `<select>` escondido, e quem recarrega é o **Aplicar**
(`matriz.html`, `$('#aplicar').onclick`). Então "nenhum marcado" pode existir como
estado de **edição**, que nunca chega ao servidor — e aí não existe número errado
para a tela mostrar. A proteção continua valendo; ela só não precisava custar o
botão.

### Os três estados

| selects | flag `vazio` | rótulo do botão | vai na URL | dá para aplicar |
|---|---|---|---|---|
| seleção vazia | `false` | **Todos** | nada | sim |
| seleção vazia | `true` | **Nenhum selecionado** | nada | **não** |
| com itens | sempre `false` | *nome* ou *N selecionados* | os itens | sim |

O `vazio` mora no **widget**, e não no select. Guardar isso dentro do select
exigiria uma opção sentinela, que contaminaria `parametros()`, a auditoria e a URL
do download — exatamente o que o desenho do V3.7.1 protegia. O widget é a camada
de interface, e é onde um estado de interface pertence.

### Uma mudança de comportamento em relação ao V3.7.1, e ela é deliberada

**Desmarcar o último item selecionado agora para em "Nenhum selecionado"**, em vez
de saltar para "Todos". No V3.7.1 esse salto era a única saída possível (o estado
não existia), mas ele fazia o painel fazer o **contrário** do clique: a pessoa
desmarca uma caixa e todas as 14 se marcam. Agora existe um estado que descreve o
que ela fez.

### A trava, e por que ela mora no `carrega()`

"Nenhum marcado" não pode virar consulta. A trava está no `carrega()`, e não no
`onclick` do Aplicar, porque **quatro caminhos diferentes recarregam a tela**: o
Aplicar, a paginação, e a troca de movimento / medida / faixa / visão. Um `if` no
Aplicar deixaria os outros três passarem, e o furo apareceria só quando alguém
paginasse com um filtro pendente.

O **download tem guarda própria**, porque ele *navega* em vez de usar `fetch` —
`carrega()` não roda nesse caminho. Sem ela, o arquivo sairia com o recorte
inteiro enquanto o painel mostra zero caixas marcadas.

A recusa **nomeia o filtro** (`Cliente`, `Dia do mês`…), e o nome vem do próprio
`<label>` do campo, lido na montagem do widget. Recusa que não diz qual filtro
está pendente manda a pessoa abrir os cinco.

### `zeraCaixa()`, e os três lugares que precisam dele

Voltar para "Todos" é limpar a seleção **e** sair do estado vazio — duas coisas,
então virou função. Os três chamadores:

1. **Limpar** — tem que devolver a tela que a pessoa recebeu, e ela não recebeu um
   filtro pendente;
2. **troca para Entrada + saída** — o filtro de operação é limpo e desabilitado
   ali (V3.7.2), e deixar o estado vazio pendurado nele travaria o Aplicar num
   filtro que a pessoa não pode nem abrir;
3. **`preencheOperacoes()`** — quando a lista de operação é refeita ao trocar de
   movimento. Este é o mais sutil: "nenhum marcado" sobre uma lista de opções que
   deixou de existir não significa nada, e travaria o Aplicar sem a pessoa ter
   como desfazer, porque o filtro que ela precisaria mexer nem mostra mais os
   mesmos itens.

### O que prova este lote

**38 asserções** no harness em node, contra o código real do `matriz.html` — os
três estados, as duas transições do "Selecionar tudo", o ganho de 13 cliques para
2, a trava do `carrega()` escrevendo a mensagem com o nome do filtro, a mudança de
comportamento do último item, o Limpar e os três `zeraCaixa`.

**As 28 asserções do V3.7.2 continuam verdes** com o código novo — a visão
conjunta não regrediu.

**Suíte da V3: 285 testes, verdes** — o mesmo número de antes, que é o ponto:
nenhum arquivo de backend foi tocado.

Duas falhas do primeiro run foram **do harness, não do código**: `option.selected`
nascia `undefined` no DOM falso (no navegador é sempre booleano) e o
`classList.toggle` do shim tinha regex errada. Registrado porque é a armadilha
óbvia desse tipo de prova — um shim frouxo mede o shim.

**O navegador — validado pela Maria em 27/ago/2026** ("validado"), no caminho C
com os CSVs de 21/ago recarregados. Nenhum defeito reportado. Isso cobre o que o
harness não podia: o painel abrindo no lugar certo e o amarelo de pendência sendo
legível — aprovação estética é humana por regra
(`memory/validar-tela-no-navegador.md`).

**O ciclo dos três lotes de hoje vale registrar como método**, porque ele se
repetiu: o V3.7.1 passou por suíte verde e por 22 asserções de harness, e o
defeito de interação (13 cliques para isolar um cliente) só apareceu quando a
Maria usou a tela. Nenhuma das duas provas podia achá-lo — a suíte não vê
interação, e o harness só verifica o que eu pensei em verificar. **Lote de tela
não fecha sem alguém usando a tela**, e aqui a prova disso é que o V3.7.3 existe.

### A alternativa que ficou fora, e por quê

Tratar "nenhum marcado" como filtro que não casa com nada, deixando a Matriz
vazia — que é o que o Power BI faz. Isso exigiria um conceito de **conjunto
vazio** no backend (`WHERE` que não casa), na auditoria e na URL do download. E
"Matriz vazia" não é uma tela que alguém quer ver: o valor de desmarcar tudo está
em ser **passo intermediário**, não resultado. Se algum dia a operação pedir o
comportamento do BI de verdade, aí é lote próprio, com o sentinela declarado.

### O que este lote NÃO faz

Não toca em backend, não tem migration, não mexe no recorte nem na visão conjunta,
e não junta raízes de CNPJ (a pergunta do CUCINARE/FLV 7 do mesmo dia ficou
**fora por decisão da Maria** — *"vamos ignorar esse dos 2 clientes por
enquanto"*; a medição está no fim desta seção).

### A medição do CUCINARE / FLV 7, guardada para quando o assunto voltar

Perguntado em 27/ago/2026: os dois aparecem como clientes separados na Matriz e
deveriam ser um? **Medido nos CSVs de 21/ago — são duas raízes de CNPJ
diferentes**, cada uma com uma grafia só:

| razão social | raiz | CNPJ completo | peso jan–ago/26 |
|---|---|---|---|
| CUCINARE PRO ALIMENTAÇÃO LTDA | `04596502` | `04596502003365` | 8.643,5 t |
| FLV 7 RESTAURANTES LTDA. | `40720488` | `40720488000227` | 804,3 t |

Não é falha da canonização: ela une **grafias da mesma raiz**, e aqui não há o que
unir. A tela mostra dois porque a decisão de 21/ago diz *"nenhuma raiz é unida a
outra. O Power BI mantém as raízes separadas, e inventar união aqui afastaria os
dois lados"* (`catering/dominio/clientes.py`).

Duas notas para quem retomar isso:

1. **O número conjunto já está na tela** — a linha da unidade e o "Total do
   recorte" somam os clientes do recorte. Falta o rótulo, não a soma.
2. **A `memory/nivel-unidade-vs-filial-e-cliente-cnpj.md` registra FLV↔CUCINARE
   como troca de nome conhecida**, com 1.003 linhas em que o nome discordava do
   CNPJ — mas isso foi medido no **DataHub**. No **DW** está limpo: cada nome cai
   numa raiz só. A confusão da fonte antiga não é a causa do que se vê hoje.
3. Se o rótulo for pedido, o desenho **não** é fundir as raízes: é um nível novo
   (`unidade › grupo › cliente › movimento`), para o grupo somar e a raiz
   continuar batendo com o BI. Fundir destruiria o segundo.

## Lote V3.8 — Histórico completo do DW (executado em 27/ago/2026 — metade entrou)

Autorizado em 27/ago/2026: *"agora quero trazer os dados full da tabela do dw"*.
**O código está pronto; a execução na VM é da Maria** — procedimento numerado em
`docs/DEPLOY.md`, seção "V3.7 + V3.8".

**Executado em 27/ago/2026, e entrou metade:** o recebimento carregou inteiro e a
expedição travou numa linha só. O que aconteceu está no "Aceite do V3.8" no fim
desta seção; o conserto é o **V3.8.1**, a seção seguinte.

### A decisão que inverte a de 25/ago, e por que não é contradição

Em 25/ago a Maria recortou o escopo em 2026, com o DW recém-reconstruído: *"o
certo é a gente só pegar de 2026 pra frente"*. Dois dias depois pediu o oposto. O
que mudou entre as duas decisões **não foi opinião, foi a tela**: o V3.7 fez ela
abrir em janeiro do ano corrente. Sem isso, guardar 2023 significaria abrir a
Matriz com **44 colunas** para responder uma pergunta que ninguém fez — e era
exatamente esse o custo que a decisão de 25/ago estava evitando.

Guardar histórico e escolher onde começar a olhar passaram a ser decisões
separadas, e é por isso que são **duas variáveis**: `DW_ANO_MINIMO` (o piso da
carga) e `CAT_ABERTURA_DE` (a abertura da tela). A confusão entre as duas é o
erro mais provável de quem mexer nisso depois, e está escrita nos dois lugares.

### A ordem que não pode inverter

**O V3.7 tem que estar na VM antes de o histórico entrar.** Como os dois vão na
mesma imagem, um deploy resolve — o piso só age no momento da carga, então a
sequência é build → `up -d` → sondagem → carga cheia. Se o histórico entrasse
antes, a tela abriria em 01/2023 até alguém perceber.

### A trava: a chave natural sobre 434 mil linhas

O passo que autoriza a carga não é a carga, é a **sondagem com o piso novo**:

```
docker compose run --rm nuvem-cat python -m catering.carga --fonte oracle --sondar
```

`chave de hoje` tem que sair **UNICA** nas duas tabelas. Se repetir, **para** — o
upsert funde medidas em silêncio quando duas linhas da fonte escrevem na mesma
linha nossa, e o assunto passa a ser identidade, não período.

Há base para esperar que passe: a chave de sete colunas (migration 0023, com
`ano_solic`) foi medida única sobre **201.848 e 231.886** linhas em 25/ago. Mas a
sondagem mede identidade **dentro da janela**, e a janela era 2026 — então a
medição de hoje é 2026, não o histórico. Este lote está literalmente executando a
instrução que o V3.5 deixou escrita: *"quem quiser saber se a chave aguenta um
período maior baixa o `DW_ANO_MINIMO` e roda o sondar de novo, que é o fluxo
certo antes de ampliar a janela"*.

### O que mudou no código (pouco, e um teste inverteu de sentido)

| arquivo | mudança |
|---|---|
| `catering/contrato.py` | `ANO_MINIMO_PADRAO` 2026 → **2023**, com as duas decisões e o motivo da virada |
| `catering/carga/fonte_oracle.py` | docstring do `WHERE` (o piso vale em toda rodada, e por que isso importa) |
| `docker-compose.yml`, `.env.example` | padrão 2023, e a distinção contra `CAT_ABERTURA_DE` |
| `tests/test_catering_carga.py` | `LINHAS["exp"]` 42.318 → **42.468**, `FORA_DA_JANELA` zerado, e o teste do piso reescrito |
| `tests/test_catering_oracle.py` | binds do piso (2026 → 2023) e três docstrings |

**Sem migration.** O schema não muda: o piso é `WHERE`, não coluna.

**O teste que inverteu, e por que ele continua sendo o mesmo teste.** As **150
linhas de dez/2025** da expedição eram o número-sentinela que denunciava piso
mexido sem querer. Com o padrão em 2023 elas passam a **entrar**, então o teste
deixou de provar "o piso corta" e passa a provar duas coisas: que o padrão traz o
arquivo inteiro, **e** que `DW_ANO_MINIMO=2026` volta a cortar exatamente aquelas
150. O número continua guardado, agora nas duas direções — número medido que sai
de um teste sem substituto é como uma regressão fica invisível.

A `FonteCSV` aplica o mesmo piso da `FonteOracle`, de propósito (V3.5): se as
duas recortassem diferente, comparar uma com a outra deixaria de provar qualquer
coisa. É por isso que uma decisão sobre o DW mexe num teste de CSV.

### O que este lote NÃO faz

Não roda a carga (é da Maria), não instala o cron de backup (está no
procedimento como recomendação, e continua sendo decisão dela), não mexe na tela
e não tem migration. E **não** constrói a varredura de PKs para linha removida na
fonte: o time do DW confirmou em 25/ago que o processo só insere e atualiza, só
guia confirmada entra e não existe desconfirmar (ver "Incremento" no contrato
fechado). O gatilho que traria isso de volta é o WMS passar a permitir cancelar
guia já confirmada.

### Consequências declaradas — nenhuma é defeito

1. **Rótulo de cliente pode mudar.** `cat_clientes` escolhe a razão social pela
   grafia de **maior peso**, recalculada sobre 3,6 anos em vez de 8 meses.
2. **Filtros ganham entradas antigas** — unidade, cliente e operação que
   existiram em 2023–2025, e possivelmente nomes de estoque novos em
   `NAO_CLASSIFICADO` (a pendência 2 do V3.6 cresce).
3. **As 16 linhas com `data_solic` impossível** (2105, 2002, 2005) voltam para o
   banco: o movimento delas é 2024/2025. A Matriz não muda (agrega por
   `nk_calendario`); elas aparecem na planilha e no download. **Decisão em
   aberto** desde o V3.5: se a planilha deve declará-las.
4. **O xlsx recusa o período inteiro** (434 mil > teto de 150 mil) e o CSV passa
   a **pedir confirmação de verdade**. As duas guardas do V3.7 estreiam com
   volume real — até aqui foram exercitadas com o teto baixado na página.
5. **2023–2025 entra sem aceite célula por célula.** Não existe CSV de referência
   para o histórico; a conferência possível é contagem e total por ano. O aceite
   do V3.2 e o do V3.7 cobriram 2026, e continuam valendo para 2026.
6. **Rebuild da tabela no DW passa a custar mais.** Quando o DW reconstrói, todo
   `dw_data_alteracao` sobe e o "incremental" vira carga cheia sozinho: ~3 min em
   vez de ~30s, numa rodada que ninguém está olhando. É seguro (o upsert não
   apaga, a chave natural sobrevive), só não é incremental.
7. **O banco de produção continua sem backup automático.** É a única pendência
   com risco real do V3.6, e este lote multiplica por 5,5 o que está em risco. O
   passo 1 do procedimento é o backup, e a linha do cron está lá para ser
   instalada na mesma janela.

### Suíte

```
python -m pytest tests/test_catering_*.py tests/test_migracao.py
```

**270 testes, ~6min20, verde** (27/ago/2026) — mesmo número do V3.7: este lote
mudou o valor de constantes medidas e o sentido de um teste, não a quantidade.

### Aceite do V3.8 — executado em 27/ago/2026, e entrou metade

A Maria rodou o procedimento. O deploy subiu (V3.7 e V3.8 na mesma imagem), a
sondagem liberou, e o `MODO=completa` fez:

| tabela | status | lidas | inseridas | atualizadas |
|---|---|---|---|---|
| recebimento | `ok` | 202.087 | 165.170 | 0 |
| expedição | **`erro`** | 0 | 0 | 0 |

**As 36.917 linhas que a conta não fecha são as iguais**, não linhas perdidas:
202.087 − 165.170 são as de 2026 que já estavam no banco e voltaram byte a byte
idênticas, e o `WHERE ... IS DISTINCT FROM` do upsert não as conta como
atualização (é a decisão do V3.1 funcionando — update incondicional reportaria
36.917 atualizadas em toda rodada e esconderia mudança real).

A expedição morreu na linha 143.410 da fonte:

```
coluna 'sk_cliente' e obrigatoria no contrato e veio vazia (None)
chave: SLIN_RMSPII_PRD/RMSPII/0000003623/2025/SECO 2018/
       ACERTO DE ESTOQUE - SEM CUSTO/24216040
```

Três consequências, e nenhuma é perda de dado:

1. **rollback, não carga parcial.** A expedição ficou exatamente como estava (só
   2026, da rodada das 07h05). É a decisão de 24/ago funcionando: o upsert não
   apaga, então o custo de uma falha é frescor, não furo;
2. **as dimensões não rodaram** — a ordem é recebimento → expedição → dimensões, e
   a rodada parou antes. Cliente, unidade e nome de estoque que só existem em
   2023–2025 ainda não têm linha canônica. A tela **não esconde nada** por isso:
   os joins são `LEFT` com `COALESCE`, então aparece o valor cru da fonte (raiz
   de CNPJ em vez da razão social);
3. **a tela abriu em 2026**, como o V3.7 prometeu — então a assimetria (recebimento
   com histórico, expedição sem) só aparece para quem filtrar para trás.

A metade que faltava entrou no mesmo dia, depois do V3.8.1 — ver o aceite dele.

## Lote V3.8.1 — A linha sem cliente, e a trava que não media contrato (executado em 27/ago/2026)

Autorizado em 27/ago/2026, depois da medição: *"só as duas"*.

### O achado: uma linha em 232.089

A carga para na **primeira** linha ruim, então o erro dizia uma coluna e não
dizia quantas. A medição — as 29 colunas obrigatórias das duas tabelas, na janela
inteira, só leitura — respondeu:

| tabela | linhas na janela | obrigatória vindo vazia |
|---|---|---|
| recebimento | 202.087 | **nenhuma** |
| expedição | 232.089 | `sk_cliente` em **1**, `nk_wms_cliente` em **1** (2025) |

Mesma linha: `ACERTO DE ESTOQUE - SEM CUSTO`. Acerto de estoque não tem cliente
do outro lado, e o DW não resolveu nem a surrogate nem o código do WMS.

### A decisão, e a regra que ela fecha

As duas colunas passam a aceitar nulo (migration 0024). O que decide não é o
tamanho do problema, é o papel das colunas:

- **`sk_cliente` é procedência.** Nenhuma consulta da V3 lê `sk_*`;
- **`nk_wms_cliente` é o código do cliente no WMS.** Nenhuma tela o lê — a tela
  junta cliente por `nk_cliente`, que nessa linha **veio preenchido**. Identidade
  e exibição ficam intactas.

A regra que sai disso está escrita no `contrato.py`: **obrigatória é a coluna sem
a qual a linha não pode ser identificada nem colocada na tela** — as sete da
chave natural, o `nk_calendario` que a Matriz agrega e o `dw_data_alteracao` que é
a marca d'água. Fora dessas, vazio na fonte é **fato**, e derrubar a rodada por
causa de uma célula que ninguém lê troca um dado ausente pela indisponibilidade
de tudo.

Três alternativas descartadas, com o motivo:

| alternativa | por que não |
|---|---|
| pular a linha e seguir | é carga parcial com outro nome: a Matriz mostraria um número quase certo e ninguém saberia o que falta |
| estreitar o piso de volta para 2026 | perde o histórico, que é o que foi pedido |
| afrouxar a classe inteira (as cinco `sk_*`) | apaga cinco alarmes que hoje funcionam para resolver um problema que a trava nova passa a pegar **antes** da carga |

### O furo era do procedimento, não da fonte

A trava do V3.8 provava **identidade** na janela nova (`chave de hoje` UNICA) e
não provava **preenchimento**. Ampliar a janela é ampliar o contrato inteiro, e a
nulabilidade tinha sido medida nos CSVs de 21/ago, que tinham um ano só — o mesmo
erro de raciocínio que a 0023 registrou sobre a unicidade da chave, na mesma
semana e pela mesma causa.

Por isso o lote não é só a migration: o **`--sondar` passa a medir preenchimento**
e a dizer `PARE` quando uma obrigatória vem vazia. Uma varredura por tabela,
agrupada por ano — o ano é o que localiza o problema, e uma consulta por coluna
furada custaria uma varredura da tabela inteira cada.

A medição cobre **todas** as colunas, não só as obrigatórias: a nulável vazia é a
limitação que a tela declara (guia cancelada sem confirmação, acerto de estoque
sem cliente) e sai na mesma leitura. Sondagem que só mostra o que bloqueia
esconde metade do que se sabe da fonte.

### A evidência já estava no repositório

`docs/CONCILIACAO_POWERBI_V2.md` (10/ago/2026, seção 3.4) mediu e escreveu:

> `NK_WMS_CLIENTE` vem **vazio** no fato para 7/10 clientes (1.497 linhas,
> 40.474 t = 21,1% do peso) — e vazio **também na dim** para os mesmos 7.

Aquilo é a `FATO_VOLUMETRIA`, a tabela que a V2 concilia — **outra** tabela do
mesmo DW. A do catering por acaso tinha a coluna preenchida em 2026, e o
contrato a declarou obrigatória sobre essa amostra.

Isso muda o peso da decisão para melhor: `nk_wms_cliente` nulável não é exceção
para uma linha, é o comportamento **normal** dessa coluna no DW. Se o catering um
dia vier com 20% dela vazia, não derruba mais nada.

E deixa a lição mais afiada do que "não generalizar de um ano": antes de declarar
uma coluna obrigatória, vale procurar no repositório o que já se mediu **dela**,
inclusive em outra tabela da mesma fonte. A evidência estava em casa há duas
semanas.

### O que mudou no código

| arquivo | mudança |
|---|---|
| `catering/contrato.py` | `sk_cliente` e `nk_wms_cliente` nuláveis, com a medição no comentário, e a regra do obrigatório escrita |
| `alembic/versions/0024_cliente_nulavel.py` | `DROP NOT NULL` nas duas colunas, nas **duas** tabelas de fato |
| `catering/carga/fonte_oracle.py` | `sql_vazios()` e `preenchimento()`: a sondagem passa a medir contrato |
| `catering/carga/__main__.py` | seção `preenchimento` na saída do `--sondar` |
| `tests/test_catering_oracle.py` | 4 testes (medida igual à do carregador, bloqueio, soma por ano, escopo) |
| `tests/test_catering_carga.py` | a linha do acerto entrando nas duas tabelas, e a chave natural continuando obrigatória |

**Migration nas duas tabelas de propósito:** `PROCEDENCIA` e `DIMENSOES` são
compartilhadas pelos dois movimentos no contrato, e o teste de schema confere
coluna por coluna contra o catálogo — schema estrito de um lado divergiria do
contrato do outro.

### Consequências declaradas

1. **A linha entra com duas células nulas**, e a sondagem passa a mostrá-la para
   sempre na lista "aceita nulo". Vazio declarado é melhor que vazio consertado;
2. **a sondagem ficou mais longa e custa uma varredura a mais por tabela.** É o
   preço de a trava responder "a carga vai passar?" em vez de "a chave é única?";
3. **medida vazia aparece agora** — as células da guia cancelada de jan/2026, que
   sempre existiram e nunca tinham sido mostradas fora de um teste;
4. **`downgrade` da 0024 falha** se a linha já tiver entrado. É o comportamento
   certo: descer exigiria apagar linha de fato.

### Aceite do V3.8.1 — executado em 27/ago/2026, 11h20

A Maria rodou o procedimento do `docs/DEPLOY.md`. **O histórico completo está em
produção nas duas tabelas.**

Contagem por ano, e ela bate exato com o que a sondagem mediu no DW **antes** da
carga — nenhuma linha de sobra nem de falta:

| | 2023 | 2024 | 2025 | 2026 | soma | medido no DW |
|---|---|---|---|---|---|---|
| recebimento | 48.763 | 56.391 | 60.016 | 36.917 | **202.087** | 202.087 |
| expedição | 53.678 | 64.660 | 70.822 | 42.929 | **232.089** | 232.089 |

As duas rodadas em `cat_cargas`, e cada número diz uma coisa:

| id | tabela | status | lidas | inseridas | atualizadas |
|---|---|---|---|---|---|
| 11 | recebimento | `ok` | 202.087 | **0** | 0 |
| 12 | expedição | `ok` | 232.089 | 189.160 | 0 |

- **o recebimento releu 202 mil e não mexeu em nada.** É a prova de idempotência
  saindo de graça: qualquer inserção aqui seria sinal de identidade instável;
- **as 189.160 da expedição são exatamente 2023+2024+2025** (53.678+64.660+70.822),
  e as 42.929 restantes são 2026 voltando idênticas.

A aritmética também fecha o mistério da rodada que falhou de manhã: no
recebimento, 2023+2024+2025 = **165.170**, que é exatamente o `linhas_inseridas`
da carga 9, e 2026 = **36.917**, que é exatamente as "iguais" dela. Aquela carga
tinha inserido o histórico inteiro e reapresentado 2026 sem tocar nele.

Mais duas provas:

- **`SELECT count(*) FROM cat_fato_expedicao WHERE sk_cliente IS NULL` = 1.** A
  linha do acerto de estoque entrou, com as duas células nulas e a identidade
  inteira. Era ela que custava 3,6 anos de histórico;
- **`visto_em` das três dimensões em `2026-08-27 14:20:56.623951+00`** — mesmo
  microssegundo nas três, o que prova de passagem a decisão do V3.1 de recalcular
  as três numa transação só (dimensão pela metade deixaria a tela com unidade
  nova e cliente velho). Elas ficaram de fora da rodada da manhã, que parou antes.

**O que não foi validado:** a tela filtrada para trás até 2023, mostrando as duas
medidas com número nas colunas antigas — é julgamento humano e continua com a
Maria. E o incremental seguinte (15h05) não foi conferido nesta sessão: o esperado
é `linhas_lidas` na casa dos milhares; 434 mil significaria que o DW reconstruiu
as tabelas (seguro, o upsert não apaga, mas não é incremental).

**A pendência do backup continua aberta** — o passo 1 do procedimento é um backup
manual, e a linha do `scripts/backup.sh` no crontab segue não instalada. Agora com
434 mil linhas atrás dela.

### Suíte

```
python -m pytest tests/test_catering_*.py tests/test_migracao.py
```

## Regras de trabalho

Um lote por vez; validar migrations (upgrade e downgrade), atualizar este
documento, commit isolado, verificação independente por agente separado e
**aguardar autorização da Maria** antes do lote seguinte.

Lote que entrega tela **não fecha por leitura**: abre no navegador, confere o
console e exercita o fluxo. No V3.2 isso achou três defeitos, um deles um
`TypeError` que aparecia no segundo clique.

### Qual suíte roda ao fechar um lote da V3

```
python -m pytest tests/test_catering_*.py tests/test_migracao.py
```

**188 testes, ~4min30, verde** (medido em 25/ago/2026, ao fechar o V3.4), contra
11min37 da suíte inteira. O tempo subiu do V3.3 (98 testes, ~72s) porque o login
custa scrypt de propósito: ~51 ms por hash, e a suíte de segurança cria usuário e
autentica em quase todo teste. É o mesmo custo que torna força bruta caro — pagar
isso no CI é o preço de ter, e não um desperdício a otimizar. A V2 está congelada e a V3 não importa nem altera `backend/` — rodar
os testes dela a cada lote da V3 é pagar 10x no loop de feedback para provar
algo que não mudou.

O `test_migracao.py` **fica**, e é o único que cruza a fronteira de propósito:
as migrations da V3 continuam na mesma cadeia (0019, 0020…) e rodam no **mesmo
Postgres que serve a VM**. Ele é o que prova que a cadeia não quebrou, e o
`test_catering_schema.py` complementa com o assert `"a 0019 mexeu na V2:
{tabela} desapareceu"`. Esse é o risco real que atravessa os dois projetos;
comportamento da V2 não atravessa, porque a V3 não toca no código dela.

A suíte completa continua valendo antes de um deploy (V3.6), quando a fronteira
deixa de ser só o schema.

### As duas falhas da V2 são `xfail`, não vermelho solto

`test_volumetria.py::test_ranking_unidade_declara_quem_ficou_fora_e_por_que` e
`test_volumetria_router.py::test_evolucao_devolve_serie_da_filial` quebraram com
a migration 0018 (`e5805b3`), que passou a exibir 015 e 016 como `RMSPII`.

Estão marcados `@pytest.mark.xfail(strict=True)` com o motivo no próprio teste.
Por que assim, e não das outras duas formas:

- **Não consertados:** em nenhum dos dois o conserto é trocar o valor esperado.
  Um usa a RMSPIII como exemplo de "fora de operação" e ela saiu do universo do
  de-para; o outro semeia no armazém `RMSPIV` e consulta `RMSPII/016`, que agora
  resolve para outra linha de `armazens` — sem refazer a fixture a série volta
  vazia e o teste fica **verde provando nada**, que é pior que vermelho.
  Consertar bem exige re-derivar regra da V2, que é o trabalho congelado.
- **Não apagados:** os dois cobrem funcionalidade viva em produção (o V2.5
  declarar quem ficou fora do ranking, e a rota de evolução). Apagar troca um
  vermelho honesto por uma lacuna invisível.
- **Não deixados vermelhos:** o problema nunca foi "existe vermelho", foi
  **vermelho não declarado** — que treina todo mundo a ignorar vermelho, e
  esconde a primeira regressão de verdade no meio das "conhecidas". O V3.0
  gastou um parágrafo provando que essas duas eram pré-existentes; o V3.1
  repetiu a prova. Esse imposto acaba aqui.

`strict=True` de propósito: se algum dia voltarem a passar, a suíte **grita**
(XPASS vira erro) em vez de aceitar em silêncio. O conserto de verdade, se
valer, é de quem for descontinuar a V2.
