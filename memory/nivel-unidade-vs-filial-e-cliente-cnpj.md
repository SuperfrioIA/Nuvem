---
name: nivel-unidade-vs-filial-e-cliente-cnpj
description: Para o número bater com o Power BI, unidade tem que ser o CNPJ (RMSPII = 001+015+016) e cliente tem que ser a raiz do CNPJ — a sigla do armazém dá 1/3 e o nome do cliente está trocado em 1.003 linhas
metadata:
  type: project
---

Descoberto em 17/ago/2026 conciliando a base de entrada por UA contra um print
do Power BI (RMSPII × SAPORE × Recebimento × peso bruto). A Maria fez uma
dinâmica na minha base e achou 2.580 t onde o BI mostra 7.746 t. As duas coisas
que explicam isso são de **rotulagem de dimensão**, não de medida:

### 1. "Unidade" no BI é o CNPJ; "filial" é o armazém

O BI agrega por `NK_WMS_FILIAL` = **um CNPJ**. A RMSPII do BI
(`06975242000187`) reúne as **três** filiais que o DataHub publica em pastas
separadas — 001, 015 e 016 — e que como armazém têm siglas **diferentes**:
RMSPII, RMSPIII e RMSPIV (cadastro Protheus 008001/008002/008003, confirmado
por print da Maria; a 016 é o **Rodoanel**).

Consequência medida (jul/2026, SAPORE, peso bruto): filtrar pela sigla
`RMSPII` dá **2.580,3 t**; as três filiais somadas dão **6.427,9 t**; o BI
mostra **7.745,7 t**. Ou seja, a sigla do armazém entrega **um terço**. O erro
oposto também existe: sem filtro de unidade entra a CWBIII (583 t de Curitiba),
que o BI não conta em RMSPII.

Os CNPJs próprios de RMSPIII (`0002-68`) e RMSPIV (`0003-49`) existem no
Protheus e **não** no fato do DW — o DW joga as três no `0001-87`.

### 2. Cliente é a raiz do CNPJ, nunca o nome

A fonte tem **17 grafias para 10 clientes**, e não é só variação de pontuação:
em **1.003 linhas (257,0 t)** o nome **discorda** do CNPJ, numa troca
sistemática de par — CONVIDA↔NOVITA e FLV↔CUCINARE — em todos os meses e nas
filiais 001 e 016. `FLV 7 RESTAURANTES LTDA.` aparece sob **três** CNPJs.

O CNPJ é o lado certo: cruzando jul/2026 por raiz de CNPJ contra o fato, esses
quatro clientes fecham entre 0,1% e 4,7%, a mesma faixa dos clientes limpos. E
é a chave que o DW usa (`NK_CLIENTE`) e que o projeto já usa
(`serie_datahub.resolver_cliente`). Agrupar por nome também **perderia** um
merge legítimo: `GR SERVIÇOS E ALIMENTOS` e `GR SERVIÇOS E ALIMENTAÇÃO` têm a
mesma raiz `02905110`.

**Why:** eu tinha rotulado a coluna como `Filial` com a sigla do armazém, que é
correta como identidade de armazém e colide com o significado de "Unidade" no
BI. Isso fez a Maria e eu medirmos recortes diferentes sem perceber — eu falava
de 17% de gap enquanto ela via 67%.

**How to apply:** qualquer entrega que vá ser comparada com o Power BI precisa
das duas camadas explícitas: `Unidade no BI` (CNPJ) **e** `Filial`/armazém
(sigla), mais `Cliente` canônico por raiz de CNPJ com a grafia da fonte
documentada à parte. Ver [[conciliacao-rmspii-primeira-passada]] (a diferença
que sobra depois disso é guia cancelada) e [[fato-volumetria-dw]].
