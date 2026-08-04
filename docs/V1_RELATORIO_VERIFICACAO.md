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

---

## Bloco B — V1.1 Catálogo semântico + V1.2 Compatibilidade de medidas (31/jul/2026)

**Método do verificador** (segundo contexto, somente leitura no repo): além da
leitura adversarial do diff, o verificador **executou de verdade** a suíte
completa (183 passed, confirmando a contagem declarada na época), o ciclo de
migração ao vivo (upgrade head → downgrade pra 0004 → upgrade head → seeds 2× —
tabelas somem/voltam exatamente, contagens estáveis) e traçou à mão 10 casos
adversariais no motor de compatibilidade (None, negativo, unidade numérica,
pct+kg, posicao+ua, tabela vazia, espaços, categoria sem base, colisão kg/g,
precisão Decimal).

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo (V1.1 + V1.2, sem cadastro de produto/SKU) | atendido | todos os bullets cobertos; Código/Descrição semeados como `rascunho` com nota "fora de escopo"; embalagens tratadas como desconhecidas (nunca conversão por embalagem) |
| 2 | Modelo semântico (seção 6 do direcionamento) | atendido | migration 0005 + seed cobrem os 20 atributos; unidade canônica derivada do conceito, sem duplicata |
| 3 | Migration | atendido | aditiva, `down_revision` correto, downgrade validado **ao vivo** |
| 4 | Seeds | atendido | idempotência executada 2×; 20 colunas na ordem do FONTES_DATAHUB; EMB nas posições 10/12; fatores t=1000, g=0.001, lb=0.45359237 conferidos |
| 5 | Motor de compatibilidade | atendido | conversão só na mesma categoria com fator (Decimal); percentual excluído de qualquer soma; desconhecida agrupa só pelo literal; bloqueios do direcionamento com mensagem; auditoria por item |
| 6 | Aplicação no caminho vivo | atendido | volume consolidado fora de kpis/por_cliente/resumo; agrupamento pela 1ª ocorrência de EMB (a do Volume); `/kpis` carrega a tabela do banco e devolve `volumes` com limitação |
| 7 | Frontend | atendido | card top 3 + "+N outras", tabela por embalagem, colspan ajustado, embalagem (dado do SharePoint) escapada em card e tabela; painel Semântica com escape total; nenhum id órfão |
| 8 | Segurança | atendido | 4 endpoints `/semantica/*` com `exigir_login`, só leitura, SQL parametrizado |
| 9 | Testes | atendido | 29 novos conferidos um a um; os 4 cenários antigos de KPIs preservados; "singular milhão" repropositado, não perdido |
| 10 | Compatibilidade/regressões | atendido | única mudança de contrato é a intencional (volume fora do `/kpis`); migrações antigas e upload intocados |
| 11 | Documentação | atendido | V1_PLANO/memórias registram bloco, decisão e contagens |
| 12 | Código morto/dependências | atendido | sem sobras do card antigo; requirements intocados (1 resíduo de fixture — R1) |
| 13 | Rastreabilidade | atendido | "separar por embalagem" + conferência 016/2607 registradas em 6 pontos |

### Ressalvas do verificador e o que foi feito

| # | Achado | Resolução |
|---|---|---|
| R1 | Fixtures de `test_resumo_poc.py` carregavam chave `volume` que saiu do contrato | **corrigido** — resíduo removido |
| R2 | `converter()` com valor não numérico vazava `decimal.InvalidOperation` | **corrigido** — vira `ConversaoInvalidaError("valor não numérico")`, com teste |
| R3/R5 | Unidade `None`/com espaços viraria grupo `"None"`/duplicado pra chamador futuro (caminho vivo já protegia) | **corrigido** — `_normalizar_unidade()` no motor (None/vazio → "(sem unidade)", strip), com teste |
| R4 | Mensagem imprecisa no cenário hipotético "categoria com fator mas sem base" (inalcançável com o seed real; comportamento conservador) | **registrado** — nunca inventa conversão; revisitar se o cenário existir um dia |
| R6 | "1 embalagens distintas" (gramática) | **corrigido** — singular/plural na tela |
| R7 | Auditoria item a item do motor não exposta no `/kpis` (só limitação + regra) | **registrado** — escolha de exposição; a auditoria completa entra quando a persistência (V1.3) gravar o que foi convertido/bloqueado |

**Conclusão: Bloco B atendido.** Nenhum defeito real encontrado no caminho vivo;
5 das 7 ressalvas corrigidas antes do commit, 2 registradas. Suíte final após as
correções: **185 passed** (183 + 2 testes das correções R2/R3).

---

## Bloco C — V1.3 Persistência e série histórica (31/jul/2026)

**Método do verificador** (segundo contexto, somente leitura no repo): `git
status`/`git diff` completos sobre o working tree (base 947fcb3), leitura
integral dos arquivos novos e dos diffs; greps adversariais no repo inteiro
(sobra do `ON CONFLICT` antigo — zero; `pertence_a_familia` — zero;
auto-cadastro de cliente — zero); arqueologia do DDL legado da VM (commit
`439ab62`) confirmando que o nome da constraint que a 0006 dropa existe também
em banco criado pelo `init_db` antigo; execução **real** da suíte completa no
ambiente de referência (230 passed na rodada do verificador) e 12 casos
adversariais traçados à mão no código novo (CNPJ 13 dígitos como float, arquivo
sem linhas válidas, clientes com mesma raiz, consolidação cruzando ano,
`forcar` com pendência de de-para, célula de outra métrica no delete de órfãs,
`fonte_id` NULL, restart com tabela vazia, reprocesso 2×, cadastro posterior,
falha no meio do lote, upload manual pós-migração).

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo (V1.3 + decisões da Maria) | atendido | volumes fora da série; sem auto-cadastro (único `INSERT INTO clientes` é o seed); sem scope creep |
| 2 | Arquitetura (aditiva, camada existente) | atendido | execução → recebidas → medidas usada de verdade, com asserts; nada movido/renomeado |
| 3 | Migration 0006 | atendido | upgrade não muda dado; nome da constraint antiga confere com legado e baseline; downgrade testado em ciclo completo contra Postgres real |
| 4 | Compatibilidade/regressões | atendido | upload manual idêntico (NULL conflita com NULL); zero sobras do conflict target antigo; `/kpis`/`/nuvem` fora do diff; motor devolve o mesmo resultado pro dado antigo |
| 5 | Segurança | atendido | `exigir_login` + teste de 401 nos 3 endpoints novos; SQL parametrizado; todo conteúdo SharePoint escapado no admin; download segue só pela lista de permissão |
| 6 | Cálculos | atendido | agregação por cliente conferida; balde NULL soma no total; delete de órfãs não alcança outra métrica/filial/competência |
| 7 | Unidades | atendido | unidade das recebidas vem do conceito canônico **aprovado** (sem ele, recusa antes de gravar); série recusa média/último/percentual com mensagem |
| 8 | Dupla contagem | atendido | grão único por construção; reprocesso espelha o último estado (upsert + órfãs); casos traçados à mão |
| 9 | Qualidade/pendências | atendido | 002 e cliente desconhecido visíveis com mensagens claras; erro em um arquivo não derruba o lote |
| 10 | Testes | atendido | suíte executada pelo verificador: 230 passed; breakdown dos testes novos confirmado por contagem estática; asserts exatos |
| 11 | Documentação | atendido | V1_PLANO/V1_ARQUITETURA/README/CLAUDE/memórias coerentes; superação da decisão antiga `medidas_cliente` registrada |
| 12 | Código morto/dependências | atendido | requirements intocados; nenhuma referência órfã |
| 13 | Rastreabilidade | atendido | `medida_recebida_id` nunca NULL no caminho novo; execuções acumulam; decisões datadas |
| 14 | Erros | atendido | exceções → 400/502; erros por arquivo acontecem antes de qualquer escrita canônica; exceção não capturada = rollback do lote inteiro |
| 15 | Exposição de dados | atendido | nenhum endpoint novo sem login; respostas sem segredo |

### Ressalvas do verificador e o que foi feito

| # | Achado | Resolução |
|---|---|---|
| R1 | Controle de processamento é por **nome** de arquivo — homônimos em subpastas diferentes flip-flopariam o controle (sem dupla contagem; premissa "um arquivo por filial×competência" vale por pasta) | **registrado** — limitação no `V1_PLANO.md`; verdade no DataHub real de hoje |
| R2 | `ValueError` de métrica fora do catálogo viraria HTTP 500 sem mensagem clara | **corrigido** — ids das métricas resolvidos antes de qualquer escrita, erro vira `ProcessamentoDatahubError` (400), com teste |
| R3 | Grão único por métrica é invariante de código, não de schema — um modelo de upload futuro gravando as métricas do DataHub no grão filial duplicaria a série | **registrado** — limitação no `V1_PLANO.md`; nenhum modelo atual referencia essas métricas |
| R4 | Arquivos órfãos no working tree (screenshots antigos, fora do bloco) poderiam entrar no commit por descuido | **acatado** — commit com staging explícito, sem `git add -A`; arquivos deixados no disco (não são deste bloco) |
| R5 | Seção do Bloco C deste relatório precisava existir antes do commit | **corrigido** — esta seção |
| R6 | Sem teste pro arquivo republicado que fica com 0 linhas válidas (espelho apaga a competência) | **corrigido** — teste novo fixa o comportamento como intencional |

**Conclusão: Bloco C atendido.** Nenhum defeito real no caminho vivo; 3 das 6
ressalvas corrigidas antes do commit, 3 registradas (R1/R3 como limitação
documentada, R4 como cuidado de staging). Suíte final após as correções:
**232 passed** (230 + 2 testes das correções R2/R6).

---

## Bloco D — V1.4 Laboratório: seleção e perfil (02/ago/2026)

**Este é o primeiro bloco que a verificação REPROVOU na primeira passada.** O
verificador encontrou 3 defeitos reais no caminho vivo — todos a mesma falha de
fundo: número parcial apresentado como completo, que é exatamente o que o V1.4
existe para evitar. Foram corrigidos antes do commit, com teste cada um.

**Método do verificador** (segundo contexto, somente leitura): leitura integral
dos 4 arquivos novos de backend, da migration, do HTML novo e dos diffs;
autoridades lidas (direcionamento §9 inteira, §14, §5, critérios de aceite, o
`V1_PLANO` incluindo a seção ABERTO e `memory/reestruturacao-datahub-4-unidades.md`);
grep por vestígio de IA nos arquivos novos (zero); execução da suíte completa
(299 passed, conferindo a contagem declarada); e — o diferencial desta rodada —
**4 scripts de trace executados contra o código real** (perfil puro; e
`perfilar_selecao`/`ler_estrutura` com cursor falso e xlsx sintéticos), cobrindo
16 casos adversariais, entre eles coluna extra no fim, família
`ENTRADA_MERCADORIAS (UA)`, cabeçalho detectado caindo em linha de dados, coluna
100% nula, filtro que não casa nada, estouro de tempo no 3º de 5 arquivos, data
como serial do Excel e planilha de uma coluna sem dado.

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo (V1.4 + as 3 decisões da Maria) | atendido | zero ocorrência de IA/provedor/chave nos arquivos novos; as 3 decisões implementadas; sem scope creep |
| 2 | Arquitetura (aditiva; pureza do perfil) | atendido | `perfil_dados` importa só `datetime` e o motor do V1.2 — **pureza e determinismo comprovados por execução** (2 rodadas, JSON igual byte a byte) |
| 3 | Migration 0007 | atendido | aditiva, CHECK com os 4 estados, índice, downgrade exercitado de fato pela suíte (coluna `observacoes` sem escritor foi removida na correção) |
| 4 | Compatibilidade/regressões | atendido | `arquivo_por_item_id` é extração fiel do loop que estava no leitor do P3; `montar_bolinhas`/`_identificar_familia` intocados; `/nuvem`, `/kpis` e o processamento do V1.3 sem alteração; 232 testes anteriores verdes |
| 5 | Segurança | atendido | `exigir_login` nos 4 endpoints + teste 401×4; SQL 100% parametrizado; **cada** interpolação do HTML novo auditada (todo conteúdo SharePoint escapado; `web_url` com `^https?://`; ids por `Number()`); lista de permissão respeitada nos dois leitores |
| 6 | Perfil determinístico (18 itens da §9.4) | atendido após correção | 16 de 18 corretos na primeira passada; R7/R8 registrados como limitação; a amostra crua passou a ser declarada no próprio artefato (R15) |
| 7 | Soma apenas quando permitida | **corrigido** | a soma sai do motor do V1.2 e os motivos existem, mas o portão era blocklist — virou allowlist (`agregacao == 'soma'`), alinhado ao `serie_datahub` (R4) |
| 8 | Guarda estrutural | atendido após correção | descarte total confirmado; rótulo com espaço/maiúscula casa; posição faltando diverge; a variante por **nome** (`(UA)`) passou a ser barrada explicitamente (R5) |
| 9 | Limites | atendido após correção | quantidade/linhas/amostra/tamanho aplicados e gravados; mensagem de truncamento corrigida (R2); tempo é orçamento entre arquivos, **declarado** quando estoura (R10 registrado) |
| 10 | Testes | atendido | 299 passed reproduzidos pelo verificador; 28/18/21 conferidos um a um; nenhum teste anterior removido ou enfraquecido; gaps de R13 fechados nas correções |
| 11 | Documentação | atendido após correção | coerente entre si e com o código; o defeito ABERTO segue corretamente sinalizado como **não resolvido** em 5 lugares; afirmações falsas corrigidas (R14) |
| 12 | Código morto/dependências | atendido após correção | `requirements` intocados; 12/12 ids do HTML usados; coluna `observacoes` órfã removida |
| 13 | Rastreabilidade (§9.6) | **corrigido** | usuário/data/arquivos/filtros/perfil/limites/status gravados e o requisito de mascaramento do Bloco E registrado em 4 lugares; a seleção passou a gravar o **pedido**, não só o resultado (R3) |
| 14 | Erros | atendido | exceção inesperada sobe (não vira "falha de arquivo"); falha parcial não corrompe (gravação é a última operação, `get_conn` faz rollback); todos falhando → 400 com os motivos |
| 15 | Exposição de dados | atendido após correção | nenhum endpoint devolve além do perfil da própria sessão; amostra crua agora **declarada no payload e na tela** (R15) |

### Defeitos reais e o que foi feito

| # | Achado | Gravidade | Resolução |
|---|---|---|---|
| R1 | O aviso de um arquivo **suprimia a declaração de filtro do outro**: a flag era da sessão, não do arquivo. Numa seleção com um arquivo sem coluna de cliente, o perfil do arquivo filtrado descrevia metade das linhas sem dizer — e dependia da ordem da seleção | defeito real no caminho vivo | **corrigido** — filtro declarado **por arquivo** (`filtro_aplicado` no perfil + primeira limitação), com teste que força a ordem adversa |
| R2 | Mensagem de truncamento afirmava "as primeiras N de M" usando o número **pós-filtro** — as N não eram as primeiras | defeito real no caminho vivo | **corrigido** — leitura e filtro são fatos separados: "Leitura limitada às primeiras N de M" (números da leitura) + "N de M lidas passaram no filtro" |
| R3 | A sessão gravava o **resultado** dos filtros: arquivo pedido e descartado desaparecia da sessão sem aviso, contra a §9.6 e contra o docstring da própria migration | defeito real (rastreabilidade) | **corrigido** — `item_ids_pedidos` + `descartados_pelos_filtros` na seleção, e aviso por arquivo descartado |
| R4 | Portão da soma era blocklist (só barrava `agregacao='nenhuma'`): `media`/`ultimo`/`contagem_distinta` somariam. Latente hoje, e divergente do `serie_datahub` | ressalva forte | **corrigido** — allowlist `agregacao == 'soma'`, com teste parametrizado nos 5 casos |
| R5 | Alegação de que a guarda estrutural protegia a família `ENTRADA_MERCADORIAS (UA)` **não se sustentava**: se os rótulos coincidirem, o catálogo da família integrada seria herdado por uma família de grão não conferido | ressalva forte | **corrigido** — variante por nome (sufixo depois da família) não recebe catálogo e o aviso é explícito; teste cobre |
| R9 | Coluna catalogada 100% nula dizia "coluna não numérica" — falso | ressalva | **corrigido** — mensagem própria ("sem nenhum valor preenchido"), com teste |
| R13c | O `V1_PLANO` afirmava "coberto por teste com a estrutura real da RJ", mas o teste usava arquivo de 2 colunas | ressalva (doc × teste) | **corrigido** — o teste passou a usar as 18 colunas reais da RJ (as 20 sem `Cliente`/`Cliente CNPJ`) |
| R14a | O `V1_PLANO` já afirmava que a verificação estava neste relatório, que não tinha seção do Bloco D | ressalva (doc) | **corrigido** — esta seção |
| R15 | Amostra sem mascaramento estava declarada em 4 documentos, **mas não no artefato** que vai pra IA | ressalva (exposição) | **corrigido** — limitação no próprio perfil e no resumo da sessão |
| R16 | `limite` da listagem sem piso/teto (LIMIT negativo → 500) | cosmético | **corrigido** — `Query(20, ge=1, le=100)`, com teste |
| R6 | Arquivo com coluna **a mais no fim** tem o catálogo aplicado sem nota (posicionalmente correto, mas silencioso) | ressalva | **registrado** no `V1_PLANO` |
| R7 | Data como **serial não formatado** do Excel é lida como número: cobertura temporal volta vazia e o serial pode ser somado se houver catálogo | ressalva | **registrado** — afeta as famílias sem semântica, que é onde o Laboratório mais atua |
| R8 | `dim_filial` do catálogo nunca é consultado: filial vem só do nome do arquivo | ressalva | **registrado** |
| R10 | Limite de tempo é orçamento entre arquivos, não deadline: o 1º arquivo nunca é limitado | ressalva | **registrado** — o estouro é declarado no aviso da sessão |
| R11 | Colunas finais sem rótulo são cortadas e linhas mais largas que o cabeçalho truncadas, sem nota | ressalva | **registrado** |
| R12 | `linha_cabecalho` informada vale para todos os arquivos da sessão (falha alto e claro nos que não batem) | ressalva | **registrado** |
| R14d | `docs/V1_CRITERIOS_ACEITE.md` está com todos os checkboxes vazios, inclusive dos blocos A–C | ressalva pré-existente | **registrado** — não é regressão do D; o registro de aceite vive no `V1_PLANO` e neste relatório |

**Conclusão: Bloco D atendido após as correções.** Os 3 defeitos reais e as 7
ressalvas corrigíveis caíram antes do commit, cada um com teste; 8 ressalvas de
robustez ficaram registradas como limitação conhecida no `docs/V1_PLANO.md`.
Suíte final após as correções: **311 passed** (299 da rodada verificada + 12
testes novos das correções).

---

## Bloco E — V1.5 Laboratório: chat + V1.6 Insight aprovado (03/ago/2026)

**Método do verificador**: agente separado (segundo contexto), sem memória da
implementação. Leu `git diff`/`git status` e os arquivos novos por completo,
executou a suíte do lote contra o Postgres local, e escreveu (e depois
removeu) dois scripts próprios pra confirmar na prática os dois achados mais
graves antes de reportar — não se limitou a leitura estática.

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Mascaramento de cliente/CNPJ antes de qualquer envio à IA | **corrigido** | amostra, `clientes.top` e `colunas[].exemplos` mascarados desde a primeira versão; a limitação do filtro de cliente (nome digitado pelo usuário, não vem da planilha) vazava sem máscara — achado crítico, corrigido |
| 2 | Unidade sempre junto da filial no contexto | **corrigido** | `origem_do_arquivo` por arquivo já estava certo; `resumo_da_sessao.filiais` embutia o código nu do Bloco D (colide entre unidades) — corrigido recalculando a partir da origem qualificada |
| 3 | IA nunca calcula/publica KPI oficial | atendido | nenhuma tabela de métrica/cockpit tocada pelos módulos novos; `especificacao` não é lida em nenhum outro lugar do código |
| 4 | Falha do provedor nunca vira resposta inventada nem exceção crua | **corrigido** | chat já tratava (mensagem grava o erro, conversa segue); a aprovação (`insight_aprovado.gerar_especificacao`) não tratava — subia HTTP 500 — corrigido com `try/except` |
| 5 | Resposta truncada nunca vira sucesso silencioso | **corrigido** | `stop_reason == "max_tokens"` não era verificado — resposta cortada/vazia era gravada como completa; corrigido em `ia_client.py` |
| 6 | Proteção contra prompt injection | atendido | dado de fonte sempre dentro de `<dados_da_fonte>`, marcado como não-instrução no system prompt; resposta da IA nunca tratada como comando/dado confiável |
| 7 | Testes mockados (zero chamada de rede real) | atendido | os três arquivos de teste do lote executados contra o Postgres local, 40 passaram sem nenhuma chamada real à Anthropic |
| 8 | XSS no frontend | atendido | todo texto novo (arquivo, resposta da IA, pergunta, nota de decisão, especificação) passa por `escaparHtml` |
| 9 | Injeção de SQL | atendido | todo `cur.execute` novo é parametrizado (`%s`); os únicos f-strings em SQL interpolam uma tupla constante do módulo, nunca entrada de usuário |
| 10 | Migration 0010 | atendido | aditiva de verdade; downgrade desfaz tudo na ordem certa; índice condiz com a única consulta existente |
| 11 | Uso de `cur`/transação | atendido | nenhum serviço novo abre conexão própria — todos recebem `cur`, igual ao resto do projeto |
| 12 | Limites (tamanho de pergunta, mensagens por sessão) | atendido, com ressalva | checados antes de qualquer gravação/chamada cara; sem lock — ver achado de baixa gravidade |

### Achados e o que foi feito

| # | Achado | Gravidade | Resolução |
|---|---|---|---|
| E1 | Nome/CNPJ digitado no filtro de cliente (`filtro_aplicado.valores`) era ecoado sem máscara dentro do texto de `limitacoes`, que ia inteiro pro contexto da IA — confirmado executando o código real com um filtro de cliente aplicado | **crítico** | **corrigido** — `mascaramento.py` mascara `limitacoes` com o mesmo mapa de pseudônimos da amostra, casando por texto normalizado (`.lower().strip()`) |
| E2 | `insight_aprovado.gerar_especificacao` não tratava `ConfiguracaoIAIncompletaError`/`ia_client.IAError` — falha do provedor na aprovação subia crua e virava HTTP 500 no endpoint | **alto** | **corrigido** — `try/except` mapeando pra `InsightAprovadoError` (o router já convertia essa classe em 400) |
| E3 | `resumo_da_sessao.filiais` do contexto embutia o código nu do Bloco D (`"001"`), que colide entre unidades diferentes desde a reestruturação (`RMSPII/001` × `CWB3/001`) — confirmado com sessão de dois arquivos do mesmo código em unidades diferentes | **alto** | **corrigido** — `montar_contexto` recalcula `filiais` a partir da origem qualificada de cada arquivo; o formato persistido do Bloco D não muda |
| E4 | `stop_reason == "max_tokens"` nunca era verificado — resposta cortada no meio (ou vazia, se o thinking consumiu o orçamento) era gravada como sucesso completo | **médio** | **corrigido** — `ia_client.py` levanta `IAIndisponivelError`, reaproveitando o caminho de "conversa segue sem inventar resposta" que já existia pra outras falhas |
| E5 | Checagem de `MAX_MENSAGENS_POR_SESSAO` sem lock: duas requisições concorrentes na mesma sessão podem, em tese, passar do teto, porque a chamada à IA (até 60s) acontece dentro da mesma janela da checagem | baixo | **aceito, registrado** no `V1_PLANO.md` — consistente com o resto do Laboratório (nenhum outro limite usa lock); é teto de custo/uso, não controle de segurança |
| E6 | Redundância: `obter_configuracao_ia()` é lido tanto em `laboratorio_chat.perguntar` quanto dentro de `ia_client._client()` na primeira chamada do processo | estilo | **aceito** — nenhum efeito funcional, ambas as leituras são de env var idempotente |

**Conclusão: Bloco E atendido após as correções.** Os 4 achados reais (1
crítico, 2 altos, 1 médio) caíram antes do commit, cada um com teste de
regressão novo (inclusive um arquivo de teste inteiro, `tests/test_ia_client.py`,
que passou a exercitar a lógica de `ia_client.py` com um client falso — antes
só existia mock do wrapper inteiro, nunca da lógica interna dele). Achado de
baixa gravidade (E5) e nota de estilo (E6) ficaram registrados como limitação
conhecida. Suíte final após as correções: **382 passed** (330 antes do lote +
52 novos: 8 de mascaramento, 6 do wrapper da IA, 24 do chat/contexto/
endpoints, 14 da aprovação/descarte/endpoints; nenhum teste anterior removido
ou enfraquecido). Zero chamada de rede real à Anthropic na suíte.

---

## Bloco F — V1.7 Cockpit executivo (03/ago/2026)

**Método do verificador**: agente separado (segundo contexto, sem memória da
implementação). Leu `git status`/`git diff` e os 10 arquivos novos + os 4
alterados por completo; conferiu contra `docs/V1_NUVEM_IA_DIRECIONAMENTO.md`
(seção 11 e 5.7), `docs/V1_CRITERIOS_ACEITE.md` e `docs/V1_PLANO.md`; rodou a
suíte completa contra o Postgres real (wsl/docker) e isolou os 4 arquivos de
teste do lote; conferiu as migrations 0001–0010 (nenhuma nova, como
declarado) e as migrations 0003/0006 pra confirmar a alegação sobre o grão
mínimo da linhagem; grepou por sobra de referência às funções privadas
renomeadas em `serie_datahub.py` (zero); e escreveu (depois descartou) um
script que roda as funções reais de `frontend/comum.js` pra confirmar o
achado mais grave antes de reportá-lo como certeza, em vez de reportar
suspeita como fato.

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Filtros globais de período/filial/cliente obedecidos por cards, gráficos, tabelas e resumos | atendido, com ressalva | `resumo`/`comparar_filiais`/`comparar_clientes`/`qualidade` e a tela aplicam de/ate/filial/cliente de forma consistente; só aceitam um valor por filtro ou "todos" — a seção 5.7 do direcionamento pede "uma, várias ou todas" (achado F2, baixo, registrado abaixo) |
| 2 | Visões obrigatórias (consolidado, série, comparação filiais/clientes, ranking, participação, acumulado, variação, qualidade/cobertura, drill-down, origem/linhagem) | atendido | todas presentes; linhagem em tela separada por decisão explícita da Maria |
| 3 | KPIs iniciais só com métricas confiáveis | atendido | "quantidade de operações" fora dos cards é leitura correta do catálogo — `registros_movimentacao` é descrita em `seed_metricas.py` como "indicador de volume de dados, não de negócio"; "participação do maior cliente" sobre `valor_mercadoria_movimentada` é escolha razoável e documentada (direcionamento não fixa a métrica) |
| 4 | Nenhum "volume total" com unidades incompatíveis | atendido | cockpit não introduz card de "volume"; usa só as métricas do catálogo |
| 5 | Peso em toneladas (card abreviado + detalhamento completo); percentuais nunca somados diretamente | **corrigido** | achado F1 (abaixo): gráficos de série/ranking mostravam peso em kg cru, e não havia detalhamento completo em toneladas na tela — corrigido antes do commit. Percentuais: confirmado que nunca são somados (sempre `valor_linha/total*100`) |
| 6 | Qualidade e origem separadas da área principal | atendido | bloco `#cockpitQualidade` fora dos cards/gráficos principais, mesmos campos do `/nuvem` agregados por recorte |
| 7 | Sem migration nova | atendido | `alembic/versions` intacto (0001–0010); cockpit/linhagem leem só tabelas existentes desde o Bloco C |
| 8 | Segurança — SQL injection | atendido | todo `cur.execute` com f-string em `cockpit.py`/`linhagem.py` interpola só cláusulas fixas montadas pelo código; todo valor variável vai via `%s`/lista de params, mesmo padrão de `serie_datahub.py` |
| 9 | Segurança — XSS no frontend | atendido | todo texto vindo da API passa por `escaparHtml`; `web_url` validado com `/^https?:\/\//i` antes de virar `href`, idêntico ao padrão de `frontend/nuvem.html` |
| 10 | Autenticação | atendido | os 6 endpoints novos chamam `exigir_login(request)` como primeira linha; testado (401 sem sessão) |
| 11 | Refactor de `serie_datahub.py` (funções privadas → públicas) | atendido | renomeação pura + extração de `exigir_metrica_aditiva` com o mesmo corpo que estava inline; zero sobra de referência à assinatura antiga no repositório |
| 12 | Cálculos — participação %, qualidade agregada, casos de borda | atendido | `percentual = valor/total*100 if total else 0.0` evita `ZeroDivisionError`; `GROUP BY cliente_id, c.nome` impede colapso de clientes homônimos; filial sem de-para mapeado gera `WHERE FALSE` (conjunto vazio) em vez de exceção |
| 13 | Consistência arquitetural | atendido | `cockpit.py`/`linhagem.py` só recebem `cur`; erros próprios traduzidos pro router em 400/404; sem estado global novo |
| 14 | Testes | atendido | **414 passed** confirmados pelo verificador (rodada completa) e 32 isolando os 4 arquivos novos; nenhum teste anterior alterado/removido |
| 15 | Decisões da Maria implementadas | atendido | "Sem cliente identificado" exposto e nunca escondido; linhagem em rota top-level separada; nenhum KPI de insight (placeholder vazio); duas rotas independentes `/cockpit` e `/linhagem` |

### Achados e o que foi feito

| # | Achado | Gravidade | Resolução |
|---|---|---|---|
| F1 | Peso bruto movimentado aparecia em **kg**, não em toneladas, no tooltip/eixo do gráfico de série histórica e nos rankings de filiais/clientes — só o card do resumo convertia. Peso bruto é a opção default do seletor de métrica, a primeira coisa vista ao abrir `/cockpit`. Confirmado por execução real das funções de `comum.js`. Reabria a pendência D4 do relatório do Bloco A ("conversão pra tonelada nessa tabela entra na revisão do V1.7") | **alto** | **corrigido** — `formatarValorPorUnidade()` novo em `cockpit.html`, converte quando `metrica.unidade === "kg"`, aplicado nos formatadores de eixo/tooltip de `renderizarSerie`/`renderizarRanking`; acrescentada a linha "Peso bruto (detalhado)" no bloco de qualidade (mesmo padrão do `/nuvem`) |
| F2 | Filtros de filial e cliente (cockpit e linhagem) aceitam só um valor por vez ou "todos" — a seção 5.7 do direcionamento lista "uma, várias ou todas as filiais"/cliente como decisão fixada. Herdado da interface de `serie_datahub` desde o Bloco C, não é regressão deste bloco; nunca tinha sido registrado como limitação conhecida antes | baixo | **aceito, registrado** no `V1_PLANO.md` — os rankings já mostram todos os itens lado a lado, o que mitiga parcialmente; resolver exige filtro multi-select na tela + `= ANY(%s)` no backend, trabalho de lote próprio |
| F3 | A repartição dos 32 testes novos por arquivo, na primeira versão do texto do `V1_PLANO.md`, não batia com a contagem real por arquivo (o total de 32 estava certo) | cosmético | **corrigido** — texto ajustado antes do commit |

**Conclusão: Bloco F atendido após a correção do achado F1.** A arquitetura, a
segurança (SQL parametrizado, XSS escapado, autenticação em todos os
endpoints novos, refactor de `serie_datahub.py` comportamentalmente
idêntico) e os cálculos de participação/qualidade estavam corretos desde a
primeira versão, inclusive nos casos de borda testados (total=0, cliente
homônimo com `cliente_id` diferente, filial sem de-para). O único defeito
real (F1, alto) caiu antes do commit, com o mesmo padrão de correção já
usado no `/nuvem`. F2 (baixo) ficou registrado como limitação conhecida; F3
foi só correção de texto.

**Suíte**: **414 passed** (382 do Bloco E + 32 novos), confirmada pelo
verificador independente contra o Postgres real e novamente após a correção
do achado F1. Nenhum teste anterior foi alterado, enfraquecido ou removido.

---

## Bloco G — V1.8 Produção e entrega (G1: 03/ago/2026; G2: 04/ago/2026; G3: 04/ago/2026)

Dividido em três checkpoints (G1/G2/G3), cada um com verificação independente
própria antes do commit, mesma regra dos Blocos A–F. Esta seção consolida os
três no formato deste relatório — G1 e G2 já tinham sido verificados por
agente separado antes de cada commit, com os achados narrados em
`docs/V1_PLANO.md`; o texto abaixo os transcreve pro formato tabular. G3 foi
verificado de fato durante a escrita desta seção.

### G1 — Produção destravada e continuidade

**Método do verificador**: agente separado (segundo contexto), antes do
commit `ddd4f87`. Conferiu `docker-compose.yml`/`.env.example` (variáveis da
IA chegando ao container), rodou a suíte completa, testou de verdade o ciclo
backup→drop total do schema→restore→contagem de linhas, e reproduziu o
cenário de exceção crua pra confirmar o handler global.

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo (continuidade, não acesso/auditoria — isso é G2/G3) | atendido | IA env vars, backup/restore testado, `/health` + handler global + timeouts, rollback por SHA; nenhuma mudança de acesso/auditoria/logs neste checkpoint |
| 2 | Arquitetura | atendido | aditivo; sem pool de conexões (decisão explícita — timeouts resolvem o risco de continuidade sem mudar a forma de acesso ao banco) |
| 3 | Migrations | atendido | nenhuma migration nova no G1 |
| 4 | Compatibilidade/regressões | atendido | `/health` e o handler global não mudam contrato de nenhum endpoint existente; os 70 `HTTPException` já espalhados continuam ganhando por MRO |
| 5 | Segurança | atendido | `/health` sem login é sonda de infraestrutura (Docker healthcheck), não expõe dado de negócio — mesma lógica do `/docs`, que só fecha no G2; `restore.sh` exige confirmação explícita (destrutivo por natureza) |
| 6 | Testes | atendido | **420 passed** (414 do Bloco F + 6 novos); `connect_timeout` não entrou em teste automatizado (exigiria simular host inacessível de forma confiável) — limitação aceita, mesmo padrão já usado em blocos anteriores |
| 7 | Documentação | atendido | `docs/DEPLOY.md` (Passo 4.2, rotação do secret do Graph, backup e restauração, rollback reescrito por SHA), `memory/graph-secret-rotacao.md` |

### Achados e o que foi feito (G1)

| # | Achado | Gravidade | Resolução |
|---|---|---|---|
| G1-1 | `scripts/backup.sh`/`restore.sh` sem bit executável no git — o repo tem `core.filemode=false` no Windows, então o bit setado em disco não era rastreado; um clone Linux (a VM) receberia os scripts sem permissão de execução | alto | **corrigido** — `git update-index --chmod=+x` nos dois arquivos antes do commit, confirmado por `git ls-files --stage` (`100755`) |
| G1-2 | `restore.sh` sem `psql -v ON_ERROR_STOP=1` — uma restauração parcialmente falha continuaria executando e reportaria sucesso (exit 0), mascarando perda de dado silenciosa | alto | **corrigido** — flag acrescentada nos dois `psql` do script; reteste do caminho feliz confirmou que a restauração normal não regrediu (contagem de `armazens` igual antes/depois) |

**Conclusão: G1 atendido após as correções.** Os 2 achados (ambos altos, um de
infraestrutura de deploy e um de integridade de restauração) caíram antes do
commit. **Suíte**: 420 passed.

### G2 — Acesso, auditoria e logs

**Método do verificador**: agente separado (segundo contexto), antes do
commit `c71d71e`. Conferiu que o gate por `Depends(exigir_login)` nos 6
routers cobre exatamente as mesmas rotas que a chamada imperativa cobria
antes (nenhuma rota "sobrou" fora dos dois routers do admin), rodou a suíte
completa, e reproduziu ao vivo os dois cenários dos achados (forçar uma
exceção não tratada pra inspecionar o header; bater em `/frontend/ADMIN.HTML`
num filesystem case-insensitive) antes de reportar como certeza.

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo | atendido | gate declarativo, páginas HTML fechadas, rate limit, `/docs` fechado, auditoria, logging estruturado, sanitização de `str(e)` — nenhum item de G1/G3 misturado |
| 2 | Arquitetura | atendido | `dependencies=[Depends(exigir_login)]` a nível de router elimina a possibilidade estrutural de uma rota nova ficar pública por esquecimento; nenhum módulo movido |
| 3 | Migration `0011_auditoria` | atendido | aditiva, com `downgrade` e teste de ciclo completo (a `0010` não tinha isso — lacuna registrada no G1 e fechada aqui) |
| 4 | Compatibilidade/regressões | atendido | contratos HTTP de 401 preservados (testes existentes não mudaram de comportamento); nenhum handler perdeu funcionalidade ao remover o parâmetro `request` onde ele só servia pro `exigir_login` |
| 5 | Segurança | atendido, com 2 achados corrigidos | 48 handlers cobertos por `Depends`; `/frontend/*.html` bloqueado (senão o redirect das páginas seria bypassável); rate limit calibrado (10 falhas/10min por IP, decisão da Maria pra não travar o CSC atrás do mesmo IP); `/docs`/`/redoc`/`/openapi.json` fechados |
| 6 | Exposição de dados | atendido | nenhum endpoint novo sem login; os 3 pontos de `except Exception` genérico em `admin.py` (upload/preview/reprocessamento) deixaram de repassar `str(e)` cru ao cliente |
| 7 | Testes | atendido | **446 passed** (420 do G1 + 26 novos: 11 de `test_auth.py`, 8 de `test_auditoria.py`, 6 de `test_main.py`, 1 do ciclo da migration `0011`) |
| 8 | Documentação | atendido | `docs/V1_PLANO.md` (seção G2), memórias atualizadas |

### Achados e o que foi feito (G2)

| # | Achado | Gravidade | Resolução |
|---|---|---|---|
| G2-1 | `X-Request-Id` saía `"-"` justo no caso de 500 não tratado (o que mais precisa de correlação no log): o `ContextVar` do request id é resetado no `finally` do middleware assim que a exceção propaga por cima dele, antes do handler global (que roda no `ServerErrorMiddleware`, por fora) poder lê-lo | alto | **corrigido** — o id passou a ser gravado também em `request.state` (o mesmo objeto `Request` sobrevive à pilha inteira, ao contrário do `ContextVar`) e lido de lá no handler; teste de regressão em `test_excecao_nao_tratada_vira_500_sem_expor_detalhe` |
| G2-2 | Bloqueio de `.html` no mount `/frontend` era case-sensitive — num filesystem case-insensitive (Windows/Mac, não a VM Linux de produção) `/frontend/ADMIN.HTML` passava direto | médio | **corrigido** — `.lower()` antes de comparar; a proteção deixa de depender de acidente do sistema de arquivos; testes novos para `ADMIN.HTML` e `Admin.Html` |

**Conclusão: G2 atendido após as correções.** 1 achado alto e 1 médio, ambos
corrigidos antes do commit, cada um com teste de regressão. **Suíte**: 446
passed.

### G3 — Testes de integração, checklist e fechamento da V1

**Método do verificador**: agente separado (segundo contexto, sem memória da
implementação), antes do commit. Leu `git status`/`git diff` completos
(confirmando que nenhum arquivo de `backend/`/`frontend/` entra no escopo —
G3 só acrescenta testes, script e documentação), leu `tests/test_e2e_pipeline.py`
linha a linha seguindo a cadeia real até `cockpit.py`/`linhagem.py` pra
confirmar que as asserções dependem da lógica de produção (não são um atalho
que passaria mesmo com um bug razoável no meio do caminho), rodou a suíte
completa (448 passed) e especificamente `tests/test_migracao.py -k legado`
pra confirmar, de forma independente, o achado de que a cadeia `0001`→`0011`
já subia a partir do schema legado desde antes deste checkpoint, e rodou
`scripts/verificar_v1.py` contra o stack local (21 itens OK) e contra uma
porta fechada (pra checar o comportamento de erro).

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | Escopo (sem alterar `backend/`/`frontend/`) | atendido | confirmado por `git diff --stat`; só testes, script e documentação |
| 2 | Teste E2E até cockpit/linhagem prova a cadeia real | atendido | `tests/test_e2e_pipeline.py` chama `processamento_datahub.processar_arquivo` (o caminho de produção, só `graph_datahub.baixar_item` mockado); as asserções em `cockpit.comparar_filiais` (`GROUP BY a.sigla`) e `linhagem.origem_da_celula` (cruzamento `medidas → medidas_recebidas → execucoes → processamentos_datahub`) dependem da lógica real; CNPJs e de-paras de filial usados batem com os seeds reais |
| 3 | Migrations em banco existente (clone do schema legado da VM) | atendido | achado próprio (não é lacuna nova): `migracao.migrar()` já faz `stamp(BASELINE)` + `upgrade("head")` a partir do `LEGADO_DDL`; `test_legado_valido_recebe_stamp_sem_tocar_dados` já prova isso contra o head dinâmico, que hoje é `0011` — confirmado de forma independente, sem necessidade de teste novo |
| 4 | `scripts/verificar_v1.py`, com 2 achados corrigidos | atendido após correção | cobre health, gate de login, páginas fechadas, `/frontend/*.html`, `/docs`, request id; senha nunca exposta em log/print |
| 5 | Documentação (README/V1_ARQUITETURA/V1_CRITERIOS_ACEITE/V1_RELATORIO_VERIFICACAO/V1_PLANO) | atendido após correção | ver achado G3-1; demais atualizações conferidas contra o código e contra este relatório |
| 6 | Regressão | atendido | **448 passed** (446 do G2 + 2 novos de `test_e2e_pipeline.py`); nenhum teste anterior alterado, enfraquecido ou removido |
| 7 | Segurança | atendido | nenhum segredo em log; `verificar_v1.py` é cliente HTTP, não abre superfície nova |
| 8 | Correção de um defeito pré-existente neste documento (fora do escopo do G3, achado ao editar o arquivo) | corrigido | o parágrafo de conclusão do Bloco E estava fisicamente colado no final deste arquivo, depois da conclusão do Bloco F; reordenado pra logo após a tabela de achados do Bloco E, texto preservado integralmente |

### Achados e o que foi feito (G3)

| # | Achado | Gravidade | Resolução |
|---|---|---|---|
| G3-1 | `docs/V1_CRITERIOS_ACEITE.md` chegou a citar esta seção ("Bloco G") como evidência antes dela existir, e a marcar como feito o próprio item "verificação independente final e relatório de entrega" antes da verificação ter acontecido — ordem invertida em relação ao padrão dos Blocos A–F (verificar → corrigir → escrever a seção → só então marcar o critério de aceite citando ela) | alto | **corrigido** — esta seção foi escrita e os achados G3-2/G3-3 corrigidos antes de qualquer commit; a citação em `V1_CRITERIOS_ACEITE.md` agora aponta pra uma seção que já existe de fato |
| G3-2 | `scripts/verificar_v1.py` alegava no próprio docstring cobrir "rate limit", mas o código nunca disparava as 10 falhas necessárias nem checava 429 | médio | **corrigido** — docstring ajustado pra declarar exatamente o que é testado; o cenário de rate limit permanece coberto (e correto, sem risco de travar o próprio IP) em `tests/test_auth.py` |
| G3-3 | `scripts/verificar_v1.py` sem tratamento de erro de conexão — contra uma URL fora do ar, estourava traceback bruto do `httpx`/`httpcore` em vez de reportar FALHA de forma limpa | médio | **corrigido** — `try/except httpx.HTTPError` em `main()`, reproduzido antes e depois da correção (antes: traceback; depois: `FALHA nao foi possivel falar com ... `, saída 1) |

**Conclusão: G3 atendido após as correções.** O teste E2E é genuinamente forte
(depende da cadeia real de ponta a ponta, não é um atalho); o achado sobre a
migration em banco legado confirmou que a cobertura já existia, sem exigir
código novo; os 3 achados reais (1 alto de documentação, 2 médios no script
novo) caíram antes do commit. **Suíte**: 448 passed.

---

## Conclusão da V1 (Blocos A–G)

Os sete blocos da V1 (V1.0–V1.8) estão feitos, cada um com verificação
independente própria e commit isolado, seguindo o mesmo método do início ao
fim: agente separado sem memória da implementação, instruído a procurar
defeito, rodando a suíte real contra Postgres (nunca mock de banco) e, nos
casos de maior risco, reproduzindo o cenário ao vivo antes de reportar como
certeza. Todo bloco menos o A, o C (achados só de robustez/documentação) e o
G1 (achados de infraestrutura de deploy) teve pelo menos um defeito real de
código encontrado e corrigido antes do commit — o Bloco D foi reprovado na
primeira passada; o Bloco E teve um vazamento crítico de mascaramento; o
Bloco F teve peso bruto em kg cru na tela default do cockpit; o G2 teve o
request id perdido justo no caso que mais precisa de correlação. Nenhum
defeito real chegou a produção: a VM está hoje em `origin/main` (commit
`98ca86f`, Bloco F) — G1/G2/G3 existem só localmente até a Maria autorizar o
deploy.

**Pendências conhecidas, todas declaradas com decisão explícita da Maria (não
esquecimento) e sem código pra fingir o contrário:**

- destino externo do backup (fora da VM) — G1, decisão "pensar depois";
- identidade por pessoa (a auditoria é sempre `ator = "admin"`) — segue senha
  única, decisão do G1/G2; a coluna já existe pronta para quando entrar;
- sem HTTPS — decisão do G1/G2; o cookie de sessão não tem `secure`;
- filtro de filial/cliente do cockpit e linhagem aceita um valor por vez ou
  "todos", não múltiplos — F2, Bloco F;
- controle de processamento por nome de arquivo, superado pela reestruturação
  do DataHub em 4 unidades — **corrigido** em 02/ago/2026 (chave por `item_id`);
- rate limit de login em memória (sem persistência, perde estado num restart
  do container) e sem lock no teto de mensagens do Laboratório (E5) —
  proporcional a ferramenta interna de CSC, não defesa contra atacante
  determinado;
- grão único por métrica do DataHub é invariante de código, não de schema
  (Bloco C) — nenhum modelo atual referencia essas métricas, mas não criar
  sem revisar a regra.

**V1 atendida.** Deploy de G1+G2+G3 na VM (`git push` + runbook de
`docs/DEPLOY.md`) fica decisão separada da Maria — não é ação deste checkpoint.
