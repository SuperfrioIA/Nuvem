---
name: confirmar-sigla-antes-de-citar-filial
description: Antes de citar dado "da RMSPII/III/IV" ou recomendar qual filial focar, confirmar código-sigla em memory/filiais-catering-poc.md — não assumir pela memória solta
metadata:
  type: feedback
---

Errei ao recomendar "focar na RMSPII/016" pra conciliação com o Power BI
(06/ago/2026): **016 é RMSPIV, não RMSPII.** O mapa correto —
`001 → RMSPII`, `015 → RMSPIII`, `016 → RMSPIV` — já estava em
[[filiais-catering-poc]]. Os números que citei como "já quantificados" (devolução
39% das linhas, concentração SAPORE ~81%) são da filial `016`, ou seja, da
**RMSPIV** — não da RMSPII. A Maria corrigiu.

**Why:** as siglas RMSPII/III/IV soam parecidas e a controladoria enxerga as três
juntas como um único grupo em conversa de negócio, mas os códigos de filial e as
siglas oficiais são 1:1 e fixos (`filiais_datahub.SIGLA_POR_CODIGO`). Citar
"RMSPII/016" mistura duas unidades diferentes e pode levar a puxar/comparar dado
da unidade errada.
**How to apply:** antes de citar um número "da RMSPII/RMSPIII/RMSPIV" ou de
recomendar em qual filial focar um levantamento (conciliação, amostra, etc.),
checar a tabela de [[filiais-catering-poc]] pra confirmar código↔sigla — nunca
assumir pela lembrança de qual filial "parece" ser a maior ou a mais citada.
