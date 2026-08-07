---
name: cache-consulta-e-isolamento-de-teste
description: O cache de consulta do V2.7 é singleton de módulo — zerar o schema no teste precisa zerar o cache junto, senão a contaminação aparece longe da causa
metadata:
  type: feedback
---

`backend/services/cache_consulta.py` (lote V2.7, 07/ago/2026) é um dicionário de
módulo chaveado **só pelos parâmetros da consulta** — nada no estado do banco
entra na chave. Isso é correto em produção (a garantia declarada é "desatualizado
no máximo um TTL"), mas quebra o isolamento da suíte: dois testes que chamam o
mesmo endpoint com os mesmos filtros e dados diferentes recebem a resposta do
primeiro.

O `banco_vazio` do `tests/conftest.py` agora chama `cache_consulta.invalidar()`
junto do `fechar_pool()` que já existia — **é o mesmo raciocínio**: teste que zera
o schema não pode herdar estado de processo do teste anterior.

**Why:** sem isso a suíte falhou em `test_e2e_pipeline.py::test_pipeline_duas_
filiais_nao_mistura_origem`, que **passa isolado**. A falha aparece num arquivo
que não tem nada a ver com cache, e o teste que contaminou nem falha — 6 minutos
de suíte para descobrir que a causa estava em outro lugar.

**How to apply:** ao acrescentar qualquer estado de processo (cache, pool,
contador, cliente HTTP reaproveitado), zerá-lo no `banco_vazio`. E antes de
investigar teste que falha na suíte e passa isolado, suspeitar de estado de
módulo antes de suspeitar do teste. Ver [[suite-testes-local]] para o outro modo
de falha enganoso (container do Postgres derrubado pelo Docker Desktop no meio da
rodada — o keepalive do WSL expira e a suíte trava somando timeouts).
