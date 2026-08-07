# V2.7 — Escala e operação — plano de execução e registro

Construído em 07/ago/2026, no mesmo modo autônomo autorizado pela Maria para o
V2.5/V2.6. Escopo de origem: `docs/proposta_v3_volumetria.md`, seção "V2.7 —
Escala e operação": cache de consulta com TTL curto e invalidação após
processamento; top N com bucket, paginação da matriz, limites de resposta; log de
consulta lenta; backup/restore com evidência.

## 1. Cache de consulta com TTL curto

`backend/services/cache_consulta.py` (novo). Uma carga do Cockpit dispara 8
requests, e as consultas de volumetria agregam `medidas` várias vezes cada
(`evolucao` chama `serie()` duas vezes; `resumo` chama `evolucao` três). O cache
tira o trabalho repetido do banco — e, por acerto, tira também a conexão do pool:
o `get_conn()` fica **dentro** da função que calcula, então acerto de cache não
pega conexão nenhuma.

**A garantia é uma só, e está declarada:** uma leitura pode estar desatualizada
no máximo `CACHE_CONSULTA_TTL` segundos (60 por padrão). Não existe "cache
coerente" aqui — coerência exigiria transação ou invalidação distribuída, e o
custo não se paga numa ferramenta interna cuja fonte é reprocessada algumas vezes
por dia.

Decisões que valem registrar:

- **Invalidação explícita para o que a pessoa vê acontecer**: `POST
  /datahub/processar`, `POST /admin/depara`, `DELETE /admin/depara/{id}`, `POST
  /admin/upload/processar` e `POST /admin/execucoes/{id}/reprocessar` chamam
  `cache_consulta.invalidar()`. Sem isso, o admin que acabou de cadastrar um
  de-para continuaria vendo a pendência por um minuto e concluiria que o cadastro
  não funcionou. A invalidação é **depois do commit** (fora do `with` da
  transação): invalidar dentro repovoaria o cache com o estado velho se ela
  abortasse. Os dois últimos entraram na revisão independente — o upload manual
  grava em `medidas` pelo `ingestao.gravar_agregados` e tinha ficado de fora,
  contra o princípio declarado aqui. `POST /admin/scores/recalcular` **não**
  invalida de propósito: ele escreve em `scores`, que nenhuma leitura do Cockpit
  consulta.
- **Pendência de cliente e de tipo de estoque não têm endpoint de resolução**
  (não existe cadastro de cliente pela API): elas saem do painel no próximo
  processamento, que invalida. O docstring do módulo citava "cadastrar cliente"
  como caminho invalidado — mencionava um endpoint inexistente, corrigido.
- **`scripts/processar_saida.py` roda em outro processo** (decisão D4 do V2.3),
  então não consegue invalidar — depois dele a tela pode ficar até um TTL
  mostrando o número anterior. É o mesmo bound de sempre; só vale saber que ali
  ele é o único mecanismo.
- **Erro não é cacheado.** A exceção sobe de dentro da função que calcula e a
  tradução para HTTP 400 continua na mesma borda de sempre.
- **Teto de entradas** (`CACHE_CONSULTA_TETO`, 256): a chave inclui os filtros,
  que são produto cartesiano (período × filial × cliente × tipo × grandeza ×
  direção × página). Sem teto o dicionário cresceria indefinidamente com quem
  brinca nos filtros. Expulsa primeiro o expirado, depois o mais velho.
- **Chave determinística com `sort_keys`**: sem isso dois dicts iguais com ordem
  de inserção diferente dariam chaves diferentes e o cache nunca acertaria.
- **Cálculo fora do lock**: consulta lenta não pode bloquear os outros requests.
  O preço é duas requisições simultâneas da mesma chave calcularem as duas —
  desperdício aceitável; o contrário serializaria a tela inteira.
- **`ttl=0` desliga o cache sem tirar o caminho do código** — é o que os testes
  **do próprio módulo de cache** usam. Ressalva levantada pela revisão
  independente: `_lido` não expõe `ttl`, então os testes de router rodam com o
  cache **ligado**. Nenhum teste hoje faz duas chamadas com os mesmos parâmetros
  e dados diferentes dentro de um mesmo teste (varrido), então não há falso
  verde — mas é armadilha para o próximo teste escrito, e a rede de segurança é
  o `invalidar()` do `banco_vazio`.
- O valor guardado é o próprio dict do serviço, **sem copiar**. Os routers só
  serializam; documentado que não se deve mutar o dict devolvido.

## 2. Limites de resposta e top N com bucket

- **`tamanho_pagina` da matriz** ganhou teto no `Query` (1..2000): valor fora da
  faixa vira 422 do FastAPI com a faixa na mensagem, nunca uma resposta gigante.
  O teto **é o mesmo** que a exportação CSV da tela usa
  (`MATRIZ_TETO_EXPORTACAO`) — se os dois divergissem, o botão Exportar tomaria
  422 justamente no caso que ele existe para atender.
- **`ranking` ganhou `limite` opcional (1..500) com BUCKET**, não top N puro:
  as linhas além do limite viram uma linha `Outros (N)` com a soma, mais
  `total_linhas` e uma limitação declarando o corte. Cortar sem bucket é o
  defeito clássico do ranking limitado — a diferença desaparece da tela como se
  não existisse; com bucket, a participação do bucket mais a das linhas visíveis
  cobre o total. **Ressalva de precisão** (revisão independente): cada
  `participacao_pct` é arredondado a 1 casa independentemente, então a soma pode
  dar 99,9 % ou 100,1 % — a propriedade é "nada foi descartado", não "a soma
  bate exatamente em 100,0".
- **A tela passou a pedir o top ao backend** (`limite=12` nos clientes) em vez de
  cortar com `slice()` e jogar o resto fora, e o título declara "top 12 de N". O
  bucket aparece com cor própria (é agrupamento, não uma linha real) e o tooltip
  diz "soma das linhas fora do top".
- **`unidades_fora_do_ranking` usa o ranking completo, não a página**: unidade
  que caiu no bucket *tem* linha, só não está visível — declará-la como "sem
  movimento no período" seria falso. Coberto por teste.

## 3. Log de consulta lenta

Extensão do middleware que já existia (Bloco G / G2), não um middleware novo:
acima de `LIMITE_CONSULTA_LENTA` segundos (1,5 por padrão) a requisição entra no
log como `WARNING`.

**Nomes dos parâmetros presentes, nunca os valores** — `cliente`/`filial` em
claro no log é exatamente o que o Bloco G/G2 tirou do access log do uvicorn.
Saber *quais* filtros estavam ativos basta para reproduzir; o valor a pessoa
informa depois, se precisar. 1,5s não é SLA: é o ponto em que a tela já parece
travada para quem clicou.

## 4. Backup/restore com evidência — **pendente da VM, declarado**

`scripts/backup.sh` e `scripts/restore.sh` existem desde o Bloco G/G1 e o runbook
está em `docs/DEPLOY.md`. O que o V2.7 pedia era **evidência de execução**, e ela
não pode ser produzida daqui: exige o stack `docker compose` da VM, com dado real.

Roteiro do ensaio, para rodar na VM (não executado):

1. `./scripts/backup.sh` e conferir o arquivo gerado em `backups/` (tamanho > 0,
   data de hoje).
2. `python3 scripts/totais_competencia.py antes.txt` — a foto dos totais.
3. Restaurar o dump **num banco de teste**, nunca sobre o de produção, e rodar
   `totais_competencia.py depois.txt` contra ele.
4. `diff antes.txt depois.txt` vazio é a evidência: o backup restaura o mesmo
   número, não só um arquivo que existe.
5. Anexar a saída dos quatro passos ao runbook.

Registrado como **pendência de execução na VM**, não como feito.

## 5. Validação

- **Suíte completa contra Postgres real: 596 passed, 0 failed** (container
  efêmero contra o `nuvem-teste-db` via WSL). Testes
  novos: `tests/test_cache_consulta.py` (9 casos, sem banco — acerto, ordem de
  chave irrelevante, chave distinta por parâmetro, `None` × ausente não
  colidindo, expiração, `ttl=0`, invalidação, erro não cacheado, teto) e 3 casos
  de ranking com bucket em `tests/test_volumetria.py`.
- `py_compile` em cada arquivo Python tocado; `node --check` no JS de
  `cockpit.html`.
- **Uma falha de isolamento achada e corrigida na própria rodada**: a suíte
  reprovou em `test_e2e_pipeline.py::test_pipeline_duas_filiais_nao_mistura_origem`,
  que **passa isolado**. Causa: o cache é singleton de módulo, e o `banco_vazio`
  zerava o schema sem zerar o cache — dois testes com os mesmos filtros e dados
  diferentes recebiam a resposta do primeiro. `tests/conftest.py` passou a chamar
  `cache_consulta.invalidar()` junto do `fechar_pool()` que já existia, pelo mesmo
  raciocínio. Registrado em `memory/cache-consulta-e-isolamento-de-teste.md`.
- **Não verificado nesta sessão:** o efeito do cache sob concorrência real (dois
  requests simultâneos da mesma chave) e o ganho de tempo medido na VM. O
  comportamento sob concorrência é o declarado no módulo (as duas calculam), não
  um bug — mas ninguém mediu.
- **Conhecido e não corrigido** (revisão independente, severidade baixa):
  `cache_consulta.estatisticas()` só é lido pelos testes — o operador não tem
  como saber na VM se o cache está ajudando. Expor num endpoint de diagnóstico
  fica para quando houver pergunta de desempenho real. E `atualizarSecaoGrandeza`
  no frontend não é sequenciada: dois cliques rápidos em "próxima →" podem deixar
  a página exibida atrás do estado, porque a resposta mais lenta vence a corrida.

## 6. Fora deste lote (declarado)

- Cache compartilhado entre processos (Redis ou tabela): o app roda num worker
  só; entre processos, só o TTL vale (ver seção 1).
- Índice novo em `medidas` além dos dois do V2.1: nenhuma consulta deste lote
  mostrou plano ruim que justificasse, e não houve `EXPLAIN` contra volume real.
- Gráfico do Laboratório no Cockpit — V2.8.
