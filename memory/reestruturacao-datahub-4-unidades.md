---
name: reestruturacao-datahub-4-unidades
description: Em 31/jul/2026 o DataHub virou 4 unidades (RMSPII/CWB3/RJ/SANCA) e criou 7 colisões de nome — CORRIGIDO em 02/ago/2026 pelo lote de identidade (migration 0008)
metadata:
  type: project
---

A pasta do SharePoint DataHub foi reestruturada entre 29 e 31/jul/2026: passou de
**249 arquivos / 31 pastas / 711 MB** para **367 / 61 / 955 MB**, e a raiz deixou de
ter as áreas operacionais direto — agora tem quatro unidades. O que o projeto conhecia
como a pasta inteira é só o galho `RMSPII` (272 arquivos); as outras são `RJ` (42),
`CWB3` (30) e `SANCA` (21). Apareceu a família `ENTRADA_MERCADORIAS (UA)` (35 arquivos),
não catalogada.

**O defeito (corrigido):** `ENTRADA_MERCADORIAS_001_2601..2607.xlsx` existe em `RMSPII/`
e em `CWB3/` — 7 colisões, mesmo nome e mesmo código de filial `001`, armazéns
diferentes. Como `processamentos_datahub` tinha `UNIQUE(arquivo)`, os dois disputavam o
registro, o "pula inalterados" flip-flopava, `_remover_celulas_orfas` fazia um apagar as
células do outro, e `medidas_recebidas` (append-only) ficaria com dado da CWB3 sob o
`armazem_id` da RMSPII, de forma permanente. **Nunca chegou a acontecer em produção**: na
época a VM estava em `0004_catalogo_metricas` (hoje está em `0011`, depois do deploy do
Bloco G em 05/ago/2026) e o processamento do histórico nunca rodou lá — era
risco a prevenir, não dano a compensar. Foi essa constatação que dispensou invalidação
de linhagem, incidente corretivo e máquina de eventos.

**A correção (02/ago/2026, lote entre os Blocos D e E):**

- identidade do arquivo = `item_id` do Graph (migration `0008_identidade_datahub`:
  `UNIQUE(arquivo)` → `UNIQUE(item_id)`, mais `caminho` e `unidade`). Mover ou renomear
  no SharePoint atualiza o registro em vez de criar outro;
- de-para qualificado pela unidade em `armazem_na_fonte` (`RMSPII/001`) — texto livre
  desde o 0001, então sem coluna nova; ver [[filiais-catering-poc]];
- de-para resolvido **antes** do download: origem sem de-para vira pendência e o
  arquivo não é baixado;
- padrão de nome aceita filial com hífen (`004-003`), então a RJ deixou de sumir em
  silêncio e virou pendência visível;
- guarda dupla de colisão em `processar_todos` — pré-checagem por (origem, competência)
  antes de baixar, e checagem por (armazém, competência) durante a rodada. Colisão
  **aborta e reverte a rodada inteira**, ao contrário de erro de arquivo, que só marca
  aquele arquivo;
- o mesmo defeito existia no **caminho vivo** e também foi corrigido: as bolinhas do
  `/nuvem` rotulavam os 7 arquivos da CWB3 como "001 · RMSPII", e o card executivo podia
  pegar arquivo de outra unidade — `item_mais_recente()` passou a se restringir às
  unidades com de-para (hoje só RMSPII).

**Fora do lote, de propósito:** tabela nova de arquivo, hash de conteúdo, leitor da
variante RJ de 18 colunas, e o de-para real de CWB3/SANCA/RJ (decisão humana, não
código). A `ENTRADA_MERCADORIAS (UA)` não casa no padrão de nome, então não é
processada.

**Why:** era regressão em código já entregue e verificado (Bloco C) causada por mudança
externa, não por bug de escrita — e o erro não aparecia na tela, só na linhagem.

**How to apply:** ao processar na VM, esperar CWB3, SANCA e RJ como **pendências** no
painel — é o comportamento correto, não falha. O de-para novo se cria com uma linha
qualificada em `depara_armazem`. Análise e decisões descartadas:
`docs/decisoes_datahub_identidade_linhagem.md`; levantamento da fonte:
`docs/VERIFICACAO_DATAHUB_31JUL2026.html`.
