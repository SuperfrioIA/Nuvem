---
name: projeto-nuvem-ia
description: Camada de insights SuperFrio — POC DataHub concluída; desde 31/jul/2026 em construção da V1 de produção (blocos A–G, V1_PLANO.md é a fonte do status)
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
fonte única `backend/services/filiais_datahub.py`), 154 testes. **Nenhum bloco
seguinte autorizado** — Bloco B (catálogo semântico + compatibilidade de medidas)
aguarda OK da Maria. O texto abaixo é o histórico até a virada.

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
