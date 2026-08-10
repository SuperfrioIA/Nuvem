# V2 — Plano e status

**Este documento é a fonte única do status da V2** (lotes V2.1–V2.8). Criado em
06/ago/2026, na abertura da V2. Especificação e decisões fechadas:
`docs/proposta_v3_volumetria.md`; decisões em forma curta:
`memory/volumetria-v2-decisoes.md`.

A V1 está fechada e implantada — `docs/V1_PLANO.md`, seção "Conclusão da V1".
Aquele documento continua sendo a fonte do que a V1 entregou e das limitações
que ela declarou; **o status do que está sendo construído agora vive aqui**.

Histórico do raciocínio: `docs/proposta_v2_volumetria_cockpit_laboratorio.md`
(05/ago/2026) é a proposta inicial, superada pela V3 — consultar só para
entender de onde as decisões vieram, nunca como plano.

Regras de trabalho (as mesmas da V1): um lote por vez; ao final de cada lote
rodar a suíte completa, validar migrations (upgrade e downgrade), atualizar este
documento, commit isolado, verificação independente por agente separado e
**aguardar autorização da Maria** antes do lote seguinte.

---

## Objetivo da V2

Uma camada analítica visual de volumetria integrada, com número auditável até o
arquivo de origem:

```text
quanto entrou · quanto saiu · total movimentado · saldo
como evoluiu no mês e no acumulado
quais unidades e quais clientes puxaram o resultado
como se distribui por tipo de estoque
o que está pendente ou fora de cobertura
```

Frase-guia: primeiro uma camada visual confiável de volumetria integrada; depois
o Laboratório explorando em cima dessa base já governada.

---

## Status por lote

| Lote | O quê | Status |
|---|---|---|
| **V2.1** | Cobertura e base — de-para, índices, pool, estado de família não integrada | **feito** (06/ago/2026, deployado na VM) |
| **V2.1.1** | `sem_dado`: competência sem movimento não é erro | **feito** (06/ago/2026) — achado na primeira rodada real |
| **V2.2** | Tipo de estoque como dimensão | **feito** (06/ago/2026) |
| **V2.3** | Saída (`SAIDA_MERCADORIAS`, banda *Separado Fisicamente*) | **feito e deployado** (06–07/ago/2026) — revisão independente (2 críticos + 7 médios corrigidos), suíte verde contra Postgres real, migrations validadas via `alembic` CLI. **Deploy na VM em 07/ago/2026, `verificar_v2.py` sem nenhuma falha.** Falta rodar `scripts/processar_saida.py` — a saída ainda não foi ingerida (ver abaixo) |
| **V2.4** | Consultas de volumetria sob `/cockpit/` | **feito e deployado** (07/ago/2026) — mesma suíte verde contra Postgres real; `verificar_v2.py` sem falhas na VM |
| **V2.5** | Cockpit visual | **feito e deployado** (07/ago/2026) — plano em [`V2_5_PLANO_EXECUCAO.md`](V2_5_PLANO_EXECUCAO.md); validado em navegador antes do deploy |
| **V2.6** | Conciliação com o Power BI | **entregue no que não depende da VM** (07/ago/2026) — [`CONCILIACAO_POWERBI_V2.md`](CONCILIACAO_POWERBI_V2.md) + `scripts/conciliacao.py`. **Segunda passada em 10/ago achou a causa do gap: guia de entrada cancelada** (seção 3.1 do documento) — P-0/P-1/P-2 fechadas, D-2/D-3 descartadas com número; seguem abertas P-3 a P-8, sendo P-8 uma decisão de produto da Maria. Células de saída dependem do `processar_saida.py` |
| **V2.7** | Escala e operação | **feito e deployado** (07/ago/2026) — plano em [`V2_7_PLANO_EXECUCAO.md`](V2_7_PLANO_EXECUCAO.md); backup/restore **com evidência segue pendente de execução na VM** |
| **V2.8** | Laboratório com gráficos | não autorizado |

---

## Diagnóstico de partida (06/ago/2026)

O levantamento da fonte que originou as decisões está na seção 4 da
`proposta_v3_volumetria.md`. Antes de abrir o V2.1, os pontos que o lote toca
foram conferidos no código e no dado real. O que mudou em relação ao que estava
escrito:

### Conferido no dado, hoje: o layout da RJ

A `proposta_v3_volumetria.md`, seção 6, afirmava que a `ENTRADA_MERCADORIAS` da
RJ que existe (`004-003`) tem as 20 colunas conhecidas, e que a variante sem
`Cliente` "fica para quando aparecer". **Está errado.** Conferido pelo Graph,
somente leitura, em 06/ago/2026, arquivo por arquivo:

| Origem | Colunas na linha 1 | Bate com as 20 esperadas |
|---|---:|---|
| `CWB3/001` | 20 | sim, rótulo a rótulo |
| `SANCA/025` | 20 | sim, rótulo a rótulo |
| `RJ/004-003` | **18** | **não** — faltam `Cliente` e `Cliente CNPJ` |

A RJ tem 8 arquivos (2601–2608), todos `004-003`, aba `SLIN`, cabeçalho na
linha 1, sem nenhuma coluna de cliente. `docs/FONTES_DATAHUB.md` estava certo
desde 02/ago; a proposta V3 é que assumiu o contrário.

**Consequência no V2.1:** `RJ/004-003 → RMRJ` **não entra** no de-para deste
lote. O leitor exige as 20 colunas; dar de-para pra RJ agora tiraria os 8
arquivos dela de "pendência limpa" e os colocaria em erro de leitura — trocaria
um problema por outro, exatamente o que o lote de identidade de 02/ago evitou. A
RJ entra quando existir o leitor da variante (V2.3).

**Consequência de produto, para decidir quando a RJ entrar:** sem coluna de
cliente, todas as linhas da RMRJ caem no balde "sem cliente identificado". Peso
e valor aparecem; decomposição por cliente, não. Isso é decisão da Maria no
V2.3, não detalhe de implementação.

### Conferido no código: expandir o de-para mexe no `/nuvem`

`entrada_mercadorias.item_mais_recente()` — o arquivo que alimenta o card
executivo do `/nuvem` — recorta os candidatos por
`filiais_datahub.unidades_conhecidas()`, que é **derivado do mapa de de-para**.
O docstring do próprio módulo (`entrada_mercadorias.py:171-176`) diz que esse
recorte só deve cair quando as unidades tiverem "de-para **e leitor**
homologados".

Acrescentar CWB3 e SANCA ao mapa derruba o recorte de graça: o arquivo mais
recente da família pode passar a ser de Curitiba, e o card executivo mostraria
número de Curitiba sob o rótulo da RMSPII. O V2.1 corrige isso fixando a unidade
representativa do `/nuvem` de forma explícita, sem derivar do de-para.

### Conferido no código: um dos três índices propostos é morto

A UNIQUE `medidas_celula_unica` é
`(metrica_id, armazem_id, competencia, cliente_id)`
(`alembic/versions/0006_persistencia_datahub.py:47-52`). O índice btree dela já
atende `(metrica_id, armazem_id, competencia)` — que é o segundo índice da lista
da proposta (seção 5, V2.1). Criá-lo custaria escrita e disco e enganaria quem
lesse depois.

O V2.1 cria os dois que de fato faltam:

| Índice | Por quê |
|---|---|
| `(metrica_id, competencia)` | consultas por período sem filtro de armazém; hoje `competencia` é a 3ª coluna da UNIQUE |
| `(metrica_id, cliente_id, competencia)` | `cliente_id` é a **4ª** coluna da UNIQUE — não serve a filtro de cliente |

O terceiro **não é criado**, e o motivo fica registrado na migration.

### Conferido no código: `processar_arquivo` isolado não está exposto

A seção 19.2 da proposta V2 pedia guarda de colisão em qualquer processamento de
arquivo individual. Hoje **só `processar_todos` está exposto por HTTP**
(`backend/routers/datahub.py:151`), e é ele que tem as duas guardas de colisão.
Nada a corrigir — mas o V2.3 empurra o processamento da saída para fora do
request (33 MB por filial/competência), que é justamente o desenho onde aparece
um gatilho por arquivo. **Regra do V2.3, escrita aqui para não se perder:**
processamento por arquivo só pode existir passando pela guarda de colisão.

### Herdado da proposta V2 e não carregado pela V3: estado de família não integrada

A seção 19.3 da proposta V2 pedia estado explícito para família nova, família
conhecida não integrada e layout não homologado. A V3 tira a
`ENTRADA_MERCADORIAS (UA)` do escopo, mas não carregou a ideia de **exibir** o
estado. Com 810 arquivos na fonte e uma família integrada, o painel hoje não
distingue "fora de escopo por decisão" de "erro". Entra no V2.1, junto do
de-para: os dois falam de cobertura.

### Achado fora de escopo, registrado: pasta `.claude` na raiz do DataHub

A listagem de 06/ago/2026 mostrou uma pasta `.claude` na raiz da pasta
configurada do DataHub, contendo `scheduled_tasks.lock` e `settings.local.json`
— arquivos de ferramenta, não do DataHub. Alguém rodou o Claude Code com o
diretório de trabalho dentro da pasta sincronizada do SharePoint.

O cliente Graph do projeto é somente leitura por construção (`Sites.Selected` +
concessão `read`, mais a guarda de somente-leitura em
`tests/test_graph_datahub.py`), mas **um processo com cwd na pasta sincronizada
escreve no DataHub pelo sistema de arquivos, contornando essa garantia**. Nada
foi tocado; a limpeza é decisão da Maria, pelo SharePoint.

---

## Lote V2.1 — Cobertura e base (feito, 06/ago/2026)

Autorizado pela Maria em 06/ago/2026, com plano apresentado em texto e duas
respostas dela: conferir o layout da RJ antes de decidir o de-para (feito, ver
acima) e **pool de conexão dentro deste lote**, como último item.

> Dobrar o dado disponível e indexar, sem tocar em leitor de planilha nem em
> tela de dashboard.

Escopo:

1. **De-para das unidades novas** — `CWB3/001 → CWBIII` e `SANCA/025 → RMSPV`
   (as duas siglas já existem e estão ativas em `backend/seed_depara.py`). Entra
   em `filiais_datahub.SIGLA_POR_CODIGO`, que é a fonte única dos dois caminhos
   (exibição e ingestão), e **como migration**, não só seed: o seed é
   `ON CONFLICT DO NOTHING`, então em banco novo funciona, mas na VM as linhas
   antigas de `depara_pendencias` ficariam penduradas no painel. A migration
   insere o de-para e apaga a pendência correspondente — é a lição de 03/ago
   (correção de cadastro entra como migration, não como SQL manual no runbook).
   `RJ/004-003` fica fora (ver diagnóstico). `RMSPII/002`, `RJ/004-001` e
   `RJ/005-001` seguem fora, por decisão da Maria de 02/ago.
2. **`/nuvem` deixa de derivar a unidade representativa do de-para** — unidade
   fixada explicitamente, com o motivo escrito, e teste provando que de-para
   novo não muda o arquivo do card executivo.
3. **Dois índices em `medidas`** (ver diagnóstico), com downgrade e o motivo do
   terceiro não existir registrado na migration.
4. **Estado explícito de cobertura** — família conhecida não integrada, família
   nova detectada e layout não homologado visíveis no painel, em vez de silêncio
   ou de "erro".
5. **Pool de conexão** em `backend/database.py`, preservando o `connect_timeout`
   e o `statement_timeout` atuais e devolvendo a conexão no `finally`. Último
   item do lote: é o único que toca todos os requests da aplicação.
6. **Sincronizar e processar**, incluindo a competência 2608 (a V1 processou até
   2607). Arquivos hoje em `pendencia_depara` reprocessam sozinhos —
   `_ja_processado` só reconhece status `ok`, então não precisa de `forcar`.
7. **`scripts/verificar_v2.py`** somente leitura, no molde do `verificar_v1.py`:
   alembic em head, UNIQUE de `item_id`, de-para sem código nu, contagem por
   unidade, pendências visíveis, nenhum processamento com unidade NULL fora da
   raiz.

**Aceite:** CWB3 e SANCA saem de pendência e aparecem no ranking de unidades; a
contagem de `processamentos_datahub` com status `ok` sobe de 21 para o total dos
arquivos de entrada de 2026 das três unidades com de-para; a RJ continua como
pendência **limpa** (nunca erro); as consultas do Cockpit passam a usar índice; o
card do `/nuvem` continua exibindo o mesmo arquivo de antes do lote; o script
readonly roda na VM sem gravar nada.

**Fora do lote (declarado):** tipo de estoque (V2.2), leitor e ingestão da saída
(V2.3), consultas de volumetria (V2.4), tela (V2.5), conciliação (V2.6), leitor
da variante de 18 colunas da RJ (V2.3).

### Verificação independente (agente separado, antes do commit): REPROVADO na primeira passada

17 achados, 5 altos. Os quatro primeiros são a mesma falha de fundo — **mudei o
backend e não varri os consumidores até o fim** —, e dois deles são o defeito que
este projeto mais persegue (número parcial lido como completo). Todos corrigidos
antes de fechar o lote:

| # | Sev. | O que estava errado | Correção |
|---|---|---|---|
| 1 | alto | A mensagem de cobertura da RJ dizia "origem sem de-para", que se lê como cadastro esquecido. O painel tem `POST /api/admin/depara`, que cria o de-para e apaga a pendência: um admin lendo aquilo transformaria as 8 pendências limpas da RJ em 8 erros de leitura — exatamente o que o lote reteve o de-para pra evitar | `UNIDADES_SEM_LEITOR_HOMOLOGADO` em `nuvem_datahub`; a mensagem nomeia o layout de 18 colunas e diz "não cadastrar até existir o leitor da variante" |
| 2 | alto | Arquivo de CWB3/SANCA dentro da bolinha "Integrada" com Cobertura vazia, sob uma nota que dizia "usados nos indicadores desta tela" — mas os indicadores são só da RMSPII. Lia-se como se os KPIs incluíssem Curitiba | `_cobertura_do_arquivo` declara "ingerido na série histórica, mas fora dos indicadores desta tela"; a nota da bolinha nomeia a unidade |
| 3 | alto | A renomeação do vocabulário de estado vazou identificador cru: o chip do `/laboratorio` renderizava `estado` direto, então passaria a exibir `nao_integrada`, `so_pdf` | `listar_familias` repassa `estado_tag`/`estado_nota`; o chip usa o rótulo |
| 4 | alto | A bolinha nova `ENTRADA_MERCADORIAS (UA)` caía no ramo de órfã, empilhada na **mesma posição fixa** do `PALLETS_EXCEDENTES` (círculos e rótulos sobrepostos, só o último clicável) e o ramo de órfã **descartava** o rótulo novo — a única família para a qual o vocabulário foi criado nunca o mostrava | `(UA)` entrou no domínio VOLUMETRIA (ela é entrada de mercadoria, grão UA); órfãs passaram a ser espaçadas; "sem domínio" e cobertura passaram a coexistir em vez de uma sobrescrever a outra |
| 5 | alto | `perfil_dados.py` comparava com o valor antigo `"só_pdf"`: comparação morta, e uma **limitação declarada foi desligada em silêncio** | Constantes `ESTADO_*` em `nuvem_datahub` (a próxima renomeação quebra no import, não em silêncio) |
| 6 | médio | O pool entregava conexão morta: depois de um restart do Postgres ou de um reaper de TCP ocioso, o primeiro request falhava com o banco de pé — buraco de continuidade novo, num módulo que existe pra fechá-los | Sonda de vivacidade na retirada, com uma retentativa |
| 7 | médio | `minconn=1` não entregava o ganho declarado: o `_putconn` do psycopg2 só guarda enquanto `len(pool) < minconn` e **fecha o resto** — das 6 conexões de um load do Cockpit, cinco eram jogadas fora | `minconn=10` |
| 8 | médio | `maxconn=20` abaixo do limitador de threads do anyio (40): `getconn` não espera por vaga, levanta `PoolError` → HTTP 500 para quem chegou depois, enquanto antes só ficava mais lento. E o `/health` respondia "banco indisponivel" — mandando quem está de plantão investigar um Postgres saudável | `maxconn=40`; `PoolEsgotadoError` próprio e `/health` distinguindo "sem conexão livre no pool" de "banco indisponível" |
| 9 | médio | `desenharTabelaArquivos` **continuava** decidindo "Integrada" pelo nome da família e dizendo "Não mapeada" onde o nó já dizia "Não integrada": três rótulos para o mesmo estado na mesma tela | Rótulo do backend nas duas funções; legenda corrigida |
| 10 | médio | Ao virar família própria, a `(UA)` perdeu o aviso que dizia que **os rótulos coincidem com os da família integrada e o grão é UA, não item** — a informação que de fato protege | `_RISCO_DE_ROTULO_COINCIDENTE`, com o aviso explícito de que tratar esses números como os da integrada dobraria quantidade |
| 11–17 | baixo | `unidades_com_depara()` virou código morto; teste pré-existente com nome e docstring falsos (a CWB3 tem de-para agora) e duplicando o novo; `DELETE` da migration com subquery escalar em `conectores.tipo`, que não é UNIQUE; docstrings falsos em `seed_datahub` e `nuvem_datahub`; `verificar_v2.py` não capturava `http.client.HTTPException` (resposta malformada daria traceback); cobertura culpando o de-para quando a causa é o nome fora do padrão | todos corrigidos; `unidades_com_depara()` mantida com consumidor claro no docstring |

O verificador confirmou como **corretos**: a migration nos dois sentidos e em banco
existente, os dois índices se justificando por filtro real de `cliente_id`, o
terceiro sendo de fato prefixo da UNIQUE, a `(UA)` não quebrando ingestão
(`_PADRAO_NOME` não casa com ela), a proteção do Bloco D intacta, nenhuma escrita
no SharePoint, `verificar_v2.py` só stdlib e falhando limpo, e nenhum teste
removido.

**Um estreitamento ficou registrado sem correção**: a combinação "homônimo +
um lado em pendência" deixou de ser exercitada, porque as duas unidades homônimas
reais (RMSPII/001 e CWB3/001) agora têm de-para. O mecanismo segue coberto por
outros três testes; construir o cenário exigiria inventar uma unidade que não
existe na fonte.

**Suíte**: **462 passed** (448 no fechamento da V1 + 14 novos; nenhum removido).
Sintaxe das quatro telas conferida com `node --check`.

---

## Lote V2.1.1 — `sem_dado`: competência sem movimento não é erro (feito, 06/ago/2026)

Achado na **primeira rodada real de processamento na VM**, depois do V2.1: dos 46
arquivos da família, 23 processados, 18 pulados e **5 erros** — todos
`ENTRADA_MERCADORIAS_025_2601..2605` da SANCA, com "arquivo sem linhas de dado
(so cabecalho)". A unidade começou a operar em 2606; aqueles arquivos são só
cabeçalho e sempre serão.

O erro era nosso, não da fonte, e tinha duas consequências:

1. **Cinco erros permanentes no painel**, para algo que nunca seria corrigido.
   Erro que não se resolve treina quem olha a ignorar a lista — e aí o erro de
   verdade passa batido.
2. **Re-download em toda rodada, para sempre**: `_ja_processado` exigia status
   `ok`, então nenhum dos cinco era pulado. É a mesma classe de problema que o
   lote de identidade de 02/ago corrigiu (o flip-flop do reprocessamento),
   reaparecendo por outra causa.

O que o lote entregou:

- **Migration `0013_status_sem_dado`**: alarga o `CHECK` de
  `processamentos_datahub.status` para aceitar `sem_dado`. Era obrigatório — o
  CHECK inline da `0006` só admitia `ok`/`erro`/`pendencia_depara`, e gravar sem
  alargar estouraria em produção na primeira SANCA vazia. O downgrade converte
  `sem_dado` de volta para `erro` **antes** de reapertar o CHECK (o valor que o
  código anterior gravaria para o mesmo arquivo — não inventa estado).
- **`entrada_mercadorias.ler()` deixa de levantar exceção** e devolve
  `sem_dado: True`. Quem decide o que fazer é o chamador — o leitor não sabe se
  quem pergunta vai persistir ou exibir.
- **Processamento grava `sem_dado`** como status **terminal**: `_STATUS_TERMINAIS
  = ("ok", "sem_dado")` no "pula inalterado", então os arquivos param de ser
  rebaixados. Se a SANCA republicar o `2601` com dado, o `modificado_em` muda e
  ele reprocessa sozinho — a chave de frescor continua a mesma.
- **`sem_dado` entra na guarda de colisão** junto do `ok`: ele não grava célula,
  mas **poda** o escopo (armazém, competência); fora da guarda, um arquivo vazio
  apagaria as células do irmão numa colisão sem a rodada abortar.
- **Decisão (a) da Maria** (06/ago/2026): arquivo republicado vazio **apaga** as
  células que havia gravado — a série é espelho fiel do último estado da fonte,
  coerente com o que a V1 já faz quando todas as linhas são inválidas. Saiu de
  graça: com nenhum agregado, o prune de órfãs já remove tudo daquele recorte.
- **A tela executiva continua recusando**: `/kpis` e `/ler` declaram
  "arquivo sem linhas de dado" com a mesma mensagem de antes. Ela mostra UM
  arquivo como se fosse a leitura da operação — renderizar zero ali, sem
  declarar, seria apresentar ausência de medição como medição.
- **Painel com rótulo legível** ("sem movimento"), não o identificador cru — a
  mesma correção que a verificação do V2.1 exigiu para o vocabulário de estado.
- **`scripts/verificar_v2.py`**: conta `sem_dado` como processado, ganhou um
  check de "nenhum arquivo com status erro", e **`RMSPII/002` saiu de
  `PENDENCIAS_ESPERADAS`** — o `002` só existe em `DADOS_GERAIS` e
  `OCORRENCIAS_ENTREGAS`, famílias não integradas, então nunca pode virar
  pendência de processamento. O script avisava "pendência esperada ausente" para
  sempre, pedindo uma coisa impossível.

**Distinção que o lote preserva de propósito:** `sem_dado` é **zero linha**.
Arquivo com linhas que falham na validação continua `ok` com `linhas_validas = 0`
— ali existe dado, e ele está ruim. Misturar os dois esconderia export quebrado
atrás de "sem movimento" (coberto por teste).

**Suíte**: **471 passed** (462 do V2.1 + 9 novos: 4 do `sem_dado` no
processamento, 2 do ciclo/guarda do CHECK da `0013`, 2 da recusa nos endpoints de
exibição e 1 do leitor; nenhum removido — o teste que exigia exceção no arquivo
vazio passou a exigir a leitura marcada, que é o comportamento novo).

---

## Lote V2.2 — Tipo de estoque como dimensão (feito, 06/ago/2026)

Autorizado pela Maria em 06/ago/2026, com plano apresentado em texto cobrindo os
dois pontos que ela pediu explicitamente: o escopo do prune de órfãs
acompanhando a UNIQUE nova (risco 4 da `proposta_v3_volumetria.md`) e a prova de
que o total por competência é o mesmo antes e depois do reprocesso.

> Introduzir a dimensão na entrada, antes de existir saída.

Escopo:

1. **`backend/services/tipo_estoque.py`** (novo) — classificação por
   palavra-chave de `Nome Estoque`: `CONGELADO`, `SECO`, `HORTIFRUTI`,
   `UTENSILIOS`, ou o sentinela `NAO_CLASSIFICADO` (valor vazio, sem palavra-chave
   ou ambíguo — nunca desempatado por ordem da lista). O leitor
   (`entrada_mercadorias.py`) não foi tocado: `Nome Estoque` já era lido e só era
   descartado na agregação.
2. **Migration `0014_tipo_estoque`**: coluna em `medidas` e `medidas_recebidas`,
   `CHECK` fechando os 5 valores, `medidas_celula_unica` vira `UNIQUE NULLS NOT
   DISTINCT` de 5 colunas, tabela nova `tipo_estoque_pendencias` (mesmo padrão de
   `depara_pendencias`/`cliente_pendencias`). Upgrade sem backfill nem DELETE — as
   linhas existentes ficam com `tipo_estoque` NULL e continuam únicas (a UNIQUE
   de 4 colunas já garantia isso). Downgrade destrutivo só para células com
   `tipo_estoque` preenchido e a linhagem delas, preservando a célula sem a
   dimensão — mesma política da 0006 para `cliente_id`.
3. **`processamento_datahub._agregar_por_cliente_e_tipo`**: agregação passa a
   agrupar por `(cliente_id, tipo_estoque)`; pendência de tipo registrada uma vez
   por valor distinto dentro do arquivo, mesmo padrão de cliente e de-para.
4. **`_remover_celulas_orfas`**: o `WHERE` que busca candidatos a órfã continua
   `(metrica_id, armazem_id, competencia)`, **sem** `tipo_estoque` — o filtro por
   tipo é feito depois, em Python, comparando `(cliente_id, tipo)` contra o que o
   processamento atual emitiu. É essa varredura larga que limpa a célula do grão
   antigo (`tipo_estoque` NULL) assim que o arquivo reprocessa; estreitar o
   `WHERE` por tipo teria deixado a célula antiga sobreviver ao lado da nova e o
   total da competência dobraria em silêncio.
5. **`serie_datahub.serie`**: filtro opcional `tipo_estoque`, mesmo nível de
   filial/cliente; `clientes_atendidos` recusa esse filtro com mensagem clara.
   **Fora do lote**: ranking/distribuição por tipo (V2.4).
6. **`linhagem.celulas`** passa a devolver `tipo_estoque`; a tela `/linhagem`
   ganhou a coluna com rótulo legível (nunca o identificador cru).
7. **`cockpit.qualidade`** e o painel do admin passam a exibir pendências de
   tipo de estoque, mesmo padrão das pendências de filial e cliente.
8. **`scripts/verificar_v2.py`**: checks novos (coluna existe nas duas tabelas,
   UNIQUE de 5 colunas, distribuição por tipo impressa, pendências como AVISO). O
   check de "nenhuma célula com `tipo_estoque` NULL" é **AVISO, não FALHA** — a
   janela entre o deploy (upgrade da migration no startup) e o "Processar
   arquivos" com FORÇAR é estado esperado, documentado na própria migration;
   tratar como FALHA reprovaria uma rotina de deploy normal.
9. **`scripts/totais_competencia.py`** (novo), somente leitura: soma por
   `(métrica, competência, filial)`, arredondada a 3 casas (a mesma soma em
   acumuladores separados por tipo pode divergir no último bit de um float —
   arredondar evita falso positivo no `diff`). Runbook: rodar antes do deploy,
   rodar depois do reprocesso com forçar, `diff` — a coluna do total tem que
   bater linha a linha, só `n_celulas` cresce.
10. **Reprocesso com `forcar=True`**: prova automatizada
    (`test_reprocesso_forcado_preserva_total_por_competencia`) e prova manual
    (`totais_competencia.py`).

**Aceite:** os quatro tipos aparecem na consulta; valor não casado vira
pendência visível e não some; total por competência antes e depois do lote é o
mesmo — confirmado por teste (soma agregada, não célula por célula) e por
validação manual da migration nos dois sentidos via `alembic` CLI direto contra
o banco de teste (upgrade → dado real → downgrade → reprocessar upgrade),
independente da suíte. **Deployado na VM em 06/ago/2026**: migration `0014`
aplicada no startup, "Reprocessar tudo" processou os 46 arquivos da família (0
pulados, 0 erros) e `scripts/verificar_v2.py` rodou sem falhas.

### Verificação independente (agente separado, antes do commit): aprovado com uma ressalva

Um achado, severidade média: o check novo de "grão misto" em `verificar_v2.py`
usava `_checar` (reprova o deploy) para um estado que a própria migration
documenta como correto — célula com `tipo_estoque` NULL entre o deploy e o
"Processar arquivos" com FORÇAR. Rodar o script nessa janela normal daria FALHA
falsa. Corrigido: virou `_avisar`, mesmo padrão do check análogo de unidade sem
arquivo processado.

O verificador confirmou como **corretos**: o escopo do prune (não filtra por
tipo, varre o recorte inteiro — testado com célula de grão antigo semeada à mão
e reprocesso real, não simulado já no grão novo), a migration nos dois sentidos
e em banco com dado, todos os consumidores de `medidas`/`medidas_recebidas`
varridos (`serie_datahub`, `cockpit`, `linhagem`, `motor.calcular_scores`), a
contagem de `clientes`/`sem_cliente` no relatório por cliente distinto (não por
bucket cliente×tipo), a validação do filtro de tipo de estoque na série
(inclusive a recusa em `clientes_atendidos`), o frontend sem identificador cru
em nenhuma tela e sem `colspan` desalinhado, e nenhuma escrita no SharePoint.

**Suíte**: **514 passed** (471 do V2.1.1 + 43 novos: 22 de `tipo_estoque.py`
puro, 7 de agregação/prune/reprocesso em `processamento_datahub`, 4 de migration,
4 de filtro em `serie_datahub`, 2 de `ingestao`, 2 de router, 1 de `linhagem`, 1
de `cockpit`; nenhum removido). Um teste pré-existente
(`test_migracao_0006_ciclo_completo_preserva_grao_filial`) fixava o formato da
constraint no "head" — atualizado para refletir as 5 colunas, mesma lição do
próprio docstring do arquivo ("os testes de migração comparam contra o head, não
contra a baseline fixa").

**Fora do lote (declarado):** ranking/distribuição por tipo de estoque nas
consultas do cockpit (V2.4), leitor e ingestão da saída (V2.3), tela (V2.5),
conciliação com o Power BI (V2.6).

---

## Lote V2.3 — Saída (autorizado em 06/ago/2026, código construído, verificação pendente)

Autorizado pela Maria em 06/ago/2026. **Plano de execução completo:
[`docs/V2_3_PLANO_EXECUCAO.md`](V2_3_PLANO_EXECUCAO.md)** — é lá que estão a
evidência da conferência, os passos em ordem, o aceite e os riscos. Esta seção é
só o resumo do que ficou decidido.

> A direção que falta, na fonte e na banda decididas.

### A conferência da fonte derrubou quatro premissas da proposta

Perfilei 10 arquivos de `SAIDA_MERCADORIAS` das quatro unidades pelo Graph,
somente leitura, em 06/ago/2026 — mesmo procedimento que o V2.1 usou com o
layout da RJ.

1. **Não existe coluna de valor na saída, em nenhuma unidade.** Os 36 rótulos
   terminam em `Corte Físico / Início / Final / Separador`. A proposta pede seis
   métricas; o dado sustenta **cinco**.
2. **A SANCA tem 34 colunas e a banda inteira desloca** — `Peso Bruto` na coluna
   **29**, não 31. Ler 31 num arquivo da SANCA leria `Início`, um timestamp, como
   peso. O leitor tem que achar a banda pela linha 5 e contar o deslocamento.
3. **Quem não tem cliente na saída é a RMSPV, não a RMRJ.** A RJ tem
   `Cliente`/`Cliente CNPJ` na saída; falta na *entrada* dela. São dois casos, os
   dois tratados no lote.
4. **Escopo real:** 248 arquivos, 2,60 GB, competências 2110..2608. **Só 2026: 72
   arquivos, 616 MB.**

Confirmados: `_f1`/`_f2` são **disjuntos** (ao contrário do `DADOS_GERAIS`); a
CWB3 publica **sem sufixo** e 12 competências têm parte única; `Status Separação`
é `Concluído` em 296.586 linhas amostradas, **nenhum `Cancelado`**.

### Decisões da Maria

| # | Decisão |
|---|---|
| D1 | **Cinco métricas, não seis** — `valor_mercadoria_saida` não é criada, não tem fonte. |
| D2 | Linha sem cliente cai no balde `NULL` existente, **sem pendência fantasma** (não há CNPJ para cadastrar). |
| D3 | **Só 2026.** O histórico anterior fica declarado como disponível e deliberadamente fora. |
| D4 | Roda por **script de linha de comando na VM**. Botão no painel é V2.7. |
| D5 | `clientes_atendidos` **continua só na entrada**; a união das direções é V2.4. |
| D5.1 | O **balde "sem cliente identificado" passa a ser exibido como número**, separado por causa (não cadastrado × unidade sem coluna na fonte). |

### Ordem de execução (resumo)

Métricas e conceitos (`0015`, rename em lugar) → varredura dos consumidores do
nome → leitor da saída → variante de 18 colunas da entrada → de-para da RJ
(`0016`) → `layout_lido` (`0017`) → partição, guarda e processamento → script de
processamento → balde sem cliente visível → cobertura e catálogo →
`verificar_v2.py`.

**O rename é o item mais perigoso do lote, não o leitor.** Renomear em lugar
(`UPDATE metricas SET nome`) preserva o `metrica_id` e as células; inserir nome
novo deixaria o cockpit em 0 t **sem erro nenhum**. E quase todo consumidor do
nome falha em silêncio: kg no lugar de tonelada no cockpit, check de deploy
passando por vacuidade em `verificar_v2.py`, `diff` vazio aprovando o lote em
`totais_competencia.py`.

### O que foi construído (06/ago/2026)

Todo o escopo do plano de execução, seguindo a ordem acima:

- **Migrations `0015` (rename entrada + par de saída), `0016` (de-para da RJ)
  e `0017` (`layout_lido`)** — as duas primeiras testadas em código quanto à
  preservação de célula/vínculo no rename e ao no-op em banco novo/existente;
  a `0017` com o `CHECK` fechado nos quatro layouts.
- **`backend/services/saida_mercadorias.py`** (novo) — cabeçalho de dois
  níveis, banda oficial por deslocamento (não posição chumbada), dois layouts
  (36/34 colunas), streaming (gerador, nunca materializa a lista de linhas),
  filtro de `Status Separação = Cancelado`.
- **`entrada_mercadorias.py`** — variante de 18 colunas da RJ, detectada pelo
  cabeçalho.
- **`processamento_datahub.py`** — reescrito: agregador parametrizado por
  produtor, partição de 1..N partes, guarda de colisão com `indice_parte`,
  prune isolado por produtor (`_METRICAS_ENTRADA` / `_METRICAS_SAIDA`, nunca
  os dois juntos numa chamada), filtro de escopo D3.
- **`scripts/processar_saida.py`** (novo, roda dentro do container — Dockerfile
  ajustado pra copiá-lo) — decisão D4, uma partição por transação.
- **Balde "sem cliente identificado" visível** (D5.1) — `serie_datahub.py`
  (`_armazens_sem_coluna_cliente`, derivado de `layout_lido`, nunca de lista
  fixa), `cockpit.py` e `frontend/cockpit.html`.
- **Catálogo semântico da saída** — 36 campos, só `Peso Bruto` da banda oficial
  aprovado; corrigido de passagem um bug real no seed (`return` cedo que
  faria os campos da saída nunca serem aplicados em banco já migrado).
- **`nuvem_datahub.py`** — `SAIDA_MERCADORIAS` como `integrada`, escopo D3
  declarado por arquivo, RJ sai de "layout não homologado".
- **`scripts/verificar_v2.py`** — checks da seção 3.11 do plano de execução.
- **Varredura de consumidores do nome** completa (frontend, `cockpit.py`,
  `serie_datahub.py`, os dois scripts) — nenhum ponto ficou com o nome antigo
  fora de docs/memória.

### Verificação contra Postgres real (07/ago/2026)

Esta sessão (Sonnet) não tinha `docker` no PATH do Bash/PowerShell, mas achou
um caminho: `memory/suite-testes-local.md` documentava um Postgres de teste
(`nuvem-teste-db`, porta 5433) rodando dentro do WSL da máquina da Maria,
inacessível direto do host mas alcançável via `wsl -d Ubuntu-24.04`. Rodou a
suíte de verdade num container Python efêmero (`python:3.11-slim`,
`pip install -r requirements-dev.txt`) ligado à mesma rede Docker do banco —
nunca modificou o ambiente da Maria fora desse container descartável.

- **Suíte completa: 577 passed, 0 failed.** A primeira rodada achou **7
  falhas reais** (nenhuma delas bug de produção — todas eram testes que não
  acompanharam as mudanças deste lote):
  - `test_migracao_0006_...preserva_grao_filial` e
    `test_migracao_0014_...preserva_celula_sem_tipo_estoque`: os dois faziam
    `SELECT id FROM metricas` **sem** `WHERE nome = 'metrica_teste'` — desde a
    `0015` a tabela já nasce com 2 linhas (peso/registros de saída) antes do
    `INSERT` do teste, e o `[0][0]` pegava a métrica errada. `WHERE` explícito
    adicionado nos dois.
  - `test_processamento_datahub.py::test_origem_sem_depara_nao_baixa_o_arquivo`
    e `test_filial_com_hifen_da_rj_vira_pendencia_visivel`: usavam a RJ como
    exemplo de origem **sem** de-para — a migration `0016` deste mesmo lote
    deu de-para a ela (RMRJ). Trocados por `RMSPII/002`/`003` (que continuam
    pendentes de verdade).
  - `test_endpoint_campos_por_fonte` e
    `test_seed_metricas_preenche_catalogo_semantico`: contagens hardcoded (1
    fonte, 15 métricas) que o lote mudou pra 2 fontes e 17 métricas.
  - `test_seed_novo_e_migracao_existente_terminam_com_texto_identico` (o
    teste de paridade escrito nesta sessão): achou uma FK faltando (`brl` em
    `unidades`, no setup do teste) e, depois de corrigida, achou uma
    divergência **real** de caractere (`NAO` maiúsculo no seed, `nao`
    minúsculo na migration — erro de digitação da própria correção desta
    sessão) que o teste existe justamente pra pegar. Corrigido.
  - Todas as 7 corrigidas; suíte rodou de novo **duas vezes** depois, 577
    passed as duas vezes.
- **As três migrations novas foram validadas nos dois sentidos** via `alembic`
  CLI direto (não só pela suíte): `alembic downgrade 0014_tipo_estoque` e
  `alembic upgrade head` contra um banco **semeado** (`init_db()` completo,
  não só `migrar()`) — exatamente o cenário que o bug crítico da FK em
  `catalogo_campos` (revisão independente, abaixo) exigia pra aparecer.
  Ciclo completo, sem erro.
- **`scripts/verificar_v2.py` não rodou**: o script assume um stack
  `docker compose` com serviço `nuvem-db` (o da VM); o Postgres de teste
  aqui é um container avulso (`nuvem-teste-db`), fora desse contexto, e não
  tem dado real de arquivo processado do SharePoint pra verificar de
  qualquer forma. Fica pra rodar na VM, com o dado de verdade.
- **Checagem estática cobriu tudo**: `py_compile` em cada arquivo Python
  tocado, `node --check` no JavaScript embutido de `cockpit.html`.
- **Nada foi implantado na VM nem no SharePoint** — só leitura, como sempre;
  o container de teste usado é exatamente isso, um banco de teste, nunca a
  VM de produção.

### Revisão independente (Opus, 07/ago/2026)

Auditoria adversarial de todo o diff não commitado, sem acesso à conversa que
escreveu o código — achou **2 críticos e 7 médios reais**, todos corrigidos
nesta sessão antes do fechamento:

- **Crítico — downgrade da `0015` quebrava em qualquer banco semeado**:
  `catalogo_campos.conceito_id` referencia `conceitos_canonicos(id)` sem
  `ON DELETE`; o campo posição 32 de `SAIDA_MERCADORIAS` fica ligado a
  `peso_bruto_saida` pelo seed, e o `DELETE` do downgrade batia de frente com
  essa FK. Corrigido com `UPDATE ... SET conceito_id = NULL` antes do
  `DELETE`; teste `test_migracao_0015_downgrade_remove_so_o_que_o_lote_criou`
  trocado de `banco_vazio` pra `banco_migrado` (só assim reproduz o bug).
- **Crítico — `scripts/processar_saida.py` estourava `KeyError` e derrubava a
  rodada inteira** quando uma origem de saída não tinha de-para: o relatório
  de `pendencia_depara` não tem as mesmas chaves do relatório de sucesso, e a
  leitura estava fora do `try/except` de isolamento por partição.
  Corrigido — pendência agora é contada e relatada à parte, nunca derruba as
  partições seguintes nem conta como sucesso no resumo.
- **Médio — `layout_lido` virava `NULL` num reprocesso com erro ou
  pendência**, reclassificando em silêncio o balde "sem cliente identificado"
  de `sem_coluna_na_fonte` (não resolvível) pra `nao_cadastrado` (resolvível)
  — exatamente o defeito que a D5.1 existe pra evitar. Corrigido com
  `COALESCE` no `UPDATE` do upsert.
- **Médio — partição com arquivo sem sufixo de parte junto com `_fN` somava
  em silêncio** em vez de dar erro (a guarda de colisão não pega esse caso,
  só índice duplicado). Corrigido com uma checagem própria em
  `_agrupar_particoes_saida`, com teste puro cobrindo.
- **Médio — `medidas_gravadas` gravado em dobro** numa partição de N partes
  (o total da partição inteira ia pra CADA linha de parte, e
  `cockpit.qualidade()` soma por status). Corrigido: só a primeira parte
  carrega o total, as demais ficam com 0.
- **Médio — banco novo semeado e banco existente migrado terminavam com texto
  diferente** nas métricas/conceitos do V2.3 (um guard usa `UPDATE ... WHERE
  dominio IS NULL`, outro usa `ON CONFLICT DO NOTHING` — qual vence depende
  de qual caminho o banco percorreu). Textos alinhados entre a migration `0015`
  e os seeds; teste de paridade novo
  (`test_seed_novo_e_migracao_existente_terminam_com_texto_identico`) cobre a
  exigência da seção 3.1 do plano de execução, que não tinha teste.
- **Médio — `scripts/totais_competencia.py` não conseguia mais produzir a
  prova antes/depois** que o runbook pede: o rename de métrica fazia o
  `diff` acusar 100% das linhas como diferentes só pelo rótulo. Adicionada a
  flag `--nomes-antigos`.
- **Médio — duas superfícies novas sem nenhum teste**: o balde "sem cliente
  identificado" inteiro (D5.1) e a variante de 18 colunas da entrada (RJ).
  Testes novos em `test_serie_datahub.py` e `test_entrada_mercadorias.py`.
- **Médio — comentário afirmava recência que o SQL não tem**:
  `_armazens_sem_coluna_cliente` classifica um armazém como "sem coluna" pra
  sempre, não só no processamento mais recente — docstring corrigida pra
  declarar o risco em vez de afirmar algo que o código não faz (implementar a
  janela de recência ficou registrado como melhoria futura, não bloqueante:
  nenhum armazém trocou de layout até hoje).
- **Baixos** (rótulo de check que não testava o que dizia, ordem de dois
  `if` que rotulava errado um arquivo de saída fora de escopo, texto colado
  sem espaço no catálogo semântico, `registros_saida` com unidade `un` em vez
  de `registros` como o par de entrada) — todos corrigidos.

O núcleo do lote (rename em lugar, isolamento do prune, leitor por
deslocamento de banda) saiu confirmado sólido pela revisão.

---

## Lote V2.4 — Consultas de volumetria (autorizado e construído em 07/ago/2026)

Autorizado pela Maria em 07/ago/2026 **para planejar e construir mesmo com a
verificação da V2.3 ainda pendente** contra Postgres real — decisão explícita
dela, não esquecimento. **Plano de execução completo:
[`docs/V2_4_PLANO_EXECUCAO.md`](V2_4_PLANO_EXECUCAO.md)** (decisões E1–E9).

> Os números que a tela vai consumir, sob `/cockpit/`. Só backend — desenho
> visual é V2.5.

### O que foi construído

- **`backend/services/volumetria.py`** (novo) — `evolucao`, `resumo`,
  `ranking`, `matriz`. Conceito de **grandeza** (`peso`, `registros`, `valor`)
  mapeando pro par de métricas entrada/saída; `valor` não tem par (decisão D1
  do V2.3) e nunca inventa um. Escopo temporal misto tratado por mês: mês
  anterior a 2026-01 fica `null` (fora de escopo, D3 do V2.3) — não é zero.
  Reaproveita `serie_datahub.serie()`, `resolver_filial`, `resolver_cliente`,
  `metrica_info`, `exigir_metrica_aditiva`, `resolver_tipo_estoque` e
  `filtros_sql` — nenhuma consulta duplicada.
- **`GET /cockpit/volumetria/{resumo,evolucao,ranking,matriz}`** —
  `backend/routers/cockpit.py`. `evolucao` **substitui** `GET /datahub/serie`
  (rota removida de `backend/routers/datahub.py`); `ranking`/`matriz` são
  endpoints novos e adicionais, não trocam `/cockpit/comparacao/*` (que
  continuam servindo o gráfico atual de uma métrica só).
- **`clientes_atendidos` somando as duas direções** (decisão D5 do V2.3,
  empurrada pra cá) — `serie_datahub.contagem_clientes_atendidos_unificada`,
  exposta em `resumo` **ao lado** da contagem só-entrada que a tela já
  mostra, nunca substituindo em silêncio.
- **Balde "sem cliente identificado" da saída** (decisão D5.1 do V2.3,
  empurrada pra cá) — `serie_datahub.balde_sem_cliente_saida`, generalizado a
  partir do motor que já existia pra entrada (`_balde_sem_cliente` comum),
  sem `valor_brl` (a saída não tem métrica de valor).
- **`frontend/cockpit.html`** — a única linha que chamava `/datahub/serie`
  agora chama `/cockpit/volumetria/evolucao`; `renderizarSerie`/
  `renderizarVariacao` ajustadas pra forma nova. Mesmo visual de hoje — mostrar
  entrada × saída × saldo juntos na tela é V2.5.
- Testes novos: `tests/test_volumetria.py` (regra de negócio, 20 casos),
  `tests/test_volumetria_router.py` (autenticação + encaixe HTTP), mais casos
  em `tests/test_serie_datahub.py` (balde da saída, contagem unida, `filtros_sql`
  com lista de métricas). `tests/test_datahub_router.py` perdeu os três testes
  de `/serie` (rota removida).

### Assunção que precisa da confirmação da Maria

**`total = entrada + saída`** (throughput do período) e **`saldo = entrada −
saída`** (variação líquida: positivo acumula estoque, negativo reduz) — é a
leitura mais comum em operação logística, mas ninguém validou o nome nem a
fórmula com ela ainda. Se "saldo" significar outra coisa pro negócio, é só
trocar a fórmula em `volumetria.py` (dois lugares: `evolucao` e `ranking`) —
não tem migração nem dado persistido envolvido.

### Verificação contra Postgres real (07/ago/2026)

Rodou junto com a verificação do V2.3 (mesmo container efêmero contra o
`nuvem-teste-db` via WSL — ver detalhes na seção do V2.3). `test_volumetria.py`
(20 casos), `test_volumetria_router.py` e os casos novos de
`test_serie_datahub.py` — todos escritos às cegas nesta sessão, cada consulta
conferida manualmente linha a linha contra a lógica de `volumetria.py` antes
de rodar pela primeira vez — **passaram de primeira**, sem nenhum ajuste.
`scripts/verificar_v2.py` segue sem rodar (mesma limitação do V2.3: assume
`docker compose` da VM, não o container de teste avulso).

---

## Lotes V2.5, V2.6 e V2.7 (07/ago/2026)

Autorizados pela Maria em 07/ago/2026: o V2.5 com plano apresentado em texto e
confirmado, e **V2.6/V2.7 em sequência sem nova autorização por lote** — mesmo
modo autônomo do V2.3/V2.4 (decisões de design seguem sem pausa, documentadas;
perguntas bloqueantes vão para o relatório final). Meta declarada por ela:
chegar no passo anterior ao Laboratório (V2.7 fechado) até as 12h. Pedido
explícito de método: **validar contra o Postgres real de forma incremental**,
conforme cada parte ficasse pronta, e **não repetir a auditoria Opus lote a
lote** — reservá-la para o fechamento final.

**Suíte ao fim dos três lotes: 598 passed, 0 failed** contra Postgres real (577
no fechamento do V2.4 + 21 novos; nenhum removido). Cada lote tem plano de
execução próprio, que é onde estão as decisões e as limitações declaradas:

- **V2.5 — Cockpit visual**: [`V2_5_PLANO_EXECUCAO.md`](V2_5_PLANO_EXECUCAO.md).
  Tema claro/escuro, filtro de tipo de estoque, cards das três grandezas com
  entrada/saída/total/saldo, evolução combinada, dois rankings, matriz em
  Tabulator com um nível de abertura e exportação CSV, estado de unidade fora do
  ranking (três estados distintos), faixa de indicadores aprovados. Duas adições
  pequenas de backend (`unidades_fora_do_ranking` e
  `GET /laboratorio/aprovados`). **Validado em navegador de verdade** (Playwright
  contra a app rodando com Postgres semeado) — foi essa validação que achou
  quatro defeitos de tela que a leitura não pegou, o principal deles o seletor de
  filial mostrando três unidades homônimas com rótulo idêntico.
- **V2.6 — Conciliação**:
  [`CONCILIACAO_POWERBI_V2.md`](CONCILIACAO_POWERBI_V2.md) + `scripts/conciliacao.py`
  (somente leitura). 11 diferenças conhecidas com causa nomeada e **efeito
  esperado no sinal**, 5 pendências registradas. A principal: o gap de 13,2 % tem
  o **sinal contrário** ao que a decisão 6 previa. Nenhum número novo foi
  inventado — as células que exigem a VM estão marcadas como pendentes.
- **V2.7 — Escala e operação**: [`V2_7_PLANO_EXECUCAO.md`](V2_7_PLANO_EXECUCAO.md).
  Cache de consulta com TTL curto (garantia declarada: desatualizado no máximo
  um TTL) com invalidação nas escritas que a pessoa vê acontecer, teto de
  `tamanho_pagina` casado com o teto da exportação CSV, top N **com bucket**
  (nunca corte silencioso), log de consulta lenta sem valor de filtro no log.
  **Backup/restore com evidência fica pendente da VM** — o roteiro do ensaio está
  escrito, a execução não aconteceu.

### Revisão independente dos três lotes (agente Opus separado, 07/ago/2026)

Feita **uma vez, no fechamento**, como a Maria pediu (não lote a lote). Auditoria
adversarial do diff inteiro, sem acesso à conversa que escreveu o código: **3
críticos, 7 médios e 12 baixos**. Todos os que eram defeito real foram corrigidos
antes de fechar. Os três críticos são a mesma família — **texto afirmando mais do
que o código sabe**:

| # | Sev. | O que estava errado | Correção |
|---|---|---|---|
| 1 | crítico | `sem_movimento_no_periodo` dizia "**é zero medido de verdade**", mas o estado é derivado de "tem célula em alguma competência" — nada consulta `processamentos_datahub`. Arquivo do período em `erro`, ou competência não publicada, produzem a mesma ausência: a tela afirmaria medição onde não houve, apagando a distinção que o V2.1.1 criou (`sem_dado` × `erro`) e contradizendo o próprio bloco "Qualidade" da mesma tela | a nota deixou de afirmar medição e manda conferir Qualidade antes de ler como zero; o quarto estado derivado de `processamentos_datahub` ficou registrado como melhoria |
| 2 | crítico | **o CSV declarava filtro que não foi aplicado**: com `filial` + `cliente`, a matriz vira dimensão cliente (que recusa filtro de cliente), e o rodapé — montado dos filtros da tela, não dos enviados — afirmava `cliente=SAPORE` num arquivo com o armazém inteiro. Arquivo circula desacoplado da tela; quem abre não tem como descobrir | rodapé passou a ser montado do que foi de fato enviado, mais uma linha `# ATENCAO: o filtro ... NAO foi aplicado`. Conferido no navegador |
| 3 | crítico | **`tipo_estoque` era ignorado em silêncio por dois blocos** (`/cockpit/resumo` e `/cockpit/qualidade`, da V1.7, não aceitam o parâmetro) — contra o aceite escrito "filtros globais afetam todos os visuais". Pior: dentro da mesma caixa, "Peso bruto (detalhado)" vinha filtrado e "Total de arquivos processados" não | aviso declarado acima dos cards, nomeando os dois blocos e o filtro ignorado |
| 4 | médio | `fora_de_operacao` afirmava que a ausência **é** encerramento, mas `ativo` é estado de hoje, sem data de encerramento — falso para recorte anterior ao encerramento | nota passou a dizer "pode ser" e a mandar conferir o período |
| 5 | médio | o **acumulado** de `evolucao` usava `saida=0.0` para período inteiramente fora do escopo (o mensal já usava `null`), publicando "Saída 0 · Saldo = entrada" sob o rótulo "total movimentado". Latente hoje (a entrada por item também só existe em 2026), real no dia em que houver entrada anterior | `saida`/`saldo` viram `None` quando `ate < 2026-01`, com dois testes (o caso e a contraprova dentro do escopo) |
| 6 | médio | **escritas em `medidas` que não invalidavam o cache**: upload manual e reprocessamento de execução — contra o princípio declarado no próprio módulo | `invalidar()` nos dois, depois do commit. `scores/recalcular` **não** invalida, de propósito (escreve em `scores`, que o Cockpit não lê) |
| 7 | médio | a matriz por cliente descartava o filtro de cliente **sem declarar** (o ranking análogo declarava) | mesma frase do ranking na nota da matriz |
| 8 | médio | `scripts/conciliacao.py` anunciava "Recorte: unidade RMSPIV" no cabeçalho e a seção 2 listava todas as unidades — quem colasse ao lado de um print do BI filtrado compararia coisas diferentes | a seção declara que `--unidade` não se aplica a ela |
| 9 | médio | docstring e plano citavam invalidação em "cadastrar cliente" — **endpoint que não existe** | corrigido; a pendência de cliente sai no próximo processamento, e isso está escrito |
| 10 | médio | **"três filiais homônimas" são quatro** — RMSPIV também se chama "Barueri/SP", e é a `016`, a de maior volumetria e parte do agregado "RMSPII" do BI. O código sempre cobriu; o documento subdimensionava o risco que ele mesmo levanta | corrigido nos três documentos e na memória |
| 11–22 | baixo | identificador cru de status na tela (`ok`/`erro`/`sem_dado` — a correção que o V2.1.1 fez no `/nuvem` e faltava aqui); variação com base zero rotulada "não medido" em vez de "não calculável"; `null` desenhando barra em zero no ranking; nome de parâmetro cru no log (linha de log forjável); truncamento sem reticência e `0` para cliente < 500 kg no script; teste cujo nome afirmava dois casos e exercitava um; contagens de teste erradas nos planos; enumeração incompleta de tabelas lidas; participação somando 99,9 %/100,1 % por arredondamento | todos corrigidos ou declarados com precisão |

O verificador confirmou como **corretos**: a chave do cache cobrindo todos os
parâmetros de cada endpoint (conferidos um a um contra a assinatura do serviço),
erro não cacheado, a tradução para HTTP 400 sendo **superconjunto** da de antes,
invalidação depois do commit nos três pontos originais, `escaparHtml` em todos os
pontos que interpolam dado do banco, o CSV (separador, escape, célula vazia ×
zero real, corte declarado), `total_linhas` medido antes do corte, o bucket
tratando `saida=None` sem misturar linhas, `unidades_fora_do_ranking` usando o
ranking completo, `linhagem.html` sobrevivendo à migração do rótulo, nenhuma
regressão de contrato em `/cockpit/resumo` e `/cockpit/comparacao/*`, nenhum teste
removido, nenhum número inventado no documento de conciliação (os 40 valores
conferidos contra a memória), e nenhuma injeção de SQL no script.

**Suíte depois das correções: 598 passed, 0 failed** (21 novos sobre os 577 do
V2.4). A tela foi **reaberta no navegador** depois das correções: os avisos novos,
a nota da matriz, os rótulos de status e o `# ATENCAO` do CSV conferidos no
conteúdo, zero erro de JavaScript.

### Deploy dos lotes V2.3 a V2.7 na VM (07/ago/2026)

`git push` + `git pull` na VM + `docker compose up -d --build` (migrations `0015`,
`0016` e `0017`, do V2.3, aplicadas no startup — os lotes V2.5/V2.6/V2.7 não têm
migration). **`scripts/verificar_v2.py` rodou sem nenhuma falha** — era a
pendência aberta desde o V2.3, e é a primeira vez que os checks da saída (par
entrada/saída de métricas, escopo D3, `layout_lido`) rodaram contra dado real.

**Pendência aberta e com consequência visível na tela:**
`scripts/processar_saida.py` **ainda não rodou**, então não existe nenhuma célula
de `peso_bruto_saida`/`registros_saida` no banco de produção. O processamento da
saída é por script de linha de comando, não pelo botão do painel (decisão D4 do
V2.3), e ele nunca foi executado.

Isso não é um estado neutro no Cockpit: competência de 2026 está **dentro** do
escopo da saída, então a ausência de célula vira `saida = 0.0` **real** — os
cards mostram "Saída 0" e "Saldo = entrada", e a matriz mostra `0`, sem nada
declarando que a saída não foi ingerida. A limitação que a resposta traz é a do
escopo D3 (períodos anteriores a 2026), que é outra coisa. Ou seja: até o script
rodar, a tela apresenta "não medimos ainda" como "medimos e deu zero" — o
defeito que este projeto mais persegue, aqui por dado faltando, não por código
errado.

Duas saídas, nesta ordem de preferência:

1. **Rodar o processamento** —
   `docker compose exec nuvem-app python scripts/processar_saida.py` (uma
   partição por transação; 72 arquivos de 2026, ~616 MB). Resolve de fato.
2. Se por algum motivo a ingestão da saída ficar para depois, **declarar na
   tela** que a direção saída não tem arquivo processado no recorte — é a mesma
   melhoria já registrada no V2.5 (o quarto estado derivado de
   `processamentos_datahub`, achado 1 da revisão independente). Enquanto nenhuma
   das duas acontecer, o número de saída do Cockpit não deve ser usado.

---

## Próximo lote autorizado

**Nenhum além do V2.7.** V2.8 (Laboratório com gráficos) segue não autorizado.

Sobre V2.3 e V2.4: construídos,
revisados de forma independente e agora **verificados contra Postgres real**
(577 testes, migrations validadas via `alembic` CLI nos dois sentidos contra
banco semeado). O que falta pro fechamento formal: `scripts/verificar_v2.py`
na VM (precisa do stack `docker compose` real, com dado processado de
verdade) e o deploy em si — nenhuma dessas etapas depende mais de acesso a
Postgres, só da VM. Eles foram commitados em 07/ago/2026 (`67bba8f`) e agora
sobem junto com o V2.5/V2.6/V2.7 no mesmo deploy.

V2.1, V2.1.1 e V2.2 foram deployados e validados juntos na VM em 06/ago/2026:
`git pull` + `up -d --build` (migrations `0012`, `0013` e `0014` rodaram no
startup), "Reprocessar tudo" (forçar) processou os 46 arquivos da família
ENTRADA_MERCADORIAS (0 pulados, 0 erros — todos gravaram no grão novo, com
`tipo_estoque`), e `scripts/verificar_v2.py` rodou **sem falhas**.
