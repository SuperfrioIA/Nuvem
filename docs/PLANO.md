# Plano de construção — Nuvem IA

> Plano ativo da POC: [docs/POC_ATUAL.md](POC_ATUAL.md). Este arquivo é o histórico
> do plano de produto (Lotes 0–10, R0–R3) — nenhum lote daqui está autorizado
> automaticamente (29/jul/2026).

Plano em lotes (agrupados por módulo tocado, não por prioridade). **Um lote por vez;
aguardar validação antes do próximo.** Gatilho pra começar: a Maria diz "vamos pro
Lote N". Ao fechar um lote, marcar o check e **commitar** — este arquivo é a verdade
compartilhada entre sessões.

Status possíveis por lote: `a fazer` · `em andamento` · `feito` · `bloqueado`.

## Como escolher o modelo

- **Fable 5** — pensar/decidir: design denso, estatística, ambiguidade.
- **Opus 4.8** — capacidade máxima quando o problema trava (viz difícil, bug cabeludo).
- **Sonnet 5** — cavalo de batalha: construir código bem-especificado.
- **Haiku 4.5** — tarefas pequenas, mecânicas, spec fechada (scripts, glue).

O desenho já está fechado nos docs, então quase tudo é construção → Sonnet. Fable/Opus
só onde há julgamento (o motor).

---

## Lote 0 — Destravar o mundo externo

**Status: em andamento** · não é código; começa já e roda em paralelo a tudo.
**Modelo:** — (coordenação humana; redigir pedido/contrato = Sonnet 5).

- [x] Pedido à TI: app registration no Entra ID, permissão `Sites.Selected` — app
      `nuvem-ia` registrado, consentimento de administrador aprovado (16/jul/2026). Site
      dedicado criado: `https://superfrioarmazens.sharepoint.com/sites/nuvem-ia`.
      *21/jul/2026: fora do caminho crítico da apresentação da POC — a demo roda com
      os dados locais na máquina da Maria; SharePoint entra depois.*
- [x] **Vínculo com o SharePoint funcionando (29/jul/2026)** — mudou o site: as bases
      ficam no **site DataHub**, não no `nuvem-ia`
      (`/sites/DataHub`, pasta `Documentos Compartilhados/00.Dados/00.Bronze/00.Dados_Sistemicos`).
      Concessão `read` executada pelo Carlos (`carlos.rvsilva`, SharePoint Admin) — a
      concessão de `Sites.Selected` é **por site**, e o consentimento de 16/jul não
      bastava. Leitura confirmada com **token de aplicação**, não com conta de usuário.
      Inventário completo (228 arquivos, 711 MB, 8 famílias do WMS SLIN), colunas por
      família e obstáculos em **docs/FONTES_DATAHUB.md**. Escrita no site `nuvem-ia`
      (backup do `pg_dump` + retenção dos xlsx) segue pendente e foi deliberadamente
      **deixada fora** deste pedido para não atrasar a leitura.
- [ ] De-para dos códigos numéricos de filial dos arquivos do DataHub (`001`, `002`,
      `015`, `016`) para as siglas WMS do `depara_armazem` — bloqueia agregar qualquer
      métrica dessas fontes por armazém. Ver docs/FONTES_DATAHUB.md §6
- [ ] Confirmar quem publica na `00.Dados_Sistemicos` e com que cadência (as evidências
      apontam republicação da competência corrente, não arquivo novo por mês)
- [ ] Congelar o contrato da planilha de ocupação (aba + colunas fixas + quem preenche)
- [x] Filiais do piloto escolhidas (21/jul/2026): **família RMSP** — a POC é catering
      (docs/PILOTO.md refeito nessa data; análise completa em `docs/Analise/saida/`).
      RMSPII/III são o núcleo (clientes de refeição coletiva), RMSP dá o caso Frimesa
      (anti-dupla contagem) e RMSPV acompanha (nasceu no WMS em 14/jul/2026, vazia)
- [ ] Definir o dono de cada dado (ocupação / comercial / volumetria) — prioridade:
      quem responde pelo comercial de Barueri (contratos take-or-pay do catering)
- [ ] Pedidos ao time do DW que destravam a POC catering: integrar a volumetria da
      RMSPIII ao fato; gerar o relatório detailed (posição×cliente) pras RMSP (hoje
      só RPI tem); corrigir o segmento dos clientes de catering (constam como "Ind.
      Química/Resinas/Tintas" na dimensão de clientes)
- [ ] Confirmar se ocupação tem histórico retroativo (se não, começa a acumular agora)
      — análise 17/jul: os relatórios de ocupação são foto do dia; o histórico diário
      existe no DW mas só é recuperável via banco/API (Lote 10, pós-MVP). Sem isso,
      vale a regra: acumular a partir de agora, 1 foto por competência
- [ ] Combinar com a TI o destino do `pg_dump` fora da VM (candidato natural: o site
      SharePoint `nuvem-ia`, já criado — falta confirmar)
- [x] Chave SSH da VM com acesso ao repo `SuperfrioIA/Nuvem` (20/jul/2026): a default era
      deploy key do Conciliador; criada a `nuvem_deploy` (apelido `github-nuvem` no
      `~/.ssh/config`) e cadastrada como deploy key read-only no repo. Runbook completo em
      docs/DEPLOY.md
- [x] Porta 8002 na rede interna (20/jul/2026): não precisou de chamado — a 8002 já
      respondeu de outra máquina após o deploy (cai numa faixa/regra do Security Group já
      liberada na VM, como a 8001 do Hub). Valcann fica de fallback se alguma porta futura
      não abrir

**Check de conclusão:** pedido protocolado; contrato escrito e combinado; filiais escolhidas.

## Lote 1 — Esqueleto + primeiro dado real

**Status: feito** (15/jul/2026) · infra + banco + admin upload. **Modelo:** Sonnet 5.

- [x] `docker-compose`, `Dockerfile`, `.env` (porta 8002, 2 containers, worker único)
- [x] Esqueleto FastAPI (API + estáticos)
- [x] `database.py`: 9 tabelas (inclui `modelos_importacao`) + `init_db` idempotente
- [x] Conector `upload_manual` com modelos de importação: mapeamento de colunas
      (armazém/competência fixos ou por coluna; métrica por soma ou razão
      numerador/denominador; cliente reconhecido mas não persistido), salvo e
      reutilizável por relatório — ver docs/ARQUITETURA.md
- [x] Retenção do arquivo original do upload (pasta local na VM, plugável pra
      SharePoint depois) + referência na execução — drill-down manual dessa fonte
- [x] `admin.html` mínimo: upload xlsx (com tela de mapeamento/escolha de modelo),
      CRUD de-para, log de execuções
- [x] Auth: senha única no `/admin`

**Check de conclusão:** validado rodando os containers de verdade (WSL/Docker local —
não tem Docker Desktop; a distro WSL já tem Docker Engine + Compose, dispensa
Docker Desktop). Sobe limpo na 8002 com `--build`; upload sem de-para grava 0 e vira
pendência; de-para resolve; reprocesso com modelo salvo grava em `medidas`; execução
aparece no log com o arquivo original referenciado. **Infra validada na VM real em
20/jul/2026** (sobe na 8002, admin autentica, seed carregado); o fluxo de
upload/de-para/reprocesso segue validado só local por ora.

Bug de infra achado e corrigido no processo: `nuvem-app` tentava conectar no Postgres
antes dele aceitar conexão (caía e reiniciava sozinho, disfarçado pelo
`restart: unless-stopped`). Corrigido com healthcheck (`pg_isready`) + `depends_on:
condition: service_healthy`.

Achado de qualidade de dado (não é código): no arquivo real de ocupação,
`Cap Peso Bruto` vem zerado em 100% das linhas (par inviável) e `Cap Posição`/`Cap
Volume`/`Cap LPN` têm valor sentinela `999999999` (precisa listar em
`ignorar_valores` no modelo, campo já existe). Mesmo filtrando, nenhum par testado deu
um número "limpo" de ocupação — segue pendente a confirmação com o dono do dado (ver
memory/decisoes-fechadas.md / Lote 0). *Atualização 17/jul/2026: a análise dos
relatórios explicou as sentinelas — `999999999` = posição sem limite físico
(blocado/drive-in) e `888888888` = posição de ressuprimento (RESSUP); e o par "limpo"
de ocupação é posições ocupadas ÷ capacidade do pos_sum, tratando as posições virtuais.
O tratamento vira regra de modelo no Lote 8; a confirmação com o dono do dado continua
valendo como checagem.*

**Primeiro número real na tela.**

## Lote 2 — Conectores plugáveis completos

**Status: a fazer** · camada de conectores + SharePoint. **Modelo:** Sonnet 5.
Depende do Lote 0 pra testar de verdade. *Não bloqueia a apresentação da POC
(21/jul/2026): a demo roda com dados locais (upload manual + retenção em pasta
local, desenho do Lote 1); SharePoint entra depois, sem mudar arquitetura.*

*Nota 29/jul/2026: parágrafo acima superado — o SharePoint DataHub passou a ser
fonte permanente, não conector opcional que "entra depois" (ver
memory/decisoes-fechadas.md). O canal DataHub ganhou marco próprio (Lotes P0–P6,
docs/POC_ATUAL.md), fora deste plano; o `sharepoint_excel` deste Lote 2 continua
válido como conector formal (formato canônico + modelos de importação), a construir
depois da POC.*

- [ ] Interface única (`testar` / `buscar` / `detalhar`)
- [ ] Conector `sharepoint_excel` (Microsoft Graph)
- [ ] Registro + toggle no admin

**Check de conclusão:** toggle liga/desliga; `testar()` responde ok/erro; com credencial,
`buscar()` traz ocupação do SharePoint no mesmo formato canônico. Sem credencial, "testar
conexão" acusa erro (esperado) e seguimos no upload manual.

## Lote 3 — Motor + scores

**Status: feito** (16/jul/2026) · motor de scores. **Modelo:** Sonnet 5.

- [x] Decidido: média/desvio-padrão amostral (não mediana/MAD — arquitetura já autorizava
      pro piloto; MAD fica registrado como evolução se o nº de métricas crescer). Janela
      de até 24 competências anteriores (exclui o mês em análise); histórico mínimo de 6
      competências pra ser avaliável (abaixo disso, `historico_curto`); limiar `|z| >= 2`
      pra `fora_padrao`.
- [x] Motor em Python puro (`backend/motor.py`, só stdlib `statistics`)
- [x] Tabela `scores` (já existia no schema do Lote 1) — recalculada por completo
      (delete+insert) a cada rodada, sem recálculo seletivo (volume do piloto é pequeno)
- [x] Disparo pós-ingestão: automático ao fim de `upload/processar`; endpoint manual
      `POST /api/admin/scores/recalcular`; leitura em `GET /api/admin/scores`
- [x] "Sem dado" ≠ "dentro do padrão": ausência de linha em `medidas`/`scores` (o motor
      não grava nada nesse caso) — o Lote 5 (tela) é quem distingue isso de `normal`

**Check de conclusão:** validado local (infra na VM validada em 20/jul/2026 — ver Lote 1)
com dataset sintético controlado (perdas+volumetria, 12 meses armazém RPI + 3 meses CGH)
rodando nos containers de verdade: `historico_curto` nos 6 primeiros meses de RPI (e nos
3 meses inteiros de CGH, que nunca atinge o mínimo), `normal` no meio da série, e
`fora_padrao` batendo nas duas métricas juntas em dez/2023 (z=218 perdas, z=-54
volumetria) — reproduz o padrão do cenário conhecido. Recálculo 2x deu o mesmo resultado
(idempotente). **Falta ainda**: rodar sobre os dados reais de perdas/volumetria do Lote 1
pra confirmar que os números batem com o relatório oficial — os três arquivos novos em
`docs/` não servem pra isso (ver nota abaixo).

Achado no processo (não é do Lote 3, não corrigido): o campo `pendencias` da resposta de
`/upload/processar` (`linhas_lidas - linhas_gravadas`) fica negativo quando o modelo tem
mais de uma métrica por linha (cada linha física vira N gravações) — bug do Lote 1,
exposto agora pelo teste com 2 métricas. Fica pendente de decisão.

Nota sobre os arquivos novos em `docs/` (16/jul/2026): nenhum serve pra validar o motor
com dado real agora. `rpt_dw_occupation_detailed_v01 (2).xlsx` é o mesmo snapshot de
ocupação grão-fino do Lote 1 (um dia só, valores zerados/sentinela ainda pendentes com o
dono do dado). `data (2).xlsx` é um export largo (mês nas colunas, jan/26–jul/26) com
linha de subtotal "Total" por cliente somada junto das linhas de cliente — o parser
atual contaria em dobro se subisse como está. `conciliacao_66.csv` é conciliação
SKU×lote, fora do grão do projeto (armazém×mês).

Atualização 17/jul/2026: a análise completa desses arquivos (e de mais 7 exports novos)
está em `docs/analise/saida/` (painéis, de-para consolidado e mapa de relações). O que
mudou pra este lote: **agora existe arquivo que serve** — o export bruto do fato de
volumetria (csv, dia×filial×cliente, 2021→hoje) dá a série histórica real que faltava
pra validar o motor. Ele entra como modelo de importação no Lote 8; a validação pendente
acima fecha lá.

## Lote 4 — Rotina agendada + backup

**Status: a fazer** · **Modelo:** Sonnet 5; script de backup pode ser Haiku 4.5.

- [ ] APScheduler embutido, 1×/dia, worker único
- [ ] Execução manual pelo admin
- [ ] Rebusca das últimas 3 competências
- [ ] Reprocesso = delete + insert por conector × competência
- [ ] `pg_dump` diário copiado pra fora da VM + retenção dos xlsx do upload

**Check de conclusão:** roda sozinha e é idempotente (2× não corrompe); execução manual
funciona; dump gerado e copiado pra fora da VM.

## Lote 5 — A nuvem (tela)

**Status: a fazer** · **Modelo:** Sonnet 5; se a viz travar, escalar pra Opus 4.8.

- [ ] `index.html`: grafo de bolinhas (padrão mapa-ia), lendo só a camada fina
- [ ] Seleção de contexto (filial × período)
- [ ] Estados: aceso / normal / sem-dado

**Check de conclusão:** abre em segundos lendo só a camada fina; contexto filtra; bolinhas
fora do padrão acendem juntas; distingue sem-dado de normal.

*Nota 29/jul/2026 — **como a bolinha vai acender: quatro caminhos, nenhum autorizado.**
Levantados quando a Maria decidiu que o Lote P5.5 (nuvem do DataHub, ver
docs/POC_ATUAL.md) entrega o grafo **sem** acender: "agora é pra mostrar que temos os
dados; só depois começar a dizer que algo está anormal". Ficam registrados aqui pra
discussão futura — decidir qual(is) adotar é conversa à parte.*

1. ***Regra fixa de cobertura/publicação.** Acende quando falta o arquivo de uma
   competência numa família, quando a competência corrente não é republicada há N dias,
   ou quando uma parte `_f2`/`_f3` está ausente. Não precisa de histórico nenhum e é
   totalmente explicável ("acendeu porque falta o arquivo da filial 002 em junho"). Não
   é anomalia de negócio, é **qualidade de dado** — e por isso nunca mente. É a mais
   barata e a candidata natural a primeira.*
2. ***Variação contra a competência anterior.** Acende se a métrica variou mais de X%
   vs o mês anterior. Precisa de 2 competências só. Simples, mas o X é arbitrário sem
   histórico e série curta gera falso positivo com facilidade.*
3. ***Motor de scores atual (z-score) sobre as fontes do DW, não do DataHub.** Achado
   que motivou a lista: as bolinhas que já poderiam acender com estatística de verdade
   são as do **DW** — a volumetria (`fato.csv`) tem série 2021→hoje e está carregada
   desde o Lote 8. O DataHub tem jan–jul/2026: como o motor exige 6 competências
   anteriores à analisada, só jul/2026 seria avaliável, com desvio-padrão tirado de 6
   pontos (instável — `|z| >= 2` dispararia quase por sorteio) e as outras 6 em
   `historico_curto`. Uma nuvem híbrida (acende nas métricas do DW, "só mapa" nas do
   DataHub) é honesta e não exige nada novo no motor.*
4. ***Detectores de regra de negócio.** Cobertura contratual acima de 100%, contrato
   vencido com movimento nos últimos 60 dias, ocupação acima do limite. É o que
   responde as 3 perguntas do docs/PILOTO.md — e é o que a revisão arquitetural já
   apontou (docs/DIAGNOSTICO.md, achado 3: o z-score não responde nenhuma das 3). Mas
   depende do Lote 9 (regra de composição da ocupação, ainda não fechada) e das fontes
   do DW atualizadas.*

## Lote 6 — Confiança e acabamento

**Status: a fazer** · **Modelo:** Sonnet 5 / Haiku 4.5.

- [ ] Painel de cobertura (matriz métrica × armazém × competência presente/ausente)
- [ ] Fila de pendências de de-para no admin
- [ ] Refino visual (skill `superfrio`)
- [ ] Card no Hub (Receita 3, tipo url, nova aba)
- [ ] Tela de ajuda, se precisar

**Check de conclusão:** cobertura mostra os buracos; pendências visíveis e resolvíveis;
visual dentro da identidade; card abre a nuvem numa nova aba do portal.

---

Os Lotes 7–10 nasceram da análise dos relatórios reais do DW (17/jul/2026 —
`docs/analise/saida/`: painéis, de-para consolidado, mapa de relações). Dois princípios
fechados com a Maria nessa data: **(a) nada de DW novo** — a camada fina continua
guardando só de-para + agregados armazém×competência + scores; o relatório bruto fica
retido como arquivo do upload (drill-down manual), nunca como tabela; **(b) a POC/MVP
termina só com upload manual** dos exports que já saem hoje — integração via banco do
DW (API) é degrau pós-MVP (Lote 10).

Recorte fechado em 21/jul/2026 (análise da família RMSP —
`docs/Analise/saida/analise_rmsp.xlsx` + `analise-rmsp/`): a POC é **catering na
família RMSP** — ver docs/PILOTO.md refeito. Os Lotes 8–9 ganham esse recorte; entram
o Lote 7.1 (complementos do de-para) e o Lote 9.5 (grão cliente mínimo).

## Lote 7 — De-para oficial (a camada fina ganha o dado real)

**Status: feito** (17/jul/2026) · **Modelo:** Sonnet 5 (a carga virou reconciliação de
duas fontes divergentes, não só carga mecânica — fugiu do escopo previsto pro Haiku).

Insumo: `docs/analise/saida/depara_e_relacoes.xlsx` (de-para da análise do DW) cruzado
com `docs/analise/Empresas Grupo Superfrio 5(Filiais Ativas).csv` (cadastro oficial
Protheus, trazido pela Maria pra dar nome/município às filiais). Conferência 17/jul/2026:
a aba `depara_filial` tem **32 siglas SF**, não 31 — a diferença é a CWBI (SK_FILIAL 74,
sem WMS/CNPJ, sem histórico de volumetria, filial nova) — incluída mesmo assim, com
sigla + código ERP `001995`.

Achados da reconciliação (ver comentário no topo de `backend/seed_depara.py`):
- Código ERP da JAC na análise original estava errado (`001007`); oficial é `001008`.
- 5 filiais têm sigla operacional (WMS) diferente da sigla do cadastro Protheus, mesma
  empresa (CNPJ e código batendo): CVDI/CVD, MAQ/MAQII, SSA/SSAI, RMSP/RMSPI, POA/POAI
  — a sigla operacional virou a `sigla` oficial no banco (é como o projeto já fala
  delas), a do cadastro entrou como apelido extra.
- RPIII, MRS e CWBI não aparecem no cadastro de filiais ativas. MRS está sem
  volumetria desde 02/2023 → marcada **inativa** (`ativo=false`; some da lista padrão
  do admin/tela, mas segue no de-para pra resolver uploads antigos). RPIII e CWBI
  nunca tiveram volumetria (parecem pré-operacionais) → mantidas ativas.
- Sem colisão de apelido entre filiais diferentes (102 apelidos, todos únicos).

- [x] Nome = sigla + município (ex.: "Ribeirão Preto/SP"); RPIII/MRS/CWBI sem
      município na fonte, nome = sigla
- [x] Carregado o de-para real em `armazens`/`depara_armazem` via
      `backend/seed_depara.py` (literais no código — `docs/analise/` está no
      `.gitignore`, a VM não teria acesso ao xlsx/csv em runtime), chamado de
      `init_db()`; idempotente (`ON CONFLICT ... DO NOTHING` em `armazens`, mesma
      lógica de conectores/métricas — nunca sobrescreve edição manual)
- [x] ICE (Chile) fica fora por ora: não existe de-para ERP×WMS pra elas (nem sigla no
      cadastro de capacidade); entra quando houver fonte com apelido resolvível
- [x] Dicionário de códigos (temperatura 2=CL/3=CG/4=RF/5=SC; estrutura 2=blocado,
      3=drive-in, 4=porta-palete; acordo P=posições/L=locação) documentado como
      comentário em `backend/seed_depara.py` — não virou tabela nova (sem DW)

**Check de conclusão:** validado local (WSL/Docker) com `docker compose up -d --build`
+ restart: 33 armazéns (32 do seed + `CGH` de teste do Lote 3, preservado), MRS inativa
com seus 3 apelidos, 103 apelidos de-para (102 do seed + `CGH` pré-existente), sem
colisão, contagens idênticas após um segundo restart (idempotente). Em 20/jul/2026,
confirmado também na VM real (banco novo): `GET /api/admin/armazens` retornou as 31
filiais ativas. **Falta ainda**: o teste de ponta a ponta ("upload de relatório real
resolve sem pendência") só fecha no Lote 8, quando existir modelo de importação pra essas
famílias de relatório.

## Lote 7.1 — Complementos do de-para (POC catering)

**Status: feito** (22/jul/2026) · pequeno; tocou `backend/seed_depara.py` + tabela nova.
**Modelo:** Sonnet 5.

- [x] RMSPV no seed (nasceu no WMS em 14/jul/2026 — ERP 008009, Log Frio, Barueri;
      ainda sem capacidade cadastrada, contrato ou volumetria)
- [x] RMSPIV registrado como só-cadastro (ERP 008003, nunca apareceu em fonte do DW)
      — não vira armazém ativo
- [x] Lista curada dos clientes de catering da família na camada fina: tabela nova
      `clientes` (`backend/seed_clientes.py`), 11 clientes (não 12 — ver nota abaixo),
      todos `catering=true`. O segmento do DW está errado — não serve de filtro.

Forma escolhida: tabela própria (não marcação num de-para de clientes), mesmo padrão
idempotente do `seed_depara.py`. Fonte: `docs/Analise/clientesDw.csv` (NK_CLIENTE,
RAZAO_SOCIAL, registro vigente) cruzado com `docs/Analise/ocupacaoComercial.csv`
(contratos vigentes de RMSPII/RMSPIII) — 8 clientes vieram do contrato direto (Sapore,
GR, Wyda/Cucinare, Pimenta Verde, Novita, Grupo Neffa, Sodexo, Bimbo); os outros 3
(Convida, OG do Brasil, FLV 7) não têm contrato vigente na família (achado do
PILOTO.md) e foram localizados por nome. Não são 12: Tirolez/Delly/Frimesa/Irmãos Boa
ficaram de fora por instrução explícita (são contratos de locação da RMSP, fora do
núcleo RMSPII/RMSPIII) — a lista bateu em 11 sem precisar perguntar.

**Check de conclusão:** validado local (WSL/Docker, worktree próprio, porta 8003) com
`docker compose up -d --build` + restart: 32 armazéns ativos (31 do Lote 7 + RMSPV),
RMSPIV não aparece; 11 clientes, todos `catering=true`; contagens idênticas após
restart (idempotente); smoke test de upload (xlsx com RPI + RMSPV, formato longo) —
2 linhas lidas, 2 gravadas, 0 pendências, confirmando que a tabela nova não quebrou o
fluxo existente. `GET /api/admin/clientes` no padrão do `listar_armazens`; tabela
read-only em `admin.html` dentro do `#painel-depara`, carregada em `carregarTudo()`.

Achado de infra (não é bug deste lote): o `docker-compose.override.yml` deste worktree
tinha `ports` como lista simples — o Compose faz merge (concatena) de listas em vez de
substituir, então o app tentava subir também na 8002 (porta do worktree main) e
colidia. Corrigido com a tag `!override` do Compose Spec (suportada a partir da v2.24;
este ambiente tem v5.1.4) pra sobrescrever a porta em vez de somar. Arquivo não
versionado (local ao worktree), não precisa de ação na main.

## Lote 8 — Relatórios reais como fonte (upload, sem integração de banco)

**Status: feito** (22/jul/2026) · modelos de importação + evoluções do parser.
**Modelo:** Sonnet 5.

Cada família de relatório mapeada na análise virou um modelo de importação salvo, com
as regras de limpeza aprendidas. Evoluções do parser (`backend/conectores/upload_manual.py`):
leitura de csv (além de xlsx — 4 das 5 fontes reais são csv, `;` separador, UTF-8);
filtro de linha por valor de coluna (`filtros`, nível do modelo e/ou da métrica —
operadores `igual`/`diferente`/`vazio`/`não_vazio`/`maior_igual`/`menor_igual`); soma de
várias colunas numa métrica só (`soma_colunas` — necessário pra ocupação manual, que
quebra a mesma métrica em 5 colunas por estrutura PPA/DRV/BLC/PSH/UNI); `divisor`
opcional pra conversão de unidade sem chumbar a conta no valor bruto (peso em kg ÷ 1000
= toneladas). UI do admin ganhou os campos correspondentes (filtros do modelo
repetíveis, filtro por métrica, tipo "soma de várias colunas", campo divisor).

Recorte da POC: filiais alvo = família RMSP; ordem de entrada: fato, pos_sum,
capacidade, comercial, manual. As regras de limpeza de cada fonte vieram de
`docs/Analise/saida/analise_rmsp.xlsx` (abas Leia-me, Conferência de fontes e
Dicionário) — mesmo insumo do catálogo do Lote 8.5.

Achado da carga (22/jul/2026): `ocupacaoComercial.csv` e `ocupacaoManual.csv` usam a
chave numérica do DW pra filial (`FK_FILIAL`), não a sigla WMS — RMSP=30, RMSPII=45,
RMSPIII=46 (confirmado batendo a soma de `OCUPACAO_POSICAO_QTD` do FK_FILIAL=46 com o
achado de 9.773 posições da RMSPIII). Esses 3 códigos entraram como apelido novo em
`backend/seed_depara.py` (idempotente, só adiciona); as demais ~29 filiais fora da
RMSP ficam sem esse de-para numérico por ora — aparecem em `depara_pendencias`,
resolvíveis quando entrarem no recorte.

- [x] **Volumetria (fato.csv)** — armazém `NK_WMS_FILIAL`, competência `NK_CALENDARIO`.
      Duas métricas (`volumetria_recebimento`/`volumetria_expedicao`, decisão de
      22/jul/2026 — filtro por `NK_OPERACAO`, ÷1000 kg→t); filtros do modelo excluem
      `NK_INSTANCIA=DW_STG_PRD`, `NK_EMPRESA` vazio e peso negativo. Gap aberto (não
      bloqueia): `NK_OPERACAO="Cross Docking"` (148 linhas de ~143k) não entra em
      nenhuma das duas métricas — decidir se ganha métrica própria quando doer
- [x] **Ocupação física (pos_sum.xlsx)** — armazém `Filial`, competência `Data`
      (`%d/%m/%Y` — é foto do dia, 1 upload = 1 competência, sem ambiguidade de "qual
      dia escolher"). Métricas separadas em vez de razão única (decisão de construção):
      `posicoes_ocupadas`, `capacidade_total/_bloqueada/_disponivel` — mantém o dado
      bruto disponível pra outros usos; a razão (% ocupação) é derivada no Lote 9, não
      recalculada aqui. `posicoes_virtuais` ganhou métrica própria (decisão de
      22/jul/2026 — filtro `Local` vazio)
- [x] **Capacidade cadastrada (capacidade1HDR.csv)** — armazém `WMS_ENTITY_ID`,
      competência fixa (digitada no upload). Mesmas métricas de capacidade do pos_sum
      (`capacidade_total/_bloqueada/_disponivel`) — é o mesmo cadastro, upsert
      substitui o valor mais recente
- [x] **Ocupação comercial (ocupacaoComercial.csv)** — armazém `FK_FILIAL`, competência
      fixa. Métrica `comercial_vigente` = soma de `OCUPACAO_POSICAO_QTD` sem filtro de
      vigência (mantido manual como já combinado — `DATA_INICIAL`/`DATA_FINAL` ficam
      documentadas no catálogo do Lote 8.5, sem uso no parser ainda)
- [x] **Ocupação manual (ocupacaoManual.csv)** — armazém `FK_FILIAL`, competência
      `DW_DATA_INCLUSAO`. Métrica `ocupacao_manual` = `soma_colunas` das 5
      `OCUPACAO_POSICAO_QTD_*` (PPA/DRV/BLC/PSH/UNI)
- [x] **O que não sobe** (confirmado, sem mudança): pivô do Power BI e conciliação
      SKU×lote continuam fora — não entraram modelo nem foram tocados
- [x] Métricas novas semeadas em `backend/database.py` (mesmo padrão idempotente):
      `volumetria_recebimento`/`_expedicao` (t), `posicoes_ocupadas`/`_virtuais` (posições),
      `capacidade_total`/`_bloqueada`/`_disponivel` (posições), `comercial_vigente`
      (posições), `ocupacao_manual` (posições)

**Check de conclusão:** cada família com modelo salvo e reprocessável (upsert
idempotente); volumetria real carregada — **fecha a validação do motor com dado real
que ficou pendente no Lote 3**; competências reais de ocupação física gravadas nas
filiais do piloto.

Validado local (WSL/Docker, worktree `lote-8`, porta 8005) com `docker compose up -d
--build` subindo os 5 arquivos reais (via API e, depois, refeito manualmente na tela do
admin pra confirmar a UI): números batendo exatamente com os achados de
`analise_rmsp.xlsx` — RMSPIII 80,3%/97,1%/124% (ocupação s/ total, s/ disponível,
cobertura contratual — calculados na hora a partir de `posicoes_ocupadas`/
`capacidade_total`/`capacidade_disponivel`/`comercial_vigente`, 578 posições virtuais),
RMSPII 17,8% de bloqueio e 65,3%/79,4% de ocupação, RMSP com 96% de cobertura
(Tirolez/Delly), volumetria RMSPII jun/26 ≈ 32 mil t (recebimento+expedição). Restart
não duplicou nada (34 armazéns, 111 apelidos, 12 métricas — 3 do Lote 1 + 9 novas — após
o restart, iguais a antes). Achado de testagem: o primeiro teste pela tela do admin
achou um bug real que a validação via API não pegava — o seletor `#metricasContainer
.linha-metrica` casava também o filtro aninhado dentro de cada métrica (mesma classe
CSS reaproveitada), quebrando `montarMapeamento()`; corrigido trocando pra filho direto
(`#metricasContainer > .linha-metrica`).

## Lote 8.5 — Catálogo de fontes (tela no admin)

**Status: feito** (22/jul/2026) · decisão de 21/jul/2026 — transparência do que o
sistema vê. **Modelo:** Sonnet 5. A estrutura nasceu antes do Lote 8; modelo_id fica
NULL em todas as fontes até o Lote 8 criar os modelos de importação de verdade — aí
cada família ganha o vínculo e passa a listar execuções.

Tela **dentro do admin** listando todas as planilhas/famílias de relatório que o
sistema vê, com base no mapeamento da análise (`docs/Analise/saida/analise_rmsp.xlsx`
abas Leia-me/Conferência/Dicionário + `depara_e_relacoes.xlsx` + mapa-dados).

- [x] Tabelas `catalogo_fontes` e `catalogo_colunas` na camada fina; seed com literais
      no código (mesmo padrão do `seed_depara.py` — `docs/Analise/` está no
      `.gitignore`, a VM não lê os xlsx em runtime). É metadado/documentação, não dado
      bruto — não fere o "nada de DW novo"
- [x] Por fonte: descrição/resumo do que a planilha traz + origem (de qual tabela vem:
      fato, STG ou dimensão do DW, ou cadastro de banco)
- [x] Drill-down de colunas: todas as colunas da planilha, com significado (dicionário
      da análise) e como cada uma entra no modelo de importação (armazém / competência
      / métrica / cliente / não mapeada)
- [x] Por fonte, lista dos arquivos já subidos dela (vem do log de execuções que já
      existe — "o sistema viu este arquivo nesta data")
- [x] Escopo inicial: famílias do recorte da POC (as 5 do Lote 8); os demais
      relatórios mapeados na análise entram depois

**Check de conclusão:** admin mostra as fontes com descrição e origem; clicar numa
fonte abre as colunas com significado e papel no modelo; arquivos subidos aparecem
por fonte.

Validado local (WSL/Docker) com `docker compose up -d --build` + restart: 5 fontes
(volumetria/fato, ocupação física/pos_sum, capacidade/HDR, ocupação comercial,
ocupação manual) com todas as colunas reais dos arquivos brutos de
`docs/Analise/saida/` — não só as citadas no dicionário curado, a planilha inteira,
com papel `nao_mapeada` explícito pras chaves técnicas do DW e métricas fora do
recorte da POC. `GET /catalogo/{id}` com `modelo_id` NULL retorna `execucoes: []`
(não erro), como previsto. Contagens idênticas após restart (idempotente); fluxo de
upload/de-para existente (31 armazéns ativos, conectores) não foi afetado.

## Lote R0 — Alicerce da revisão arquitetural (testes + Alembic)

**Status: feito** (22/jul/2026) · primeiro lote da revisão arquitetural de 22/jul —
diagnóstico, matriz de riscos e plano completo (R0–R6) em **docs/DIAGNOSTICO.md**.
Os lotes R1+ aguardam aprovação; o R1 (fontes lógicas + versionamento real de
modelos) terá o desenho revisado apresentado antes de construir. **Modelo:** Fable 5.

- [x] Alembic adotado: baseline `0001_baseline` com as 12 tabelas; `init_db()` fica
      só com os seeds (nada de ALTER estrutural no startup)
- [x] Startup: migrar → seeds. Banco novo nasce da baseline (`upgrade head`); banco
      **legado** é validado (12 tabelas + colunas obrigatórias) **antes** do stamp
      automático — qualquer divergência aborta sem tocar o banco, com erro claro no
      log e contingência documentada (docs/DEPLOY.md, "Migrations")
- [x] Limite de tamanho de upload (`UPLOAD_MAX_MB`, default 50 MB, HTTP 413)
- [x] Suíte pytest com Postgres real (25 testes): parser com os **mapeamentos reais**
      dos 5 modelos (extraídos do banco do worktree lote-8 — também insumo do seed do
      R1) sobre arquivos sintéticos; ingestão (de-para/pendência/upsert idempotente);
      motor (estados/limiar/recálculo idempotente); migração (novo, legado válido,
      legado divergente aborta, baseline ≡ init_db antigo); 5 fluxos de upload ponta
      a ponta pela API
- [x] Docs corrigidos: README (status), ARQUITETURA (12 tabelas, APScheduler é Lote 4,
      migrations, testes), PILOTO (parcelas de ocupação), DEPLOY (migrations +
      contingência + como rodar testes)
- [x] Fora do escopo e não tocado: parsing, ingestão, motor, auth, frontend (além do
      limite de upload e da conexão do startup)

**Check de conclusão:** suíte verde (25 passed) rodando em container python:3.11 +
Postgres 16 de teste; banco legado **real** local adotado pelo Alembic no
`up -d --build` (35 armazéns/30 medidas preservados, stamp aplicado, restart
idempotente — mesmas contagens); os testes de drift provam que banco divergente não
recebe stamp. **Adoção repetida na VM real em 22/jul/2026**, com um achado: a VM
ainda rodava o código de antes dos Lotes 7.1/8/8.5 (não tinha passado por
`git pull` desde o primeiro deploy em 20/jul), então o banco legado abortou o
stamp automático por faltar `clientes`/`catalogo_fontes`/`catalogo_colunas` —
exatamente o caminho de contingência já documentado em docs/DEPLOY.md ("Caso 1").
Resolvido subindo uma vez a versão anterior ao R0 (`git checkout 387c674`, o
`init_db` antigo cria as 3 tabelas que faltavam) e voltando pra `main` em seguida;
o stamp passou na sequência e os dados reais foram confirmados intactos (32
armazéns, login ok). Nada foi perdido — o abort automático funcionou como
projetado.

## Lote R1 — Fontes lógicas + versionamento real dos modelos

**Status: feito** (22/jul/2026) · segundo lote da revisão arquitetural (docs/DIAGNOSTICO.md).
Escopo mínimo e seguro pedido pela Maria: rastreabilidade real de
fonte/modelo/versão/execução, sem governança pesada. **Modelo:** Sonnet 5.

- [x] `catalogo_fontes` como **fonte lógica**: ganhou `ativo` (a `chave` já era o
      código estável; nome/descrição já existiam). `modelos_importacao` ganhou
      `fonte_id` apontando pra cá.
- [x] `modelo_versoes` (nova): versão **imutável** por modelo — `mapeamento` JSONB,
      `hash_config` (sha256 canônico), `ativo`, `padrao`, `criado_em`; unique
      (modelo_id, versão), índice único parcial garantindo **uma padrão por modelo**,
      e CHECK `padrao_exige_ativo` (padrão ⟹ ativo). Editar modelo = criar versão nova
      e mover o ponteiro `padrao`; versão antiga nunca muda.
- [x] `execucoes.modelo_versao_id` (novo): toda execução nova grava a versão **exata**
      usada; execuções antigas preservadas.
- [x] Migration Alembic **0002** (preserva dados de produção): converte cada modelo
      atual em **v1** (ativa/padrão); backfill de `execucoes.modelo_versao_id` pra v1
      do seu modelo quando há modelo; execução sem modelo fica NULL. Mapeamento
      inválido **aborta** com erro claro sem tocar o banco (roda na transação do
      Alembic). `catalogo_fontes` ganha `ativo` e `modelos_importacao` ganha `fonte_id`
      no mesmo passo.
- [x] Upload/reprocessamento: **upload novo** com modelo salvo usa a versão
      **ativa/padrão**; **reprocessamento** (`POST /execucoes/{id}/reprocessar`, a
      partir do arquivo retido) usa a **mesma versão da execução original**, nunca a
      mais nova — criar versão nova não muda resultado histórico. Endpoints novos:
      `POST /modelos/{id}/versoes` (editar = nova versão), `GET /modelos/{id}/versoes`.
- [x] Testes: banco novo sobe com R0+R1; banco R0 migra pra R1; modelos existentes
      viram v1; upload grava modelo_versao_id; reprocessamento usa a versão original;
      versão nova não altera execução antiga; versão inativa não vira padrão. **31
      testes** (25 do R0 + 6 novos) verdes; 3 testes de migração do R0 ajustados
      (fixavam "head == baseline", que qualquer migration nova invalida — intenção
      preservada).
- [x] ~~Adiado: seed dos 5 modelos canônicos + vínculo `catalogo_fontes.modelo_id`~~ →
      **fechado no Lote R1.1** (abaixo). Tela de edição de versões, workflow de
      aprovação, comparação de versões: seguem fora do escopo, como combinado.

**Check de conclusão:** suíte verde (31 passed) em container python:3.11 + Postgres 16;
**clone do banco dev/R0 real** (0001_baseline, 1 modelo, 1 execução, 33 armazéns)
migrado pra 0002 com dados preservados — o modelo virou v1 (ativo/padrão), a execução
ganhou a versão, `catalogo_fontes.ativo` populado, restart idempotente (não duplica
versão). Fluxo end-to-end provado: v1 dá 16.000 t; nova versão (v2, divisor diferente)
daria 8.000 t; reprocessar a execução da v1 reproduz 16.000 t; upload novo com o modelo
usa a v2 (8.000 t). **Não deployado na VM** — aguarda validação da Maria.

## Lote R1.1 — Seed dos modelos canônicos (fecha o risco H)

**Status: feito** (22/jul/2026) · complemento curto do R1. **Modelo:** Sonnet 5.
Objetivo: banco novo já nasce utilizável (fontes lógicas + modelos + v1 vinculados),
sem criação manual na VM.

Os **5 modelos canônicos da POC** (`backend/seed_modelos.py`, literais = fonte única da
verdade dos mapeamentos; `tests/modelos_reais.py` re-exporta de lá — a imagem Docker só
copia `backend/`), cada um ligado à sua fonte lógica e com **versão v1 ativa/padrão**:

| Fonte lógica (`catalogo_fontes.chave`) | Modelo (`modelos_importacao.nome`) | Versão |
|---|---|---|
| `ocupacao_fisica` | Ocupação física (pos_sum) | v1 ativa/padrão |
| `capacidade` | Capacidade cadastrada (HDR) | v1 ativa/padrão |
| `ocupacao_comercial` | Ocupação comercial (contratos) | v1 ativa/padrão |
| `ocupacao_manual` | Ocupação manual | v1 ativa/padrão |
| `volumetria` | Volumetria (fato) | v1 ativa/padrão |

- [x] Seed idempotente (padrão `seed_depara`/`seed_catalogo`): só cria o modelo se a
      fonte ainda não tem um vinculado; nunca sobrescreve edição manual nem duplica
      versão. Roda no `init_db()` depois do `seed_catalogo` (precisa das fontes).
- [x] Vínculo nos dois sentidos: `modelos_importacao.fonte_id` → fonte e
      `catalogo_fontes.modelo_id` → modelo (o catálogo passa a listar execuções por fonte).
- [x] A config da v1 é **idêntica** ao mapeamento dos testes/fixtures (mesmo objeto
      importado). **Regra:** novas versões nascem por `POST /modelos/{id}/versoes`,
      **nunca alterando a v1** — a v1 é imutável (ver Lote R1).
- [x] Testes: `count(modelos)==1` corrigido pra delta-zero; banco novo prova
      fonte→modelo→v1 ativa/padrão (+ idempotência); os 5 uploads contra os modelos
      semeados usam a v1 padrão e batem os números conferidos. **33 testes** verdes.

**Check de conclusão:** banco novo do zero (migrar+init_db) lista as 5 fontes ativas,
cada uma com modelo vinculado e uma única versão v1 ativa/padrão; segundo `init_db` não
duplica nada; os 5 uploads pela versão padrão reproduzem RMSPIII 9.773 posições
ocupadas, RMSPII 16.000 t de recebimento (jun/26) e RMSP 700 posições manuais.
**Não deployado na VM** — aguarda validação da Maria.

## Lote R2 — Linhagem (recebida × canônica × derivada)

**Status: feito** (22/jul/2026) · terceiro lote da revisão arquitetural
(docs/DIAGNOSTICO.md). Escopo enxuto pedido pela Maria: estrutura de linhagem, sem
regra de derivação real, sem UI, sem tocar cálculo dos 5 uploads. **Modelo:** Sonnet 5.

- [x] `medidas_recebidas` (nova, append-only): 1 linha por item agregado publicado por
      uma execução — `execucao_id`, `modelo_versao_id`/`fonte_id` denormalizados,
      `armazem_id`, `cliente_id` (reservado), `metrica_id`, `competencia`,
      `data_referencia`/`unidade`/`dimensoes`/`linha_origem`/`aba_origem`/`arquivo_origem`
      (reservados, NULL nos 5 modelos atuais), `criado_em`.
- [x] `medida_linhagem` (nova): N:N entre medida derivada e as medidas/recebidas que a
      formaram (`medida_origem_tipo`, `medida_origem_id`, `papel_origem`) — pronta pro
      Lote 9, nenhuma regra real grava aqui ainda.
- [x] `medidas` ganha `medida_recebida_id`, `origem_tipo`
      (recebida/derivada/manual/ajuste/legado, CHECK), `regra_codigo`, `regra_versao`,
      `calculado_em` (CHECK: derivada exige os três preenchidos).
- [x] `ingestao.gravar_agregados` grava a recebida antes de publicar a canônica
      (`execucao_id` novo no parâmetro); nova `registrar_medida_derivada` (delete+insert
      da linhagem) só provada por teste, sem regra real ainda.
- [x] Migration Alembic **0003**: aditiva; medidas existentes não têm vínculo com
      execução (nunca tiveram) — vira `origem_tipo='legado'` sem inventar linhagem.
- [x] Testes: banco novo com R2; banco pré-R2 migra preservando medida como legado;
      upload novo grava recebida e publica canônica vinculada; reprocesso acumula
      recebidas mas mantém canônica idempotente; os 5 uploads reais continuam batendo;
      medida derivada de teste registra regra_codigo/regra_versao/calculado_em +
      linhagem. **39 testes** verdes (33 do R1.1 + 6 novos).

**Check de conclusão:** rastro completo de um valor do cockpit até o arquivo original
(medida → recebida → execução/versão/fonte → arquivo retido); reprocesso segue
idempotente na canônica; nenhuma medida legada ganhou linhagem inventada.
**Não deployado na VM** — aguarda validação da Maria.

## Lote R3 — Catálogo semântico de métricas

**Status: feito** (22/jul/2026) · quarto lote da revisão arquitetural
(docs/DIAGNOSTICO.md). Escopo pedido pela Maria — mais amplo que o preview
original da seção 6 do DIAGNOSTICO (só descrição/direção/agregação/ativo):
domínio, granularidade esperada, periodicidade e comparabilidade entraram
junto. **Modelo:** Sonnet 5.

- [x] `metricas` ganha `nome_executivo`, `dominio`, `descricao`,
      `granularidade_esperada`, `periodicidade`, `tipo` (CHECK:
      absoluta/percentual/indice/quantidade/valor_financeiro), `direcao_risco`
      (CHECK: maior_pior/menor_pior/ambos/informativo), `agregacao_padrao`
      (CHECK: soma/media/ultimo/maximo/minimo), `comparabilidade` (texto livre
      — lista aberta), `ativo`. Migration 0004, aditiva. `nome` continua a
      chave estável e `unidade` a unidade padrão — nenhuma das duas foi
      renomeada.
- [x] `backend/seed_metricas.py` (novo): preenche os campos semânticos das 12
      métricas atuais — idempotente (sentinela `dominio IS NULL`, nunca
      sobrescreve edição manual), mesmo padrão de `seed_depara`/`seed_catalogo`.
- [x] Fim da criação implícita: `get_or_create_metrica` virou
      `resolver_metrica_governada` (só SELECT) — nome de métrica fora do
      catálogo dá `ValueError` claro em vez de criar métrica fantasma.
- [x] `admin.py`: os dois pontos de gravação (`upload/processar` e
      `reprocessar`) ganharam try/except pra esse erro, finalizando a execução
      como `erro` com a mensagem (mesmo padrão já usado pro erro de parser) —
      antes desse lote essa gravação não tinha proteção nenhuma. Endpoint novo
      `GET /metricas` (read-only).
- [x] `admin.html`: painel "Métricas" read-only (mesmo padrão do catálogo de
      fontes).
- [x] Testes: seed idempotente e não-destrutivo de edição manual; métrica não
      governada não vira linha fantasma (nem via `ingestao` direto, nem via
      upload pela API — execução fica com status `erro`); os 5 uploads reais
      seguem batendo; teste de medida derivada ajustado (métrica de teste
      passa a ser inserida direto via SQL, não mais via app). **44 testes**
      verdes (39 do R2 + 5 novos).

**Check de conclusão:** modelo referenciando métrica inexistente é rejeitado
com mensagem clara (upload e reprocesso); catálogo de métricas visível no
admin com os campos semânticos; as 12 métricas atuais (3 do piloto original +
9 da POC catering, Lote 8) classificadas; nenhum valor calculado mudou. **Não
deployado na VM** — aguarda validação da Maria.

## Lote 9 — Métrica composta: ocupação real

**Status: a fazer** · derivação em cima de `medidas`; motor e tela inalterados.
**Modelo:** Fable 5 pra fechar a regra (tem julgamento); Sonnet 5 pra construir.
Depende do Lote 8 (as parcelas existirem).

Achado central da análise: nenhuma fonte sozinha diz quão cheia a filial está — RMSP
tem 12% de ocupação física com ~96% da capacidade sob contrato; POAII tem 93% do
estoque em posições virtuais.

- [ ] Fechar com a Maria a regra de composição: ocupação real = (física + comercial
      vigente + manual) ÷ capacidade, com regra anti-dupla contagem (ex.: Frimesa na
      RMSP aparece no contrato E na digitação manual)
- [ ] Insumos prontos da análise de 21/jul/2026: mostrar as duas % (sobre a capacidade
      total e sobre a disponível, descontando bloqueadas); "vencido-operando" (contrato
      vencido + cliente com movimento nos últimos 60 dias no fato, pela chave ERP) vira
      métrica derivada por código; posições virtuais somam na física (RMSPIII: 578);
      cobertura contratual (comercial ÷ capacidade) como métrica própria (RMSPIII: 124%)
- [ ] Implementar como métrica derivada pós-ingestão (mesmo gatilho dos scores),
      gravada em `medidas` como métrica normal — o motor avalia sem mudar nada

**Check de conclusão:** ocupação real por armazém×competência onde as parcelas existem;
o caso RMSP sai de ~12% pra um número que faz sentido; dupla contagem testada com o
caso Frimesa.

## Lote 9.5 — Grão cliente mínimo (catering)

**Status: a fazer** · decisão de 21/jul/2026 — revisão pontual do "cliente = v2".
**Modelo:** Sonnet 5. Depende dos Lotes 7.1 (lista de catering) e 8 (fontes com cliente).

- [ ] Tabela `medidas_cliente` (cliente × armazém × competência) — a segunda tabela-fato
      já prevista na revisão de escalabilidade, criada agora mas **só pros clientes da
      lista de catering** da família RMSP
- [ ] Métricas por cliente: posições contratadas (comercial), status do contrato
      (vigente / vencido-operando / sem contrato) e volumetria (t)
- [ ] Motor de scores idêntico rodando sobre `medidas_cliente`
- [ ] Na tela (junto do Lote 5): clicar na bolinha comercial abre a tabela de clientes
      embaixo — mesmo padrão validado no mapa-dados em 21/jul/2026

**Check de conclusão:** as 3 perguntas do PILOTO.md respondidas na tela, incluindo a
nº 3 (uso × contratado por cliente); Sapore, Sodexo e Convida visíveis com o status
correto (vigente / vencido-operando / sem contrato).

## Lote 10 — Conector `dw_api` (pós-MVP)

**Status: a fazer (pós-MVP — não entra na POC)** · **Modelo:** Sonnet 5.

Decisão de 17/jul/2026: a POC/MVP termina **sem** integração via banco. Depois dela,
os uploads do Lote 8 passam a ser buscados direto no banco do DW por API própria
(read-only), no mesmo formato canônico — os modelos e regras de limpeza do Lote 8 são
o contrato pronto da integração. Ganhos: cadência diária sem humano no loop e backfill
do histórico de ocupação (as fotos diárias que hoje se perdem entre uploads). Substitui
o antigo `pentaho_sql` da lista de fora-de-escopo.

---

## Fora de escopo (confirmado — degraus seguintes)

Previsão/sazonalidade · padrão por cliente na rede toda (a POC tem só o recorte mínimo
do Lote 9.5 — clientes de catering da família RMSP) · perdas (métrica do piloto
original — volta pós-POC; o motor aceita métrica nova sem mudança) · alertas / e-mail
· IA narradora · integração via banco do DW (virou o Lote 10 `dw_api`, pós-MVP)
· drill-down ao vivo (`detalhar()` só quando existir fonte de grão fino).
