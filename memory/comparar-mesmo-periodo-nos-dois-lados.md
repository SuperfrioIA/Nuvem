---
name: comparar-mesmo-periodo-nos-dois-lados
description: Em qualquer comparação entre duas fontes (Nuvem x Power BI, etc.), conferir que TODA linha da tabela usa o mesmo período dos dois lados — não só o total agregado
metadata:
  type: feedback
---

Ao montar a primeira comparação Nuvem x Power BI (ver
[[conciliacao-rmspii-primeira-passada]], 06/ago/2026), acertei o total agregado
(os dois lados em jan-jul/26) mas errei na tabela por cliente: usei o "Total"
do Power BI, que incluía agosto, contra o jan-jul da Nuvem. A Maria pegou:
"não faz sentido comparar até julho em um e até agosto em outro... precisa ser
comparação de manga com manga, e não banana com manga".

**Why:** é fácil acertar o número de destaque (o total) e deslizar nas linhas
de detalhe da mesma tabela, porque cada fonte tem seu próprio filtro de período
default (a Nuvem respondeu exatamente ao intervalo pedido; o print do Power BI
que eu tinha em mãos era "Total" = jan-ago, e não percebi a inconsistência até
ela apontar).
**How to apply:** antes de publicar qualquer tabela comparativa entre sistemas,
conferir linha por linha (não só o total) que o filtro de período é idêntico
dos dois lados. Se uma fonte só oferece o período errado (ex.: só tem "Total"
com um mês extra), **pedir um novo corte** em vez de inferir por subtração —
subtração a partir de números lidos de imagem/print carrega risco de erro que
some direto pro resultado errado.
