# Nuvem IA

Projeto interno SuperFrio (CSC). Leia antes de qualquer coisa:

1. [docs/V1_PLANO.md](docs/V1_PLANO.md) — **fonte única do status da V1** (blocos
   A–G / macro-lotes V1.0–V1.8, onde a construção está). Ler antes de codar;
   atualizar o status ao fechar um bloco.
2. [docs/V1_NUVEM_IA_DIRECIONAMENTO.md](docs/V1_NUVEM_IA_DIRECIONAMENTO.md) — o
   direcionamento completo da V1 (produto, arquitetura, regras, macro-lotes).
   Resumos operacionais: [docs/V1_ESCOPO.md](docs/V1_ESCOPO.md),
   [docs/V1_CRITERIOS_ACEITE.md](docs/V1_CRITERIOS_ACEITE.md),
   [docs/V1_ARQUITETURA.md](docs/V1_ARQUITETURA.md).
3. [MEMORY.md](MEMORY.md) + `memory/` — estado e decisões vivas do projeto (autoritativo).
4. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — desenho técnico da base (15/jul/2026),
   válido no que não conflita com o V1_ARQUITETURA.
5. Histórico (consultar, não é plano ativo): [docs/POC_ATUAL.md](docs/POC_ATUAL.md)
   (POC DataHub P0–P6, encerrada em 30/jul/2026), [docs/ENTREGA_POC.md](docs/ENTREGA_POC.md)
   (balanço, limitações e riscos), [docs/PLANO.md](docs/PLANO.md) (plano de produto
   0–11/R0–R3 — nenhum lote autorizado automaticamente) e
   [docs/HISTORICO.md](docs/HISTORICO.md) (prompts originais).

## Regras para IA

- Fase atual: **construção da V1 em blocos** (A, B e C feitos em 31/jul/2026;
  D em 02/ago/2026; E–G aguardam autorização). Não construir código sem pedido
  explícito da Maria. Há um **defeito aberto** herdado da reestruturação da
  fonte (V1_PLANO, seção "ABERTO") — ler antes de mexer em ingestão do DataHub.
- Antes de criar/alterar arquivos: apresentar plano em texto simples e aguardar OK
  explícito. "Beleza" vago não é OK.
- Commits **sem** co-autor Anthropic (nada de `Co-Authored-By`).
- Comunicação em português, direta, sem emojis.
- Padrões: skill `superfrio` (identidade visual) e `superfrio-trabalho` (forma de
  trabalhar — lotes, princípios técnicos, deploy Docker).
