# V2.5 — Cockpit visual — plano de execução e registro

Autorizado pela Maria em 07/ago/2026, com plano apresentado em texto e confirmado
("pode iniciar a execução"). Especificação de origem:
`docs/proposta_v3_volumetria.md`, seção "V2.5 — Cockpit visual". Consome os
endpoints que o V2.4 entregou (`/cockpit/volumetria/{resumo,evolucao,ranking,matriz}`)
— nenhuma migration, nenhum dado novo.

Autorização da Maria para este lote inclui seguir direto para o V2.6 e o V2.7 sem
nova autorização, no mesmo modo autônomo do V2.3/V2.4: decisões de design seguem
sem pausa, documentadas; perguntas bloqueantes vão para o relatório final.

## O que foi construído

### Tela (`frontend/cockpit.html`, reescrita)

1. **Tema claro e escuro.** Tokens semânticos por tema (`:root[data-tema=...]`),
   default pelo `prefers-color-scheme` e escolha explícita persistida em
   `localStorage` vencendo o sistema nos dois sentidos. O atributo é escrito por
   um script inline no `<head>`, **antes do primeiro paint** — sem isso a tela
   pisca branca antes de virar escura. Cor de série (`--c-entrada`, `--c-saida`,
   `--c-saldo`, `--heat-rgb`) vive no CSS, não no JS: trocar de tema não exige uma
   segunda tabela de cores em JavaScript para manter sincronizada. O ECharts e o
   Tabulator guardam cor no objeto de configuração, então a troca redesenha os
   visuais a partir do último payload — **sem novo request**.
2. **Filtro de tipo de estoque** como quinto filtro de dado, na URL
   (`?tipo_estoque=`) como os outros. `ROTULO_TIPO_ESTOQUE` saiu do
   `linhagem.html` e foi para `comum.js` — a mesma tabela de rótulos em duas
   telas é o que aquele arquivo existe para evitar.
3. **Segunda linha de filtros ("visão"): grandeza + direção em foco**, também na
   URL. Não filtram dado: escolhem o que está sendo olhado. Ficam junto porque
   mudam tudo o que aparece abaixo, e um link do Hub precisa poder abrir uma
   visão específica.
4. **Cards das três grandezas** (`/volumetria/resumo`): headline = total
   movimentado, com entrada · saída · saldo abaixo. Grandeza sem par de saída
   (`valor`, decisão D1 do V2.3) mostra "só entrada" no rótulo e "sem par de
   saída na fonte" na linha de direções — nunca um zero ou traço sem explicação.
5. **Card de clientes atendidos com as duas leituras**: valor principal = união
   das duas direções (V2.4), sub-linha = "somente entrada: N — é a leitura que a
   V1 publicava". Abaixo, o balde "sem cliente identificado" das duas direções,
   separado por causa (não cadastrado × unidade sem coluna de cliente na fonte) —
   decisão D5.1 do V2.3, agora nas duas direções.
6. **Evolução mensal com entrada × saída × saldo** num gráfico só: barras
   agrupadas + linha de saldo, mesma unidade. `connectNulls: false` de propósito
   — mês anterior a jan/2026 não tem saída medida, e ligar a linha por cima do
   buraco desenharia um saldo que ninguém apurou.
7. **Variação mensal governada pela direção em foco**, com uma recusa explícita:
   **variação percentual não se aplica a saldo** (de −10 para +5 não é "+150%", é
   troca de sinal). Nessa direção o gráfico passa a mostrar variação **absoluta**
   e o título declara a troca.
8. **Dois rankings lado a lado** (`/volumetria/ranking`, dimensão unidade e
   cliente), barra = direção em foco, tooltip sempre com as quatro leituras. O
   rótulo de participação **só aparece na direção `total`**, porque
   `participacao_pct` é calculado sobre o total movimentado — estampar esse
   percentual ao lado de uma barra de saldo diria uma coisa medindo outra. Quando
   há filtro de filial (ou de cliente), a nota do painel **declara** que aquele
   filtro não se aplica ao ranking daquela dimensão, em vez de o usuário achar
   que filtrou e não filtrou.
9. **Matriz com Tabulator (CDN, 6.3.1)**: dimensão × competência da direção em
   foco, heatmap leve relativo ao maior valor absoluto da página (escala
   divergente em saldo, onde o sinal é a informação), ordenação por coluna,
   paginação própria e **um nível de abertura**: expandir a unidade dispara
   `matriz?dimensao=cliente&filial=<sigla>` — reaproveita endpoint já testado, sem
   dimensão combinada nova no backend, e respeita "drill-down além de um nível"
   estar fora da V2. Se o CDN não carregar, o painel **declara a falha** em vez de
   mostrar caixa vazia (e a exportação continua funcionando, porque é montada do
   JSON).
10. **Exportar CSV** montado do JSON da matriz, não do DOM: separador `;`,
    decimal com vírgula, BOM (Excel pt-BR), competências em ISO. **Célula fora de
    escopo sai vazia, nunca 0** — exportar zero ali transformaria "não medimos" em
    "mediu e deu zero". Rodapé comentado com filtros, unidade de medida, a regra
    da célula vazia e as limitações da resposta. Puxa a matriz inteira (teto de
    2000 linhas) e, se o teto cortar, **o arquivo e a tela dizem quanto ficou de
    fora**.
11. **Correção do bug apontado na proposta** (`cockpit.html:470` no numeração
    antiga): `dados.ranking.length` era avaliado sem proteção quando `limite` era
    falsy — o `|| []` protegia o primeiro acesso e o segundo estourava. A função
    de ranking foi reescrita guardando a lista numa variável.
12. **Faixa de indicadores aprovados no Laboratório**, antes HTML fixo dizendo
    que não havia nenhum.

### Backend (duas adições pequenas)

13. **`volumetria.ranking` ganhou `unidades_fora_do_ranking`** (só em
    `dimensao=unidade`; `None` em cliente). Até o V2.4 a unidade sem linha
    simplesmente desaparecia da tela, e três coisas diferentes ficavam com a
    mesma aparência. Agora cada ausência tem estado e nota:

    | Estado | Derivação | O que a tela diz |
    |---|---|---|
    | `fora_de_operacao` | `armazens.ativo = false` | encerramento de operação, não queda de volume |
    | `sem_movimento_no_periodo` | tem histórico da grandeza, nada no recorte | zero medido de verdade |
    | `sem_dado_ingerido` | sem nenhuma medida da grandeza em toda a série | não medimos — e isso não é zero |

    Duas decisões de precisão: (a) o **universo não é a tabela `armazens`
    inteira** — são as unidades com de-para do conector do DataHub, unidas às que
    têm histórico dessas métricas; listar Manaus como "sem dado ingerido" na
    volumetria do DataHub seria ruído, e o cadastro tem ~28 filiais. (b) "tem
    histórico" é calculado **sem nenhum filtro do recorte** — a pergunta é "esta
    unidade já mediu esta grandeza alguma vez?"; com o filtro de cliente
    aplicado, a nota de `sem_dado_ingerido` ("sem nenhuma medida em toda a
    série") viraria mentira para unidade com série inteira de outro cliente.
14. **`GET /laboratorio/aprovados`** (`laboratorio.listar_aprovados`) — nome,
    pergunta de negócio e data das sessões aprovadas, e **nenhum valor**. O que a
    aprovação gera é especificação técnica para implementação humana, nunca KPI
    publicado (topo de `insight_aprovado.py`): exibir número naquela faixa
    publicaria indicador por acidente. A tela diz isso em texto, uma vez, sob o
    título da faixa. `especificacao` NULL (banco antigo — a coluna nasceu na
    migration 0010) cai no título da sessão em vez de derrubar a lista.
15. **`unidade` junto do acumulado de cada grandeza em `/volumetria/resumo`** —
    sem ela o card teria que saber de cor que peso é kg e valor é R$, que é como
    o rótulo começa a divergir do dado.

## Defeitos de tela achados na validação em navegador (e corrigidos)

Estes quatro só apareceram porque a tela foi aberta de verdade, não por leitura:

| # | O que estava errado | Correção |
|---|---|---|
| 1 | **O seletor de filial listava só o nome do cadastro, e QUATRO unidades se chamam "Barueri/SP"** — RMSPII, RMSPIII, RMSPIV e RMSPV (`backend/seed_depara.py`), incluindo a RMSPIV, que é a filial `016`, a de maior volumetria e parte do agregado "RMSPII" do Power BI. Quatro rótulos idênticos para unidades diferentes, sem como saber qual foi escolhida (a mesma armadilha do código de filial nu que a migration 0008 tirou do de-para). CWBIII e CWBIV também compartilham "São José dos Pinhais/PR" | opção passou a ser `SIGLA · nome`; o valor enviado ao backend continua sendo a sigla. (A contagem "três" saiu da primeira redação deste documento e foi corrigida pela revisão independente — o código sempre cobriu todos os casos) |
| 2 | Logo invisível no tema escuro (o asset é azul-escuro sobre transparente) | silhueta branca por `filter` no tema escuro — sem versão branca do arquivo, é o fallback legível |
| 3 | Rótulo de categoria do ranking **cortado no meio da palavra** pelo ECharts: "Sem cliente identificado" aparecia como "m cliente identificado" — outro nome, não um nome abreviado | `axisLabel: { width, overflow: "truncate" }` (reticência) + margem maior |
| 4 | Num drill de cliente pequeno **tudo virava "0,0 mil t"** (e "-0,0 mil t"), resolução insuficiente para tabela | `formatarValorCompacto`: abaixo de mil toneladas a mesma medida aparece em toneladas, com a unidade escrita ao lado. "mil t" continua sendo a unidade dos **cards** (decisão de 30/jul) |

## Validação

- **Suíte completa contra Postgres real: 596 passed, 0 failed** (577 no
  fechamento do V2.4 + 19 novos, nenhum removido), no container efêmero contra o
  `nuvem-teste-db` via WSL (receita de `memory/suite-testes-local.md`). Deste
  lote, testes novos: 3 em `test_volumetria.py` (os três estados de
  `unidades_fora_do_ranking`, o campo `None` em `dimensao=cliente`, e o histórico
  ignorando filtro de cliente) e 4 em `test_insight_aprovado.py` (listagem sem
  número nenhum, sessão não decidida/descartada fora, aprovada sem especificação,
  endpoint com limite validado), mais uma asserção acrescentada ao teste de 401
  que já existia. Os outros 12 dos 19 novos são do V2.7 (9 de cache, 3 de
  bucket).
- **Dois testes precisaram acompanhar a extensão de contrato** (`unidade` dentro
  do acumulado): `test_volumetria.py::test_resumo_agrega_...` e
  `test_volumetria_router.py::test_volumetria_resumo_sucesso`. São asserções de
  igualdade exata sobre um dicionário que este lote ampliou de propósito.
- **Validação em navegador de verdade** (Playwright, app rodando em
  `127.0.0.1:8003` contra o Postgres de teste semeado com volumetria plausível —
  4 unidades, 9 competências, 3 clientes + balde, 3 tipos de estoque):
  - carga inicial, tema claro e escuro, troca de tema redesenhando gráficos e
    matriz;
  - expansão lazy da matriz (unidade → clientes daquela unidade) funcionando —
    era o ponto mais frágil do lote;
  - direção em foco = saldo: variação absoluta, heatmap divergente, célula fora
    de escopo como "—";
  - filtro de filial trocando a matriz para os clientes daquela unidade, com a
    nota do ranking declarando que o filtro não se aplica ali;
  - os três estados de unidade fora do ranking, com o texto do backend;
  - **exportação CSV conferida no conteúdo**, inclusive a propriedade que mais
    importa: com direção = saldo e período cruzando 2026, as competências
    2025-11 e 2025-12 saem **vazias** (`;;`), e a RMSPIII sai com `0` real nos
    meses de 2026 — a distinção entre "não medimos" e "mediu e deu zero"
    sobrevive à exportação;
  - **zero erro de JavaScript** no console em toda a sessão (só um 404 de
    `favicon.ico`, pré-existente).
- `node --check` nos dois blocos de script de `cockpit.html`, em `linhagem.html`
  e em `comum.js`.
- **Aceite "nenhuma leitura de Excel em endpoint de dashboard"**: confirmado por
  leitura — `/cockpit/*` e `/laboratorio/aprovados` leem apenas tabelas do
  Postgres (`medidas`, `metricas`, `processamentos_datahub`, `armazens`,
  `clientes`, `conectores`, `depara_armazem`, as três tabelas de pendência e
  `laboratorio_sessoes`); nenhum toca `graph_datahub` nem lê planilha. (A
  enumeração da primeira redação estava incompleta — corrigida pela revisão
  independente; a substância do aceite se sustenta.)

## Limitações declaradas

- **A parte visual não tem cobertura automatizada nesta base** (não há Playwright
  na suíte). O que existe é a validação manual em navegador registrada acima; uma
  regressão de CSS ou de layout não é pega por teste.
- O heatmap dos filhos (clientes) usa a escala da página de unidades, então
  cliente pequeno aparece pálido. É comparável na mesma escala de propósito, mas
  não realça diferença entre clientes.
- Dependência de CDN (ECharts e Tabulator) é a mesma de antes, agora com um
  consumidor a mais — risco 5 da `proposta_v3_volumetria.md`. O Tabulator tem
  falha declarada; o ECharts não (se ele cair, os gráficos ficam em branco).
- O estado `sem_movimento_no_periodo` não foi exercitado no navegador (o dado
  semeado não tinha unidade ativa com histórico fora do recorte) — está coberto
  por teste.
- `armazens.ativo` da RMSPIII **ainda não foi corrigido na VM**
  (`memory/filiais-catering-poc.md`): lá ela vai aparecer como
  `sem_movimento_no_periodo` até aquele UPDATE rodar. Nenhum dos dois textos
  mente, mas o mais informativo só aparece depois da correção de cadastro.
