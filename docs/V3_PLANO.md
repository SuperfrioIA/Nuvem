# V3 — Plano e status

**Este documento é a fonte única do status da V3.** Criado em 24/ago/2026, na
decisão de migrar o artefato de análise para aplicação lendo o DW.

**Autorizados e feitos até agora: V3.0, V3.1 e V3.2** (24/ago/2026). Do V3.3 em
diante a divisão em lotes na seção final é proposta, não plano em execução —
autorização é por lote, como na V1 e na V2.

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
| **Fonte** | Oracle `pdwgener` (`oracleprd-aws.superfrio.com.br:1521`) — `FATO_VOL_REC_CAT` + `FATO_VOL_EXP_CAT`; `FATO_VOLUMETRIA` só para conciliação. São **tabelas inteiras**, sem filtro de extração |
| **Escopo** | **catering = instâncias SLIN**. Volume de outras instâncias (`DISTROMAQ_PRD`, `MDLZ_PRD`, `DISTRO_PRD`, `SEEDS_PRD`, `ATIVA_*`) é outro negócio e está corretamente fora. Declarar na tela; guardar a instância como coluna de procedência |
| **Carga** | 2× ao dia: **07h05 e 15h05**. O processo do DW (`catering_to_dw_volumetry_v01`) roda a cada 2h, de 6h35 a 23h35 — lemos 30 min depois, nunca no horário |
| **Incremento** | por **`DW_DATA_ALTERACAO`**, não só `DW_DATA_INCLUSAO` (linha muda entre extrações). Idempotente pela PK. **O DW insere e altera, nunca apaga** — logo não precisa de varredura de PKs para detectar remoção |
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
| A-3 | Usuário `integracao_dados_catering` — pedido em aberto na Valcann. Falta: versão do Oracle (decide se a VM precisa do Instant Client), `service name` x SID, schema/owner das tabelas, política de expiração de senha | Valcann / Maria |
| A-4 | ~~Nome do pacote novo no repo~~ — **decidido em 24/ago/2026: `catering/`**, pelo escopo do negócio e não pela métrica (já existe dado de ocupação e capacidade no projeto, que um dia pode entrar como outra métrica do mesmo escopo) | fechada |
| A-5 | ~~Qual data a Matriz agrega~~ — **`nk_calendario`** (Maria, 24/ago/2026): *"conta como expedida em fevereiro. Calendário."* A data que vale é a do **movimento**, não a do pedido | fechada |
| A-6 | **Parcialmente fechada** (Maria, 24/ago/2026): `CONG` conta como congelado, `RESFRIADO` é classe nova, `AGUA / CARVAO` é seco — implementado, e o não-classificado caiu de 3,2% para **1,3%** do peso. **Segue aberto:** `CONSOLIDADOR` e `CONSOLIDADOR - 14025`, **3.872,5 t**, que são 97% do que restou e não foram perguntados | Maria |

O A-3 é o único que bloqueia lote, e bloqueia **apenas** o V3.5. O A-6 não
bloqueia o schema (a sentinela já existe), mas o resíduo do `CONSOLIDADOR`
aparece na tela como categoria própria até ser decidido.

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
| **V3.3** | Planilha aberta (100 linhas, paginação no servidor) + download do recorte em streaming; auditoria de download | não |
| **V3.4** | Login e papéis (admin/visualizador) + auditoria de acesso | não |
| **V3.5** | Troca de `extrair()` para Oracle + agendamento 07h05/15h05 | **sim** |
| **V3.6** | Deploy na VM; desmonte do admin e do linhagem em produção | não |
| **V3.7** | Conciliação contra `FATO_VOLUMETRIA`, com as duas limitações declaradas | não |
| **V3.8** | Laboratório novo, sobre o dado do DW | não autorizado |

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
   nativo** — o CSV entrega `'25290.217'`, o `oracledb` entrega `Decimal`, e
   os dois passam pelo mesmo funil. Se a fonte já entregasse tipado, cada
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
  período observado mudaria o sentido da coluna. O V3.5 a preenche.
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

**98 testes, ~72s, verde** (medido em 24/ago/2026), contra 11min37 da suíte
inteira. A V2 está congelada e a V3 não importa nem altera `backend/` — rodar
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
