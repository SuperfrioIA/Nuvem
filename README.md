# Nuvem IA — camada de insights SuperFrio

Junta dados que hoje vivem em silos (sistemas via Pentaho, controles manuais via
SharePoint) numa **camada fina** de agregados e scores, e mostra tudo numa "nuvem" de
métricas interligadas que **acendem** quando algo foge do próprio padrão histórico.

**Status: construção em lotes.** Lotes 1 (esqueleto/banco/upload manual), 3 (motor de
scores), 7/7.1 (de-para oficial + clientes de catering), 8 (modelos das 5 fontes
reais), 8.5 (catálogo de fontes) e R0–R3 (testes + Alembic, versionamento, linhagem,
catálogo semântico) feitos; deploy validado na VM em 20/jul/2026 (só o admin — a
nuvem/`index.html` é o Lote 5). **POC do canal SharePoint DataHub (Lotes P0–P6)
encerrada em 30/jul/2026** — balanço, limitações e riscos em
[docs/ENTREGA_POC.md](docs/ENTREGA_POC.md); escopo e status por lote em
[docs/POC_ATUAL.md](docs/POC_ATUAL.md). **Nenhum lote novo autorizado.** Ver
[docs/PLANO.md](docs/PLANO.md) (histórico do plano de produto) e a revisão
arquitetural em [docs/DIAGNOSTICO.md](docs/DIAGNOSTICO.md).

## Documentos

| Doc | O quê |
|---|---|
| [docs/POC_ATUAL.md](docs/POC_ATUAL.md) | Escopo e status por lote da POC DataHub (P0–P6, encerrada) |
| [docs/ENTREGA_POC.md](docs/ENTREGA_POC.md) | Balanço da POC: o que foi provado, limitações, obstáculos do dado, riscos |
| [docs/DEMO_POC.md](docs/DEMO_POC.md) | Roteiro de apresentação (~6 min), checklist e plano B |
| [docs/CONCEITO.md](docs/CONCEITO.md) | O problema, o núcleo da ideia e a escada de mecanismos de insight |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Desenho técnico fechado: conectores, schema, containers, deploy |
| [docs/FONTES_DATAHUB.md](docs/FONTES_DATAHUB.md) | Inventário das fontes do SharePoint DataHub |
| [docs/PILOTO.md](docs/PILOTO.md) | Escopo do piloto: Perdas × Volumetria × Ocupação |
| [docs/HISTORICO.md](docs/HISTORICO.md) | Os prompts originais da Maria e como o projeto se desenrolou |
| [MEMORY.md](MEMORY.md) | Índice da memória viva do projeto (autoritativo para IA) |

## Decisões-chave (resumo)

- App **separado** do Portal SuperFrio & IceStar (Receita 3 do Hub) — repo, banco e
  deploy próprios; o Hub só cadastra um card.
- Mesma VM do Conciliador/Portal, container à parte, **porta 8002**. Postgres próprio.
- **Conectores plugáveis**: upload manual + SharePoint (Graph API) na v1, alternáveis
  pelo painel admin; Pentaho depois, sem retrabalho.
- O dado bruto fica na fonte; a nuvem guarda só de-para + agregados + scores.

Rascunho visual do piloto (artefato v0.2):
<https://claude.ai/code/artifact/a8829925-077b-4414-994a-25a5eb984aeb>
