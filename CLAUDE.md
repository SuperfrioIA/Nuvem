# Nuvem IA

Projeto interno SuperFrio (CSC). Leia antes de qualquer coisa:

1. [docs/POC_ATUAL.md](docs/POC_ATUAL.md) — dono único do escopo ativo e do status
   dos lotes P0–P6 da POC SharePoint DataHub (onde a construção parou). Ler antes de
   codar; marcar o status ao fechar um lote.
2. [MEMORY.md](MEMORY.md) + `memory/` — estado e decisões vivas do projeto (autoritativo).
3. [docs/PLANO.md](docs/PLANO.md) — histórico do plano de produto em lotes (0–10,
   R0–R3); nenhum lote daqui é autorizado automaticamente — ver `docs/POC_ATUAL.md`.
4. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — desenho técnico fechado.
5. [docs/HISTORICO.md](docs/HISTORICO.md) — os prompts originais que desenrolaram o
   projeto (contexto completo da conversa de origem).

## Regras para IA

- Fase atual: **construção em lotes** (deploy validado na VM em 20/jul/2026). Não
  construir código sem pedido explícito da Maria.
- Antes de criar/alterar arquivos: apresentar plano em texto simples e aguardar OK
  explícito. "Beleza" vago não é OK.
- Commits **sem** co-autor Anthropic (nada de `Co-Authored-By`).
- Comunicação em português, direta, sem emojis.
- Padrões: skill `superfrio` (identidade visual) e `superfrio-trabalho` (forma de
  trabalhar — lotes, princípios técnicos, deploy Docker).
