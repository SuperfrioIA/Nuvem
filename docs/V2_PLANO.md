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
| **V2.3** | Saída (`SAIDA_MERCADORIAS`, banda *Separado Fisicamente*) | não autorizado |
| **V2.4** | Consultas de volumetria sob `/cockpit/` | não autorizado |
| **V2.5** | Cockpit visual | não autorizado |
| **V2.6** | Conciliação com o Power BI | não autorizado |
| **V2.7** | Escala e operação | não autorizado |
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

## Próximo lote autorizado

**Nenhum.** V2.1, V2.1.1 e V2.2 foram deployados e validados juntos na VM em
06/ago/2026: `git pull` + `up -d --build` (migrations `0012`, `0013` e `0014`
rodaram no startup), "Reprocessar tudo" (forçar) processou os 46 arquivos da
família ENTRADA_MERCADORIAS (0 pulados, 0 erros — todos gravaram no grão novo,
com `tipo_estoque`), e `scripts/verificar_v2.py` rodou **sem falhas**.

O V2.3 (saída) só começa com autorização explícita.
