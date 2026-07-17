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
- [ ] Congelar o contrato da planilha de ocupação (aba + colunas fixas + quem preenche)
- [ ] Escolher as 1–2 filiais do piloto (insumo novo: painel comparativo de 6 candidatas
      — RPI, RMSP, RMSPII, RMSPIII, CWBII, BSB — em `docs/analise/saida/painel_piloto.xlsx`,
      17/jul/2026; atenção: RMSPIII não tem volumetria no DW)
- [ ] Definir o dono de cada dado (perdas / volumetria / ocupação)
- [ ] Confirmar se ocupação tem histórico retroativo (se não, começa a acumular agora)
      — análise 17/jul: os relatórios de ocupação são foto do dia; o histórico diário
      existe no DW mas só é recuperável via banco/API (Lote 10, pós-MVP). Sem isso,
      vale a regra: acumular a partir de agora, 1 foto por competência
- [ ] Combinar com a TI o destino do `pg_dump` fora da VM (candidato natural: o site
      SharePoint `nuvem-ia`, já criado — falta confirmar)

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
aparece no log com o arquivo original referenciado. **Ainda falta validar na VM real**
(SuperFrio) — o teste até aqui foi só local.

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
Depende do Lote 0 pra testar de verdade.

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

**Check de conclusão:** validado local (mesma ressalva do Lote 1 — falta a VM real) com
dataset sintético controlado (perdas+volumetria, 12 meses armazém RPI + 3 meses CGH)
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

## Lote 7 — De-para oficial (a camada fina ganha o dado real)

**Status: a fazer** · só dado + admin, sem módulo novo. **Modelo:** Haiku 4.5 (carga
mecânica; conferência = Sonnet 5).

Insumo: `docs/analise/saida/depara_e_relacoes.xlsx` — de-para consolidado e validado
contra capacidade, ocupação e volumetria (fecha 100% das 31 filiais SF).

- [ ] Carregar o de-para real em `armazens`/`depara_armazem`: cada filial SF com todos
      os apelidos que aparecem nas fontes — sigla (RPI), código WMS/JDA (com as
      traduções ARAP→ARP, LDN→LDNI, SFS1→RPII), código ERP Protheus (`001003`) e CNPJ —
      todos resolvendo pro mesmo armazém
- [ ] ICE (Chile) fica fora por ora: não existe de-para ERP×WMS pra elas (nem sigla no
      cadastro de capacidade); entra quando houver fonte com apelido resolvível
- [ ] Dicionário de códigos (temperatura 2=CL/3=CG/4=RF/5=SC; estrutura 2=blocado,
      3=drive-in, 4=porta-palete; acordo P=posições/L=locação) fica como documentação
      dos modelos de importação — não vira tabela nova (sem DW)

**Check de conclusão:** upload de qualquer relatório das famílias mapeadas resolve
filial sem pendência manual pras 31 SF; apelido desconhecido segue virando pendência
(nunca descarte silencioso).

## Lote 8 — Relatórios reais como fonte (upload, sem integração de banco)

**Status: a fazer** · modelos de importação + evoluções pontuais do parser.
**Modelo:** Sonnet 5. Depende do Lote 7 (de-para).

Cada família de relatório mapeada na análise vira um modelo de importação salvo, com
as regras de limpeza aprendidas. Evoluções de parser necessárias (pequenas): aceitar
csv (hoje só xlsx) e filtro simples de linha por valor de coluna.

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
- [ ] Implementar como métrica derivada pós-ingestão (mesmo gatilho dos scores),
      gravada em `medidas` como métrica normal — o motor avalia sem mudar nada

**Check de conclusão:** ocupação real por armazém×competência onde as parcelas existem;
o caso RMSP sai de ~12% pra um número que faz sentido; dupla contagem testada com o
caso Frimesa.

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

Previsão/sazonalidade · padrão por cliente (v2 = tabela-fato `medidas_cliente`) · alertas
/ e-mail · IA narradora · integração via banco do DW (virou o Lote 10 `dw_api`, pós-MVP)
· drill-down ao vivo (`detalhar()` só quando existir fonte de grão fino).
