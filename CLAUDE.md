# Nuvem IA

Projeto interno SuperFrio (CSC). Leia antes de qualquer coisa:

1. [docs/V2_PLANO.md](docs/V2_PLANO.md) — **fonte única do status da V2** (lotes
   V2.1–V2.8, onde a construção está). Ler antes de codar; atualizar o status ao
   fechar um lote. Especificação e decisões fechadas:
   [docs/proposta_v3_volumetria.md](docs/proposta_v3_volumetria.md) — a
   `proposta_v2_...` é só registro do raciocínio inicial, não é plano.
2. [docs/V1_PLANO.md](docs/V1_PLANO.md) — **fonte única do que a V1 entregou**
   (blocos A–G / macro-lotes V1.0–V1.8) e das limitações que ela declarou. V1
   fechada e implantada; o que está sendo construído agora vive no V2_PLANO.
3. [docs/V1_NUVEM_IA_DIRECIONAMENTO.md](docs/V1_NUVEM_IA_DIRECIONAMENTO.md) — o
   direcionamento completo da V1 (produto, arquitetura, regras, macro-lotes).
   Resumos operacionais: [docs/V1_ESCOPO.md](docs/V1_ESCOPO.md),
   [docs/V1_CRITERIOS_ACEITE.md](docs/V1_CRITERIOS_ACEITE.md),
   [docs/V1_ARQUITETURA.md](docs/V1_ARQUITETURA.md).
4. [MEMORY.md](MEMORY.md) + `memory/` — estado e decisões vivas do projeto (autoritativo).
5. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — desenho técnico da base (15/jul/2026),
   válido no que não conflita com o V1_ARQUITETURA.
6. Histórico (consultar, não é plano ativo): [docs/POC_ATUAL.md](docs/POC_ATUAL.md)
   (POC DataHub P0–P6, encerrada em 30/jul/2026), [docs/ENTREGA_POC.md](docs/ENTREGA_POC.md)
   (balanço, limitações e riscos), [docs/PLANO.md](docs/PLANO.md) (plano de produto
   0–11/R0–R3 — nenhum lote autorizado automaticamente) e
   [docs/HISTORICO.md](docs/HISTORICO.md) (prompts originais).

## Regras para IA

- Fase atual: **construção da V2 — volumetria integrada e cockpit visual**
  (aberta em 06/ago/2026; lote V2.1 em construção — ver `docs/V2_PLANO.md`). A
  V1 está concluída e implantada (Blocos A–G, entre 31/jul e 04/ago/2026, deploy
  do Bloco G na VM em 05/ago/2026). Não construir código sem pedido explícito da
  Maria, e a autorização é **por lote**. Antes de mexer em
  ingestão do DataHub, ler a seção "Lote de correção" do V1_PLANO: a
  identidade do arquivo é o `item_id` e a origem é `unidade/filial`
  (`RMSPII/001`), nunca o nome nem o código de filial sozinho.
- **Nada é alterado no SharePoint do DataHub** (Maria, 06/ago/2026). O cliente
  Graph é somente leitura por construção e a suíte tem guarda pra isso; a regra
  vale também pra qualquer escrita pelo sistema de arquivos — nunca rodar com o
  diretório de trabalho dentro da pasta sincronizada do DataHub.
- Antes de criar/alterar arquivos: apresentar plano em texto simples e aguardar OK
  explícito. "Beleza" vago não é OK.
- Commits **sem** co-autor Anthropic (nada de `Co-Authored-By`).
- Comunicação em português, direta, sem emojis.
- Padrões: skill `superfrio` (identidade visual) e `superfrio-trabalho` (forma de
  trabalhar — lotes, princípios técnicos, deploy Docker).
