---
name: reestruturacao-datahub-4-unidades
description: Em 31/jul/2026 o DataHub virou 4 unidades (RMSPII/CWB3/RJ/SANCA) e criou 7 colisões de nome que sujam a linhagem do Bloco C — ABERTO, não corrigido
metadata:
  type: project
---

A pasta do SharePoint DataHub foi reestruturada entre 29 e 31/jul/2026: passou de
**249 arquivos / 31 pastas / 711 MB** para **367 / 61 / 955 MB**, e a raiz deixou de
ter as áreas operacionais direto — agora tem quatro unidades. O que o projeto conhecia
como a pasta inteira é só o galho `RMSPII` (272 arquivos); as outras são `RJ` (42),
`CWB3` (30) e `SANCA` (21). Apareceu a família `ENTRADA_MERCADORIAS (UA)` (35 arquivos),
não catalogada.

**O defeito aberto:** `ENTRADA_MERCADORIAS_001_2601..2607.xlsx` existe em `RMSPII/` e em
`CWB3/` — 7 colisões, mesmo nome e mesmo código de filial `001`, armazéns diferentes,
e o de-para manda os dois para RMSPII. Como `processamentos_datahub` tem
`UNIQUE(arquivo)`, os dois disputam o registro, o "pula inalterados" para de funcionar,
`_remover_celulas_orfas` faz um apagar as células do outro, e `medidas_recebidas`
(append-only) fica com dado da CWB3 gravado sob o `armazem_id` da RMSPII — de forma
permanente. As células de `medidas` acabam corretas por acidente da ordem alfabética
(CWB3 processa antes), então **o erro não aparece na tela** — só na linhagem.

Lacunas juntas: a RJ é ignorada em silêncio (o padrão de nome exige só dígitos e
`004-003` tem hífen — não vira nem pendência), e a `ENTRADA_MERCADORIAS` da RJ tem 18
colunas, sem `Cliente`/`Cliente CNPJ`.

**Why:** é regressão em código já entregue e verificado (Bloco C) causada por mudança
externa, não por bug de escrita. O risco estava registrado como hipótese no V1_PLANO
com a premissa "verdade hoje" — a premissa caiu, e o caso real é pior que o previsto
(armazéns diferentes, não a mesma filial).

**How to apply:** antes de rodar "Processar arquivos" na VM, restringir o processamento
ao galho `RMSPII` — como está, a primeira execução em produção já suja a linhagem. A
correção é um lote com migration (decisão de fundo: identidade do arquivo passa a ser
caminho, `item_id` ou unidade+filial+competência) e deve ser avaliada **antes do Bloco
D**. Detalhamento na seção "ABERTO — a fonte foi reestruturada" do
[docs/V1_PLANO.md](../docs/V1_PLANO.md); levantamento completo em
`docs/VERIFICACAO_DATAHUB_31JUL2026.html`. Ver [[filiais-catering-poc]] (os de-paras
novos `025`/`004-*`/`005-*` seguem pendentes) e [[concentracao-sapore-016]].
