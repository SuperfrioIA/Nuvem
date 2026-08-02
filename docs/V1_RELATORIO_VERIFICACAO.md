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
