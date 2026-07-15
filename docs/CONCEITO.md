# Conceito — Nuvem IA

## O problema

A SuperFrio tem WMS, TMS, ERP e Conciliador de estoque (bancos próprios, anos de dados)
mais controles manuais em planilha/PDF (IRA-ILA, faturamento/contas a receber,
relatórios da controladoria). Existem milhares de BIs individuais que exigem
interpretação humana: **a ligação entre os dados mora na cabeça das pessoas.**

## O núcleo

Tirar o cruzamento da cabeça das pessoas e botar no sistema. Duas camadas que não se
misturam:

- **Motor** — juntar e cruzar os dados → gerar o insight. É onde mora o valor.
- **Embalagem** — a nuvem de bolinhas (estilo Obsidian Graph View). É como se navega
  e se comunica o cruzamento.

Começar pela embalagem é a armadilha; começar pelo motor com um cruzamento que entrega
um "aha" real é o caminho.

## As 3 capacidades (exemplos originais)

1. **Explicar/validar anomalia** — dez/2023: perda 50% acima da média, mas volumetria
   +100% → perda "justa". Fev/2026: perda +30% com volumetria no padrão → investigar.
2. **Prever e planejar** — padrão anual de volumetria → contratar gente antes do pico
   do cliente.
3. **Detectar padrão de risco** — cliente de catering pedindo lotes 1-2-3-2-2, comprando
   estoque sem parar e perdendo por vencimento → sinalizar o risco.

São três produtos diferentes; o piloto ataca só o nº 1.

## A escada de mecanismos de insight

1. Humano olha dados lado a lado (BI cruzado)
2. Regras fixas (fluxos pré-desenhados)
3. **Triagem estatística genérica** ← o piloto. Cada métrica é comparada com o próprio
   histórico, por contexto. Sem regra por par de métricas: qualquer métrica nova que
   entrar na base já participa. É o que faz as bolinhas "piscarem" sem ninguém ter
   programado que "perda conversa com volumetria".
4. IA narrando por cima (LLM recebe as anomalias do contexto e escreve a interpretação)
5. Mineração de correlações — **cuidado**: com milhares de séries aparecem correlações
   fortes por puro acaso. Desenho maduro: máquina tria → humano valida → validação
   recorrente vira regra/alerta automático.

## A visão da tela

Grafo de bolinhas-métricas: tamanho = volume de dados; seleção de contexto (filial,
cliente, período) filtra; bolinhas fora do próprio padrão **naquele contexto** acendem
juntas. O "ah, então está conectado" continua sendo da pessoa; o sistema faz a triagem.

## Princípio inegociável

O dado bruto fica na fonte (Pentaho, SharePoint). A nuvem guarda só o caderninho de
resumos: de-para + agregados (armazém × mês) + scores. Kilobytes — não um segundo DW.

## Entregas (as 4 torneiras)

Tela → export .xlsx → relatório HTML → e-mail automático (que é o degrau "alertas
proativos" chegando). Todas bebem da mesma camada fina; nenhuma exige recalcular nada.
