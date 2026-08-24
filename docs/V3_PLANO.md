# V3 — Plano e status

**Este documento é a fonte única do status da V3.** Criado em 24/ago/2026, na
decisão de migrar o artefato de análise para aplicação lendo o DW.

**Nenhum lote da V3 está autorizado.** A divisão em lotes na seção final é
proposta, não plano em execução. Autorização é por lote, como na V1 e na V2.

> **Cuidado com o nome:** `docs/proposta_v3_volumetria.md` **não** é deste
> documento — é a especificação da **V2**, e se chama "v3" por acidente
> histórico. O status da V2 continua em `docs/V2_PLANO.md`.

---

## O que a V3 é

Uma aplicação enxuta que lê volumetria de catering direto do **DW Oracle**, com
carga agendada, e entrega **filtros + Matriz + planilha**. O desenho da tela já
está acordado e validado: é o artefato de análise publicado em 21/ago/2026
(`Documents/analises/radar_recebimento.html`, kit de build em
`Documents/analises/_build_radar`).

**O artefato é a especificação.** É a primeira vez neste projeto que a visão foi
acordada antes de codar — a V1 e a V2 foram escritas descobrindo regra no
caminho, e é daí que vem a maior parte do retrabalho delas. Divergência entre a
aplicação e o artefato é bug da aplicação.

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
| **V3.1** | Carregador contra os CSVs, idempotente por PK, com registro de rodada; suíte nova | não |
| **V3.2** | Filtros + Matriz. **Aceite: mesmo número dos CSVs agregados por `nk_calendario`**, célula por célula — ver ressalva abaixo | não |
| **V3.3** | Planilha aberta (100 linhas, paginação no servidor) + download do recorte em streaming; auditoria de download | não |
| **V3.4** | Login e papéis (admin/visualizador) + auditoria de acesso | não |
| **V3.5** | Troca de `extrair()` para Oracle + agendamento 07h05/15h05 | **sim** |
| **V3.6** | Deploy na VM; desmonte do admin e do linhagem em produção | não |
| **V3.7** | Conciliação contra `FATO_VOLUMETRIA`, com as duas limitações declaradas | não |
| **V3.8** | Laboratório novo, sobre o dado do DW | não autorizado |

**Ressalva sobre o V3.2 — o aceite não é literalmente o artefato.** O artefato
agrega por `data_solic`; a aplicação agrega por `nk_calendario` (A-5). Comparar
os dois direto acusaria diferença onde não há erro nenhum. Então:

- a referência do aceite é **os mesmos CSVs, agregados por `nk_calendario`**,
  célula por célula;
- diferença contra o artefato **no meio do período** é bug e tem que ser
  investigada (os totais mensais batem em ≤1,2% de jan a jul);
- diferença **nas bordas do período** é esperada e é a própria decisão A-5 —
  dez/2025 tem 1.408,8 t por solicitação contra 133,9 t por calendário.

Se em algum momento incomodar apresentar artefato e aplicação com números
diferentes na borda, o artefato pode ser reconstruído por calendário — é uma
linha no `ler_dw_volumetria.py`. Não foi feito: o artefato está publicado e
aprovado como está.

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

## Regras de trabalho

As mesmas da V1 e da V2: um lote por vez; ao final de cada lote rodar a suíte
completa, validar migrations (upgrade e downgrade), atualizar este documento,
commit isolado, verificação independente por agente separado e **aguardar
autorização da Maria** antes do lote seguinte.

Enquanto nenhum lote da V3 estiver autorizado, o `CLAUDE.md` continua
declarando a V2 como fase atual — correto, porque é o que está em produção.
