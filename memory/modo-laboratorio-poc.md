---
name: modo-laboratorio-poc
description: A partir de 17/ago/2026, rodadas de relatório/view/artefato rodam como POC de laboratório — Claude como motor de exploração, sem tocar ou depender do código do V2 já construído
metadata:
  type: feedback
---

Em 17/ago/2026 a Maria decidiu que, dado o ritmo de mudança das regras de
negócio na V2 (RJ sem coluna de cliente, guia de entrada cancelada, mês
parcial, queda da SODEXO — cada uma exigiu retrabalho de código porque a regra
só ficou clara depois de olhar o dado real), as próximas rodadas de relatório,
view e artefato rodam como POC de laboratório: o Claude é o motor de cálculo e
exploração, não o backend determinístico.

**Why:** fixar lógica em código enquanto ela ainda está mudando quase todo dia
é retrabalho caro. A regra só deve virar backend depois de estabilizar — mas a
V2 tem como objetivo central um número auditável e reprodutível até o arquivo
de origem (`docs/V2_PLANO.md`), e isso exige determinismo que um LLM não
garante sozinho fazendo a conta. Por isso o modo laboratório não substitui o
backend, ele antecede: explora e valida a regra antes dela ser formalizada.

**How to apply**, em toda sessão nesse modo:
1. Não altera código de produção (`backend/`, migrations, frontend do
   cockpit) nem nenhum arquivo já commitado do V2. Regra descoberta que virar
   candidata a backend entra como proposta de lote no `V2_PLANO.md` — só entra
   em código com autorização explícita da Maria, por lote, como já é a norma.
2. Lê a fonte crua (DataHub via Graph somente leitura, DW/`fato.csv`,
   exports), não as tabelas/endpoints que o V2 já calculou — pra não herdar
   sem querer uma limitação do código atual dentro de uma exploração que devia
   ser livre. Comparar com o que o cockpit já mostra é válido como conciliação
   explícita, não como fonte.
3. Script, relatório e view desse modo não entram no código do produto —
   ficam como documento, artifact publicado, ou script solto fora de
   `backend/`/`frontend/`, nunca misturado com o que é produto.
4. Continua valendo [[sharepoint-datahub-somente-leitura]]: leitura somente,
   nunca escrita, nunca diretório de trabalho dentro da pasta sincronizada.
5. Combinado fechado numa conversa sem lote formal (não é V2.x) — registrado
   aqui pra não precisar reexplicar em sessão nova; o `CLAUDE.md` aponta pra
   `memory/` como leitura obrigatória antes de qualquer coisa.
