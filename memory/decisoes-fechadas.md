---
name: decisoes-fechadas
description: Decisões de arquitetura fechadas em 15/jul/2026 — não rediscutir sem a Maria pedir
metadata:
  type: project
---

- App separado do Portal (Receita 3 do CONTRIBUTING do Hub); o Hub só cadastra um card.
- Mesma VM do Conciliador (porta 80) e Hub (8001); nuvem-ia na **8002**, compose próprio
  com 2 containers: `nuvem-app` (FastAPI + APScheduler + frontend vanilla) e `nuvem-db`
  (Postgres, volume nomeado).
- **Conectores plugáveis** (interface `testar()`/`buscar()` → formato canônico
  `{metrica, armazem_na_fonte, competencia, valor}`): `upload_manual` e `sharepoint_excel`
  na v1, alternáveis por toggle no admin; `pentaho_sql` no futuro sem mudar motor/tela.
- Graph API depende de app registration no Entra ID (`Sites.Selected`) — caminho crítico
  externo com a TI; o código fica pronto, credenciais entram depois.
- Auth: senha única protegendo só o `/admin`; nuvem aberta na rede interna.
- Camada fina: 9 tabelas (conectores, armazens, depara_armazem, depara_pendencias,
  metricas, medidas, scores, execucoes, **modelos_importacao**). `medidas` com unique
  (metrica, armazem, competencia) → upsert idempotente. Scores são derivados/recalculáveis
  (cache), não fonte de verdade.
- Motor: Python puro, score = desvio vs próprio histórico 12–24m. Sem libs de ML.
- Da revisão de escalabilidade (15/jul/2026): rotina rebusca as últimas 3 competências;
  reprocesso = delete+insert por conector × competência; valor sem de-para vira
  pendência no admin (nunca descarte silencioso); backup = pg_dump diário pra fora da
  VM + retenção dos xlsx do upload (de-para não é rederivável); `nuvem-app` com worker
  único (APScheduler duplicaria); dimensão cliente = v2 com segunda tabela-fato
  (`medidas_cliente`), não coluna em `medidas`.
- Da análise de arquivos reais do lote 1 (15/jul/2026): relatórios reais não são
  tabela limpa armazém×mês — vêm em grão mais fino (posição×dia, SKU×lote), com várias
  colunas candidatas pra mesma dimensão (ex: filial como SK/ERP/WMS/QLS) e cliente
  misturado. Por isso `upload_manual` ganhou **modelos de importação**: mapeamento de
  colunas nomeado e reutilizável (tabela `modelos_importacao`), salvo por relatório.
  Armazém e competência podem vir de uma coluna do arquivo OU ser valor fixo digitado
  no upload (relatório já recortado pra 1 filial/1 mês, sem essas colunas). Métrica é
  soma direta de uma coluna OU razão entre duas (numerador/denominador — necessário pra
  métricas de nível/capacidade tipo ocupação; a razão das somas já resolve certo mesmo
  com várias linhas por dia dentro do mês). Coluna de cliente é reconhecida no modelo
  (documentação, mira a v2) mas não persiste — o processamento agrega (soma/razão) por
  armazém+competência+métrica, absorvendo cliente/SKU/posição/etc.; coluna não mapeada
  simplesmente não entra no banco. Export tipo matriz/pivô do Power BI (hierárquico,
  com subtotal) não é suportado no parser — fonte deve exportar em tabela plana.
- Retenção do arquivo original do `upload_manual` **começa no Lote 1** (antecipada do
  Lote 4): é o caminho de drill-down manual pra essa fonte (abrir o `.xlsx` de novo),
  já que a camada fina só guarda o consolidado. Começa local (pasta na VM, plugável) e
  migra pra SharePoint (Graph API, mesma credencial do `sharepoint_excel`) quando o
  Entra ID for liberado — **o pedido à TI (Lote 0) precisa incluir permissão de escrita
  (write) na concessão de acesso ao site**, não só leitura (a leitura já era necessária
  pra buscar a planilha de ocupação).
- Motor de scores (Lote 3, fechado 16/jul/2026): média e desvio-padrão amostral (não
  mediana/MAD) da janela de até 24 competências anteriores à analisada (exclui o mês
  corrente); histórico mínimo de 6 competências pra ser avaliável — abaixo disso, estado
  `historico_curto` (tem valor, mas ainda sem score). Limiar `|z| >= 2` vira
  `fora_padrao`; desvio-padrão zero com valor igual à média é `normal`, diferente é
  `fora_padrao` direto (z indefinido). `scores` é sempre recalculado por completo
  (delete+insert) a cada rodada, nunca seletivo — volume do piloto não justifica a
  complexidade. Disparo automático ao fim de todo `upload/processar`, mais endpoint
  manual de recálculo. Validado local com dado sintético (reproduziu o padrão do
  cenário conhecido — perda e volumetria fora do padrão juntas); ainda não validado com
  dado real (ver docs/PLANO.md, Lote 3).

- Da análise dos relatórios reais do DW (17/jul/2026, `docs/analise/saida/`): **nada de
  DW novo** — a camada fina segue só com de-para + agregados armazém×competência +
  scores; relatório bruto fica como arquivo retido do upload, nunca vira tabela. **A
  POC/MVP fecha só com upload manual** dos exports que já saem hoje; integração com o
  banco do DW via API (`dw_api`) é degrau pós-MVP (Lote 10). Chave mestra descoberta:
  `SK_FILIAL` do fato = `FK_FILIAL` das STG (mesma surrogate da DIM_FILIAL); de-para
  consolidado das 31 filiais SF pronto pra virar seed (Lote 7). O export bruto do fato
  de volumetria (2021→hoje) é quem valida o motor com dado real (Lote 8).

**Why:** decisões tomadas em conversa com a Maria em 15/jul/2026, 16/jul/2026 e 17/jul/2026 — evita rediscutir do zero.
**How to apply:** detalhes em docs/ARQUITETURA.md e docs/PLANO.md. Mudar essas decisões
só com OK explícito dela. Ver [[projeto-nuvem-ia]].
