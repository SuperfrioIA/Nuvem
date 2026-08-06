---
name: volumetria-v2-decisoes
description: Decisões fechadas da V2 de volumetria em 06/ago/2026 — métricas separadas por direção, sem tabela agregada, sem ano anterior, tipo de estoque como dimensão
metadata:
  type: project
---

Decisões da Maria em 06/08/2026, fechando a revisão da proposta V2. Plano completo em
[docs/proposta_v3_volumetria.md](../docs/proposta_v3_volumetria.md).

- **Direção = métricas separadas** (`peso_bruto_entrada` / `peso_bruto_saida`, e o
  mesmo par para valor e registros). Não entra coluna `direcao`. `total` e `saldo` são
  derivados na consulta.
- **Não criar `fato_volumetria_mensal`.** `medidas` já é o agregado mensal; o que falta
  é índice — não havia nenhum sobre `medidas` em 11 migrations.
- **Fonte oficial de saída: `SAIDA_MERCADORIAS`**, banda *Separado Fisicamente*. Ver
  [[layout-saida-mercadorias]].
- **Tipo de estoque entra como dimensão**, 4 valores: `CONGELADO`, `SECO`,
  `HORTIFRUTI`, `UTENSILIOS`. Ver [[operacao-e-tipo-estoque]].
- **`Operação` soma tudo**, como a V1 já faz — devolução e transferência interna
  continuam contando como entrada.
- **Só 2026.** Sem comparação com ano anterior, sem a família `ENTRADA_MERCADORIAS (UA)`,
  sem a volumetria do DW. Comparativo da tela é mês anterior.
- **Budget fora da V2.**
- **De-para novo:** `CWB3/001 → CWBIII`, `SANCA/025 → RMSPV`, `RJ/004-003 → RMRJ`.
  Todos 1:1 — ver [[filiais-catering-poc]].
- **Cockpit evolui `/cockpit` no lugar**, sem rota nova.
- **Frontend sem framework:** ECharts (já presente) + Tabulator via CDN para a matriz.
  React foi avaliado com protótipo e recusado — o visual não dependia dele.
- **Primeiro lote: de-para + índices.** Cadastro, não código.

**Why:** a proposta V2 foi escrita antes de olhar a fonte, e cinco premissas dela caíram
no levantamento de 06/08. Duas em particular invertem prioridade: metade dos arquivos
processados estava em pendência de de-para (cobertura, não visual, era o gargalo), e a
saída tem histórico desde out/2021 enquanto a entrada por item só existe em 2026 — ver
[[historico-datahub-por-familia]].

**How to apply:** antes de construir qualquer coisa da V2, ler o `proposta_v3` e não o
`proposta_v2` — a v2 fica como registro do raciocínio inicial. A decisão de somar tudo
em `Operação` precisa aparecer na conciliação com o Power BI **antes** de alguém
comparar os dois números, senão a ferramenta parece errada: devolução é 39% das linhas.
