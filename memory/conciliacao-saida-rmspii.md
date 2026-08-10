---
name: conciliacao-saida-rmspii
description: Conciliação da SAÍDA RMSPII (jan-jun/26) — gap de 8,1% com causa parcial; guia de saída cancelada/cortada tem peso ZERO na fonte (não mensurável); banda descartada; resíduo de ~3 kt segue aberto (P-9)
metadata:
  type: project
---

Medido em 10/ago/2026 (sessão autônoma), mesmo recorte da entrada: jan–jun/26,
peso bruto, RMSPII (pastas 001/015/016 ↔ CNPJ 06975242000187 no DW). Detalhe em
`docs/CONCILIACAO_POWERBI_V2.md` §3.2 e na planilha
`docs/Analise/saida/conciliacao_slin_x_dw.xlsx` (12 abas).

**Números:** Nuvem 85.150,1 t (leitura direta do SharePoint, 36 arquivos, banda
*Separado Fisicamente*) × DW 92.694,3 t (`fato.csv`, Expedição) → **gap 7.544,2 t
(8,1%)**; no líquido 6,9%. O banco da VM tinha 85.150,0 t — ingestão fiel.

**O que fechou:**
- **Banda (D-7) descartada com número:** Solicitado 86.251,4 / Atendido 84.394,3
  / Separado 85.150,1 t — 1,3% entre bandas contra 8,1% de gap.
- **O mecanismo "guia sem item" existe na saída** (402 canceladas + 125 cortadas
  integralmente em 001+016), **mas TODAS têm `Peso Líq.` = 0 na fonte** — na
  saída o peso nasce na separação; não há como medir a tonelagem cancelada, só
  contar. É a diferença estrutural contra a entrada (lá o cabeçalho tem peso).
- **Estimativa** (contagem × peso médio da guia efetiva do cliente): ≈ 3.014 t
  líq em 001+016 + ≈ 643 t extrapolando SODEXO/015 → ≈ 3,7 kt dos 7,5 kt.
  SAPORE fecha em ~104% (239 canc + 71 cortadas — maior cancelador, espelho da
  entrada).
- **Anomalia GR no DW (P-11):** Expedição da GR com bruto/líquido 1,109 contra
  1,022 na fonte e 1,022 no próprio DW na entrada — ≈ 1,1 kt do gap da GR é
  definição de peso bruto, não volume.

**O que segue aberto (P-9):** resíduo sistemático de ≈ 2,6–3,0 kt (≈ 3% do DW),
positivo nos seis meses: GR ≈ 1 kt, PIMENTA ≈ 0,6 kt (gap relativo 14–45% ao
mês), SODEXO ≈ 0,6 kt, CUCINARE ≈ 0,3 kt. Fechar exige extrato do DW no grão de
GSM ou o peso solicitado das guias canceladas/cortadas no WMS.

**Why:** sem este registro, a próxima passada tentaria de novo medir o cancelado
de saída pelas guias (peso é zero, não dá) ou culparia a banda (já descartada).
**How to apply:** qualquer comparação de saída usa a banda *Separado
Fisicamente* e trata cancelamento como CONTAGEM. Não somar "estimativa" como se
fosse medição. Ver [[conciliacao-rmspii-primeira-passada]] (entrada),
[[depara-filial-rmspii-dw]] (filiais) e [[layout-saida-mercadorias]] (bandas).
