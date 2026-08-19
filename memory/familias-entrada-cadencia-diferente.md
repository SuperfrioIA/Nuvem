---
name: familias-entrada-cadencia-diferente
description: ENTRADA_MERCADORIAS (item) e ENTRADA_MERCADORIAS (UA) são reexportadas em cadências diferentes — o mês corrente pode estar completo numa e defasado dez dias na outra
metadata:
  type: project
---

Medido em 17/ago/2026, montando a base de recebimento por UA. As duas famílias
de entrada da MESMA filial e da MESMA competência tinham fim de série
diferente:

| RMSPII/016, competência 2608 | Modificado no SharePoint | Vai até |
|---|---|---|
| `ENTRADA_MERCADORIAS` (grão de item) | 17/ago 12:30 | **17/08** |
| `ENTRADA_MERCADORIAS (UA)` (grão de pallet) | 10/ago | **07/08** |

Naquele dia foram reexportadas saída, guias, cortes, entregas, ocorrências,
estoque por lote e a entrada por **item** — a entrada por **UA** não. Quem
olhasse só o inventário (o arquivo `_2608` existe nas duas) concluiria que
agosto estava igual nas duas.

**Why:** a Maria sincronizou os dados e pediu pra conferir se dava pra ver "até
hoje". Dava — na família que a análise tinha acabado de deixar de lado. Sem
conferir o `lastModifiedDateTime` e o último dia DENTRO do arquivo, a base
sairia com agosto defasado em dez dias sem ninguém perceber, e o mês recente é
justamente o que a operação olha primeiro.

**How to apply:** antes de prometer que o mês corrente está completo, conferir
duas coisas por família (não por competência): o `lastModifiedDateTime` do
arquivo e o **último dia de `Solicitação` dentro dele**. Existir o arquivo da
competência não significa que ele foi reexportado. E **não emendar as duas
famílias** para tapar o buraco do mês corrente: uma linha do UA é um pallet e
uma do item é uma linha de item — emendar cria degrau falso exatamente no mês
mais recente. Se o mês corrente precisa estar fechado no UA, alguém precisa
reexportar do SLIN; é ação humana no WMS. Ver [[nao-ler-mes-parcial]],
[[layout-entrada-por-unidade]] e [[modo-laboratorio-poc]].
