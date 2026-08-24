# Nuvem IA

Projeto interno SuperFrio (CSC). Leia antes de qualquer coisa:

1. [docs/V3_PLANO.md](docs/V3_PLANO.md) — **fonte única do status da V3, que é a
   fase atual** (lotes V3.0–V3.8, onde a construção está, o contrato fechado e
   as decisões abertas). Ler antes de codar; atualizar o status ao fechar um
   lote.
2. [docs/V2_PLANO.md](docs/V2_PLANO.md) — **fonte única do que a V2 entregou**
   (lotes V2.1–V2.8). **V2 congelada** — é o que está em produção na VM, e não
   se mexe mais nela (Maria, 24/ago/2026). Especificação:
   [docs/proposta_v3_volumetria.md](docs/proposta_v3_volumetria.md) — o nome
   diz "v3" por acidente histórico, mas é a especificação da **V2**; a
   `proposta_v2_...` é só registro do raciocínio inicial.
3. [docs/V1_PLANO.md](docs/V1_PLANO.md) — **fonte única do que a V1 entregou**
   (blocos A–G / macro-lotes V1.0–V1.8) e das limitações que ela declarou. V1
   fechada e implantada.
4. [docs/V1_NUVEM_IA_DIRECIONAMENTO.md](docs/V1_NUVEM_IA_DIRECIONAMENTO.md) — o
   direcionamento completo da V1 (produto, arquitetura, regras, macro-lotes).
   Resumos operacionais: [docs/V1_ESCOPO.md](docs/V1_ESCOPO.md),
   [docs/V1_CRITERIOS_ACEITE.md](docs/V1_CRITERIOS_ACEITE.md),
   [docs/V1_ARQUITETURA.md](docs/V1_ARQUITETURA.md).
5. [MEMORY.md](MEMORY.md) + `memory/` — estado e decisões vivas do projeto (autoritativo).
6. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — desenho técnico da base (15/jul/2026),
   válido no que não conflita com o V1_ARQUITETURA.
7. Histórico (consultar, não é plano ativo): [docs/POC_ATUAL.md](docs/POC_ATUAL.md)
   (POC DataHub P0–P6, encerrada em 30/jul/2026), [docs/ENTREGA_POC.md](docs/ENTREGA_POC.md)
   (balanço, limitações e riscos), [docs/PLANO.md](docs/PLANO.md) (plano de produto
   0–11/R0–R3 — nenhum lote autorizado automaticamente) e
   [docs/HISTORICO.md](docs/HISTORICO.md) (prompts originais).

## Regras para IA

- Antes de iniciar processos, rodar testes ou validar algo localmente, ler
  `docs/EXECUCAO_LOCAL.md` — fonte oficial do método real de subir, testar e
  encerrar o projeto nesta máquina.
- Fase atual: **construção da V3 — volumetria de catering lendo o DW Oracle**
  (aberta em 24/ago/2026; **V3.0 (contrato + schema) e V3.1 (carregador) feitos
  em 24/ago**; V3.2 em diante não autorizado — status em `docs/V3_PLANO.md`). O
  código novo vive em `catering/`; a fonte é o DW, **não** o SharePoint DataHub.
  Não construir código sem pedido explícito da Maria, e a autorização é
  **por lote**.
- **A V2 está congelada** (Maria, 24/ago/2026): não se mexe mais nela. Ela
  continua sendo o que está em produção na VM, então `backend/`, `frontend/` e
  as migrations até a 0018 ficam **intactos** — a V3 não altera nem importa
  código de lá. Regra reaproveitada entra por **cópia com teste próprio**.
  Duas falhas conhecidas da suíte (`test_volumetria.py` e
  `test_volumetria_router.py`, siglas antigas depois do `e5805b3`) são V2 e
  ficam como estão. O antigo só sai da VM depois da tela nova de pé.
- Contexto histórico do DataHub (**não é instrução para a V3**, que não o usa):
  se algum dia for preciso mexer na ingestão do DataHub, ler a seção "Lote de
  correção" do V1_PLANO — a identidade do arquivo é o `item_id` e a origem é
  `unidade/filial` (`RMSPII/001`), nunca o nome nem o código de filial sozinho.
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
