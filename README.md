# Nuvem IA — camada de insights SuperFrio

Junta dados que hoje vivem em silos (sistemas via Pentaho, controles manuais via
SharePoint) numa **camada fina** de agregados e scores, e mostra tudo numa "nuvem" de
métricas interligadas que **acendem** quando algo foge do próprio padrão histórico.

**Status: fase de arquitetura — nenhum código construído ainda.**

## Documentos

| Doc | O quê |
|---|---|
| [docs/CONCEITO.md](docs/CONCEITO.md) | O problema, o núcleo da ideia e a escada de mecanismos de insight |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Desenho técnico fechado: conectores, schema, containers, deploy |
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
