# V2.4 — Consultas de volumetria sob `/cockpit/` — plano de execução

Autorizado pela Maria em 07/ago/2026 para planejar e construir, mesmo com a
verificação da V2.3 ainda pendente contra Postgres real (decisão explícita
dela, registrada em `docs/V2_PLANO.md`). Especificação de origem:
`docs/proposta_v3_volumetria.md`, seção "V2.4 — Consultas de volumetria", mais
os itens que o V2.3 explicitamente empurrou pra cá (tabela "Fora do lote" de
`docs/V2_3_PLANO_EXECUCAO.md`):

- `clientes_atendidos` somando as duas direções (D5 do V2.3);
- balde "sem cliente identificado" da **saída** (RMSPV) exibido (D5.1 do V2.3);
- as quatro consultas de volumetria (`resumo`, `evolução`, `ranking`, `matriz`).

Este lote é só backend (endpoints + serviço). Desenho visual, Tabulator,
tema claro/escuro e "dois rankings lado a lado na tela" são V2.5
(`docs/proposta_v3_volumetria.md`, seção V2.5) — não construir aqui.

## Mapeamento do estado atual

- `backend/services/serie_datahub.py` já tem `resolver_filial`,
  `resolver_cliente`, `parse_competencia`, `metrica_info`,
  `exigir_metrica_aditiva`, `resolver_tipo_estoque`, `filtros_sql` (WHERE
  reaproveitável em qualquer query sobre `medidas`) e `serie()` (mensal +
  anual + acumulado de UMA métrica). Nada disso muda de assinatura.
- `backend/services/cockpit.py` tem `resumo()`, `comparar_filiais()`,
  `comparar_clientes()`, `qualidade()` — todos de UMA métrica por vez, sem
  filtro de `tipo_estoque`. **Não tocar**: continuam servindo
  `/cockpit/resumo`, `/cockpit/comparacao/*`, `/cockpit/qualidade` como hoje,
  inclusive pro gráfico atual do `cockpit.html`.
- `/datahub/serie` (`backend/routers/datahub.py`) é a única rota pública que
  usa `serie_datahub.serie()` diretamente. Único consumidor no frontend:
  `cockpit.html:446`.
- Métricas existentes: `peso_bruto_entrada`/`peso_bruto_saida`,
  `valor_mercadoria_entrada` (sem par — decisão D1 do V2.3, a fonte
  `SAIDA_MERCADORIAS` não tem coluna de valor em nenhuma unidade),
  `registros_entrada`/`registros_saida`.
- Escopo temporal misto: `peso_bruto_saida`/`registros_saida` só existem a
  partir de `COMPETENCIA_MINIMA_SAIDA = 2026-01` (decisão D3 do V2.3);
  `peso_bruto_entrada` tem histórico desde antes disso.

## Decisões deste lote

| # | Decisão |
|---|---|
| **E1** | Módulo novo `backend/services/volumetria.py` (não crescer `cockpit.py`) — a forma dos dados é diferente o bastante (par de direções, não métrica única) pra justificar arquivo próprio, mesmo padrão de `saida_mercadorias.py` ter nascido separado de `entrada_mercadorias.py`. |
| **E2** | Conceito de **grandeza**: `peso`, `registros`, `valor` — cada uma mapeia pro par de métricas (entrada, saída\|None). `valor` não tem par; devolve `saida=None`, `total=entrada`, `saldo=None`, com limitação declarada. Nunca inventa saída pra grandeza que não tem. |
| **E3** | **`total = entrada + saída`** (throughput do período) e **`saldo = entrada − saída`** (variação líquida — positivo acumula estoque, negativo reduz). **Assunção a confirmar com a Maria** — é a leitura mais comum de "saldo" em operação logística, mas ninguém validou esse nome/fórmula com ela ainda. |
| **E4** | Escopo temporal misto tratado por **mês**, não só por resposta inteira: mês anterior a `COMPETENCIA_MINIMA_SAIDA` fica com `saida=None`/`total=None`/`saldo=None` (fora de escopo, **não é zero** — declarar `null` evita a leitura errada de "não teve saída esse mês" quando na verdade "não medimos saída nesse mês"). Mês dentro do escopo sem linha na fonte vira `0.0` de verdade. Acumulado/ranking/matriz somam só os meses dentro do escopo e declaram uma limitação quando o intervalo pedido cruza a fronteira de 2026. |
| **E5** | `/cockpit/volumetria/evolucao` **substitui** `/datahub/serie` (rota antiga removida, não convivem as duas). Não é mais "uma métrica por vez": recebe `grandeza` e devolve `mensal`/`anual`/`acumulado` já com entrada/saída/total/saldo — usa `serie_datahub.serie()` duas vezes por trás (uma por direção) e funde os resultados; não duplica SQL. `clientes_atendidos` **não migra** pra cá (não é uma grandeza com par entrada/saída — é contagem distinta, tratada à parte no `/resumo`, ver E6). `serie_datahub.serie()` continua existindo sem mudança nenhuma (ainda usada por `cockpit.py` e agora também por dentro de `volumetria.py`). |
| **E6** | `/cockpit/volumetria/resumo` é o payload agregado de visão geral: as três grandezas acumuladas no período, mais `clientes_atendidos` **com as duas leituras lado a lado** (`entrada`: só entrada, driver atual; `uniao`: `COUNT(DISTINCT cliente_id)` sobre `registros_entrada` **e** `registros_saida` juntos) e o balde "sem cliente identificado" das duas direções (entrada já existia; saída é novo, mesma lógica de `_balde_sem_cliente_entrada` generalizada, sem `valor_brl` porque a saída não tem métrica de valor). Omite o bloco de clientes quando há filtro de `cliente` (mesma regra que `cockpit.resumo()` já usa) ou de `tipo_estoque` (contagem distinta não filtra por tipo — mesma regra do `serie()` atual). |
| **E7** | `/cockpit/volumetria/ranking?grandeza=&dimensao=unidade\|cliente` — ranking com entrada/saída/total/saldo/participação por linha, usando `filtros_sql` pra montar o `WHERE` (reaproveitado, não duplicado) com `GROUP BY` na dimensão. `dimensao=unidade` não aceita filtro de `filial` (seria rankear uma unidade sozinha); `dimensao=cliente` não aceita filtro de `cliente`, pelo mesmo motivo — mesma convenção que `comparar_filiais`/`comparar_clientes` já seguem hoje. **Endpoint novo, adicional** — não substitui `/cockpit/comparacao/filiais\|clientes` (que continuam servindo o gráfico atual de uma métrica só; "dois rankings lado a lado" na tela é V2.5). |
| **E8** | `/cockpit/volumetria/matriz?grandeza=&direcao=entrada\|saida\|total\|saldo&dimensao=unidade\|cliente&pagina=&tamanho_pagina=` — pivô dimensão × competência da direção escolhida, paginado, linhas ordenadas pelo total da direção decrescente. `direcao=saida\|total\|saldo` pedida numa grandeza sem par de saída é erro claro (400), não silêncio. |
| **E9** | `tipo_estoque` é filtro opcional em `evolucao`, `ranking` e `matriz` (reaproveita `resolver_tipo_estoque`); em `resumo` filtra as três grandezas normalmente mas desliga o bloco de clientes (E6). |

## Fora deste lote (adiado, registrado pra não reabrir a pergunta)

- Qualquer desenho visual, gráfico combinado entrada×saída×saldo, Tabulator,
  tema — **V2.5**.
- Trocar `/cockpit/comparacao/filiais\|clientes` por `/volumetria/ranking` no
  `cockpit.html` atual — o gráfico de hoje continua como está; a tela nova é
  V2.5.
- Cache/TTL, paginação com limite de segurança agressivo, log de consulta
  lenta — **V2.7**.

## Testes

- `tests/test_volumetria.py` (novo) — regra de negócio contra `cursor`,
  mesmo padrão de `test_cockpit.py`: grandeza com e sem par, escopo temporal
  misto (mês fora de escopo vira `null`, dentro vira `0.0`), ranking por
  unidade e por cliente com "Sem cliente identificado", matriz com paginação
  e direção inválida pra grandeza sem par, resumo com balde das duas direções
  e `clientes_atendidos` lado a lado.
- `tests/test_serie_datahub.py` — teste novo pra `_balde_sem_cliente_saida`
  (mirror do de entrada, sem `valor_brl`) e pra contagem de clientes unida.
- `tests/test_volumetria_router.py` (novo) — só autenticação e encaixe HTTP,
  mesmo padrão de `test_cockpit_router.py` (regra de negócio não duplica
  aqui).
- `tests/test_datahub_router.py` — remove os testes de `GET /serie` (rota
  deixou de existir).

## Ordem de execução

1. `serie_datahub.py`: generalizar `_balde_sem_cliente_entrada` num helper
   comum + `_balde_sem_cliente_saida`; contagem unida de `clientes_atendidos`.
2. `backend/services/volumetria.py`: `evolucao`, `resumo`, `ranking`,
   `matriz`.
3. `backend/routers/cockpit.py`: as quatro rotas novas.
4. `backend/routers/datahub.py`: remove `/serie`.
5. `frontend/cockpit.html`: troca a UMA linha que chama `/datahub/serie` pra
   `/cockpit/volumetria/evolucao?grandeza=...`, mapeando o valor atual do
   seletor (`peso_bruto_entrada`→`peso`, `valor_mercadoria_entrada`→`valor`);
   ajusta `renderizarSerie`/`renderizarVariacao` pra ler `.entrada` em vez de
   `.valor` e `.unidade` em vez de `.metrica.unidade` — **mesmo visual de
   hoje**, só aponta pro endpoint novo (redesenho é V2.5).
6. Testes (seção acima).
7. `docs/V2_PLANO.md`: status do lote.
