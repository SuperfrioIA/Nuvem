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
| **E** | V1.5 Laboratório: chat + V1.6 Insight aprovado | **feito** (03/ago/2026) |
| **F** | V1.7 Cockpit executivo | **feito** (03/ago/2026) |
| **G** | V1.8 Produção e entrega | **feito** — G1, G2 e G3 (03–04/ago/2026) |

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

**Bloco F deployado e validado na VM em 03/ago/2026**: `git pull` +
`up -d --build` (sem migration pendente — o Bloco F não criou nenhuma), `/cockpit`
e `/linhagem` respondendo 200, login 200, `GET /api/admin/cockpit/qualidade`
devolvendo dado real do recorte sem filtro (42 arquivos: 21 `ok`/21
`pendencia_depara`) — as pendências de filial (`CWB3/001`, `RJ/004-003`,
`SANCA/025`) e de cliente (`LC ADMINISTRACAO DE RESTAURANTES`, CNPJ raiz
`60691250`) batem com as já conhecidas acima, nenhuma pendência nova surgiu.

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

## Bloco E — V1.5 Laboratório: chat + V1.6 Insight aprovado (feito, 03/ago/2026)

Autorizado pela Maria em 03/ago/2026 ("confirmado, pode seguir"), depois de um
plano em texto com uma decisão dela na abertura: **provedor de IA é a Anthropic
Claude API**, modelo padrão `claude-sonnet-5` (custo, sem exigir o teto de
raciocínio da tarefa), configurável por variável de ambiente sem redeploy de
código.

**O que o lote entregou:**

- **Migration `0010_laboratorio_chat`** (aditiva): tabela `laboratorio_mensagens`
  (uma linha por turno usuário/assistente; `contexto_enviado` grava o que de
  fato saiu pro provedor, auditoria da seção 9.6/12; `erro` no lugar de
  `conteudo` quando a chamada falha — nunca resposta inventada; `feedback` é
  reação a UMA mensagem do assistente, gostei/não gostei/pedir ajuste/pedir
  comparação/acrescentar contexto). `laboratorio_sessoes` ganha `especificacao`
  (JSONB, só na aprovação), `decisao_nota` e `decidido_em` — aprovar/descartar
  são decisão da SESSÃO inteira, não de uma mensagem.
- **`backend/config.py`**: `obter_configuracao_ia()` no mesmo padrão preguiçoso
  do Graph — sem `ANTHROPIC_API_KEY` o app sobe normal, só falha quando o chat
  for de fato usado. `IA_MODELO`/`IA_EFFORT` com default, trocáveis por
  variável de ambiente.
- **`backend/services/ia_client.py`**: wrapper fino do SDK Anthropic (isola o
  SDK, como `graph_datahub.py` isola o Graph). `thinking` sempre adaptativo;
  recusa por política (`stop_reason == "refusal"`) e resposta truncada
  (`stop_reason == "max_tokens"`) viram erro tratado, nunca sucesso silencioso
  com conteúdo incompleto.
- **`backend/services/mascaramento.py`**: função pura que troca cliente/CNPJ
  por pseudônimo consistente (mesmo cliente = mesmo pseudônimo) em quatro
  pontos do perfil determinístico onde o nome aparece em claro: amostra,
  `clientes.top`, `colunas[].exemplos` e o texto de limitação do filtro de
  cliente (esse último só apareceu na verificação independente — é o nome que
  o próprio usuário digitou no filtro, ecoado de volta pelo perfil).
- **`backend/services/laboratorio_chat.py`**: monta o contexto controlado
  (perfil determinístico do Bloco D + amostra mascarada, nunca a planilha),
  resolve **unidade junto da filial** por arquivo (reusa `filiais_datahub`/
  `inventario_datahub`, sem heurística própria) e recalcula duas chaves do
  resumo da sessão especificamente para a IA — nunca no formato persistido do
  Bloco D: `limitacoes` (deduplicada a partir das já mascaradas por arquivo) e
  `filiais` (trocada pela origem qualificada; o código nu colide entre
  unidades diferentes, ex. `RMSPII/001` × `CWB3/001`). Envia pergunta,
  grava resposta ou erro, nunca lança exceção pro chamador.
- **`backend/services/insight_aprovado.py`** (V1.6): ao aprovar, gera a
  especificação técnica da seção 10 combinando parte determinística do perfil
  (fontes, campos, conceitos, unidade, granularidade, limitações — nunca da
  IA) com saída estruturada da IA (nome, pergunta de negócio, fórmula, riscos,
  exemplos — schema fixo). Nunca publica KPI nem grava em tabela de métrica
  oficial. Descartar não chama a IA.
- **Endpoints novos** em `routers/laboratorio.py`: `GET/POST
  /sessoes/{id}/mensagens`, `POST /sessoes/{id}/mensagens/{id}/feedback`,
  `POST /sessoes/{id}/aprovar`, `POST /sessoes/{id}/descartar` — todos atrás de
  login, todos buscando a sessão primeiro (404 se não existir).
- **Painel de chat em `/laboratorio`**: mensagens sugeridas da seção 9.5 como
  botões, campo livre, histórico, feedback por mensagem, aprovar/descartar com
  confirmação; especificação aprovada e nota de decisão renderizadas na tela.

**Verificação independente** (agente separado, antes do commit): achou 1
crítico, 2 altos e 1 médio — todos corrigidos antes de fechar o lote:

1. **Crítico** — o nome do filtro de cliente (texto digitado pelo usuário,
   não vem da planilha) era ecoado sem máscara no texto de limitação
   ("Perfil calculado APÓS filtro de cliente (SAPORE): ...") e ia inteiro pro
   contexto da IA. Corrigido em `mascaramento.py` (mascara a limitação com o
   mesmo mapa da amostra).
2. **Alto** — falha da IA na aprovação (`insight_aprovado.gerar_especificacao`)
   subia como exceção crua, virando HTTP 500 em vez do 400 tratado que o
   resto do Laboratório sempre devolve. Corrigido com `try/except` mapeando
   pra `InsightAprovadoError`.
3. **Alto** — `resumo_da_sessao.filiais` embutia o código nu do Bloco D, que
   colide entre unidades (`RMSPII/001` × `CWB3/001` viram os dois "001").
   Corrigido recalculando `filiais` a partir da origem qualificada de cada
   arquivo, só dentro do contexto do Bloco E (o formato persistido do Bloco D
   não muda).
4. **Médio** — resposta cortada pelo limite de tokens (`stop_reason ==
   "max_tokens"`) era gravada como sucesso, sem sinal de que estava
   incompleta. Corrigido em `ia_client.py` (vira erro tratado, mesmo caminho
   de "conversa segue sem inventar resposta").

**Decisões do lote:**

1. **Contexto sempre recalculado a partir do perfil**, nunca reaproveitando
   `resumo`/`limitacoes` do Bloco D como estão persistidos — o formato
   gravado na sessão continua sendo o de exibição/histórico; o que vai pra IA
   é uma projeção própria do Bloco E, montada a cada chamada.
2. **Contexto completo reenviado a cada turno** (a API é sem estado; o perfil
   da sessão é imutável) em vez de cache/prompt caching — simplicidade sobre
   otimização de custo neste volume (ferramenta interna de CSC).
3. **Sem consistência de pseudônimo ENTRE arquivos** da mesma sessão — casar
   os mapas exigiria expor o de-para em algum lugar, contra o propósito do
   mascaramento. Dentro de um arquivo, o mesmo cliente é sempre o mesmo
   pseudônimo.
4. **Aprovar é ação única, não conversação** — falha da IA na aprovação vira
   erro tratado que interrompe a ação (o usuário tenta de novo), diferente do
   chat, que grava o erro numa mensagem e deixa a conversa seguir.

**Fora do lote (declarado):** cockpit (F); consolidação entre sessões/insights
aprovados; qualquer leitura de `especificacao` fora da própria tela do
Laboratório (a especificação é insumo pra implementação humana, não é
consumida em código).

**Limitação aceita (achado de severidade baixa da verificação independente,
não corrigida):** a checagem do limite de mensagens por sessão
(`MAX_MENSAGENS_POR_SESSAO`) não usa lock — duas requisições concorrentes na
mesma sessão podem, em tese, passar do teto, porque a chamada à IA (até 60s)
acontece dentro da mesma janela da checagem. Consistente com o resto do
Laboratório (nenhum outro limite usa lock); é um teto de custo/uso, não um
controle de segurança, e o volume esperado (ferramenta interna) não justifica
a complexidade de lock agora.

**Suíte**: **382 passed** (52 novos: 8 de mascaramento — incluindo o caso do
achado crítico —, 6 do wrapper da IA testado com client falso — cobertura que
não existia antes da verificação independente —, 24 do chat/contexto/
endpoints e 14 da aprovação/descarte/endpoints; nenhum teste anterior removido
ou enfraquecido). Testes sempre mockados — nenhuma chamada de rede real à
Anthropic na suíte.

## Bloco F — V1.7 Cockpit executivo (feito, 03/ago/2026)

Autorizado pela Maria em 03/ago/2026 ("pode seguir então"), depois de um
escopo discutido em texto com quatro decisões dela: **cliente pode ser
exposto** nas comparações/ranking ("Sem cliente identificado" como categoria
própria, nunca escondido); **linhagem completa em tela separada**, pensando
em duas telas — uma de diretoria (cockpit) e outra até o grão mínimo
(linhagem); **espaço reservado pra KPIs do Laboratório**, sem nenhum ativo
ainda (nenhum insight foi aprovado); e **biblioteca de gráficos Apache
ECharts**, por ser madura (sem risco de beta) e mais flexível que uma lib
básica — inclusive com leitura futura de que sua configuração declarativa
(JSON) combina bem com o fato de o projeto já ter uma camada de IA (sem
mudar a regra de que a IA nunca publica direto no cockpit).

**Decisão de portabilidade pro Hub SuperFrio** (fechada em conversa com o time
do Hub antes do lote): o Hub vai **linkar direto** as duas telas (não
embutir via iframe — o Hub não tem autenticação compartilhada com o
nuvem-ia, e o sandbox de iframe dele pressupõe apps no mesmo repositório);
os filtros globais viram **query string** (`?de=&ate=&filial=&cliente=`),
permitindo o Hub linkar direto pra uma visão filtrada; as duas telas
(executiva e linhagem) ficam em **rotas top-level independentes** (`/cockpit`
e `/linhagem`, não uma sub-rota da outra) porque o modelo de permissão do Hub
só concede acesso por app inteiro — cada tela vira um card/app separado, com
possibilidade de role distinta quando o Hub tratar isso. O modo `embed` foi
desenhado e descartado do escopo imediato (fica pronto pro dia em que houver
autenticação compartilhada). Autenticação/SSO entre Hub e nuvem-ia fica
pendência declarada dos dois lados — não é bloqueante pra link direto.

**O que o lote entregou:**

- **Sem migration nova**: o cockpit lê só tabelas que já existiam (`medidas`,
  `medidas_recebidas`, `execucoes`, `processamentos_datahub`, `armazens`,
  `clientes`, `metricas`) — a série que os alimenta já estava pronta desde o
  Bloco C.
- **`backend/services/cockpit.py`**: `resumo()` (cards de peso/valor
  acumulados, clientes atendidos, participação do maior cliente — reaproveita
  `serie_datahub.serie()` por métrica, não recalcula nada), `comparar_filiais()`
  e `comparar_clientes()` (ranking com participação % sobre o total do
  recorte; cliente sem cadastro entra como "Sem cliente identificado") e
  `qualidade()` (agregação de `processamentos_datahub` por status no recorte
  de competência/filial, mais as pendências de de-para já existentes).
- **`serie_datahub.py` ganhou funções públicas** (`resolver_filial`,
  `resolver_cliente`, `metrica_info`, `exigir_metrica_aditiva`, antes
  privadas): o cockpit reaproveita a mesma resolução de filial/cliente/métrica
  do V1.3 em vez de duplicá-la — nenhuma mudança de comportamento, só
  visibilidade.
- **`backend/services/linhagem.py`**: grão mínimo real do que o sistema
  persiste — célula (`medidas`) → a recebida que a originou
  (`medidas_recebidas`, via `medida_recebida_id`) → a execução que processou
  o arquivo (`execucoes`) → o arquivo de origem no SharePoint (cruzando o
  caminho da execução com `processamentos_datahub`, que guarda o `item_id`, e
  com o inventário em cache, que guarda o `web_url`).
- **Endpoints novos**, todos atrás de login: `GET /api/admin/cockpit/resumo`,
  `/comparacao/filiais`, `/comparacao/clientes`, `/qualidade`; `GET
  /api/admin/linhagem/celulas` e `/celulas/{id}`. A série histórica e o
  acumulado **não** ganharam endpoint novo — o cockpit consome direto `GET
  /api/admin/datahub/serie` (Bloco C).
- **Duas telas novas**: `/cockpit` (filtros globais de período/filial/cliente
  na URL; cards; série histórica e variação mensal com ECharts; comparação de
  filiais e de clientes com ranking e participação; qualidade e origem
  separada da área principal; espaço vazio de KPIs do Laboratório) e
  `/linhagem` (filtro por métrica/competência/filial/cliente; lista de
  células; cadeia de origem por célula, com link pro arquivo no SharePoint
  quando o `web_url` existir).

**Decisões do lote:**

1. **"Quantidade de operações" fora dos cards** (secão 11.4 do
   direcionamento pede essa métrica "quando semanticamente válida") — a única
   candidata, `registros_movimentacao`, é documentada no próprio catálogo
   (`seed_metricas.py`) como "indicador de volume de dados, não de negócio";
   promovê-la a KPI executivo contradiria essa declaração. O card volta
   quando existir uma métrica de negócio aprovada pra operações.
2. **Participação do maior cliente calculada sobre valor** (não peso): o
   direcionamento não diz qual métrica -- valor é a leitura mais direta de
   participação de negócio; peso já tem card próprio.
3. **Grão mínimo da linhagem é arquivo × cliente × competência, não a linha
   crua da planilha**: o processamento (V1.3) agrega por cliente e descarta
   as linhas individuais depois de agregar — elas nunca são persistidas.
   Descer a NF/item de linha exigiria persistir as linhas cruas, fora do
   escopo deste lote.
4. **`qualidade()` filtra por filial voltando pelo de-para** (`depara_armazem`):
   `processamentos_datahub` guarda unidade/filial crus, de antes da resolução
   — o filtro por armazem precisa da mesma fonte que a ingestão usa, não um
   atalho novo.

**Fora do lote (declarado):** autenticação/SSO entre Hub e nuvem-ia; modo
`embed`; cache/persistência de ranking (calculado ao vivo — volume atual não
justifica); semântica de famílias do DataHub além de `ENTRADA_MERCADORIAS`;
qualquer KPI de insight aprovado no Laboratório (nenhum foi aprovado ainda).

**Suíte**: **414 passed** (382 do Bloco E + 32 novos: 12 de `test_cockpit.py`
— resumo, comparação de filiais/clientes, qualidade —, 6 de `test_linhagem.py`
— cadeia completa, célula legada, erros —, e 14 dos endpoints novos
(`test_cockpit_router.py` + `test_linhagem_router.py`); nenhum teste anterior
removido ou enfraquecido).

**Verificação independente** (agente separado, antes do commit): achou 1
defeito real confirmado por execução (peso bruto aparecia em kg, não em
toneladas, nos gráficos de série e ranking — só o card do resumo convertia;
reabria a pendência D4 do relatório do Bloco A) e 2 achados menores. Todos
tratados antes do commit:

1. **Alto, corrigido** — peso em kg nos gráficos de série/ranking em vez de
   toneladas (a métrica default do seletor), e nenhum "detalhamento completo"
   em toneladas na tela (item 5 dos critérios de aceite deste bloco). Corrigido
   com `formatarValorPorUnidade()` (converte quando a unidade da métrica é
   `kg`) nos formatadores de eixo/tooltip de `renderizarSerie`/`renderizarRanking`,
   mais a linha "Peso bruto (detalhado)" no bloco de qualidade (mesmo padrão
   já usado no `/nuvem`).
2. **Baixo, registrado como limitação** — os filtros de filial e cliente
   (cockpit e linhagem) aceitam só um valor por vez ou "todos"; a seção 5.7 do
   direcionamento lista "uma, várias ou todas as filiais"/cliente como decisão
   fixada. Herdado da interface de `serie_datahub` desde o Bloco C, não é
   regressão deste bloco — os rankings já mostram todos os itens lado a lado,
   o que mitiga parcialmente. Resolver exigiria filtro multi-select na tela e
   `= ANY(%s)` no lugar de `= %s` nas consultas — trabalho de um lote próprio,
   não correção pontual.
3. **Cosmético, corrigido** — a repartição dos 32 testes novos por arquivo
   nesta seção estava errada (já corrigida no texto acima).

## Bloco G — V1.8 Produção e entrega (em andamento)

Autorizado pela Maria em 03/ago/2026 ("pode iniciar a execução do g1"), depois
de um mapeamento dos 14 itens da §14 do direcionamento contra o repositório
real. O bloco é o mais largo da V1 — ficou dividido em três checkpoints
(G1/G2/G3), cada um com suíte verde, commit isolado e autorização da Maria
antes do próximo, mesma regra dos Blocos A–F. Cinco decisões dela na abertura:
**manter senha única** (sem tabela de usuário); **sem HTTPS por enquanto**;
**destino externo do backup fica pra depois** (mecanismo local + teste de
restauração entram já); **fechar as páginas HTML sem login** (G2); e o
**secret do Graph foi criado em 15/jul/2026** (registrar data e processo).

### G1 — Produção destravada e continuidade (feito, 03/ago/2026)

Atacou o que deixava a V1 instável em produção hoje, não o que faltava de
acesso/auditoria (isso é G2) ou de testes E2E/documentação (G3):

- **IA chegando ao container**: `ANTHROPIC_API_KEY`/`IA_MODELO`/`IA_EFFORT`
  não estavam no `docker-compose.yml` nem no `.env.example` — o chat do
  Laboratório (Bloco E) estava fechado no código mas não funcionava em
  produção nenhuma, mesmo com a chave no `.env` da VM, porque o compose mapeia
  variável por variável (não usa `env_file:`). Acrescentadas as três, com
  default de modelo/esforço.
- **Backup local, testado**: `scripts/backup.sh` (`pg_dump` via `docker
  compose exec` + `tar` dos uploads retidos, comprimidos e carimbados,
  retenção configurável) e `scripts/restore.sh` (zera o schema `public` e
  restaura, com confirmação explícita — destrutivo por natureza). Testado de
  verdade: dump tirado, schema inteiro derrubado (`DROP SCHEMA ... CASCADE`)
  pra simular perda total, restaurado, contagem de linhas conferida contra o
  estado anterior (`armazens`: 36 → 36). **Cópia pra fora da VM é pendência
  declarada** (decisão da Maria: pensar depois, combinar com a TI) — o dump
  fica só no disco da VM por ora.
- **Continuidade técnica**: `GET /health` (sem login — sonda de
  infraestrutura, confere o banco com `SELECT 1`, 503 se não responde) +
  healthcheck no `docker-compose.yml` pro `nuvem-app` (antes só o Postgres
  tinha); handler global de exceção (`backend/main.py`) — qualquer exceção
  crua que escapasse de um router virava 500 do Starlette com traceback no
  corpo, agora vira `500 {"detail": "erro interno"}` tratado, sem mudar o
  comportamento dos 70 `HTTPException` já espalhados no código (FastAPI
  resolve por MRO — handler mais específico continua ganhando);
  `connect_timeout=5`/`statement_timeout=30s` em `backend/database.py` — hoje
  não havia nenhum dos dois, um Postgres inacessível ou uma query presa
  travava a aplicação inteira. **Pool de conexões fica fora do G1**: worker
  único e volume de ferramenta interna não justificam a complexidade agora;
  os timeouts resolvem o risco de continuidade sem mudar arquitetura.
- **Rollback de verdade**: o plano cogitava git tag + push a partir da VM —
  não dá, a deploy key da VM é só leitura (`docs/DEPLOY.md`, Passo 2).
  Reescrito por SHA local: antes de cada deploy, registrar o commit rodando
  (`git rev-parse HEAD` num log local) e tirar um dump com `scripts/backup.sh`;
  deploy ruim = `git checkout <SHA-anterior>` + (se o schema mudou)
  `scripts/restore.sh` do dump pré-deploy.
- **Secret do Graph — data e processo**: criado em 15/jul/2026, expira em
  15/jul/2027, processo de rotação documentado em `docs/DEPLOY.md` e em
  `memory/graph-secret-rotacao.md`.

**Decisões do lote:**

1. Backup mecanismo + teste de restauração entram agora; destino externo
   (fora da VM) fica pendência declarada — decisão explícita da Maria, não
   esquecimento.
2. Sem pool de conexões — timeouts resolvem o risco de continuidade sem
   mudar a arquitetura de acesso ao banco; reavaliar se o volume crescer.
3. `/health` sem login — é sonda de infraestrutura (Docker healthcheck), não
   expõe dado de negócio; mesma lógica de `/docs`/`/openapi.json`, que
   continuam abertos (fechar é G2).
4. Rollback por SHA local em vez de tag/push — a deploy key da VM não tem
   permissão de escrita no GitHub, por desenho (Passo 2 do runbook).

**Fora do G1 (declarado, fica pro G2/G3):** gate por `Depends`/páginas HTML
fechadas, rate limit de login, tabela de auditoria com ator, logging
estruturado com request id, teste E2E até cockpit/linhagem, checklist
automatizado (`scripts/verificar_v1.py`), atualização de
README/`V1_CRITERIOS_ACEITE.md`/`V1_ARQUITETURA.md`.

**Suíte**: **420 passed** (414 do Bloco F + 6 novos: `/health` ok e com banco
indisponível, `/health` sem exigir login, handler global não vazando detalhe
da exceção crua, `HTTPException` existente sem mudar de comportamento,
`statement_timeout` aplicado na conexão — nenhum teste anterior removido ou
enfraquecido). `connect_timeout` não entrou em teste automatizado (exigiria
simular host inacessível de forma confiável) — limitação aceita, mesmo padrão
já usado em blocos anteriores pra timeouts difíceis de simular.

**Verificação manual** (não entra em pytest — são scripts de shell e
configuração de compose, não código Python testável em unidade):
`docker compose up -d --build` local com `nuvem-app` chegando a `healthy`;
`curl /health` → 200; backup → drop total do schema → restore → contagem de
linhas batendo com o estado anterior.

### G2 — Acesso, auditoria e logs (feito, 04/ago/2026)

Autorizado pela Maria em 03/ago/2026 ("bora pro g2"), com plano apresentado e
aprovado antes de qualquer código. Ataca as quatro lacunas estruturais de
acesso/auditoria/log deixadas fora do G1 de propósito.

- **Gate declarativo em vez de chamada imperativa**: `exigir_login(request)`
  era a primeira linha de 48 dos 51 handlers — uma rota nova que esquecesse a
  linha ficava pública em silêncio. `backend/routers/admin.py` virou dois
  routers (`router_publico`: `/login`, `/logout`, `/me`, sem gate;
  `router`: o resto, com `dependencies=[Depends(exigir_login)]`); os outros 5
  routers (`datahub`, `catalogo`, `laboratorio`, `cockpit`, `linhagem`)
  ganharam a mesma `dependencies=` no `APIRouter(...)`. A chamada imperativa e
  o parâmetro `request` (onde não sobrava outro uso) saíram de todos os
  handlers — rota nova sem gate deixou de ser possível por construção.
- **Páginas HTML fechadas**: `/nuvem`, `/laboratorio`, `/cockpit`, `/linhagem`
  checam `autenticado(request)` e redirecionam pra `/admin` sem sessão;
  `/admin` continua aberto (é a própria tela de login). O mount `/frontend`
  ganhou uma subclasse de `StaticFiles` que recusa qualquer `.html` direto
  (senão o redirect das páginas seria bypassável por
  `/frontend/cockpit.html`) — nada no projeto referenciava esses caminhos
  (confirmado por grep antes de fechar).
- **Rate limit e trava no login**: `backend/auth.py` ganhou contador em
  memória por IP — **10 falhas em 10 minutos bloqueia por 10 minutos**,
  calibrado com a Maria pra não travar o CSC inteiro se estiver atrás do
  mesmo IP da rede interna (um lockout mais agressivo travaria o time inteiro
  por uma pessoa errando a senha).
- **`/docs`, `/redoc`, `/openapi.json` fechados** (`docs_url=None` etc.) —
  expunham o schema e a superfície inteira da API sem login.
- **Tabela de auditoria com ator**: migration `0011_auditoria`
  (`eventos_auditoria`: `criado_em`, `ator` default `'admin'`, `tipo`,
  `detalhe JSONB`, `ip`) + `backend/services/auditoria.py` (`registrar`).
  Cobre exatamente os pontos que o mapeamento do bloco apontou como ausentes:
  `login_sucesso`/`login_falha`/`login_bloqueado`/`logout`,
  `download_arquivo_execucao`, `armazem_criado`, `depara_criado`/
  `depara_apagado`, `insight_aprovado`/`insight_descartado`. Sincronização do
  DataHub não entra — já tem trilha própria (`sincronizacoes_datahub`).
- **Logging estruturado**: `backend/logging_config.py` (novo) —
  `configurar_logging()` lê `LOG_LEVEL`, formato com request id via
  `contextvars`; chamada na importação de `backend/main.py`, cobrindo os
  `log.info` de `backend/migracao.py` que antes não apareciam em lugar
  nenhum. Middleware novo gera o id por requisição, devolve `X-Request-Id`,
  loga 4xx/5xx por **método + path** (nunca query string — onde
  `cliente`/`filial` vazavam em claro no access log do uvicorn, agora
  desligado com `--no-access-log` no `Dockerfile`).
- **Sanitização do `str(e)`**: dos 9 pontos com `except Exception`/`detail=
  str(e)` no projeto, só 3 em `admin.py` eram de fato abertos (`except
  Exception` genérico em torno de `upload_manual.preview`/`aplicar_modelo`) —
  passaram a logar a exceção real (`logger.warning`) e devolver mensagem
  genérica ao cliente. Os outros 6 (2 em `admin.py`, vindo do nosso
  `ingestao.py`/`json` stdlib; 3 nos serviços) já eram seguros — mensagem
  curada, não interpola exceção crua — e ficaram como estavam.

**Decisões do lote:**

1. Rate limit por IP, 10/10min — calibrado com a Maria especificamente pra
   não travar o CSC atrás do mesmo IP da rede interna; estado em memória
   (perde num restart do container), proporcional a ferramenta interna, não
   defesa contra atacante determinado.
2. `/docs` fechado por padrão — reverter é uma linha, se um dia fizer falta
   pra uso próprio.
3. `ator` da auditoria é sempre `"admin"` — senha única, mesma decisão do G1;
   a coluna existe pronta pra identidade por pessoa, que não é deste bloco.
4. Auditoria da sincronização do DataHub não duplicada — já tem trilha
   própria desde o Bloco C.

**Fora do G2 (declarado, fica pro G3):** teste E2E até cockpit/linhagem,
checklist automatizado (`scripts/verificar_v1.py`), atualização de
README/`V1_CRITERIOS_ACEITE.md`/`V1_ARQUITETURA.md`, identidade por pessoa.

**Suíte**: **446 passed** (420 do G1 + 26 novos: 11 de `test_auth.py`
— assinatura/expiração do cookie, rate limit puro e fim-a-fim —, 8 de
`test_auditoria.py` — um por ponto de chamada —, 6 de `test_main.py` — gate
das páginas, bloqueio de `.html`, `/docs` fechado, request id no header — e 1
do ciclo da migration `0011`; nenhum teste anterior removido ou enfraquecido).

**Verificação independente** (agente separado, antes do commit): achou 1
alto e 1 médio, os dois corrigidos antes de fechar o lote:

1. **Alto, corrigido** — o `X-Request-Id` saía `"-"` bem no caso que mais
   precisa de correlação: o `ContextVar` do request id é resetado no
   `finally` do middleware assim que a exceção propaga por cima dele, antes
   do handler global (que roda no `ServerErrorMiddleware`, por fora) poder
   lê-lo. Corrigido gravando o id também em `request.state` (o mesmo objeto
   `Request` sobrevive à pilha inteira, ao contrário do `ContextVar`) e lendo
   de lá no handler.
2. **Médio, corrigido** — o bloqueio de `.html` no `/frontend` era
   case-sensitive; num filesystem case-insensitive (Windows/Mac — não a VM
   Linux de produção) `/frontend/ADMIN.HTML` passava direto. Corrigido com
   `.lower()` antes de comparar; a proteção deixa de depender de acidente do
   sistema de arquivos.

### G3 — Testes de integração, checklist e fechamento da V1 (feito, 04/ago/2026)

Autorizado pela Maria em 04/ago/2026 ("vamos para o g3 agora"), com plano
apresentado e aprovado antes de qualquer código. Ataca o que ficou
deliberadamente fora do G1/G2: testes de integração ponta a ponta e a
documentação/checklist de fechamento da V1 inteira (critério de aceite do
V1.8: testes de integração e regressão; migrations em banco novo E existente;
deploy documentado; checklist executado; verificação independente final e
relatório de entrega).

- **Teste E2E até cockpit/linhagem** (`tests/test_e2e_pipeline.py`, novo):
  roda o pipeline real de ingestão
  (`processamento_datahub.processar_arquivo`, com só o download do Graph
  mockado) e confere que a mesma célula aparece consistente no cockpit
  (`/cockpit/resumo`, `/cockpit/comparacao/filiais`) e na linhagem
  (`/linhagem/celulas`, `/linhagem/celulas/{id}`) — prova que as camadas se
  encaixam de ponta a ponta, não só cada uma isolada (os testes unitários por
  endpoint continuam existindo, sem duplicação).
- **Migrations em banco existente**: achado do próprio checkpoint, não
  código novo — `tests/test_migracao.py` já provava, desde antes deste bloco,
  que a cadeia completa de migrations sobe sem erro a partir do `LEGADO_DDL`
  (o schema real de antes do Alembic) até o head dinâmico, que hoje é a
  `0011_auditoria` do G2. A premissa do plano original ("falta esse teste")
  estava errada; confirmado de forma independente antes de aceitar a
  conclusão.
- **`scripts/verificar_v1.py`** (novo): automatiza a verificação manual pós-
  bloco que vinha sendo feita a mão com curl desde o Bloco A — health, gate
  de login, páginas HTML fechadas, `/frontend/*.html` bloqueado, `/docs`
  fechado, request id no header. Rodado contra o stack local (21 itens OK);
  contra a VM fica para quando a Maria decidir fazer o deploy do bloco.
- **Documentação de fechamento**: seção "Bloco G" em
  `docs/V1_RELATORIO_VERIFICACAO.md` (G1+G2 transcritos pro formato tabular
  do relatório + verificação de fato do G3 + conclusão final da V1);
  checkboxes de V1.0–V1.8 marcados em `docs/V1_CRITERIOS_ACEITE.md`, cada um
  citando a evidência e, onde existe, a ressalva conhecida; `README.md` e
  `docs/V1_ARQUITETURA.md` atualizados para refletir os Blocos A–G feitos.

**Fora do G3 (nenhuma decisão da Maria autoriza, e os critérios de aceite do
V1.8 não pedem):** identidade por pessoa (segue senha única); deploy de fato
na VM (`git push` + runbook) — fica decisão separada da Maria, por ser ação
em sistema compartilhado.

**Suíte**: **448 passed** (446 do G2 + 2 novos de `test_e2e_pipeline.py`).

**Verificação independente** (agente separado, antes do commit): confirmou o
teste E2E e o achado sobre a migration em banco legado, e achou 3 problemas,
todos corrigidos antes de fechar o lote:

1. **Alto, corrigido** — `docs/V1_CRITERIOS_ACEITE.md` citava a seção "Bloco
   G" deste relatório como evidência antes dela existir, e marcava como feito
   o próprio item "verificação independente final" antes da verificação
   acontecer — ordem invertida em relação ao padrão dos Blocos A–F. Corrigido
   escrevendo a seção de fato antes de qualquer commit.
2. **Médio, corrigido** — `scripts/verificar_v1.py` alegava no docstring
   cobrir rate limit, mas o código nunca disparava as 10 falhas necessárias.
   Corrigido ajustando o docstring pra declarar exatamente o que é testado
   (o cenário de rate limit já está coberto, corretamente, em
   `tests/test_auth.py` — testá-lo de novo aqui arriscaria travar o próprio
   IP por 10 minutos).
3. **Médio, corrigido** — `scripts/verificar_v1.py` sem tratamento de erro de
   conexão: contra uma URL fora do ar, estourava traceback bruto em vez de
   reportar FALHA. Corrigido com `try/except httpx.HTTPError`.

Achado adicional, fora do escopo do G3 mas corrigido ao editar o arquivo: o
parágrafo de conclusão do Bloco E em `docs/V1_RELATORIO_VERIFICACAO.md`
estava fisicamente colado no final do documento, depois da conclusão do
Bloco F — reordenado, texto preservado integralmente.

**Achado real, no primeiro deploy de verdade na VM (04/ago/2026):**
`scripts/verificar_v1.py` usava `httpx` — dependência do projeto, mas só
instalada **dentro da imagem Docker** (`scripts/` nem é copiado pro
container pelo `Dockerfile`); o Python do host que roda o `docker compose`
não tem nenhuma dependência do projeto. `ModuleNotFoundError: No module
named 'httpx'` ao rodar no host. **Corrigido**: reescrito só com stdlib
(`http.client`, sem `pip install` nenhum), testado de novo local (mesmos 21
itens OK) e contra porta fechada (FALHA limpa, sem traceback). Nenhuma
verificação — independente ou minha — tinha pegado isso antes porque todo
teste rodou no Windows de desenvolvimento, que tem as dependências do
projeto instaladas globalmente; o host da VM não. Lição: o ambiente onde um
script de operação vai rodar de verdade precisa ser conferido, não só
onde ele foi escrito.

## Conclusão da V1

**Os sete blocos (A–G) estão feitos e implantados.** Relatório completo, com
a lista de pendências conhecidas e declaradas (destino externo do backup,
identidade por pessoa, sem HTTPS, filtro de filial/cliente de valor único,
rate limit sem persistência, grão único por métrica como invariante de
código) em `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Conclusão da V1".
**Deploy do Bloco G (G1+G2+G3) na VM feito em 05/ago/2026** — `origin/main`
e a VM estão no commit `a6b79a5`; validado ao vivo com
`scripts/verificar_v1.py` (21 itens OK) e teste real do chat do Laboratório
com a `ANTHROPIC_API_KEY` configurada no `.env` da VM.

## Próximo bloco autorizado

**Nenhum.** A V1 está fechada e implantada; próximo passo é decisão da Maria
(destino externo do backup, identidade por pessoa, ou novo trabalho fora do
escopo da V1).
