# Roteiro da demonstração — POC SharePoint DataHub

Lotes P5 e P5.5. Objetivo: provar de ponta a ponta que a aplicação lê o DataHub,
atualiza sob demanda e calcula KPIs auditáveis com resumo textual — sem IA em
nenhuma etapa de cálculo. Duração alvo: **~6 minutos** (o passo 6, a Nuvem do
DataHub, é o primeiro a cortar se o tempo apertar).

Escopo e status dos lotes: `docs/POC_ATUAL.md`. Este documento não repete regra de
negócio nem decisão técnica — só o roteiro de apresentação.

---

## Checklist de preparação (antes de abrir a tela pra plateia)

- [ ] `.env` local com os 5 `GRAPH_*` preenchidos (`GRAPH_TENANT_ID`,
      `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SITE_PATH`, `GRAPH_PASTA`).
- [ ] Container rebuildado, não só reiniciado — `frontend/` e `backend/` são `COPY`
      no Dockerfile, `git pull`/edição no disco não basta:
      ```
      docker compose up -d --build
      ```
- [ ] WSL não vai dormir no meio da demo: distro com algum processo ativo
      (`sleep infinity` numa aba, ou `.wslconfig` com `vmIdleTimeout` maior). Se a
      distro cair, o Docker cai junto e os containers reiniciam sozinhos — já
      aconteceu e parece bug do app.
- [ ] Sincronizar **antes** de começar (Sincronizar agora → conferir contagem) —
      não depender da sincronização ao vivo pra validar que a conexão funciona.
- [ ] Ter um arquivo de teste pronto pra subir no SharePoint ao vivo (pasta
      configurada em `GRAPH_PASTA`, qualquer nome/extensão — só pra aparecer na
      recontagem; não precisa ser um `ENTRADA_MERCADORIAS` válido).
- [ ] Login do admin em mãos (senha do `.env`, variável `ADMIN_PASSWORD`).
- [ ] Aba do navegador já aberta em `http://localhost:8002/admin`, sessão logada,
      no painel **DataHub** (evita logar na frente de todo mundo).
- [ ] Conferir que existe pelo menos um arquivo `ENTRADA_MERCADORIAS_*.xlsx` já
      sincronizado — sem ele a aba "KPIs da POC" só mostra o erro de "sincronize
      primeiro".
- [ ] Segunda aba do navegador em `http://localhost:8002/nuvem` (Nuvem do DataHub,
      Lote P5.5), já logada — é a mesma sessão do admin, mas página separada. Sem
      sincronização feita ela devolve "nenhuma sincronização do DataHub ainda".

### Plano B — SharePoint não responde na hora

Causas mais prováveis: rede da sala sem saída HTTPS pra Microsoft, token expirado
por ambiente trocado, ou instabilidade do Graph. Se a sincronização ao vivo falhar:

1. Não insistir tentando de novo na frente da plateia — a tela já mostra o
   resumo da **última sincronização boa** (o cache preserva o resultado anterior
   em caso de erro, ver `docs/POC_ATUAL.md` § P2). Seguir a demo com esses dados.
2. Pular direto pra aba "KPIs da POC" — ela não depende de sincronizar de novo,
   usa o arquivo mais recente já no inventário. **Atenção:** ela ainda *baixa* esse
   arquivo do Graph pra recalcular; se o SharePoint estiver fora, ela também falha.
3. O **grafo da nuvem** (`/nuvem`) é a parte mais resistente: desenha só com o
   inventário em cache, sem nenhuma chamada nova ao Graph. Clicar na bolinha e ver
   a lista de arquivos também funciona offline. O que não funciona sem SharePoint é
   descer nos KPIs/prévia da `ENTRADA_MERCADORIAS`, que baixa o arquivo.
4. Se nem isso: ter um print/gravação curta da sincronização funcionando como
   material de apoio, e explicar verbalmente o fluxo.

---

## Roteiro (passo a passo)

### 1. Contexto (30s, sem tocar na tela)

Explicar em 1-2 frases: hoje o WMS exporta planilhas pro SharePoint DataHub e
alguém teria que abrir manualmente pra tirar qualquer número. A POC prova que dá
pra ler isso automaticamente, com auditoria, sem IA inventando número.

### 2. Painel DataHub (1 min)

- Mostrar o painel já com pasta configurada e a última sincronização.
- Explicar: "conexão só de leitura com o SharePoint — o app não escreve nada lá".

### 3. Sincronização ao vivo (1min30)

- Abrir o SharePoint (outra aba) e subir o arquivo de teste na pasta configurada.
- Voltar pro admin, clicar **Sincronizar agora**.
- Apontar a contagem de arquivos subindo (ou o arquivo novo na lista de recentes)
  — isso prova que não é dado estático, é lido do SharePoint na hora.

### 4. Aba KPIs da POC (1 min)

- Abrir a aba **KPIs da POC**.
- Ler a linha de contexto no topo: `Filial X | Competência mês/ano | Fonte:
  SharePoint DataHub` — de que arquivo, de que mês, de onde.
- Mostrar os **4 cards**, nesta ordem: valor total movimentado, volume total, peso
  bruto (em mil toneladas) e quantidade de clientes.
- A auditoria de cada card está no **tooltip** (passar o mouse por cima): regra,
  registros válidos e arquivo de origem. Não fica escrita embaixo do card — a tela
  foi desenhada pra plateia executiva, o detalhe técnico aparece sob demanda.
- Se perguntarem de onde saiu o número, o bloco **"Qualidade e origem dos dados"**
  logo abaixo tem arquivo, linhas processadas, % válido e a hora da sincronização.

### 5. Resumo textual (30s)

- Ler em voz alta os 2 parágrafos do resumo executivo.
- Frisar que **nenhuma palavra ali foi escrita por IA**: é template determinístico
  preenchido com os KPIs calculados em código. A interpretação de negócio (qual
  coluna soma o quê) é regra fixa.
- O aviso "gerado por template, sem IA" **não está** no texto executivo — ele vive
  na área técnica da tela (decisão de 30/jul/2026, pra não poluir o texto de
  apresentação). Ou seja: isso é fala tua, não é ler a tela.

### 6. Nuvem do DataHub (1 min)

- Trocar pra aba `/nuvem` — mesma sessão, página separada do admin.
- Mostrar o grafo: **cada bolinha é uma família** do DataHub, agrupada nos 4
  domínios (ENTRADA, SAÍDA, ENTREGAS, ESTOQUE). Tamanho = quantidade de arquivos.
- Explicar o que as bolinhas **não** são: não é semáforo de risco, nenhuma acende.
  É o mapa do que existe hoje no DataHub — 8 famílias mapeadas, 1 já integrada.
- As linhas **tracejadas** são junções reais de dado, conferidas cruzando os
  arquivos: `SAIDA_MERCADORIAS` liga em `GUIAS_SAIDA` por `GSM` (100% das chaves).
  Frisar: junção que não foi conferida no dado **não** foi desenhada.
- Clicar numa bolinha → lista dos arquivos reais daquela família, com link pro
  SharePoint. Na `ENTRADA_MERCADORIAS` (a integrada) descem também os KPIs e uma
  prévia de 100 linhas validadas.

### 7. Fechamento (30s)

- Gráfico de valor por cliente (top 10) e tabela por cliente — mostrar que dá pra
  descer no detalhe sem sair da tela.
- Encerrar com o que vem depois, **sem prometer data**: essa é a POC de um canal
  (o DataHub), com 1 das 8 famílias lida de verdade. O que existe desenhado e não
  construído: integração durável das outras famílias na camada fina, bolinha que
  acende por regra de negócio, e a camada de IA que narra em vez de template.

---

## Perguntas prováveis (e resposta curta)

- **"Isso já está em produção?"** — Não como produto. A aplicação roda na VM
  (`172.31.49.141:8002`) com a conexão do DataHub funcionando, mas a demo é local
  (fase 1) e o código das telas do P5/P5.5 ainda não subiu pra VM. Não há usuário
  final usando: é POC.
- **"A IA participa de algum cálculo?"** — Não. IA está cortada desta POC por
  decisão de 29/jul/2026; todo número sai de código determinístico.
- **"Funciona pras outras famílias do DataHub (SAÍDA, ESTOQUE...)?"** — Não ainda.
  Essa POC lê só `ENTRADA_MERCADORIAS` como prova de conceito; ler as outras 7
  famílias é trabalho futuro, não escopo desta demo. As bolinhas da nuvem mostram
  que as 8 estão **mapeadas** (sabemos o que tem lá) — mapeada não é lida.
- **"Por que as bolinhas não acendem / não mostram alerta?"** — Decisão consciente:
  primeiro provar que temos os dados, depois dizer que algo está anormal. Além
  disso o DataHub tem só 7 competências publicadas (jan–jul/2026) e o motor de
  score exige 6 anteriores à analisada — o desvio-padrão sairia instável e o alerta
  disparia quase por sorteio. Preferimos não fingir detector de anomalia.
- **"Como vocês sabem que essas famílias se conectam?"** — As junções tracejadas
  foram conferidas cruzando os arquivos reais, não inferidas por nome de coluna
  parecido. `SAIDA_MERCADORIAS`↔`GUIAS_SAIDA` bateu 847 de 847 chaves. O que não
  bateu 100% está registrado com o percentual, e o que não foi conferido não está
  desenhado.
- **"Dá pra ver o ano todo / comparar meses?"** — Não nesta POC: ela lê um arquivo
  por vez e não persiste o resultado. A série histórica está desenhada (Lote 11 do
  `docs/PLANO.md`) e é viável, porque a tabela de medidas já é temporal.
- **"E se o SharePoint estiver fora do ar na hora?"** — Ver Plano B acima.
