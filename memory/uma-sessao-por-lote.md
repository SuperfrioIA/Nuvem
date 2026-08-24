---
name: uma-sessao-por-lote
description: Maria (24/ago/2026) — a partir da V3, cada lote roda numa sessão própria do Claude Code, não todos na mesma conversa
metadata:
  type: feedback
---

Ao autorizar o V3.0 em 24/ago/2026, a Maria pediu: *"depois nas próximas
tarefas precisamos abrir outras sessões, para trabalharmos por lote para melhor
eficiência."*

**Why:** a conversa que decidiu a V3 acumulou muita coisa que o lote seguinte
não precisa — a discussão de artefato x aplicação, o cruzamento com o
`fato.csv`, o e-mail para a Valcann, o desenho da legenda-filtro do artefato.
Carregar isso para dentro de um lote de construção gasta contexto e mistura
assuntos. Sessão nova por lote entra com o contexto certo: o `CLAUDE.md`, o
`docs/V3_PLANO.md` e a `memory/`, que são justamente as fontes que existem para
isso.

**How to apply:**
1. **Um lote, uma sessão.** Ao fechar um lote, atualizar o `V3_PLANO.md` (é o
   contrato de entrada do lote seguinte) antes de encerrar — quem abrir a
   próxima sessão lê de lá, não do histórico da conversa.
2. **O que precisa sobreviver entre sessões vai para arquivo versionado**, não
   para a memória da conversa: decisão em `V3_PLANO.md`, aprendizado
   transversal em `memory/`. Vale a mesma regra de [[v3-recomeca-nao-refatora]].
3. **Decisão aberta é numerada no plano** (A-1, A-2, ...), para a sessão nova
   saber o que ainda falta sem precisar reler conversa.
4. Não vale para conversa de decisão e brainstorm — essa continua sendo uma só,
   e é onde o escopo do lote é fechado antes de abrir a sessão de construção.
