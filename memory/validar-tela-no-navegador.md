---
name: validar-tela-no-navegador
description: Lote de tela só está verificado depois de abrir no navegador — no V2.5 isso achou 4 defeitos que revisão de código não pega, incluindo três filiais homônimas indistinguíveis
metadata:
  type: feedback
---

Receita que funcionou em 07/ago/2026 (lote V2.5, cockpit visual), na máquina da
Maria, sem tocar em produção:

1. Semear o Postgres de teste (`localhost:5433`) com dado plausível — várias
   unidades, várias competências, clientes + balde sem cliente, tipos de estoque.
2. Subir a app no host: `PYTHONPATH=<raiz>` e `DATABASE_URL=postgresql://nuvem:teste@localhost:5433/nuvem_teste`,
   `python -m uvicorn backend.main:app --port 8003`. O Python global do host tem
   uvicorn/fastapi/psycopg2.
3. `/cockpit` **redireciona para `/admin`** quando não autenticado — logar no
   `/admin` primeiro (a tela de login é aberta de propósito) e só então navegar.
4. Playwright: navegar, screenshot de página inteira, `browser_evaluate` para
   mexer nos filtros e ler o DOM, e `browser_console_messages` para provar que
   não há erro de JS.
5. Para conferir download sem baixar arquivo: interceptar `URL.createObjectURL`,
   capturar o Blob e ler `.text()`.

**Why:** os quatro defeitos que essa validação achou no V2.5 não apareciam em
revisão de código nenhuma. O pior: o seletor de filial listava só o *nome* do
cadastro, e RMSPII, RMSPIII e RMSPV se chamam todas "Barueri/SP" — três unidades
diferentes com rótulo idêntico. Os outros: logo invisível no tema escuro, rótulo
de categoria do ECharts cortado no meio da palavra ("Sem cliente identificado"
virava "m cliente identificado" — outro nome, não um nome abreviado), e drill de
cliente pequeno mostrando tudo como "0,0 mil t". Também foi só no navegador que
deu para confirmar que a expansão lazy da matriz (Tabulator dataTree +
`row.update({_children})`) funciona de verdade.

**How to apply:** lote que mexe em tela não fecha por `node --check` + leitura.
Abrir, clicar, ler o console. Ver [[suite-testes-local]] para o banco de teste e
[[sessao-autonoma-perguntas-no-final]] para o modo de trabalho.
