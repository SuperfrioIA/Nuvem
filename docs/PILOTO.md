# POC — Catering na família RMSP

Substitui o desenho original do piloto (Perdas × Volumetria × Ocupação, rascunho
v0.2) em 21/jul/2026, depois da análise dos dados reais da família RMSP
(`docs/Analise/saida/`: `analise_rmsp.xlsx`, `analise-rmsp/` e `mapa-dados/`).
O desenho original permanece no histórico do git.

## Em uma frase

Organizar o catering da família RMSP — quem ocupa o quê, com que contrato e quanto
movimenta — com a nuvem acendendo sozinha o que foge do padrão.

## As 3 perguntas que a tela responde em menos de 1 minuto

1. **A RMSPIII aguenta mais um contrato de catering?** (na análise: 97,1% do espaço
   disponível ocupado, 124% da capacidade já contratada)
2. **Quem está operando sem contrato vigente este mês?** (na análise: 7.034 posições
   em contratos vencidos em 30/12/2025 com 6 clientes operando, mais Convida, FLV 7
   e OG do Brasil sem contrato nenhum)
3. **O uso de cada cliente está dentro do contratado?** (ex.: Sapore, 3.697 posições
   contratadas × uso real)

## Escopo

Filiais (decidido 21/jul/2026 — família toda):

| Filial | Papel na POC |
|---|---|
| RMSPII | Núcleo do catering (Sapore, GR, Wyda/Cucinare, Pimenta Verde, Novita, Sodexo + 3 clientes sem contrato) |
| RMSPIII | Núcleo do catering (Sodexo, Bimbo); a mais pressionada; **sem volumetria no DW** |
| RMSP | Contexto de locação (Tirolez/Delly) + caso Frimesa — valida a regra anti-dupla contagem |
| RMSPV | Acompanhando: nasceu no WMS em 14/jul/2026, vazia; espaço de crescimento do catering |

RMSPIV existe só no cadastro Protheus (sem WMS, sem dado) — fora.

**Clientes:** lista curada dos clientes de catering (~12) mantida na camada fina
(Lote 7.1). O segmento do DW está errado pra eles (constam como "Ind.
Química/Resinas/Tintas") — não dá pra filtrar por segmento.

**Perdas:** fora da POC (decidido 21/jul/2026). Volta como métrica nova depois —
o motor aceita sem mudar nada.

## Dados que entram

| Métrica | Fonte (export do DW) | Grão |
|---|---|---|
| Ocupação física (% s/ total e % s/ disponível), bloqueadas, virtuais | pos_sum | filial × mês |
| Comercial contratado: vigente e vencido-operando (posições) | comercial + fato (regra dos 60 dias) | filial × mês |
| Cobertura contratual (comercial ÷ capacidade) | derivada | filial × mês |
| Volumetria recebimento/expedição (t) | fato (histórico 2021→hoje) | filial × mês |
| Ocupação real composta (anti-dupla contagem) | derivada — Lote 9 | filial × mês |
| Posições contratadas, status do contrato e volumetria por cliente | comercial + fato | cliente × filial × mês |

Histórico: volumetria tem backfill imediato (2021→hoje, RMSP e RMSPII); ocupação e
comercial acumulam 1 foto por competência a partir de agora. Regras de limpeza de
cada fonte: documentadas em `analise_rmsp.xlsx` (abas Leia-me e Dicionário).

## Grão cliente mínimo (decidido 21/jul/2026)

`medidas_cliente` (cliente × armazém × competência), segunda tabela-fato como já
previsto na revisão de escalabilidade — mas **só pros clientes da lista de catering**.
Métricas: posições contratadas, status do contrato (vigente / vencido-operando /
sem contrato) e volumetria. O mesmo motor de scores roda em cima.

"Vencido-operando" = contrato com data final vencida + cliente com movimento nos
últimos 60 dias no fato (pela chave ERP do cliente) — derivado por código; regra
validada na análise de 21/jul.

## Motor (3 passos) — inalterado

1. **Aprende o normal** — média + desvio das últimas 24 competências, por métrica × contexto
2. **Mede o desvio** — o mês em análise vira "quantos desvios do próprio normal"
3. **Vira estado** — dentro / fora do padrão (a bolinha acende)

Roda na rotina agendada; a tela lê o resultado pronto.

## Leituras-exemplo (reais, da análise de 21/jul/2026)

- **RMSPIII:** cobertura contratual 124% com 97% do disponível ocupado → as duas
  bolinhas acesas juntas = não vender mais espaço; regularizar antes.
- **RMSPII:** 7.034 posições vencidas em 30/12/2025 com os clientes operando → a
  bolinha comercial acende pela queda brusca (os contratos venceram todos juntos).
- **Convida Refeições:** 1.292 t movimentadas em 2026 sem contrato → cliente aparece
  na volumetria sem par no comercial.

## Critérios de sucesso

- As 3 perguntas respondidas em menos de 1 minuto na tela.
- Números batendo com `analise_rmsp.xlsx` (que bate com os relatórios do DW).
- Volumetria 2021→hoje navegável (RMSP/RMSPII); mês novo entra por upload com
  modelo salvo, esforço conhecido.
- Caso Frimesa sem dupla contagem na ocupação real.

## Perguntas em aberto

- **Dono do dado comercial de Barueri:** quem valida contratos/posições do catering?
- **Pedidos ao time do DW:** integrar a volumetria da RMSPIII ao fato; gerar o
  relatório detailed (posição × cliente) pras RMSP (hoje só RPI tem); corrigir o
  segmento dos clientes de catering.
- **Contrato da planilha de ocupação** (aba/colunas/quem preenche) — segue do Lote 0.
- **RMSPV:** quando começa a operar?

## Depois da POC

+ filiais e métricas (perdas volta aqui) → padrão por cliente na rede toda →
previsão/sazonalidade → alertas + IA narrando → conector `dw_api` (Lote 10).
Cada degrau entrega valor sozinho.
