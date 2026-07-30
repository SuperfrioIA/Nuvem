---
name: concentracao-sapore-016
description: A SAPORE é ~81% da filial 016 — o KPI de valor alto dela é real, já conferido, não reinvestigar
metadata:
  type: project
---

Na competência 2026-07 da filial 016 (`ENTRADA_MERCADORIAS_016_2607`, conferido em
30/jul/2026), a SAPORE responde por:

- 6.032 de 8.411 linhas — 71,7%
- 1.273.705 de 1.571.339 volumes — 81,1%
- 3.460.757 de 4.281.727 kg — 80,8%
- R$ 29.643.496,98 de R$ 36.649.308,72 — 80,9%

A concentração aparece igual nas quatro medidas, e o preço médio da SAPORE é R$ 8,57/kg
contra R$ 8,56/kg do arquivo inteiro — ela não está inflada por mercadoria caríssima, o
valor é alto porque o peso é alto. A filial 016 é essencialmente um armazém SAPORE.
Comparação: PIMENTA VERDE tem R$ 20,24/kg mas só 3% do peso.

Não há nota gigante: a maior guia de entrada da SAPORE é R$ 567.198,36 (1,9% do total
dela); 50% do valor vem de 98 guias, 80% de 259. São 694 guias em 25 dias — ~28 por dia,
R$ 1,19 mi/dia, ~R$ 42,7 mil por guia.

Detalhe de definição em aberto: o card "Valor total movimentado" soma entrada **e**
devolução. Na 016/2607 são 2.246 linhas de `DEVOLUCAO DE MERCADORIAS (SEM NF-E)` valendo
R$ 573.506,14 (R$ 481.711,12 da SAPORE) — 1,6% do total. Sem devolução, a SAPORE seria
R$ 29.161.785,86. E o rótulo pode ser lido como faturamento SuperFrio, quando é o valor
da mercadoria declarado nas notas dos clientes.

**Why:** o número da SAPORE no painel de KPIs assusta quem vê pela primeira vez. Foi
conferido do zero (download próprio do Graph, recálculo fora do backend, cruzamento com
GUIAS_ENTRADA) e está correto — não precisa refazer.
**How to apply:** se o assunto voltar, responder que já foi validado e apontar para aqui.
Antes de apresentar o painel, decidir com a Maria se devolução entra no valor movimentado
e se o rótulo do card muda. Ver [[chaves-nf-entrada-datahub]].
