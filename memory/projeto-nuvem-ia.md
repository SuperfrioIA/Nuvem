---
name: projeto-nuvem-ia
description: Camada de insights SuperFrio — junta silos numa camada fina e mostra nuvem de métricas que acendem fora do padrão
metadata:
  type: project
---

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
`medidas`, migration 0003, 39 testes; ver [[decisoes-fechadas]]). R1/R1.1/R2 ainda não
deployados na VM. Próximo: deploy na VM ou decidir o Lote 9 (ocupação composta). Base
analítica da POC: `docs/Analise/saida/` (analise_rmsp.xlsx + analise-rmsp/ +
mapa-dados com tabelas por nó e filtro por filial). Dona: Maria Watanabe (CSC).

**Why:** hoje há milhares de BIs individuais e o cruzamento mora na cabeça das pessoas.
**How to apply:** o motor de cruzamento é o valor; o grafo é a embalagem. Máquina tria,
humano valida. Nunca copiar dado bruto pra dentro — só resumos. Ver [[decisoes-fechadas]].
