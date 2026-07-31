# V1 — Arquitetura

Criado em 30/jul/2026 (Bloco A / V1.0). Complementa — não substitui —
`docs/ARQUITETURA.md` (desenho fechado em 15/jul/2026, ainda válido no que não
conflita) e `docs/DIAGNOSTICO.md` (revisão arquitetural de 22/jul/2026, R0–R3
implementados). Origem das regras: `docs/V1_NUVEM_IA_DIRECIONAMENTO.md`,
seções 5–13.

Princípio geral da V1: **preservar a estrutura atual e fazer mudanças aditivas.**
Nada de microsserviços, framework frontend novo, troca de banco ou reescrita.
Não mover arquivos por estética.

## Base herdada (o que já existe e permanece)

- **Infra**: FastAPI + Postgres 16 + Alembic (migrations `0001`–`0004`) + Docker
  Compose, porta 8002, worker único, frontend vanilla sem build step.
- **Ingestão**: conector `upload_manual` com modelos de importação versionados
  (`modelo_versoes` imutáveis; editar = nova versão); execuções com versão exata;
  arquivo original retido.
- **Linhagem (R2)**: `medidas_recebidas` (append-only) → `medidas` (canônica,
  upsert idempotente) + `medida_linhagem` pra derivadas; rastro completo de um
  número até o arquivo original.
- **Catálogo (R3 + 8.5)**: `metricas` com campos semânticos (domínio, tipo,
  direção de risco, agregação padrão, comparabilidade); criação implícita de
  métrica extinta; `catalogo_fontes`/`catalogo_colunas` como fonte lógica.
- **DataHub (P1–P5.5)**: cliente Graph somente leitura (`Sites.Selected` + `read`,
  Client Credentials, cache de token, download por `item_id` com corte de
  tamanho); inventário em cache de processo; leitura validada de
  `ENTRADA_MERCADORIAS` (coluna por nome, cabeçalho conferido); KPIs
  determinísticos; resumo por template; página `/nuvem`.
- **Motor de scores** (Lote 3): z-score por métrica×armazém, intocado.
- **Testes**: suíte pytest com Postgres real (nunca mock de banco).

## Estrutura-alvo (aditiva, construída pelos blocos B–F)

```
backend/
├── catalogo/                    ← V1.1 (Bloco B)
│   ├── conceitos.py             conceitos canônicos
│   ├── campos.py                campos de fonte → conceito
│   ├── unidades.py              unidades, categorias, conversões seguras
│   └── metricas.py              definição governada de KPI
├── services/
│   ├── catalogo_semantico.py    ← V1.1
│   ├── compatibilidade_medidas.py ← V1.2 (bloqueio de soma incompatível)
│   ├── perfil_dados.py          ← V1.4 (perfil determinístico pré-IA)
│   ├── laboratorio_insights.py  ← V1.5 (sessões, chat, rastreabilidade)
│   ├── promocao_kpi.py          ← V1.6 (especificação a partir do insight)
│   ├── cockpit.py               ← V1.7 (consultas com filtros globais)
│   └── (existentes: graph_datahub, inventario_datahub, entrada_mercadorias,
│        kpis_poc, resumo_poc, nuvem_datahub — mantidos)
├── routers/
│   ├── catalogo.py              ← V1.1
│   ├── laboratorio.py           ← V1.4/V1.5
│   ├── cockpit.py               ← V1.7
│   └── (existentes: admin.py, datahub.py — mantidos)

frontend/
├── admin.html                   administração (upload, de-para, catálogos, DataHub)
├── nuvem.html                   nuvem do DataHub (mapa + visão executiva da família integrada)
├── laboratorio.html             ← V1.4/V1.5
└── cockpit.html                 ← V1.7
```

## Modelo semântico (V1.1) — resumo

Cada campo de fonte carrega, quando aplicável: fonte, família,
arquivo/tabela/endpoint, nome original, descrição funcional, conceito canônico,
tipo de dado, unidade original e canônica, **categoria da unidade** (massa,
quantidade, embalagem, estrutura logística, cubagem, desconhecida),
transformação, regra de agregação, granularidade, dimensões
(competência/filial/cliente), obrigatoriedade, status do mapeamento, versão,
vigência, observações e responsável pela validação. Exemplo canônico na seção 6
do direcionamento (`SLIN.Peso Bruto` → `peso_bruto_movimentado`, kg, massa, soma).

Regra de ouro: campos diferentes só consolidam no mesmo conceito quando
definição, unidade, granularidade, transformação e agregação forem compatíveis
**e aprovadas**. Mapeamento é dado versionado, não `if` no código.

## Modelo de KPI governado (V1.1/V1.7) — resumo

Todo KPI declara: nome/código, pergunta de negócio, descrição executiva,
conceitos, fontes permitidas, fórmula, unidade canônica, granularidade,
dimensões, agregação temporal/por filial/por cliente, **tipo aditivo,
semi-aditivo ou não aditivo**, filtros/exclusões, qualidade, comparabilidade,
versão/vigência, status, aprovação, linhagem e testes esperados. Percentuais
nunca são somados diretamente; semi-aditivos (ex.: ocupação) definem regra por
dimensão (última fotografia válida / média ponderada / não permitido).

## Persistência e série histórica (V1.3)

O fluxo da POC (ler só o arquivo mais recente, calcular em memória, não
persistir) **não atende à V1**. O caminho passa a ser a camada existente:

```
execuções → medidas_recebidas → medidas canônicas → consultas do cockpit
```

Granularidade mínima recomendada: competência × filial × cliente × métrica.
Fonte sem cliente: manter ausente (não inventar) e restringir análises
dependentes. Suportar série mensal, consolidação anual, mês contra mês,
período anterior, acumulado, rankings, participação e visão consolidada.
Reprocessamento idempotente; competência corrente republicada substitui.
Insumos já mapeados: `docs/PLANO.md` Lote 11 (ressalvas do dado) e
`docs/FONTES_DATAHUB.md` (obstáculos 1–8 — cabeçalho variável, `_f1/_f2/_f3`,
`DADOS_GERAIS` quebrado, 711 MB → conector incremental).

## Laboratório de Insights (V1.4–V1.6)

Fluxo: selecionar fontes → **perfil determinístico em código** → contexto do
catálogo → pergunta (sugerida ou livre) → análise controlada → resposta no chat
→ avaliar → salvar/descartar/aprovar. A IA recebe metadados, estatísticas e
amostra segura — nunca descobre os números livremente. Aprovação gera
especificação técnica; publicação de KPI é sempre implementação determinística
posterior (V1.6 → implementação → testes → validação → publicação).

## Segurança e governança da IA (V1.5+)

Antes de enviar qualquer dado: provedor aprovado, política corporativa,
retenção/mascaramento definidos, nenhum segredo, dados pessoais e de clientes
limitados, tamanho limitado, preferência por agregados e perfil estruturado,
amostra reduzida, registro do que foi enviado + modelo + parâmetros.

Proteções obrigatórias (já praticadas nas telas atuais, valem pra tudo que é
novo): prompt injection em células, conteúdo externo malicioso, HTML não
escapado, URLs arbitrárias, comandos escondidos, exposição de token, acesso
indevido, resposta da IA tratada como dado não confiável.

## Decisões de arquitetura do Bloco A (V1.0)

- Visão executiva consolidada em `/nuvem` (o admin deixou de duplicar o painel
  de KPIs — dívida do P6 resolvida pelo caminho "tirar do admin");
- Exibição de peso: cálculo interno em kg, conversão pra tonelada só na
  apresentação (card, detalhamento e texto);
- De-para de filial **só de exibição** (código → sigla oficial confirmada:
  001·RMSPII, 015·RMSPIII, 016·RMSPIV), fonte única no backend
  (`backend/services/filiais_datahub.py`), exposto como `filial_sigla` nas
  respostas de `/kpis` e `/nuvem`; o frontend só formata o rótulo
  (`rotuloFilial` em `comum.js`). Não é ingestão nem depende de
  `depara_armazem` — quando a V1.3 persistir por filial, o de-para real do
  banco assume;
- Nenhuma migration no Bloco A; schema segue em `0004_catalogo_metricas`.

## Verificação independente

Após cada bloco: `docs/V1_RELATORIO_VERIFICACAO.md` (escopo, arquitetura,
migrations, compatibilidade, segurança, cálculos, unidades, filtros, qualidade,
testes, documentação, código morto, dependências, regressões, exposição de
dados, erros, rastreabilidade). Futuro, quando útil: `scripts/verificar_v1.py`.
