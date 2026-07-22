---
name: decisoes-fechadas
description: Decisões de arquitetura fechadas em 15/jul/2026 — não rediscutir sem a Maria pedir
metadata:
  type: project
---

- App separado do Portal (Receita 3 do CONTRIBUTING do Hub); o Hub só cadastra um card.
- Mesma VM do Conciliador (porta 80) e Hub (8001); nuvem-ia na **8002**, compose próprio
  com 2 containers: `nuvem-app` (FastAPI + APScheduler + frontend vanilla) e `nuvem-db`
  (Postgres, volume nomeado).
- **Conectores plugáveis** (interface `testar()`/`buscar()` → formato canônico
  `{metrica, armazem_na_fonte, competencia, valor}`): `upload_manual` e `sharepoint_excel`
  na v1, alternáveis por toggle no admin; `pentaho_sql` no futuro sem mudar motor/tela.
- Graph API depende de app registration no Entra ID (`Sites.Selected`) — caminho crítico
  externo com a TI; o código fica pronto, credenciais entram depois.
- Auth: senha única protegendo só o `/admin`; nuvem aberta na rede interna.
- Camada fina: 9 tabelas (conectores, armazens, depara_armazem, depara_pendencias,
  metricas, medidas, scores, execucoes, **modelos_importacao**). `medidas` com unique
  (metrica, armazem, competencia) → upsert idempotente. Scores são derivados/recalculáveis
  (cache), não fonte de verdade.
- Motor: Python puro, score = desvio vs próprio histórico 12–24m. Sem libs de ML.
- Da revisão de escalabilidade (15/jul/2026): rotina rebusca as últimas 3 competências;
  reprocesso = delete+insert por conector × competência; valor sem de-para vira
  pendência no admin (nunca descarte silencioso); backup = pg_dump diário pra fora da
  VM + retenção dos xlsx do upload (de-para não é rederivável); `nuvem-app` com worker
  único (APScheduler duplicaria); dimensão cliente = v2 com segunda tabela-fato
  (`medidas_cliente`), não coluna em `medidas`.
- Da análise de arquivos reais do lote 1 (15/jul/2026): relatórios reais não são
  tabela limpa armazém×mês — vêm em grão mais fino (posição×dia, SKU×lote), com várias
  colunas candidatas pra mesma dimensão (ex: filial como SK/ERP/WMS/QLS) e cliente
  misturado. Por isso `upload_manual` ganhou **modelos de importação**: mapeamento de
  colunas nomeado e reutilizável (tabela `modelos_importacao`), salvo por relatório.
  Armazém e competência podem vir de uma coluna do arquivo OU ser valor fixo digitado
  no upload (relatório já recortado pra 1 filial/1 mês, sem essas colunas). Métrica é
  soma direta de uma coluna OU razão entre duas (numerador/denominador — necessário pra
  métricas de nível/capacidade tipo ocupação; a razão das somas já resolve certo mesmo
  com várias linhas por dia dentro do mês). Coluna de cliente é reconhecida no modelo
  (documentação, mira a v2) mas não persiste — o processamento agrega (soma/razão) por
  armazém+competência+métrica, absorvendo cliente/SKU/posição/etc.; coluna não mapeada
  simplesmente não entra no banco. Export tipo matriz/pivô do Power BI (hierárquico,
  com subtotal) não é suportado no parser — fonte deve exportar em tabela plana.
- Retenção do arquivo original do `upload_manual` **começa no Lote 1** (antecipada do
  Lote 4): é o caminho de drill-down manual pra essa fonte (abrir o `.xlsx` de novo),
  já que a camada fina só guarda o consolidado. Começa local (pasta na VM, plugável) e
  migra pra SharePoint (Graph API, mesma credencial do `sharepoint_excel`) quando o
  Entra ID for liberado — **o pedido à TI (Lote 0) precisa incluir permissão de escrita
  (write) na concessão de acesso ao site**, não só leitura (a leitura já era necessária
  pra buscar a planilha de ocupação).
- Motor de scores (Lote 3, fechado 16/jul/2026): média e desvio-padrão amostral (não
  mediana/MAD) da janela de até 24 competências anteriores à analisada (exclui o mês
  corrente); histórico mínimo de 6 competências pra ser avaliável — abaixo disso, estado
  `historico_curto` (tem valor, mas ainda sem score). Limiar `|z| >= 2` vira
  `fora_padrao`; desvio-padrão zero com valor igual à média é `normal`, diferente é
  `fora_padrao` direto (z indefinido). `scores` é sempre recalculado por completo
  (delete+insert) a cada rodada, nunca seletivo — volume do piloto não justifica a
  complexidade. Disparo automático ao fim de todo `upload/processar`, mais endpoint
  manual de recálculo. Validado local com dado sintético (reproduziu o padrão do
  cenário conhecido — perda e volumetria fora do padrão juntas); ainda não validado com
  dado real (ver docs/PLANO.md, Lote 3).

- Da análise dos relatórios reais do DW (17/jul/2026, `docs/analise/saida/`): **nada de
  DW novo** — a camada fina segue só com de-para + agregados armazém×competência +
  scores; relatório bruto fica como arquivo retido do upload, nunca vira tabela. **A
  POC/MVP fecha só com upload manual** dos exports que já saem hoje; integração com o
  banco do DW via API (`dw_api`) é degrau pós-MVP (Lote 10). Chave mestra descoberta:
  `SK_FILIAL` do fato = `FK_FILIAL` das STG (mesma surrogate da DIM_FILIAL); de-para
  consolidado das 31 filiais SF pronto pra virar seed (Lote 7). O export bruto do fato
  de volumetria (2021→hoje) é quem valida o motor com dado real (Lote 8).

- Lote 7 fechado (17/jul/2026): de-para real de 32 filiais SF carregado em
  `armazens`/`depara_armazem` via `backend/seed_depara.py` (literais no código, chamado
  de `init_db()` — idempotente, nunca sobrescreve edição manual). Cruzando a análise do
  DW com o cadastro oficial Protheus (`Empresas Grupo Superfrio`, CSV trazido pela
  Maria), apareceram divergências reais: código ERP da JAC estava errado na análise
  original (001007 → correto é 001008); 5 filiais têm sigla operacional (WMS) diferente
  da sigla do cadastro Protheus, mesma empresa (CVDI/CVD, MAQ/MAQII, SSA/SSAI,
  RMSP/RMSPI, POA/POAI) — a sigla operacional é a oficial no banco, a do cadastro é
  apelido extra; MRS não tem volumetria desde 02/2023 e está marcada inativa
  (`ativo=false`) — some da lista padrão mas segue resolvendo de-para de uploads
  antigos. RPIII e CWBI não têm histórico de volumetria (pré-operacionais) mas ficam
  ativas. Nome do armazém = sigla + município (não existe nome fantasia em nenhuma
  fonte); 3 filiais sem município (RPIII, MRS, CWBI) usam a sigla como nome.

- Da análise da família RMSP (21/jul/2026, `docs/Analise/saida/`: `analise_rmsp.xlsx`
  + página `analise-rmsp/` + mapa-dados com tabelas por nó e filtro por filial): **a
  POC é catering na família RMSP** (docs/PILOTO.md refeito nessa data). Filiais =
  família toda: RMSPII/III núcleo (Sapore, GR, Sodexo, Wyda/Cucinare, Pimenta Verde,
  Novita, Convida, FLV 7, OG, Bimbo), RMSP dá o caso Frimesa (anti-dupla contagem),
  RMSPV acompanha (nasceu no WMS em 14/jul/2026, vazia, fora do de-para — Lote 7.1).
  **Grão cliente mínimo entra na POC** (revisão pontual do "cliente = v2"):
  `medidas_cliente` só pros ~12 clientes de catering, com posições contratadas, status
  do contrato e volumetria — Lote 9.5. **Perdas fica fora da POC** (volta depois como
  métrica nova). "Vencido-operando" = contrato vencido + cliente com movimento nos
  últimos 60 dias no fato (chave ERP `NK_CLIENTE`, nunca o nome WMS — vem vazio pra
  vários). Segmento dos clientes de catering está errado no DW ("Ind. Química/Resinas/
  Tintas") — lista curada na camada fina, não filtrar por segmento.

- Apresentação da POC (21/jul/2026): os dados ficam na máquina da Maria (upload manual
  + retenção em pasta local, desenho que o Lote 1 já entrega) — SharePoint (conector do
  Lote 2 e a concessão de escrita pendente do Lote 0) **sai do caminho crítico da demo**
  e entra depois, sem mudar arquitetura (já era plugável). Requisito novo na mesma data:
  tela **catálogo de fontes, dentro do admin** (Lote 8.5) — lista todas as planilhas que
  o sistema vê, com descrição/resumo, origem (de qual tabela vem: fato/STG/dimensão do
  DW ou cadastro de banco, conforme o mapeamento da análise) e drill-down de colunas
  (significado + papel no modelo de importação); metadados em
  `catalogo_fontes`/`catalogo_colunas` com seed em literais no código (padrão
  `seed_depara.py`, porque `docs/Analise/` está no `.gitignore`).

- Lotes 7.1 e 8.5 fechados (22/jul/2026), construídos em paralelo em worktrees
  isolados (branches `lote-7.1`/`lote-8.5`) e mesclados na main sem drama (único
  conflito foi textual, em `database.py`, resolvido lado a lado). RMSPV ativa no
  seed (nasceu no WMS 14/jul); RMSPIV inativa (só-cadastro). Tabela `clientes` com
  os 11 clientes de catering da família RMSP (não 12 — Tirolez/Delly/Frimesa/Irmãos
  Boa são contrato de locação da RMSP, fora do núcleo RMSPII/RMSPIII, excluídos por
  instrução explícita). Catálogo de fontes (`catalogo_fontes`/`catalogo_colunas`)
  documenta a planilha bruta inteira das 5 famílias da POC, não só o dicionário
  curado — `modelo_id` fica `NULL` até o Lote 8 criar os modelos de importação de
  verdade. Achado de infra (não é bug do projeto): `docker-compose.override.yml`
  precisa da tag `!override` do Compose Spec pra sobrescrever `ports` em vez de
  concatenar (mergepadrão do Compose é aditivo em listas).

- Da revisão arquitetural (22/jul/2026, **docs/DIAGNOSTICO.md** — diagnóstico, matriz
  de riscos e plano R0–R6 aprovado por partes): **R0 fechado** — Alembic (baseline
  `0001_baseline` com as 12 tabelas; `init_db` só seeds; banco legado recebe stamp
  **só depois** de validação de schema — divergência aborta sem tocar o banco, nunca
  stamp automático em banco divergente); limite de upload (`UPLOAD_MAX_MB`, 50 MB);
  suíte pytest com Postgres real (25 testes — mapeamentos REAIS dos 5 modelos
  extraídos do banco do worktree lote-8 em `tests/modelos_reais.py`, que também é o
  insumo do futuro seed do R1; dados de teste sintéticos, não substituem validação
  visual dos arquivos reais). **Take or pay** (decisão de negócio confirmada):
  faturável = max(garantia mínima vigente, ocupação física do fechamento) por
  cliente×filial×mês; ocupação física ≠ ocupação econômica (dashboard corporativo);
  nenhuma fonte atual tem física por cliente pras RMSP → cálculo indisponível, sem
  proxy por volumetria, bloqueado pelo relatório detailed do DW (pedido do Lote 0);
  divergência de 917 no card take-or-pay+locações do Power BI é pendência explícita.
  R1–R6 não autorizados ainda; R1 (fontes lógicas + versionamento imutável de
  modelos, editar = nova versão) terá desenho apresentado antes de construir.

**Why:** decisões tomadas em conversa com a Maria em 15/jul/2026, 16/jul/2026, 17/jul/2026, 21/jul/2026 e 22/jul/2026 — evita rediscutir do zero.
**How to apply:** detalhes em docs/ARQUITETURA.md e docs/PLANO.md. Mudar essas decisões
só com OK explícito dela. Ver [[projeto-nuvem-ia]].
