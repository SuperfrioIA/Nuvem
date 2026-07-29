# Organização do repositório — inventário (Lote P0)

Levantamento de 29/jul/2026. Separa o que está **rastreado no Git** (`git ls-files`)
do que existe **só no disco** da Maria. Regra inegociável (seção 7.1 de
`docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md`): nada em `docs/Analise/` e `data/` é
movido, renomeado ou removido — classificados como "local (fora do Git)" e ponto.

Classificação: **ativo** (código/doc em uso corrente) · **histórico** (registro de
decisão/contexto passado, não editável em si) · **referência** (consulta técnica
estável) · **gerado** (artefato de build/execução) · **dado sensível** · **local
(fora do Git)**.

---

## 1. Raiz

| Caminho | Finalidade | Referenciado | Classificação | Ação |
|---|---|---|---|---|
| `.env.example` | Template das variáveis de ambiente (`GRAPH_*` já documentado) | sim (DEPLOY, FONTES_DATAHUB) | ativo | manter |
| `.gitignore` | Regras de exclusão do Git | sim | ativo | manter (ver §5 — ganha `.vscode/`) |
| `CLAUDE.md` | Instruções de sessão de IA | sim (lido no início de toda sessão) | ativo | **atualizar** (aponta pro POC_ATUAL.md) |
| `Dockerfile` | Build da imagem `nuvem-app` | sim | ativo | manter |
| `MEMORY.md` | Índice da memória viva | sim | ativo | **atualizar** |
| `README.md` | Porta de entrada do repo | sim | ativo | **atualizar** |
| `alembic.ini` | Config do Alembic | sim | ativo | manter |
| `docker-compose.yml` | Orquestração dos 2 containers | sim | ativo | manter |
| `pytest.ini` | Config do pytest | sim | ativo | manter |
| `requirements.txt` | Dependências de produção | sim | ativo | manter |
| `requirements-dev.txt` | Dependências de teste (pytest etc.) | sim | ativo | manter |

## 2. `alembic/`

| Caminho | Finalidade | Classificação | Ação |
|---|---|---|---|
| `alembic/env.py` | Bootstrap do Alembic (lê `DATABASE_URL`) | ativo | manter |
| `alembic/versions/0001_baseline.py` | Baseline — as 12 tabelas originais | ativo/histórico (migration nunca se edita) | manter |
| `alembic/versions/0002_versionamento_modelos.py` | Lote R1 — `modelo_versoes` etc. | idem | manter |
| `alembic/versions/0003_linhagem.py` | Lote R2 — `medidas_recebidas`/`medida_linhagem` | idem | manter |
| `alembic/versions/0004_catalogo_metricas.py` | Lote R3 — catálogo semântico | idem | manter |

Migrations aplicadas nunca são reescritas ou removidas — são histórico executável.
Nenhuma ação aqui além de manter.

## 3. `backend/`

| Caminho | Finalidade | Classificação | Ação |
|---|---|---|---|
| `backend/__init__.py` | Marca o pacote | ativo | manter |
| `backend/main.py` | Entrypoint FastAPI | ativo | manter |
| `backend/database.py` | Schema (seeds idempotentes; DDL vive nas migrations) | ativo | manter |
| `backend/migracao.py` | Lógica de adoção do banco legado pelo Alembic (Lote R0) | ativo | manter |
| `backend/auth.py` | Senha única do `/admin` | ativo | manter |
| `backend/armazenamento.py` | Retenção do arquivo original do upload | ativo | manter |
| `backend/ingestao.py` | De-para, upsert, gatilho do motor | ativo | manter |
| `backend/motor.py` | Motor de scores (stdlib `statistics`) | ativo | manter |
| `backend/versoes.py` | Versionamento imutável de modelos de importação (Lote R1) | ativo | manter |
| `backend/seed_depara.py` | Seed do de-para oficial de filiais (Lote 7) | ativo | manter |
| `backend/seed_clientes.py` | Seed dos 11 clientes de catering (Lote 7.1) | ativo | manter |
| `backend/seed_catalogo.py` | Seed do catálogo de fontes/colunas (Lote 8.5) | ativo | manter |
| `backend/seed_modelos.py` | Seed dos 5 modelos canônicos + v1 (Lote R1.1) | ativo | manter |
| `backend/seed_metricas.py` | Seed dos campos semânticos das métricas (Lote R3) | ativo | manter |
| `backend/conectores/__init__.py` | Marca o pacote | ativo | manter |
| `backend/conectores/base.py` | Interface `Conector` (`testar/buscar/detalhar`) | ativo (não instanciada ainda — Lote 2 pendente, achado já registrado em DIAGNOSTICO) | manter |
| `backend/conectores/upload_manual.py` | Parser (csv/xlsx, filtros, soma/razão, divisor) | ativo | manter |
| `backend/routers/__init__.py` | Marca o pacote | ativo | manter |
| `backend/routers/admin.py` | Endpoints do admin | ativo | manter |

Nenhum arquivo órfão ou duplicado encontrado em `backend/`. `backend/services/` e
mais um módulo em `backend/routers/` (`datahub.py`) são esperados a partir do
Lote P1 — não criados neste lote.

## 4. `tests/`

| Caminho | Finalidade | Classificação | Ação |
|---|---|---|---|
| `tests/__init__.py` | Marca o pacote | ativo | manter |
| `tests/conftest.py` | Fixtures (Postgres real, nunca mock) | ativo | manter |
| `tests/arquivos_sinteticos.py` | Geradores de xlsx/csv sintéticos pros testes | ativo | manter |
| `tests/modelos_reais.py` | Re-exporta os mapeamentos de `backend/seed_modelos.py` (a imagem Docker só copia `backend/`) | ativo | manter |
| `tests/test_parser.py` | Testes do parser com os 5 mapeamentos reais | ativo | manter |
| `tests/test_ingestao.py` | De-para/pendência/upsert idempotente | ativo | manter |
| `tests/test_motor.py` | Estados/limiar/recálculo idempotente | ativo | manter |
| `tests/test_migracao.py` | Banco novo/legado válido/legado divergente | ativo | manter |
| `tests/test_versionamento.py` | Versionamento de modelos (Lote R1) | ativo | manter |
| `tests/test_upload_fluxos.py` | 5 fluxos de upload ponta a ponta pela API | ativo | manter |

44 testes ao todo (ver `docs/DIAGNOSTICO.md`/`docs/PLANO.md`). Nenhum candidato à
remoção.

## 5. Raiz — pasta não rastreada, fora do escopo do `.gitignore`

| Caminho | Finalidade | Classificação | Ação |
|---|---|---|---|
| `.vscode/settings.json` | Preferência pessoal de cor do editor (extensão Peacock) — sem segredo, conferido | local (fora do Git), não listado no `.gitignore` | **adicionar `.vscode/` ao `.gitignore`** (config pessoal de editor, não deveria virar candidata a commit acidental) |

## 6. `docs/`

| Caminho | Finalidade | Referenciado | Classificação | Ação |
|---|---|---|---|---|
| `docs/POC_ATUAL.md` | **Novo** — dono único do escopo/status da POC DataHub | sim (CLAUDE/README/MEMORY passam a apontar) | ativo | criado neste lote |
| `docs/ORGANIZACAO_REPOSITORIO.md` | Este arquivo | sim | ativo | criado neste lote |
| `docs/PLANO.md` | Plano de lotes de produto (0–10, R0–R3) + status vivo desses lotes | sim (muito referenciado) | ativo/histórico misto | **aviso no topo** (sem mover/reescrever linhas existentes) |
| `docs/ARQUITETURA.md` | Desenho técnico fechado (conectores, schema, deploy) | sim | referência | manter |
| `docs/DIAGNOSTICO.md` | Diagnóstico + matriz de riscos + plano R0–R6 (22/jul/2026) | sim (ARQUITETURA, PLANO, decisões) | referência/histórico | manter |
| `docs/DEPLOY.md` | Runbook de deploy na VM + como rodar testes (Docker/WSL) | sim | ativo | manter |
| `docs/FONTES_DATAHUB.md` | Inventário do SharePoint DataHub (29/jul/2026) | sim (base do P1–P3) | ativo | manter |
| `docs/PILOTO.md` | Escopo do piloto catering RMSP | sim | ativo | manter |
| `docs/CONCEITO.md` | O problema, o núcleo da ideia, a escada de mecanismos | sim (README) | referência (fundamento conceitual, não muda) | manter |
| `docs/HISTORICO.md` | Prompts originais da Maria que fundaram o projeto (14–15/jul/2026) | sim (README, CLAUDE) | histórico | manter no lugar — candidato a `docs/historico/` num lote futuro, não movido agora pra não quebrar link nenhum |
| `docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md` | Especificação original dos Lotes P0–P6 | sim (POC_ATUAL.md aponta pra cá o detalhe técnico) | histórico (a partir de hoje) | **marcado como superado** no topo, mantido no lugar (não movido) |
| `docs/configuracao_graph_api.docx` | Pedido original à TI (app registration) — parcialmente superado (ver FONTES_DATAHUB §1) | sim (FONTES_DATAHUB cita) | histórico | manter — único binário rastreado, já conferido sem credenciais |

Nenhuma reorganização grande de `docs/` neste lote: os únicos claramente
"história pura" (`HISTORICO.md`, a partir de hoje também o DIRECIONAMENTO) ficam no
lugar por segurança de link — mover é reversível e fica como próximo passo
opcional, não um requisito do P0.

## 7. `memory/`

| Caminho | Finalidade | Classificação | Ação |
|---|---|---|---|
| `memory/decisoes-fechadas.md` | Decisões de arquitetura fechadas, entradas datadas | ativo | **nova entrada datada** (29/jul/2026, Lote P0) |
| `memory/projeto-nuvem-ia.md` | Estado vivo do projeto | ativo | manter |
| `memory/vm-nuvem-ia.md` | IP interno da VM de produção | referência/dado de infra | manter — IP é de rede interna (não pública), já usado deliberadamente para validar deploy sem SSH; repositório é privado. Nenhuma ação — sinalizado aqui por transparência (item 7.4 do DIRECIONAMENTO) |

## 8. `frontend/`

| Caminho | Finalidade | Classificação | Ação |
|---|---|---|---|
| `frontend/admin.html` | Tela única do admin (upload, de-para, catálogo, métricas) | ativo | manter |

`frontend/datahub.html` e `frontend/kpis.html` são esperados a partir dos Lotes
P2/P4 — não criados neste lote.

## 9. Verificação de dados/segredos rastreados (seção 7.3 do DIRECIONAMENTO)

Busca por padrões de credencial (`client_secret`, `password=`, `senha=`, `token=`,
`api_key=`) em todo o repositório rastreado: só apareceram nomes de variável/campo
em `.env.example`, `docs/FONTES_DATAHUB.md`, `docs/DEPLOY.md`,
`docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md`, `frontend/admin.html`,
`backend/auth.py` e `tests/conftest.py` — nenhum valor real. Único binário
rastreado: `docs/configuracao_graph_api.docx` (já conferido, sem credenciais).
Nenhuma planilha, CSV, dump ou output de análise está no Git — tudo isso vive em
`docs/Analise/` e `data/`, ambos no `.gitignore` (confirmado abaixo).

## 10. Local — fora do Git (intocável, regra da seção 7.1)

Confirmado via `git status --ignored`: existem **só no disco** da Maria, nunca
entraram no histórico do Git.

| Caminho | Conteúdo | Classificação | Ação |
|---|---|---|---|
| `data/uploads/*.xlsx` | Arquivos originais retidos de uploads (drill-down manual) | dado sensível / local | **intocável** — não mover, renomear ou remover |
| `docs/Analise/*.csv`, `*.xlsx` | Exports brutos do DW/WMS, base analítica da POC | dado sensível / local | **intocável** |
| `docs/Analise/saida/*` (inclui `analise-rmsp/`, `mapa-dados/`) | Painéis e outputs da análise (17–22/jul/2026) | dado sensível / local | **intocável** |
| `.env` | Segredos reais (Postgres, admin, `GRAPH_*`) | dado sensível / local | **intocável**, já corretamente fora do Git |
| `.pytest_cache/`, `**/__pycache__/` | Artefatos de execução | gerado | nenhuma ação — já ignorados |

Nada aqui é classificado além de "local (fora do Git)", conforme a regra
inegociável do P0.

---

## Resumo

- **Nenhum arquivo foi movido, renomeado ou removido neste lote.**
- **Nenhum dado real, credencial ou binário sensível está rastreado no Git.**
- Dois documentos novos criados (`POC_ATUAL.md`, este); cinco arquivos existentes
  recebem atualização (`CLAUDE.md`, `README.md`, `MEMORY.md`, `docs/PLANO.md` — só
  aviso —, `memory/decisoes-fechadas.md`); um documento marcado como superado
  (`docs/DIRECIONAMENTO_POC_NUVEM_IA_CLAUDE.md`); `.gitignore` ganha `.vscode/`.
- Candidatos a reorganização futura (não executados agora): mover `docs/HISTORICO.md`
  e o DIRECIONAMENTO superado para uma pasta `docs/historico/`.
