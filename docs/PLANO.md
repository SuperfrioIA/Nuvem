# Plano de construção — Nuvem IA

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
      dedicado criado: `https://superfrioarmazens.sharepoint.com/sites/nuvem-ia`. Falta
      só a concessão de escrita (`write`, não só leitura — o app vai gravar backup do
      `upload_manual` lá além de ler a planilha de ocupação) nesse site: pedido feito a
      quem tem `Sites.FullControl.All`/SharePoint Admin, aguardando aprovação.
      *21/jul/2026: fora do caminho crítico da apresentação da POC — a demo roda com
      os dados locais na máquina da Maria; SharePoint entra depois.*
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

**Status: a fazer** · modelos de importação + evoluções pontuais do parser.
**Modelo:** Sonnet 5. Depende do Lote 7 (de-para).

Cada família de relatório mapeada na análise vira um modelo de importação salvo, com
as regras de limpeza aprendidas. Evoluções de parser necessárias (pequenas): aceitar
csv (hoje só xlsx) e filtro simples de linha por valor de coluna.

Recorte da POC (21/jul/2026): filiais alvo = família RMSP; ordem de entrada: fato
(backfill 2021→hoje de RMSP/RMSPII), pos_sum, capacidade, comercial, manual. As regras
de limpeza de cada fonte estão documentadas em `docs/Analise/saida/analise_rmsp.xlsx`
(abas Leia-me, Conferência de fontes e Dicionário).

- [ ] **Volumetria (export bruto do fato, csv)** — a fonte mais valiosa: histórico
      2021→hoje, dia×filial×cliente. Modelo: soma peso bruto por armazém×competência
      (avaliar métricas separadas de recebimento/expedição via filtro de operação).
      Limpeza aprendida: fora instância `DW_STG_PRD`, empresa vazia e pesos negativos
- [ ] **Ocupação física (pos_sum)** — foto do dia, filial×câmara. Modelo: razão
      posições ocupadas ÷ capacidade total (razão de somas já suportada); sentinelas
      via `ignorar_valores`. Foto → competência: 1 foto por mês (decidir a regra:
      último dia?). Posições virtuais (linha sem câmara/capacidade mas com ocupação):
      decidir se viram métrica própria ("posições virtuais") — é sinal de operação,
      não sujeira
- [ ] **Capacidade cadastrada (header por filial)** — posições totais/bloqueadas por
      filial; denominador da ocupação real. Muda raramente; sobe quando mudar
- [ ] **Ocupação comercial (contratos)** — posições locadas vigentes por filial (o
      WMS vê o espaço vazio, mas está vendido). No MVP o recorte de vigência é manual
      (filtrar antes de subir); filtro por data no parser só se doer na prática
- [ ] **Ocupação manual (export do STG)** — parcela das filiais fora do WMS (ICE,
      GYN, UDI, POA...) e casos tipo cross fracionado. Foto diária: mesma regra de
      competência do pos_sum
- [ ] **O que não sobe** (confirmado): pivô do Power BI (`data (2)` — subtotal duplica
      e é só um recorte do próprio fato) e conciliação SKU×lote (fora do grão, sem
      chave de filial/cliente/data)

**Check de conclusão:** cada família com modelo salvo e reprocessável (delete+insert
idempotente); volumetria real 2021→hoje carregada — **fecha a validação do motor com
dado real que ficou pendente no Lote 3**; ao menos 1 competência real de ocupação
física gravada nas filiais do piloto.

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
