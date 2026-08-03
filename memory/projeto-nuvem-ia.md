---
name: projeto-nuvem-ia
description: Camada de insights SuperFrio — POC DataHub concluída; desde 31/jul/2026 em construção da V1 de produção (blocos A–G, V1_PLANO.md é a fonte do status); Bloco E integrou Anthropic Claude no chat do Laboratório, Bloco F entregou o cockpit executivo (03/ago/2026)
metadata:
  type: project
---

**Fase atual (31/jul/2026): construção da V1 de produção.** A POC SharePoint
DataHub (P0–P6) foi concluída com sucesso em 30/jul/2026; o projeto deixou de ser
prova de conceito. Orientação principal: `docs/V1_NUVEM_IA_DIRECIONAMENTO.md`;
status: `docs/V1_PLANO.md` (fonte única — blocos A–G / macro-lotes V1.0–V1.8).
**Bloco A (V1.0, transição para produto) feito em 31/jul/2026**: docs V1 criados,
telas sem texto de POC, visão executiva consolidada em `/nuvem` (painel duplicado
do admin removido — dívida do P6 resolvida), resumo executivo com peso em
toneladas, filiais com sigla de exibição (001·RMSPII, 015·RMSPIII, 016·RMSPIV —
fonte única `backend/services/filiais_datahub.py`), 154 testes. **Bloco B
(V1.1 catálogo semântico + V1.2 compatibilidade de medidas) feito em
31/jul/2026**: migration 0005 (`unidades`/`conceitos_canonicos`/`catalogo_campos`),
seed semântico (famílias DataHub como fontes lógicas; 20 campos de
ENTRADA_MERCADORIAS por posição), motor de compatibilidade (conversão segura,
bloqueio de soma incompatível, percentual nunca soma), painel "Semântica" no
admin, e o KPI "Volume total" substituído por "Volumes por embalagem" (24
embalagens misturadas no dado real, inclusive KGS — decisão da Maria: separar
por embalagem). **Bloco C (V1.3 persistência e série histórica) feito em
31/jul/2026**: migration 0006 (`medidas` com grão cliente via `cliente_id` +
UNIQUE NULLS NOT DISTINCT; inventário do DataHub persistido; controle de
processamento por arquivo; pendências de cliente), processamento da família
ENTRADA_MERCADORIAS pra camada canônica (execução → recebidas → medidas,
idempotente, reprocessa só o alterado, remove célula órfã), consulta
`GET /datahub/serie` (mensal/anual/acumulado, só métrica aditiva;
`clientes_atendidos` derivado por contagem distinta) e botão "Processar
arquivos" no admin. Decisões da Maria no C: volumes por embalagem FORA da série
persistida; SEM auto-cadastro de cliente (pendência + balde "sem cliente
identificado"). **Bloco D (V1.4 Laboratório: seleção e perfil) feito em
02/ago/2026**: tela nova `/laboratorio`, leitura estrutural genérica de qualquer
arquivo do DataHub (cabeçalho por família, coluna por posição), perfil
determinístico completo (tipos com conformidade, nulos, distintos, mín/máx,
duplicidades, chaves candidatas, cobertura temporal, clientes, granularidade,
qualidade, limitações, amostra) com **soma só onde o catálogo autoriza** e
guarda que descarta o catálogo quando a estrutura do arquivo diverge, migration
0007 (`laboratorio_sessoes`). Decisões da Maria no D: qualquer arquivo é
selecionável; tela separada; amostra sem mascaramento (mascarar vira requisito
do Bloco E). **Lote de correção — identidade e linhagem do DataHub, feito em
02/ago/2026**: migration 0008 (`processamentos_datahub` chaveada por `item_id`,
mais `caminho` e `unidade`; de-para qualificado `RMSPII/001` sem coluna nova),
de-para resolvido antes do download, padrão de nome aceitando filial com hífen
(a RJ deixou de sumir), guarda dupla de colisão que aborta e reverte a rodada, e
a correção do caminho vivo (a sigla das telas passou a sair da origem
qualificada — os arquivos `001` da CWB3 apareciam como RMSPII). Não houve reparo
de linhagem porque nada chegou a ser processado em produção; detalhes e o que
foi cortado da análise original em [[reestruturacao-datahub-4-unidades]].
**Bloco E (V1.5 chat do Laboratório + V1.6 insight aprovado) feito em
03/ago/2026**: primeira integração de IA generativa do projeto — provedor
Anthropic Claude API (`claude-sonnet-5` padrão, configurável por env var).
Contexto controlado (perfil determinístico do Bloco D + amostra mascarada,
nunca a planilha) com cliente/CNPJ trocado por pseudônimo consistente e
unidade sempre junto da filial (nunca só o código, ambíguo entre unidades
desde a reestruturação). Aprovar gera especificação técnica (parte
determinística do perfil + rascunho estruturado da IA), nunca publica KPI.
Verificação independente achou e corrigiu 1 vazamento crítico (nome do
filtro de cliente ecoado sem máscara), 2 altos (erro da IA na aprovação
virando 500; colisão de código de filial entre unidades no contexto) e 1
médio (resposta truncada tratada como sucesso) antes do commit — detalhes em
`docs/V1_PLANO.md`. **Bloco F (V1.7 cockpit executivo) feito em 03/ago/2026**:
duas telas novas — `/cockpit` (visão de diretoria: filtros globais de
período/filial/cliente na URL, cards, série histórica e variação mensal com
Apache ECharts, comparação/ranking de filiais e clientes com participação,
qualidade agregada) e `/linhagem` (grão mínimo real do sistema: célula →
recebida → execução → arquivo de origem no SharePoint — não desce à linha
crua da planilha, que não é persistida). Sem migration nova (lê tabelas que
já existiam desde o Bloco C). Decisão de portabilidade fechada com o time do
Hub SuperFrio antes do lote: link direto (sem iframe — sem auth
compartilhada), filtros na URL, duas telas = dois cards separados no Hub
(detalhes em [[cockpit-hub-integracao]]). **Nenhum bloco seguinte
autorizado** — Bloco G (produção e entrega) aguarda OK.

Nuvem IA junta dados de sistemas (futuramente via Pentaho) e controles manuais
(SharePoint/upload) numa camada fina (de-para + agregados + scores) e mostra uma nuvem
de bolinhas-métricas que acendem quando fogem do próprio padrão histórico, por contexto
(filial × mês). **POC fechada em 21/jul/2026: catering na família RMSP**
(docs/PILOTO.md refeito) — ocupação + contratos take-or-pay + volumetria, com grão
cliente mínimo (Lote 9.5) e perdas fora por ora. Fase atual: construção em lotes (ver
docs/PLANO.md) — Lotes 1 (esqueleto, banco, upload manual), 3 (motor de scores), 7
(de-para oficial das 32 filiais SF), 7.1 (RMSPV/RMSPIV + clientes de catering), 8
(modelos de importação das 5 fontes reais), 8.5 (catálogo de fontes no admin) e R0
(testes + Alembic — primeiro lote da revisão arquitetural de 22/jul/2026,
docs/DIAGNOSTICO.md) feitos; **primeiro deploy na VM real validado em 20/jul/2026**
(só o admin, na 8002, rede interna — runbook em docs/DEPLOY.md) e **R0 deployado na
VM real em 22/jul/2026** (adoção do Alembic no banco legado, 32 armazéns
preservados — achado: VM estava desatualizada desde o deploy de 20/jul, resolvido
pela contingência já prevista em docs/DEPLOY.md). Lote 0 quase fechado
(filiais escolhidas em 21/jul; falta Entra ID, donos do dado e pedidos ao DW — o
relatório detailed agora bloqueia o take or pay). **Lotes R1 e R1.1 fechados em
22/jul/2026** (fontes lógicas + versionamento imutável de modelos + rastreabilidade
fonte/modelo/versão/execução; R1.1 semeia os 5 modelos canônicos com v1 vinculada —
banco novo já nasce utilizável; 33 testes; ver [[decisoes-fechadas]]). **R2 fechado**
(22/jul/2026, linhagem: `medidas_recebidas` + `medida_linhagem` + origem/regra em
`medidas`, migration 0003, 39 testes; ver [[decisoes-fechadas]]). R3 fechado (catálogo
semântico de métricas). **R1–R3 deployados na VM em 30/jul/2026** (`alembic current`
= `0004_catalogo_metricas (head)`), junto com a configuração dos `GRAPH_*` no `.env`
de produção — a saída HTTPS da VM já estava liberada, sem chamado, e a sincronização
real do DataHub rodou na VM sem erro. Runbook em docs/DEPLOY.md, "Passo 4.1".

**Virada de 29/jul/2026: o SharePoint DataHub virou fonte permanente e o vínculo está
funcionando.** O app `nuvem-ia` lê com token de aplicação o site
`/sites/DataHub`, pasta `00.Dados/00.Bronze/00.Dados_Sistemicos` (`Sites.Selected` +
concessão `read`, somente leitura). A pasta tem 228 arquivos / 711 MB em 8 famílias de
export do WMS SLIN (série jan–jul/2026, clientes de catering da POC) — **não** são as 5
fontes canônicas do DW. Trajeto novo pedido pela Maria: olhar sempre o DataHub e mesclar
com as fontes do DW (a atualizar) e com o que ela acrescentar. Inventário completo,
colunas por família, obstáculos e pendências em `docs/FONTES_DATAHUB.md`. Próximo passo:
**KPI básico de amostra** a partir do SharePoint, só para provar o vínculo, antes do KPI
da POC.

Base analítica da POC: `docs/Analise/saida/` (analise_rmsp.xlsx + analise-rmsp/ +
mapa-dados com tabelas por nó e filtro por filial). Dona: Maria Watanabe (CSC).

**Why:** hoje há milhares de BIs individuais e o cruzamento mora na cabeça das pessoas.
**How to apply:** o motor de cruzamento é o valor; o grafo é a embalagem. Máquina tria,
humano valida. Nunca copiar dado bruto pra dentro — só resumos. Ver [[decisoes-fechadas]].
