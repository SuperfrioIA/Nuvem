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
| B | V1.1 Catálogo semântico + V1.2 Compatibilidade de medidas | a fazer — **não autorizado** |
| C | V1.3 Persistência e série histórica | a fazer — não autorizado |
| D | V1.4 Laboratório: seleção e perfil | a fazer — não autorizado |
| E | V1.5 Laboratório: chat + V1.6 Insight aprovado | a fazer — não autorizado |
| F | V1.7 Cockpit executivo | a fazer — não autorizado |
| G | V1.8 Produção e entrega | a fazer — não autorizado |

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

**Pendências herdadas (não-código), na ordem:**

1. Validar o `/nuvem` ao vivo contra o SharePoint real (herdada do P5.5; as
   mudanças do Bloco A tornam essa validação ainda mais necessária);
2. Subir o código atual pra VM (`docs/DEPLOY.md`, passo 4.1) **e aplicar o
   `UPDATE` de `ativo` das filiais** (`memory/filiais-catering-poc.md`);
3. Decidir devolução/rótulo no card de valor (`docs/ENTREGA_POC.md`, seção 3);
4. Pendências humanas das fontes (`docs/FONTES_DATAHUB.md`, seção 6).

**Suíte**: **154 passed** (150 da POC + 4 novos: peso abaixo de mil toneladas por
extenso, filial com sigla no resumo, filial sem de-para fica sem sigla, de-para de
exibição das 3 filiais confirmadas; asserts de `filial_sigla` acrescentados nos
testes existentes de router e nuvem; os asserts de texto do resumo foram ajustados
de "milhões de kg" pra toneladas — nenhum teste removido).
**Verificação independente**: `docs/V1_RELATORIO_VERIFICACAO.md`.

## Próximo bloco autorizado

**Nenhum.** O Bloco B (V1.1 catálogo semântico + V1.2 compatibilidade de medidas)
só começa com autorização explícita da Maria.
