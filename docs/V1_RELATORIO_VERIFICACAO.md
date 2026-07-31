# V1 — Relatório de verificação independente

Um registro por bloco (direcionamento, seção 16). A verificação é feita por um
segundo contexto, somente leitura, **antes do commit** do bloco — instruída a
procurar defeito, não a confirmar sucesso. Status possíveis: atendido · parcial
· não atendido · bloqueado.

---

## Bloco A — V1.0 Transição para produto (31/jul/2026)

**Método do verificador**: `git diff`/`git status` completos sobre o working tree
do bloco, leitura dos arquivos novos, greps por referências órfãs no repositório
inteiro, execução direta dos helpers puros (`_peso_em_toneladas`,
`filiais_datahub.sigla`) e contagem estática de testes (HEAD × working tree). A
suíte pytest foi executada pelo executor no ambiente de referência (Docker/WSL,
Postgres real), não pelo verificador — ver item 10.

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo (só o que o V1.0 pede) | atendido | 10 itens do macro-lote cobertos; diff restrito a docs, telas, exibição do resumo, `filiais_datahub.py` e campo aditivo `filial_sigla`; sem scope creep |
| 2 | Arquitetura (aditiva, nada movido) | atendido | nenhum módulo movido/renomeado; `kpis_poc.py`/`resumo_poc.py` mantêm o nome (decisão 2 do V1_PLANO) |
| 3 | Migrations | atendido | nenhuma migration nova; `alembic/versions` intacto em `0001`–`0004` |
| 4 | Compatibilidade (contratos de API e telas) | atendido | `/kpis` e `/nuvem` só ganharam `filial_sigla`; zero referência órfã a `kpisPoc*`/`painel-kpispoc` após a remoção do painel do admin |
| 5 | Segurança (escape, segredos) | atendido | todo conteúdo de origem SharePoint nos renders novos passa por `escaparHtml()`; `web_url` validada `^https?://`; nenhum log novo |
| 6 | Cálculos (nada muda, só exibição) | atendido | `kpis_poc.py` fora do diff; conversões conferidas por execução (4.281.700 kg → "4,28 mil toneladas"; 512.300 kg → "512,3 toneladas") |
| 7 | Unidades (kg interno, tonelada na tela) | atendido | conversão /1000 só nos formatadores; payload segue em kg |
| 8 | Filtros | atendido | filtro de filial da nuvem continua filtrando pelo código; só o rótulo ganhou a sigla |
| 9 | Qualidade e origem | atendido | bloco separado em `nuvem.html` com arquivo, linhas, % válido, peso detalhado, sincronização e nota técnica |
| 10 | Testes | atendido | 150 → **154 passed** no ambiente de referência (Docker/WSL, Postgres real), nenhum teste removido; o verificador confirmou a contagem estática (não conseguiu executar a suíte no contexto dele — sem dependências) |
| 11 | Documentação | atendido | docs V1 criados e coerentes; README/CLAUDE/MEMORY apontam pro V1_PLANO; POC_ATUAL/PLANO/DEMO_POC marcados históricos (defeitos D1/D2/D6/D8 encontrados e corrigidos, abaixo) |
| 12 | Código morto | atendido | nenhum id/CSS/JS órfão; `formatarMoeda`/`formatarNumeroKpi` só em `comum.js` |
| 13 | Dependências | atendido | `requirements*.txt` intocados; módulo novo é stdlib pura |
| 14 | Regressões | atendido | upload/de-para/execuções/catálogo/métricas/sincronização intocados |
| 15 | Exposição de dados | atendido | nenhuma tela ou endpoint novo sem `exigir_login`; `/nuvem` e `/admin` seguem atrás de sessão |
| 16 | Erros | atendido | `carregarIntegrado` com catch e fallback do status; `_erros_como_http` intacto |
| 17 | Rastreabilidade | atendido | decisões do bloco em `docs/V1_PLANO.md` e `memory/decisoes-fechadas.md` |

### Defeitos encontrados pelo verificador e o que foi feito

| # | Achado | Resolução |
|---|---|---|
| D1 | `V1_RELATORIO_VERIFICACAO.md` referenciado antes de existir | **corrigido** — este arquivo (criado após a verificação, antes do commit) |
| D2 | `V1_ARQUITETURA.md` dizia que o de-para de filial era constante no frontend; a implementação é no backend | **corrigido** — doc alinhado à implementação (`backend/services/filiais_datahub.py`) |
| D3 | Alegação "passed" da suíte não verificável no contexto do verificador | **aceito** — suíte executada pelo executor no ambiente de referência; contagem estática conferida pelo verificador |
| D4 | Coluna "Peso bruto (kg)" da tabela por cliente segue em kg (unidade declarada no rótulo) | **registrado** — ressalva na decisão 3 do V1_PLANO; conversão entra na revisão do cockpit (V1.7) |
| D5 | Janela cosmética de ~50 kg (999.950–999.999 kg renderiza "1.000,0 toneladas" em vez de "1 mil toneladas") | **registrado** — sem impacto em dado real; corrigir se aparecer na prática |
| D6 | `POC_ATUAL.md` mantinha "dono único do escopo **ativo**" abaixo do banner de histórico | **corrigido** — parágrafo reescrito no passado ("congelada") |
| D7 | `015=RMSPIII` sem assert direto em teste | **corrigido** — teste novo cobre as 3 filiais confirmadas (154º teste) |
| D8 | Datas da virada oscilavam entre 30 e 31/jul | **corrigido** — virada/diagnóstico em 30/jul/2026 (chegada do direcionamento), execução do Bloco A fechada em 31/jul/2026 |

**Conclusão: Bloco A atendido.** Nenhum defeito funcional de código encontrado;
os 8 achados eram de documentação/cobertura e foram corrigidos ou registrados
antes do commit. Pendências herdadas (não são deste bloco) listadas no
`docs/V1_PLANO.md`.
