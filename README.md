# Nuvem IA — camada de insights SuperFrio

Conecta fontes diferentes (SharePoint DataHub, exports do DW via upload, futuramente
Pentaho/API), entende suas estruturas, padroniza conceitos, permite explorar
oportunidades com rastreabilidade e publica indicadores corporativos confiáveis em
uma visão única por período, filial e cliente.

**Status: construção da V1 de produção, em blocos.** A POC da integração SharePoint
DataHub foi concluída com sucesso em 30/jul/2026 (balanço em
[docs/ENTREGA_POC.md](docs/ENTREGA_POC.md)); a partir daí o projeto entrou na
construção da V1. **Blocos A (V1.0 — transição para produto) e B (V1.1 catálogo
semântico + V1.2 compatibilidade de medidas) feitos em 31/jul/2026; Blocos C–G
aguardam autorização.** Fonte única do status:
[docs/V1_PLANO.md](docs/V1_PLANO.md).

## Documentos ativos (V1)

| Doc | O quê |
|---|---|
| [docs/V1_PLANO.md](docs/V1_PLANO.md) | **Fonte única do status da V1** (blocos A–G / macro-lotes V1.0–V1.8) |
| [docs/V1_NUVEM_IA_DIRECIONAMENTO.md](docs/V1_NUVEM_IA_DIRECIONAMENTO.md) | O direcionamento completo da V1 (produto, arquitetura, regras) |
| [docs/V1_ESCOPO.md](docs/V1_ESCOPO.md) | Resumo do escopo e decisões fixadas da V1 |
| [docs/V1_CRITERIOS_ACEITE.md](docs/V1_CRITERIOS_ACEITE.md) | Critérios de aceite por macro-lote |
| [docs/V1_ARQUITETURA.md](docs/V1_ARQUITETURA.md) | Arquitetura da V1 (base herdada + estrutura-alvo) |
| [docs/V1_RELATORIO_VERIFICACAO.md](docs/V1_RELATORIO_VERIFICACAO.md) | Verificação independente de cada bloco |
| [docs/FONTES_DATAHUB.md](docs/FONTES_DATAHUB.md) | Inventário das fontes do SharePoint DataHub (vivo — obstáculos e junções) |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Desenho técnico da base (conectores, schema, containers, deploy) |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Runbook de deploy na VM (inclui variáveis do Graph e migrations) |
| [MEMORY.md](MEMORY.md) | Índice da memória viva do projeto (autoritativo para IA) |

## Histórico (consultar; não é plano ativo)

| Doc | O quê |
|---|---|
| [docs/POC_ATUAL.md](docs/POC_ATUAL.md) | POC DataHub (P0–P6) — escopo e status por lote, **encerrada em 30/jul/2026** |
| [docs/ENTREGA_POC.md](docs/ENTREGA_POC.md) | Balanço da POC: o que foi provado, limitações, obstáculos do dado, riscos |
| [docs/DEMO_POC.md](docs/DEMO_POC.md) | Roteiro da apresentação da POC |
| [docs/PLANO.md](docs/PLANO.md) | Plano de produto em lotes (0–11, R0–R3) — nenhum lote autorizado automaticamente |
| [docs/DIAGNOSTICO.md](docs/DIAGNOSTICO.md) | Revisão arquitetural de 22/jul/2026 (R0–R3 implementados) |
| [docs/PILOTO.md](docs/PILOTO.md) | Escopo do piloto catering RMSP |
| [docs/CONCEITO.md](docs/CONCEITO.md) | O problema e o núcleo da ideia |
| [docs/HISTORICO.md](docs/HISTORICO.md) | Os prompts originais da Maria e como o projeto se desenrolou |

## Decisões-chave (resumo)

- App **separado** do Portal SuperFrio & IceStar (Receita 3 do Hub) — repo, banco e
  deploy próprios; o Hub só cadastra um card.
- Mesma VM do Conciliador/Portal, container à parte, **porta 8002**. Postgres próprio.
- **SharePoint DataHub é fonte permanente** (29/jul/2026), somente leitura, convivendo
  com o upload manual — fontes diferentes, mesma camada fina.
- O dado bruto fica na fonte; a nuvem guarda só de-para + agregados + scores.
- **IA nunca calcula nem publica KPI**; cálculo é sempre determinístico em código.
- Sem cadastro de produto; sem soma de medidas incompatíveis (ver
  [docs/V1_ESCOPO.md](docs/V1_ESCOPO.md)).
