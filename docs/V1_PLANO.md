# V1 — Plano e status

**Este documento é a fonte única do status da V1** (blocos A–G / macro-lotes
V1.0–V1.8). Criado em 30/jul/2026, no Bloco A. Especificação completa de cada
macro-lote: `docs/V1_NUVEM_IA_DIRECIONAMENTO.md` (seção 14); resumo do escopo:
`docs/V1_ESCOPO.md`; critérios de aceite: `docs/V1_CRITERIOS_ACEITE.md`;
arquitetura: `docs/V1_ARQUITETURA.md`.

Histórico anterior (não confundir): `docs/POC_ATUAL.md` (POC DataHub P0–P6,
encerrada em 30/jul/2026) e `docs/PLANO.md` (plano de produto Lotes 0–11/R0–R3 —
nenhum lote de lá autorizado automaticamente; o que a V1 aproveitar de lá entra
pelos macro-lotes daqui).

Regras de trabalho: um bloco por vez; ao final de cada bloco rodar a suíte
completa, validar migrations, atualizar este documento, commit isolado, relatório
de verificação (`docs/V1_RELATORIO_VERIFICACAO.md`) e **aguardar autorização da
Maria** antes do bloco seguinte.

---

## Diagnóstico de partida (30/jul/2026)

Comparação do direcionamento V1 com o repositório real, feita antes do Bloco A:

**O que já existe e é aproveitado direto** — FastAPI + Postgres + Alembic (4
migrations) + Docker Compose na porta 8002; auth de admin; upload manual com
modelos de importação versionados (`modelo_versoes`, imutáveis); linhagem
(`medidas_recebidas`, `medida_linhagem`, origem em `medidas`); catálogo semântico
inicial em `metricas` (R3) e catálogo de fontes (`catalogo_fontes`/`catalogo_colunas`);
motor de scores; cliente Graph somente leitura + inventário do DataHub em cache +
leitura validada de `ENTRADA_MERCADORIAS` + 5 KPIs auditáveis + resumo
determinístico + página da nuvem (`/nuvem`). Suíte de 150 testes com Postgres real.

**Lacunas que os blocos B–G atacam** (nenhuma é do Bloco A):

| Lacuna | Evidência | Bloco |
|---|---|---|
| Catálogo semântico não cobre campo de fonte → conceito canônico (só métricas) | `metricas` (R3) não tem conceito/unidade canônica por campo de fonte | B (V1.1) |
| Nenhuma regra de compatibilidade de unidade; card "Volume total" soma coluna `Volume` sem unidade definida | `kpis_poc.calcular()` soma `Volume` cru | B (V1.2) |
| KPIs do DataHub não persistem: 1 arquivo por vez, recálculo a cada chamada, nada em `medidas` | `entrada_mercadorias.item_mais_recente()` + `GET /kpis` | C (V1.3) |
| Inventário do DataHub em cache de processo (reinício zera) | `inventario_datahub.py` | C (V1.3) |
| Sem Laboratório (telas, perfil determinístico, chat, rastreabilidade) | não existe | D/E (V1.4–V1.6) |
| Sem cockpit com filtros período/filial/cliente, séries e comparações | não existe | F (V1.7) |
| Sem backup rodando, sem rotação de secret do Graph, senha única de admin | risco declarado em `docs/ENTREGA_POC.md` | G (V1.8) |

**Riscos herdados relevantes pra V1** (declarados, não resolvidos pelo Bloco A):
export quebrado do `DADOS_GERAIS` (`_f2` cópia do `_f1`); NF truncada (contagem de
notas não construível — agregar por `GEM`); cabeçalho variável e rótulos repetidos
por família (leitura por posição em `SAIDA_MERCADORIAS`); 711 MB exigem conector
incremental; de-para da filial `002` pendente; client secret do Graph expira em
12 meses sem processo de rotação; devolução dentro do card de valor (decisão
pendente da Maria).

**Migrations**: o Bloco A não muda schema (banco continua em
`0004_catalogo_metricas`). Primeira migration nova prevista no Bloco B (catálogo
semântico).

---

## Status por bloco

| Bloco | Macro-lotes | Status |
|---|---|---|
| **A** | V1.0 — Transição para produto | **feito** (31/jul/2026) |
| **B** | V1.1 Catálogo semântico + V1.2 Compatibilidade de medidas | **feito** (31/jul/2026) |
| **C** | V1.3 Persistência e série histórica | **feito** (31/jul/2026) |
| **D** | V1.4 Laboratório: seleção e perfil | **feito** (02/ago/2026) |
| **—** | Lote de correção: identidade e linhagem do DataHub | **feito** (02/ago/2026) |
| E | V1.5 Laboratório: chat + V1.6 Insight aprovado | a fazer — não autorizado |
| F | V1.7 Cockpit executivo | a fazer — não autorizado |
| G | V1.8 Produção e entrega | a fazer — não autorizado |

## Estado do deploy (03/ago/2026)

A VM (`172.31.49.141:8002`) estava parada em `0004_catalogo_metricas` desde
30/jul — quatro migrations atrasadas. Em 03/ago/2026 subiu tudo e **três
pendências não-código que estavam abertas desde o Bloco A foram fechadas**:

| Pendência | Aberta desde | Fechada |
|---|---|---|
| Subir o código pra VM (`docs/DEPLOY.md`) | Bloco A (31/jul) | 03/ago/2026 — `git pull` + `up -d --build`, migrations `0005`→`0008` aplicadas no startup |
| Aplicar o `UPDATE` de `ativo` das filiais (015 inativa / 016 ativa) | Bloco A (31/jul) | 03/ago/2026 — rodado na VM pela Maria |
| Processar o histórico na VM ("Processar arquivos") | Bloco C (31/jul) | 03/ago/2026 — executado e validado pela Maria |

O `UPDATE` de `ativo` foi a **lição que virou regra**: ficou como passo manual
esquecível por quatro dias porque o seed é insert-only. Desde a migration
`0009_cadastro_filiais` (03/ago), correção de dado de cadastro entra como
migration, não como SQL manual no runbook — migration não esquece.

**Ainda abertas** (não-código): validar o `/nuvem` ao vivo contra o SharePoint
real (se já foi feita, marcar junto desta); decidir devolução/rótulo no card de
valor (`docs/ENTREGA_POC.md`, seção 3); pendências humanas das fontes
(`docs/FONTES_DATAHUB.md`, seção 6), onde entram os **de-paras das unidades
novas** (`CWB3/001`, `SANCA/025`, `RJ/004-*`, `RJ/005-*`) e a filial `002`, que a
Maria manteve pendente em 02/ago; cadastrar os clientes que aparecerem como
pendência no painel.

## Bloco A — V1.0 Transição para produto (feito, 31/jul/2026)

O que o lote entregou, item a item do direcionamento:

- **Documentação criada**: `docs/V1_ESCOPO.md`, `docs/V1_PLANO.md` (este),
  `docs/V1_CRITERIOS_ACEITE.md`, `docs/V1_ARQUITETURA.md`,
  `docs/V1_RELATORIO_VERIFICACAO.md`; direcionamento copiado pro repositório
  (`docs/V1_NUVEM_IA_DIRECIONAMENTO.md`).
- **README e MEMORY atualizados** com a mudança de fase; `CLAUDE.md` aponta a
  leitura obrigatória pra V1.
- **Histórico separado**: os documentos da POC e do plano antigo permanecem onde
  estão (nenhum arquivo movido — links cruzados e memória apontam pra eles), mas o
  README os agrupa como histórico e cada plano antigo aponta pro `V1_PLANO.md`
  como plano ativo. Nada foi removido (regra 19 do direcionamento).
- **Status da Nuvem corrigido**: de "POC encerrada, nenhum lote autorizado" para
  "construção da V1 — Bloco A feito, Bloco B aguardando autorização".
- **Textos de POC removidos das telas ativas**: `nuvem.html` não fala mais em POC;
  a aba "KPIs da POC" do `admin.html` foi removida (ver decisão abaixo).
- **Peso em toneladas**: o card executivo e o detalhamento já estavam em toneladas
  (P5); o texto do resumo executivo, que ainda dizia "milhões de kg", passou a
  dizer toneladas (`backend/services/resumo_poc.py`). Cálculo interno segue em kg;
  conversão é só de exibição.
- **Resumo executivo reorganizado + qualidade e origem separada**: a visão
  executiva vive na página da nuvem (`/nuvem`, família integrada): contexto →
  cards → leitura executiva → detalhamento por cliente → prévia; o bloco
  "Qualidade e origem dos dados" (arquivo, linhas processadas, % válido, peso
  detalhado, sincronização, nota técnica) entrou lá, separado da área principal.
- **Filial 016/RMSPIV revisada**: o seed já estava correto (commit `b6ecec5` —
  015/RMSPIII inativa, 016/RMSPIV ativa); as telas agora exibem a sigla oficial
  junto do código (`016 · RMSPIV`) e o resumo executivo nomeia a filial
  (`016 (RMSPIV)`), usando só o de-para confirmado pela Maria em 30/jul/2026
  (001/015/016 — `memory/filiais-catering-poc.md`). Fonte única do de-para de
  exibição: `backend/services/filiais_datahub.py`, exposto como `filial_sigla`
  nas respostas de `/kpis` e `/nuvem` — não é ingestão; o de-para real do banco
  assume na V1.3. Filial `002` continua só código (de-para pendente).
  **Pendência de VM mantida**: aplicar o `UPDATE` de `ativo` no Postgres de
  produção quando o deploy subir.
- **Limpeza técnica**: consolidada a duplicação do painel de KPIs (dívida
  declarada no P6) — o render saiu do `admin.html` e a visão executiva ficou só
  em `nuvem.html`, que ganhou o detalhamento por cliente e a qualidade/origem que
  só existiam no admin; `formatarMoeda`/`formatarNumeroKpi` foram pro `comum.js`.

**Decisões do lote:**

1. **Painel de KPIs saiu do admin** (era plano B da apresentação da POC; a
   apresentação passou). O admin volta a ser só ferramenta de administração; a
   visão executiva é o produto (`/nuvem`). Caminho já previsto na dívida
   registrada em `docs/ENTREGA_POC.md` ("tirar do admin").
2. **Nenhum arquivo/módulo renomeado ou movido** (`kpis_poc.py`, `resumo_poc.py`
   etc. mantêm o nome): o direcionamento pede pra remover POC das **telas
   ativas**, e proíbe mover arquivo por estética (seção 13). Renomear módulo
   ripple em imports/testes sem valor pro usuário.
3. **Card "Volume total" mantido por ora**, com a ressalva registrada: a coluna
   `Volume` do SLIN não tem unidade definida (decisão 5.3 do direcionamento); o
   destino dele (categoria de unidade, separação ou remoção) é do Bloco B (V1.2)
   e da montagem do cockpit (V1.7). Mesma ressalva pra coluna "Peso bruto (kg)"
   da tabela por cliente — herdada do admin, unidade declarada no rótulo;
   conversão pra tonelada nessa tabela entra na revisão do V1.7.
4. **Texto do resumo em toneladas** substitui a decisão de 30/jul/2026 que mantinha
   "milhões de kg" na frase — o direcionamento V1 é posterior e explícito
   ("a unidade executiva é tonelada").

**Fora do lote (declarado):** persistência/série histórica (C), compatibilidade
de unidades (B), qualquer mudança de schema/migration, deploy na VM.

**Pendências herdadas (não-código), na ordem** — situação atual na seção "Estado
do deploy", no início deste documento; os itens 2 e 3 abaixo foram **fechados em
03/ago/2026**:

1. Validar o `/nuvem` ao vivo contra o SharePoint real (herdada do P5.5; as
   mudanças do Bloco A tornam essa validação ainda mais necessária);
2. ~~Subir o código atual pra VM (`docs/DEPLOY.md`, passo 4.1) **e aplicar o
   `UPDATE` de `ativo` das filiais**~~ (`memory/filiais-catering-poc.md`) —
   **feito em 03/ago/2026**;
3. Decidir devolução/rótulo no card de valor (`docs/ENTREGA_POC.md`, seção 3);
4. Pendências humanas das fontes (`docs/FONTES_DATAHUB.md`, seção 6).

**Suíte**: **154 passed** (150 da POC + 4 novos: peso abaixo de mil toneladas por
extenso, filial com sigla no resumo, filial sem de-para fica sem sigla, de-para de
exibição das 3 filiais confirmadas; asserts de `filial_sigla` acrescentados nos
testes existentes de router e nuvem; os asserts de texto do resumo foram ajustados
de "milhões de kg" pra toneladas — nenhum teste removido).
**Verificação independente**: `docs/V1_RELATORIO_VERIFICACAO.md`.

## Bloco B — V1.1 Catálogo semântico + V1.2 Compatibilidade de medidas (feito, 31/jul/2026)

Autorizado pela Maria em 31/jul/2026 ("pode seguir para o bloco b").

**V1.1 — Catálogo semântico:**

- **Migration `0005_catalogo_semantico`** (aditiva, com downgrade): `unidades`
  (categoria + fator de conversão pra base da categoria; no máximo uma base por
  categoria, por índice único parcial), `conceitos_canonicos` (unidade canônica,
  categoria, agregação, comparabilidade, versão/vigência/status) e
  `catalogo_campos` (mapeamento campo a campo por **posição** no cabeçalho — o
  rótulo `EMB` repete nas posições 10 e 12; `unidade_por_coluna` aponta a coluna
  que carrega a unidade linha a linha; dimensões, obrigatoriedade, status,
  versão, vigência, observações, responsável).
- **`backend/seed_semantico.py`** (literais, idempotente): 12 unidades (kg base
  de massa com t/g/lb conversíveis; estrutura logística **sem** conversão de
  propósito — posição/UA/palete/LPN não se convertem), 7 conceitos canônicos,
  as 9 famílias do DataHub registradas como **fontes lógicas** em
  `catalogo_fontes` (`tipo_origem='sharepoint_datahub'`) e os 20 campos de
  `ENTRADA_MERCADORIAS` mapeados (KPIs com status `aprovado` e responsável da
  conferência; campos de semântica incerta como `rascunho`).
- **`backend/services/catalogo_semantico.py`** (só SELECT) +
  **`backend/routers/catalogo.py`** (`GET /api/admin/semantica/*`, autenticados)
  + painel **"Semântica"** no admin (read-only: conceitos, unidades/conversões,
  campos por fonte).

**V1.2 — Compatibilidade de medidas:**

- **`backend/services/compatibilidade_medidas.py`**: conversão segura só dentro
  da mesma categoria com fatores conhecidos (t/g/lb→kg conferidos por teste);
  bloqueio com mensagem clara pra caixa+kg, unidade+palete, categorias
  diferentes, unidade fora do catálogo e par sem fator; **percentual nunca soma,
  nem consigo mesmo**; `somar_medidas()` separa por unidade o que não consolida
  e devolve limitações declaradas + auditoria item a item.
- **Aplicado no caminho vivo**: o KPI **"Volume total" foi removido** — conferido
  no dado real (016/2607 via Graph, 31/jul/2026) que a coluna `Volume` é
  declarada na embalagem da coluna `EMB`, com **24 embalagens distintas
  (inclusive KGS)** misturadas; **decisão da Maria (31/jul/2026): separar por
  embalagem**. A tela executiva ganhou o card "Volumes por embalagem" (top 3 +
  contagem das demais), a tabela completa no detalhamento e a limitação
  declarada na qualidade; a soma de volume **por cliente** também saiu (mistura
  embalagens do mesmo jeito); o resumo executivo deixou de citar volume
  consolidado. Peso (kg único) e valor (R$ único) seguem somáveis, validados
  pelo catálogo.

**Decisões do lote:**

1. Tela administrativa do catálogo é **de consulta**; os mapeamentos entram por
   seed versionado no git (configuráveis e versionados sem `if fonte ==` no
   código) — edição via UI fica pra quando existir fluxo de aprovação.
2. Campos semânticos só da família integrada; as outras 8 famílias entram como
   fonte lógica sem campos (regra 14 do direcionamento — nada de processar tudo
   automaticamente). As 5 fontes do DW continuam documentadas em
   `catalogo_colunas`; o mapeamento semântico delas entra quando forem
   revisitadas (V1.3+).
3. A unidade canônica de um campo é **derivada do conceito** (uma fonte de
   verdade só — o campo não guarda cópia).
4. O painel antigo "Catálogo" do admin passa a listar também as fontes DataHub
   (sem colunas do Lote 8.5) — conviver é aceitável; consolidar as duas visões é
   trabalho do cockpit (V1.7).
5. Enforcement da compatibilidade na **ingestão** (parser/`soma_colunas` do
   upload manual) fica pro V1.3, junto da persistência — os 5 modelos atuais
   somam colunas da mesma unidade por construção (conferido no catálogo do
   Lote 8.5).

**Fora do lote (declarado):** persistência/série histórica (C), Laboratório
(D/E), cockpit (F); semântica de `Fração`/`EMB` da posição 12 segue `rascunho`
(não validada com o negócio); devolução no card de valor segue pendência.

**Suíte**: **185 passed** (154 do Bloco A + 31 novos: 18 do motor de
compatibilidade, 10 do catálogo semântico/endpoints, 3 de volumes por embalagem
nos KPIs; os asserts de volume consolidado foram substituídos pelos de
separação — nenhum cenário de teste perdido). **Verificação independente**
executada antes do commit, com 5 ressalvas corrigidas:
`docs/V1_RELATORIO_VERIFICACAO.md`.

## Bloco C — V1.3 Persistência e série histórica (feito, 31/jul/2026)

Autorizado pela Maria em 31/jul/2026 ("vamos para o proximo" + plano aprovado
via pergunta estruturada: "Pode executar"). Duas decisões dela no mesmo ato:
**volumes por embalagem ficam fora da série persistida** (exigiria dimensão de
embalagem; o card segue ao vivo do arquivo) e **sem auto-cadastro de cliente**
(cliente fora do cadastro vira pendência; as linhas dele somam no balde "sem
cliente identificado" até o cadastro).

**O que o lote entregou:**

- **Migration `0006_persistencia_datahub`** (downgrade validado por teste de
  ciclo completo): `medidas` ganha `cliente_id` e a UNIQUE de 3 colunas vira
  `UNIQUE NULLS NOT DISTINCT` de 4 (Postgres 16) — única mudança não puramente
  aditiva do bloco, exigida pelo grão mínimo do direcionamento (seção 8) na
  camada existente; nenhum dado muda (linhas antigas ficam `cliente_id NULL`).
  Tabelas novas: `sincronizacoes_datahub` (inventário persistido — restart não
  zera mais a lista de permissão de downloads), `processamentos_datahub`
  (estado corrente por arquivo; o histórico de rodadas segue em `execucoes`) e
  `cliente_pendencias`.
- **Grão único por métrica = prevenção de dupla contagem por construção**: as
  métricas do DataHub são persistidas SÓ no grão competência × filial ×
  cliente (`cliente_id NULL` = sem cliente identificado, nunca "total da
  filial"); o total da filial é sempre a soma das linhas. `clientes_atendidos`
  não é persistido (contagem distinta não é somável — derivado na consulta).
- **Processamento** (`backend/services/processamento_datahub.py`): cada
  arquivo da família vira execução (`origem='datahub'`, conector novo
  `sharepoint_datahub`) → `medidas_recebidas` (append-only, com unidade
  canônica do conceito e arquivo de origem — linhagem preservada) → upsert das
  células canônicas. Idempotente (2× não muda nada); reprocessamento de
  arquivo alterado cria execução nova, atualiza células e **remove células
  órfãs** (ex.: cliente cadastrado depois sai do balde NULL). Cliente
  resolvido pela raiz do CNPJ (8 dígitos = `nk_erp`), tolerante a célula
  numérica do Excel (zeros à esquerda); filial pelo de-para real do banco
  (001/015/016 semeados do mesmo mapa da exibição — fonte única
  `filiais_datahub.SIGLA_POR_CODIGO`); 002 vira pendência de de-para.
- **Métricas novas governadas**: `peso_bruto_movimentado` (kg),
  `valor_mercadoria_movimentada` (R$), `registros_movimentacao` — nomes dos
  conceitos canônicos do V1.1, com atributos semânticos no seed_metricas.
- **Consulta por intervalo** (`backend/services/serie_datahub.py`, `GET
  /datahub/serie`): série mensal, consolidação anual e acumulado, filtráveis
  por filial (sigla ou código do export) e cliente (nk_erp), lendo SÓ o
  Postgres (teste prova que o Graph não é chamado). Só métrica aditiva
  consolida; média/último/percentual são recusados com mensagem
  (regra da seção 7 do direcionamento). `clientes_atendidos` refaz a contagem
  distinta no mês/ano/acumulado (somar meses duplicaria) e declara a limitação
  do balde sem cliente.
- **Motor de scores**: passa a somar por competência (série da filial) — pro
  dado antigo (1 linha por célula) o resultado é idêntico; as séries novas
  ganham score no grão filial sem violar a unicidade de `scores`.
- **Admin**: bloco "Série histórica (V1.3)" no painel DataHub — "Processar
  arquivos" (pula inalterados, por `modificado_em`), "Reprocessar tudo",
  tabela de processamentos e pendências (filial e cliente). `POST
  /datahub/processar`, `GET /datahub/processamentos`, `GET /datahub/serie`,
  todos autenticados.
- **`/nuvem` não muda** neste bloco: segue a leitura ao vivo do arquivo mais
  recente; quem consome a série é o cockpit (V1.7).

**Decisões do lote:**

1. Volumes por embalagem fora da série persistida (Maria, 31/jul/2026) — o
   card/tabela ao vivo continuam; persistir exigiria dimensão de embalagem.
2. Sem auto-cadastro de cliente (Maria, 31/jul/2026) — pendência + balde
   "sem cliente identificado"; reprocessar depois do cadastro move os valores.
3. Enforcement de unidade na ingestão do DataHub por construção: a unidade
   gravada vem do conceito canônico aprovado; sem conceito aprovado com
   unidade, o processamento recusa (teste cobre). O enforcement no parser do
   upload manual segue adiado: as 5 fontes do DW ainda não têm mapeamento
   semântico de campo (registrado no Bloco B, decisão 2).
4. Inventário persistido com o serviço puro: quem grava é o endpoint de
   sincronização e quem reidrata o cache é o startup do app — testes de
   unidade continuam sem banco.
5. Consulta de série restrita a métricas aditivas + `clientes_atendidos`
   derivado; consolidar média/último/percentual exige regra específica e fica
   pra quando um KPI assim for publicado (seção 7 do direcionamento).

**Fora do lote (declarado):** telas de série/cockpit (V1.7 — filtros globais,
comparações, rankings, participação, variação: a série que os alimenta está
pronta); Laboratório (D/E); demais famílias do DataHub (a família integrada
segue sendo só ENTRADA_MERCADORIAS — `DADOS_GERAIS` e afins entram com seus
obstáculos declarados quando forem integradas); devolução no card de valor
(pendência da Maria); de-para da filial 002 (agora visível como pendência no
admin).

**Limitações registradas** (achados da verificação independente, sem defeito
no caminho vivo):

- O controle de processamento é por **nome** de arquivo; dois arquivos
  homônimos em subpastas diferentes do DataHub disputariam o mesmo registro
  (sem dupla contagem — as células são upsertadas —, mas o controle
  flip-floparia e reprocessaria a cada clique). Premissa atual: um arquivo por
  filial × competência na família (verdade hoje).
  **⚠ SUPERADO EM 31/jul/2026 — a premissa caiu**: a fonte foi reestruturada em
  quatro unidades e há 7 colisões reais, entre armazéns **diferentes** sob o
  mesmo código de filial (caso pior que o previsto aqui: a linhagem em
  `medidas_recebidas` ficaria com o armazém errado, de forma permanente).
  **CORRIGIDO em 02/ago/2026** pelo lote de identidade (seção abaixo): a chave
  passou a ser o `item_id` e o de-para a ser qualificado pela unidade. Nunca
  chegou a acontecer em produção.
- O grão único por métrica é invariante **de código**, não de schema: um
  modelo de upload manual futuro que gravasse uma das 3 métricas do DataHub no
  grão filial causaria dupla contagem na série — nenhum modelo atual referencia
  essas métricas; não criar sem revisar esta regra.
- Arquivo republicado onde todas as linhas viraram inválidas zera as células
  daquela filial × competência (espelho fiel do último estado — intencional,
  coberto por teste).

**Pendências herdadas** (não-código): as mesmas do Bloco A/B — validar `/nuvem`
ao vivo, subir pra VM com o `UPDATE` de `ativo` das filiais, devolução no card
de valor, pendências humanas das fontes. Nova: **processar o histórico na VM**
(clicar "Processar arquivos" depois do deploy) e cadastrar os clientes que
aparecerem como pendência. **O deploy, o `UPDATE` de `ativo` e o processamento
do histórico foram feitos em 03/ago/2026** — ver "Estado do deploy" no início
deste documento.

**Suíte**: **232 passed** (185 do Bloco B + 47 novos: 20 do processamento, 12
da consulta de série, 6 da persistência do inventário, 6 dos endpoints novos,
2 do ciclo da migration 0006, 1 do motor com grão cliente; o teste do
seed_metricas foi atualizado de 12 pra 15 métricas — nenhum cenário perdido).
**Verificação independente** antes do commit (15/15 atendido, 6 ressalvas —
2 corrigidas, 4 registradas): `docs/V1_RELATORIO_VERIFICACAO.md`.

## Bloco D — V1.4 Laboratório: seleção e perfil (feito, 02/ago/2026)

Autorizado pela Maria em 02/ago/2026 ("podemos iniciar o bloco D"), com três
decisões dela na abertura do lote: **qualquer arquivo do DataHub é selecionável**
(perfil estrutural genérico, soma só onde o catálogo aprova), **tela nova em
`/laboratorio`** (não um painel do admin) e **amostra sem mascaramento** — o
mascaramento passa a ser obrigação explícita do Bloco E, antes de enviar
qualquer coisa ao provedor de IA.

**O que o lote entregou:**

- **Migration `0007_laboratorio_sessoes`** (aditiva): a sessão de análise
  (usuário, título, seleção, filtros, limites aplicados e perfil em JSONB). O
  `status` já aceita `em_analise`/`descartada`/`aprovada` para o Bloco E/F não
  precisar de migration de enum. Mensagens/modelo/parâmetros/feedback **não**
  têm coluna vazia esperando aqui — entram em tabela própria no V1.5.
- **`backend/services/leitura_datahub.py`** — leitura estrutural genérica, que
  destrava as 8 famílias sem semântica: linha de cabeçalho **por família**
  (1, 2, 3, 5 ou 6, conforme conferido no `FONTES_DATAHUB`), detectada quando a
  família é desconhecida e sobreponível à mão na tela; coluna identificada por
  **posição** (o rótulo `EMB` repete); aba `SLIN` preferida com a escolha
  declarada. As guardas do P3 continuam: só `item_id` que apareceu numa
  sincronização, só `.xlsx`, limite de tamanho no download.
- **`backend/services/perfil_dados.py`** — o perfil determinístico da seção 9.4,
  função pura. Tipo **dominante** com conformidade em percentual (uma célula
  suja não transforma coluna numérica em texto, e o que não bate fica fora das
  somas e é contado), nulos, distintos, mín/máx, duplicidades, chaves
  candidatas (simples e compostas), cobertura temporal, clientes, granularidade
  provável, qualidade, limitações e amostra.
- **Soma só quando permitida, e a decisão é do catálogo** — não do formato do
  dado. Cada coluna numérica sem soma traz o motivo: sem mapeamento aprovado,
  mapeamento em rascunho, unidade declarada linha a linha (o caso `Volume`×`EMB`),
  categoria não consolidável, **agregação declarada `nenhuma`** (o caso
  `Vlr. Unitário`) ou percentual. Quando é permitida, a soma sai do motor do
  V1.2 — a regra de somar continua num lugar só.
- **`backend/services/laboratorio.py` + `routers/laboratorio.py`** — seleção →
  limites → perfil → sessão gravada. Limites: 5 arquivos por sessão, 50 mil
  linhas por arquivo, 120s de leitura, amostra de 20 linhas (tamanho por arquivo
  reusa o `UPLOAD_MAX_MB`). Filtros de filial e competência escolhem **arquivos**
  (vêm do nome); filtro de cliente filtra **linhas**, e quando o arquivo não tem
  coluna de cliente o aviso é explícito em vez de silêncio. Falha de um arquivo
  não derruba a sessão.
- **Tela nova `/laboratorio`** com a identidade visual das outras: famílias
  expansíveis com os arquivos, filtros, limites visíveis, e o perfil renderizado
  por arquivo (colunas, chaves, cobertura, clientes, qualidade, limitações e
  amostra) + histórico de sessões. Todo conteúdo de origem SharePoint escapado;
  `web_url` validada antes de virar link.

**Guarda estrutural (achado do lote):** o catálogo semântico casa campo por
**posição**. Com a fonte reestruturada (seção ABERTO abaixo) existem variantes
da mesma família com outra estrutura — a `ENTRADA_MERCADORIAS` da unidade RJ tem
18 colunas, sem `Cliente`/`Cliente CNPJ`, e há a família
`ENTRADA_MERCADORIAS (UA)`, que o classificador por prefixo lê como a família
integrada. Aplicar o catálogo nesses casos daria **conceito e unidade trocados,
e soma liberada na coluna errada**. Então, antes de usar o catálogo, o perfil
confere se o rótulo de cada posição catalogada bate com o do arquivo; divergiu
em qualquer posição, o catálogo **inteiro** é descartado para aquele arquivo
(meio-catálogo seria pior que nenhum), o perfil sai estrutural e a divergência
é declarada em texto. Coberto por teste com a estrutura real da RJ.

**Decisões do lote:**

1. Seleção por arquivo do inventário, com a **unidade visível pelo caminho** na
   tela — desde a reestruturação o mesmo nome de arquivo existe em unidades
   diferentes; sem o caminho, dois arquivos ficariam indistinguíveis na lista.
2. Perfil é por arquivo, não consolidado entre arquivos: consolidar exigiria
   afirmar que as estruturas são compatíveis, que é exatamente o que o bloco
   não pode assumir. A sessão traz um resumo (famílias, filiais, competências,
   totais e limitações reunidas), não uma soma cruzada.
3. `usuario` da sessão é sempre `admin`: a autenticação do projeto é senha
   única, sem identidade por pessoa. Acesso por usuário é do V1.8 (Bloco G) —
   limitação declarada, não esquecimento.
4. Amostra gravada **sem** mascaramento (decisão da Maria). Como a sessão é o
   insumo do chat, **mascarar antes de enviar à IA é requisito do Bloco E** e
   está registrado aqui para não se perder.
5. O `nuvem_datahub` passou a ser a fonte única também da linha de cabeçalho por
   família (atributo da família, junto do resto da identificação) e ganhou dois
   acessores públicos; a lista de permissão de download virou função pública do
   `inventario_datahub`, usada pelos dois leitores — antes só o leitor do P3 a
   implementava.

**Fora do lote (declarado):** chat e IA (V1.5), promoção a KPI (V1.6), cockpit
(V1.7); consolidação entre arquivos; arquivos retidos do upload manual como
fonte do Laboratório; e **a correção da reestruturação da fonte** (seção ABERTO)
— o Bloco D não a resolve, só se protege dela no seu caminho.

**Limitações registradas** (achados da verificação independente que não foram
corrigidos; nenhuma é defeito no caminho vivo, todas afetam robustez ou
completude do perfil):

- **Data como serial não formatado do Excel** é lida como número: a cobertura
  temporal daquela coluna volta vazia e, se houvesse catálogo aprovado, o
  serial poderia ser somado. Afeta justamente as famílias sem semântica, que
  são o principal uso do Laboratório.
- **`dim_filial` do catálogo não é consultado**: a filial vem só do padrão do
  nome do arquivo. Famílias que não seguem o padrão (`ESTOQUE_POR_LOTE` diário
  e segregado) saem com filial nula, sem fallback por coluna.
- **Arquivo com coluna a mais no fim** tem o catálogo aplicado sem nota — está
  posicionalmente correto (o prefixo não deslocou), mas o perfil deveria dizer
  "o arquivo tem N colunas, o catálogo cobre 20".
- **O limite de tempo é orçamento entre arquivos, não deadline**: o primeiro
  arquivo nunca é interrompido, e o download tem o timeout próprio do cliente
  Graph. Quando estoura, o aviso da sessão diz quantos arquivos entraram.
- **Colunas finais sem rótulo são cortadas** e linhas mais largas que o
  cabeçalho são truncadas à largura dele, sem declarar.
- **`linha_cabecalho` informada na tela vale para todos os arquivos** da sessão:
  numa seleção mista, os que não batem falham alto e claro (entram em `falhas`),
  mas a tela oferece um campo único sem avisar disso.
- **Filtro de cliente que não casa nenhuma linha** produz um perfil de zero
  linhas que se lê como "arquivo vazio" — o filtro é declarado, mas não há uma
  frase dizendo "o filtro não casou com nenhuma linha".
- **`docs/V1_CRITERIOS_ACEITE.md` está com todos os checkboxes vazios** (blocos
  A–D). Não é regressão deste bloco; o registro de aceite efetivo vive neste
  documento e no relatório de verificação.

**Suíte**: **311 passed** (232 do Bloco C + 79 novos: 35 do perfil
determinístico, 18 do leitor estrutural e 26 do laboratório/endpoints — nenhum
teste anterior removido ou enfraquecido). Dois defeitos foram pegos pela própria
suíte e corrigidos no **código**, não no teste: (1) duas sessões gravadas na
mesma transação têm `criado_em` idêntico (é o relógio da transação), o que
deixava "mais recente primeiro" indeterminado — a listagem passou a desempatar
por `id`; (2) a coluna `observacoes` da migration não tinha escritor nenhum e
foi removida.

**Verificação independente** (`docs/V1_RELATORIO_VERIFICACAO.md`): **este foi o
primeiro bloco reprovado na primeira passada** — 3 defeitos reais no caminho
vivo, todos a mesma falha de fundo (número parcial apresentado como completo,
justamente o que o V1.4 existe para evitar): o filtro de um arquivo suprimindo a
declaração de outro, a mensagem de truncamento com número pós-filtro, e a sessão
gravando o resultado dos filtros em vez do pedido. Os três caíram antes do
commit, com teste cada um, junto de 7 outras correções (allowlist de agregação,
variante de família por nome, amostra crua declarada no artefato, teto do
`limite`, mensagem de coluna vazia, teste da estrutura real da RJ, esta seção do
relatório). 8 ressalvas de robustez ficaram registradas acima.

## Lote de correção — identidade e linhagem do DataHub (feito, 02/ago/2026)

Autorizado pela Maria em 02/ago/2026, depois de um plano em texto e duas
decisões dela: **a filial 002 fica pendente** (segue exibindo só o código) e o
**item 6 entra completo** (a correção da sigla nas telas, escopo acrescentado ao
que ela tinha listado). A análise que originou o lote, com o registro do que foi
aceito e do que foi cortado, está em
`docs/decisoes_datahub_identidade_linhagem.md`; o levantamento da fonte (com o
rastreio do cliente SAPORE que originou a investigação) em
`docs/VERIFICACAO_DATAHUB_31JUL2026.html`.

### Por que não houve reparo de histórico

A análise previa invalidar linhas contaminadas de `medidas_recebidas`, abrir um
incidente de dados e reconstruir projeções. **Nada disso foi necessário**: a VM
está em `0004_catalogo_metricas`, as migrations do Bloco C nunca subiram e
"Processar arquivos" nunca rodou em produção — a contaminação era risco a
prevenir, não dano ocorrido. Confirmar com `alembic current` na VM antes do
próximo deploy; se algum dia o cenário mudar, a proveniência é rastreável linha
a linha (cada recebida aponta para uma execução que grava o caminho completo).

### O que mudou na fonte

Varredura recursiva pelo Graph em 31/jul/2026 (app `nuvem-ia`, somente leitura):
a pasta passou de **249 arquivos / 31 pastas / 711 MB** (levantamento de 29/jul,
`docs/FONTES_DATAHUB.md`) para **367 arquivos / 61 pastas / 955 MB**.

A raiz deixou de ter as quatro áreas operacionais direto e passou a ter **quatro
unidades**; o que o projeto conhecia como a pasta inteira é hoje só o galho
`RMSPII`:

| Unidade | Arquivos | MB | Filiais nos nomes |
|---|---:|---:|---|
| `RMSPII` | 272 | 751,0 | 001, 002, 015, 016 (o que já era conhecido) |
| `RJ` | 42 | 121,0 | 004-001, 004-003, 005-001 |
| `CWB3` | 30 | 44,9 | 001 |
| `SANCA` | 21 | 37,8 | 025 |

Família nova, não catalogada: **`ENTRADA_MERCADORIAS (UA)`** (35 arquivos,
31,6 MB, em RMSPII/CWB3/RJ/SANCA; cabeçalho na linha 1, com `Cliente` e
`Cliente CNPJ`).

### O defeito (diagnóstico de 31/jul/2026 — corrigido em 02/ago)

> O texto abaixo descreve o comportamento **anterior** à correção, preservado
> porque é o que explica as escolhas do lote. O estado atual está em "O que o
> lote entregou", no fim desta seção.

A limitação já estava registrada acima, na lista de "Limitações registradas" do
Bloco C, **como hipótese** — com a premissa "um arquivo por filial ×
competência na família (verdade hoje)". **A premissa caiu.** E a análise de lá
subestima o caso que de fato ocorreu, porque assume homônimos da *mesma* filial:

`ENTRADA_MERCADORIAS_001_2601.xlsx` a `_2607.xlsx` existem em
`RMSPII/ENTRADA/ENTRADA MERCADORIAS` **e** em `CWB3/ENTRADA/ENTRADA MERCADORIAS`
— **7 colisões**. Mesmo nome, mesmo código de filial `001`, armazéns
**diferentes**, e o de-para resolve os dois para RMSPII.

Rastreando `processar_todos` com o inventário real:

1. `resumo["arquivos"]` vem ordenado por caminho
   (`inventario_datahub.py`), então `CWB3` processa antes de `RMSPII`.
2. `_ja_processado` compara `modificado_em` contra o registro **daquele nome**.
   Como as duas datas diferem, nenhum dos dois é reconhecido como inalterado —
   o "pula inalterados" para de funcionar nesses 7 e os 14 arquivos são
   reprocessados a cada rodada.
3. `_remover_celulas_orfas` apaga as células de (métrica, armazém, competência)
   que o processamento atual não emitiu — cada um apaga as células do outro.
4. `medidas_recebidas` é append-only: as linhas da CWB3 entram com o
   `armazem_id` da RMSPII e **ficam**. A linhagem passa a afirmar que dado de
   Curitiba é da RMSPII, e isso não se autocorrige.

O agravante é a invisibilidade: como RMSPII processa por último numa varredura
completa, as células de `medidas` acabam com o valor certo **por acidente da
ordem alfabética**. A série na tela pareceria correta; o erro fica só em
`medidas_recebidas`. Processar um arquivo isolado, ou a unidade ser renomeada
para algo depois de "RMSPII", inverte o resultado visível.

### Duas lacunas relacionadas

- **A RJ é ignorada em silêncio.** O padrão de nome em
  `entrada_mercadorias.py` exige só dígitos na filial e `004-003` tem hífen:
  os arquivos não entram no processamento e **não viram nem pendência de
  de-para** — diferente da SANCA (`025`), que cai corretamente como pendência
  visível no admin. Dos 367 arquivos, 34 casam no padrão hoje (20 RMSPII +
  7 CWB3 + 7 SANCA), e 7 desses 34 são a colisão.
- **A `ENTRADA_MERCADORIAS` da RJ tem 18 colunas, não 20** — faltam `Cliente` e
  `Cliente CNPJ`, as duas primeiras (RMSPII, CWB3 e SANCA têm as 20 idênticas).
  Corrigir só o filtro de nome sem tratar isso troca um problema por outro: o
  leitor recusaria o arquivo (erro claro, comportamento correto).

### O que o lote entregou

- **Migration `0008_identidade_datahub`**: `processamentos_datahub` troca
  `UNIQUE(arquivo)` por `UNIQUE(item_id)` (a coluna já existia como `NOT NULL`
  desde o 0006 — nenhum backfill) e ganha `caminho` e `unidade`, nullable. Mais
  o `UPDATE` que qualifica o de-para do DataHub (`001` → `RMSPII/001`)
  preservando o `armazem_id` de cada linha — não é delete+reseed, então um
  ajuste manual sobrevive. Em produção é no-op (o conector nasce com os seeds
  do Bloco C, que não subiram). Pendências de código nu são apagadas em vez de
  prefixadas: não dá pra afirmar a unidade de uma pendência antiga.
- **Identidade por `item_id`**: `_ja_processado` e o registro do processamento
  passam a chavear por ele; `arquivo`, `caminho` e `unidade` viram atributos
  mutáveis. Renomear ou mover no SharePoint atualiza o registro em vez de criar
  outro, e o flip-flop do "pula inalterados" acabou.
- **De-para qualificado pela unidade** (`RMSPII/001`), sem coluna nova —
  `armazem_na_fonte` é texto livre desde o 0001. A unidade sai do primeiro
  segmento do caminho do inventário (`inventario_datahub.unidade_do_caminho`,
  fonte única: quem monta o caminho é quem o interpreta). CWB3, SANCA e RJ
  passam a aparecer como **pendência qualificada** no admin.
- **De-para resolvido antes do download**: origem sem de-para não gasta uma
  chamada ao Graph pra falhar depois na leitura. É o que faz a RJ parar numa
  pendência clara em vez de num erro de "coluna não encontrada".
- **Padrão de nome aceita filial com hífen** (`004-003`): os 42 arquivos da RJ
  deixaram de sumir em silêncio. O leitor da variante de 18 colunas **não** faz
  parte do lote — sem de-para, nenhum arquivo dela é baixado.
- **Guarda dupla de colisão** em `processar_todos`: pré-checagem por (origem,
  competência) antes de baixar qualquer coisa (vê inclusive os arquivos que a
  rodada vai pular) e checagem por (armazém, competência) durante a rodada (pega
  de-paras distintos apontando pro mesmo armazém). Colisão **aborta e reverte a
  rodada inteira**, ao contrário de erro de arquivo, que só marca aquele arquivo.
  Com isso, o escopo de `_remover_celulas_orfas` ficou correto sem redesenho.
- **Correção do caminho vivo** (escopo acrescentado ao plano, aprovado pela
  Maria): as bolinhas do `/nuvem` rotulavam os 7 arquivos `001` da CWB3 como
  "001 · RMSPII" — `filiais_datahub.sigla()` passou a receber `(unidade,
  código)`. O filtro de filial da tela também passou a ser por origem, senão
  juntaria arquivos de armazéns diferentes na mesma opção. E
  `item_mais_recente()` (o arquivo do card executivo) ficou restrito às unidades
  com de-para confirmado — sem isso, o regex novo deixaria um arquivo da RJ
  virar "o mais recente" e quebrar a tela.
- **`docs/FONTES_DATAHUB.md` atualizado**: as quatro unidades, o inventário novo,
  a família `ENTRADA_MERCADORIAS (UA)` e as duas correções conferidas no dado (o
  `ESTOQUE_POR_LOTE` **tem** `Cliente` e `CNPJ Cliente` na linha 5; a competência
  corrente é republicada).

**Decisões do lote:**

1. **Filial 002 fica pendente** (Maria, 02/ago/2026) — exibida só pelo código.
   Semear exigiria a sigla do armazém, que continua sem decisão.
2. **Sem tabela nova de arquivo** — `item_id` já era coluna e a separação
   arquivo × execução já existe (`execucoes` guarda as rodadas). `hash_conteudo`
   e `ativo` resolvem problemas que não são o defeito de hoje.
3. **Sem invalidação/compensação de linhagem** — não há histórico a reparar
   (ver acima).
4. **Família fora da partição lógica** — só uma família emite estas métricas, e
   a `(UA)` não casa no padrão de nome. Registrado no código que uma segunda
   família emitindo as mesmas métricas exige a dimensão do produtor.

**Fora do lote (declarado):** leitor da variante RJ de 18 colunas, hash de
conteúdo, allowlist/dry-run/snapshot, e o de-para real de CWB3/SANCA/RJ —
decisão humana, não código.

**Suíte**: **327 passed** (311 do Bloco D + 16 novos: 2 do ciclo da migration
0008, 9 do processamento — homônimos com registros distintos, pula-inalterado
com homônimo presente, renomeação sem entidade nova, pendência sem download, RJ
com hífen, arquivo sem unidade, isolamento de células entre unidades e as duas
colisões —, 3 da identificação por unidade no leitor e 2 nas bolinhas; o teste de
filtro da série passou a exigir o código qualificado). Nenhum teste removido ou
enfraquecido. Os fixtures que montavam caminho sem unidade foram atualizados para
a árvore real (`RMSPII/...`) — inclusive o do router, que criava o arquivo solto
na raiz e por isso deixou de resolver de-para (o comportamento novo estava certo,
o fixture é que não representava mais a fonte).

## Próximo bloco autorizado

**Nenhum.** O Bloco E (V1.5 chat do Laboratório + V1.6 insight aprovado) só
começa com autorização explícita da Maria.

**Condição registrada para o Bloco E:** o bloqueio herdado da reestruturação era
sobre consumir a **série persistida**, não sobre o bloco inteiro — o Laboratório
lê o arquivo direto e não passa por `medidas`. Com o lote de correção fechado, a
série deixou de ser risco de linhagem. Fica valendo um requisito de conteúdo: o
contexto enviado à IA precisa carregar **unidade junto da filial**, nunca só
"filial 001". Segue valendo também o requisito herdado do Bloco D: **mascarar a
amostra antes de enviar ao provedor de IA**.
