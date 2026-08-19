---
name: nao-ler-mes-parcial
description: Medido em julho/2026: no mês pela metade o total erra pouco, mas 3 de 18 leituras por cliente trocam de sinal — cliente "em alta" fecha em queda
metadata:
  type: feedback
---

A mesma análise da RMSPII foi feita duas vezes: em 16/jul, com o mês na metade
(dias 1–16), e em 14/ago, com julho fechado. Comparando as duas na **mesma
extração unida**, o erro do recorte parcial não está onde se espera:

- **O total erra pouco:** variação do throughput contra junho dava −45,4% no
  parcial e fechou −40,7%.
- **O detalhe por cliente erra muito:** **3 de 18** leituras (cliente × direção)
  **trocaram de sinal**. CONVIDA REFEIÇÕES na entrada aparecia **+78,8%** e fechou
  **−22,3%** — 101,1 pontos de diferença. NOVITA na saída: +29,7% → −19,5%.
  Outras cinco mudaram mais de 20 pontos sem inverter.

**Why:** o instinto é confiar no detalhe e desconfiar do total, e aqui é o
contrário. Um recorte parcial preserva a ordem de grandeza do agregado (os grandes
clientes movimentam todo dia) mas destrói a variação dos clientes de cauda, cujo
movimento é concentrado em poucos dias do mês. Apresentar "CONVIDA +78,8%" para a
operação e depois ter que dizer "na verdade −22,3%" queima a credibilidade do painel
inteiro — e o número não estava errado, estava incompleto.

**How to apply:** ranking e variação por cliente só saem com mês fechado. Com mês
em andamento, mostrar o agregado e **suprimir** a coluna de variação por cliente, ou
marcá-la explicitamente como parcial com o número de dias decorridos. Vale para o
Cockpit e para a leitura do agente: o número de dias com movimento tem que viajar
junto com o número, sempre — jul/2026 teve 29 dias, jun/2026 teve 30 e jul/2025
teve 31, e comparar total contra total sem dizer isso já é meio caminho do erro.
Ver [[comparar-mesmo-periodo-nos-dois-lados]] e [[rmspii-julho-2026-sodexo]].
