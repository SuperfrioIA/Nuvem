# Piloto — Perdas × Volumetria × Ocupação

Espelho em markdown do rascunho visual v0.2 (artefato):
<https://claude.ai/code/artifact/a8829925-077b-4414-994a-25a5eb984aeb>

## Em uma frase

Provar o conceito em miniatura: três dados de fontes diferentes, uma chave comum, e o
sistema apontando sozinho onde olhar — sem copiar o dado bruto pra lugar nenhum.

A pergunta que o piloto responde em 1 clique: **"a perda deste mês foi normal — ou tem
cagada no meio?"**

## O que prova / o que não é

**Prova:** 3 fontes juntas com números batendo com os relatórios oficiais; de-para
funcionando; efeito "bolinhas acendem" sem regra pré-desenhada; caminho completo sem
copiar o bruto (camada fina em vez de segundo banco).

**Não é:** a plataforma final; previsão/sazonalidade; padrão por cliente; alertas
automáticos; IA narradora. (Tudo continua no plano — degraus seguintes.)

## Dados que entram

| Métrica | Onde mora | Como chega | Grão |
|---|---|---|---|
| Perdas (avarias + vencimento) | WMS / Conciliador | upload manual → depois Pentaho | armazém × mês |
| Volumetria (mov. entrada/saída) | WMS | upload manual → depois Pentaho | armazém × mês |
| Ocupação (%) | planilha operacional | Excel no SharePoint | armazém × mês |

Histórico alvo: 12–24 meses, em 1–2 filiais escolhidas.

Regras de ouro do SharePoint: ler o **Excel, nunca o PDF**; toda planilha que alimenta a
nuvem tem **contrato** (aba e colunas fixas, combinadas com quem preenche).

## De-para (exemplo)

WMS `ARM-03` = Conciliador `FIL014` = planilha "Guarulhos" → **GRU**

O de-para não existe em nenhum sistema — é conhecimento novo, primeira moradora da
camada fina, e ~80% do trabalho real quando a nuvem crescer.

## Motor (3 passos)

1. **Aprende o normal** — média + variação típica dos últimos 12–24 meses, por
   métrica × armazém
2. **Mede o desvio** — o mês em análise vira "quantos desvios acima/abaixo do próprio normal"
3. **Vira estado** — dentro do padrão / fora do padrão (a bolinha acende)

Roda dentro da rotina agendada (dado é mensal; sem tempo real). A tela lê o resultado
pronto — isso protege as fontes: uma consulta por dia, não uma por clique.

## Leituras-exemplo

- **Dez/2023:** perdas +50%, MAS volumetria +100% e ocupação +38% acesas juntas →
  perda provavelmente "justa"
- **Fev/2026:** perdas +30% e nenhuma outra bolinha acesa → nada explica a perda; investigar

## Critérios de sucesso

- Operação responde "a perda foi normal ou não?" em menos de 1 minuto
- A nuvem abre em segundos (lê só a camada fina); espera aceitável só no drill-down
- Números batem com os relatórios oficiais
- 12+ meses de histórico navegáveis
- Mês novo entra com esforço conhecido e documentado

## Perguntas em aberto

- **Dono do dado:** quem valida perdas / volumetria / ocupação?
- **Consultas no Pentaho:** quem cria? Já existem relatórios reaproveitáveis?
- **Dono das planilhas de ocupação:** com quem combinamos o contrato de planilha?
- **Ocupação tem histórico retroativo?** Se não, começa a acumular agora.
- **Quais 1–2 filiais** entram no piloto?

## Depois do piloto

+ métricas e filiais → previsão/sazonalidade → padrão por cliente → alertas + IA
narrando. Cada degrau entrega valor sozinho.
