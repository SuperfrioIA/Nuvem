# Roteiro da demonstração — POC SharePoint DataHub

Lote P5. Objetivo: provar de ponta a ponta que a aplicação lê o DataHub, atualiza
sob demanda e calcula KPIs auditáveis com resumo textual — sem IA em nenhuma etapa
de cálculo. Duração alvo: **~5 minutos**.

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

### Plano B — SharePoint não responde na hora

Causas mais prováveis: rede da sala sem saída HTTPS pra Microsoft, token expirado
por ambiente trocado, ou instabilidade do Graph. Se a sincronização ao vivo falhar:

1. Não insistir tentando de novo na frente da plateia — a tela já mostra o
   resumo da **última sincronização boa** (o cache preserva o resultado anterior
   em caso de erro, ver `docs/POC_ATUAL.md` § P2). Seguir a demo com esses dados.
2. Pular direto pra aba "KPIs da POC" — ela não depende de sincronizar de novo,
   usa o arquivo mais recente já no inventário.
3. Se nem isso: ter um print/gravação curta da sincronização funcionando como
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

### 4. Aba KPIs da POC (1min30)

- Abrir a aba **KPIs da POC**.
- Mostrar os cards: quantidade de registros, clientes, volume, peso bruto, valor
  total — e apontar que cada card tem a **regra e a fonte** embaixo (não é número
  solto, dá pra auditar).
- Passar o mouse/apontar a auditoria: "essa soma vem da coluna Vlr. Total, tantos
  registros válidos, desse arquivo específico".

### 5. Resumo textual (30s)

- Ler em voz alta o parágrafo do resumo.
- Frisar a última frase do próprio texto: "gerado por template determinístico, sem
  IA, a partir dos KPIs calculados em código" — a interpretação de negócio (qual
  coluna soma o quê) é regra fixa, não é a IA decidindo o que reportar.

### 6. Fechamento (30s)

- Gráfico de valor por cliente (top 10) e tabela por cliente — mostrar que dá pra
  descer no detalhe sem sair da tela.
- Encerrar com o que vem depois, **sem prometer data**: essa é a POC de um canal
  (o DataHub); o roadmap tem a nuvem de bolinhas por família (P5.5) e a integração
  durável na camada fina, mas nenhum dos dois está construído ainda.

---

## Perguntas prováveis (e resposta curta)

- **"Isso já está em produção?"** — Não. É POC rodando local (fase 1); subir pra
  VM é decisão separada, pós-demo.
- **"A IA participa de algum cálculo?"** — Não. IA está cortada desta POC por
  decisão de 29/jul/2026; todo número sai de código determinístico.
- **"Funciona pras outras famílias do DataHub (SAÍDA, ESTOQUE...)?"** — Não ainda.
  Essa POC lê só `ENTRADA_MERCADORIAS` como prova de conceito; ler as outras 7
  famílias é trabalho futuro, não escopo desta demo.
- **"E se o SharePoint estiver fora do ar na hora?"** — Ver Plano B acima.
