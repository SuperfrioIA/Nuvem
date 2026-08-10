# Comparabilidade DW × DataHub — o que cada lado tem, o que cruza, e o que impede o 99%+

10/08/2026, terceira rodada da conciliação de volumetria (recorte RMSPII,
jan–jun/2026). Responde à pergunta da Maria: *"por que não podemos simplesmente
pegar os arquivos e ver o que bate com o quê?"* — **podemos, e foi feito, até o
grão de DIA. O que falta para 99%+ não é método: é dado que um dos lados não
publica.** Cada lacuna abaixo tem nome, número e dono.

Números e grãos na planilha `docs/Analise/saida/conciliacao_slin_x_dw.xlsx`
(13 abas — ver a `ENTRADA_POR_DIA`). Pendências vivas em
`docs/CONCILIACAO_POWERBI_V2.md` (P-3, P-6…P-11).

---

## 1. O que cada lado tem

### Lado DW (o que o Power BI consome) — `docs/Analise/`

| Arquivo | O que é | Grão | Serve para volumetria? |
|---|---|---|---|
| `fato.csv` | `FATO_VOLUMETRIA` (extrato 16/07) | **dia × instância × filial(CNPJ) × cliente × operação** | **SIM — é o lado DW de tudo aqui** |
| `clientesDw.csv` | `DIM_CLIENTE` (61.182 registros) | cliente | sim (de-para por raiz de CNPJ) |
| `filiais.csv` | `MID_D_CROSS_REF` (de-paras internos do DW) | par referência/valor | parcial (de-para Protheus×WMS) |
| `Empresas Grupo Superfrio 5(...).csv` | cadastro Protheus de filiais | filial | sim (CNPJ por filial) |
| `data (2).xlsx` | export do visual do BI (Recebimento, RPI, 2026) | mês × cliente × operação | formato útil como contraprova; **este** arquivo é só RPI |
| `apartado/*.csv` | dicionários (PT/ES/coluna real + amostra) | — | sim, como documentação |
| `naoSei.csv`, `rpt_dw_occupation*`, `ocupacao*`, `capacidade*`, `camaras*`, `data (6).xlsx`, `Dashboard Capacidade*` | ocupação/capacidade | — | **não (fora do escopo volumetria)** |
| `conciliacao_66.csv` | conferência de estoque por SKU | SKU × lote | não |

**O que o DW NÃO tem (varrido em 10/08, arquivo a arquivo):**
- **grão de documento** — nenhuma extração tem GEM/GSM/NF. O grão mais fino é
  dia × cliente;
- **flag de cancelamento** — nada nos dicionários nem nas dimensões;
- **detalhe por filial física dentro da RMSPII** — um CNPJ só (0001-87);
- julho/2026 completo (extrato de 16/07).

### Lado DataHub/SLIN (o que a Nuvem lê) — galho RMSPII, inventário ao vivo de 10/08

| Família | 001 | 015 | 016 | Tem o que importa |
|---|---|---|---|---|
| `ENTRADA_MERCADORIAS` | 2601–2608 | **2601–2606 (para em jun)** | 2601–2608 | item com GEM, CNPJ, peso, valor, **data (Solicitação)** |
| `ENTRADA_MERCADORIAS (UA)` | 2110–2608 | **2110–2607 (tem jul!)** | 2110–2608 | mesmo movimento no grão de palete |
| `GUIAS_ENTRADA` | 2601–2608 | **NÃO EXISTE** | 2601–2608 | guia com **Status (Cancelado)**, peso e valor no cabeçalho, data |
| `SAIDA_MERCADORIAS` | 2110–2608 | 2110–2607 | 2110–2608 | item nas 3 bandas, CNPJ, peso, **Empresa**, data |
| `GUIAS_SAIDA` | 2601–2608 | **NÃO EXISTE** | 2601–2608 | guia com Status — **mas peso ZERO em cancelada/cortada** |
| `CORTES_PRODUTOS` | 2601–2608 | **NÃO EXISTE** | 2601–2608 | corte por item (guias que existem) |
| `DADOS_GERAIS` / `OCORRENCIAS` | 002 | — | 016 | entregas; filial 002, fora do recorte |
| `ESTOQUE_*` / `PALLETS_*` | 001 | — | 016/cliente | ocupação/estoque, fora do escopo |

**O que a fonte NÃO tem:**
- **peso da guia de saída cancelada/cortada** — `Peso Líq.` = 0 em 402/402
  canceladas e 125/125 cortadas integrais (o peso da saída nasce na separação);
- **qualquer guia da 015** (entrada e saída) — a família não é publicada;
- valor na saída; nome consistente de cliente (3 grafias) — resolvido pela raiz
  do CNPJ.

---

## 2. O que cruza com o quê (provado, com número)

| Cruzamento | Chave | Resultado |
|---|---|---|
| Itens × guias (entrada) | `GEM` = `Número` | 100% (medição de 30/07) |
| Itens × guias (saída) | `GSM` = `Número` | 100% juntando competências vizinhas |
| Fonte × DW por cliente | raiz do CNPJ (`NK_CLIENTE`) | 10/10 clientes, 100% do peso |
| Fonte × DW por filial | pasta = `Empresa` `001/00N` → CNPJ 0001-87 (instância `SLIN_RMSPII_PRD`) | provado nas 3,3 mi de linhas da saída |
| **Fonte × DW por DIA × cliente (entrada)** | data (Solicitação × movimento) | **onde as guias existem, o dia FECHA**: FLV7 126/126 dias com resíduo < 1 t (0,8 t no semestre); CONVIDA 121/122; OG 112/114; NOVITA 120/129. SAPORE/GR/PIMENTA: ruído de ±1 dia que se anula (soma ≈ 0). SODEXO: resíduo líquido de +2.448 t **concentrado em dias com movimento na 015** |

A linha de DIA é a resposta prática: `DW(dia, cliente) = itens(dia, cliente) +
canceladas(dia, cliente)`. Essa identidade fecha para os clientes onde os dois
termos da direita são mensuráveis. Ela é também a prova mais forte até agora de
que **o DW conta a guia cancelada** (P-7): sem somar as canceladas, nenhum
cliente fecha; somando, quatro fecham dia a dia.

---

## 3. Os impedimentos para o 99%+, um a um

| # | Impedimento | O que trava | Quem resolve |
|---|---|---|---|
| 1 | **`GUIAS_ENTRADA` da 015 não é publicada** | as ~1.6–2.4 kt de resíduo da entrada (tudo SODEXO, a única cliente da 015). Com esse arquivo, a entrada fecha no dia × cliente como os outros | quem publica o DataHub (controladoria/SLIN) — pedir também `GUIAS_SAIDA` e `CORTES` da 015, e o `ENTRADA_MERCADORIAS` 015 de jul/ago |
| 2 | **Guia de saída cancelada/cortada tem peso ZERO no export** | a tonelagem cancelada da saída (estimada ≈ 3,7 kt de um gap de 7,5 kt) só sai por estimativa. O SLIN tem o peso *solicitado* internamente; o relatório é que não o traz | quem gera o export do SLIN (campo novo: peso solicitado da guia) — OU extrato do DW no grão de GSM |
| 3 | **`fato.csv` não tem grão de documento** | o casamento 1:1 (guia a guia) e a separação exata entre "cancelada contada" e "reemissão contada uma vez" | quem mantém o DW (extrato da `FATO_VOLUMETRIA` de origem no grão GEM/GSM de UM mês bastaria para calibrar) |
| 4 | **`PESO_BRUTO` do DW com defeito nas linhas da GR** | ≈ 1,1 kt do gap da saída é peso, não volume: bruto/líquido de 1,106–1,130 na Expedição (fonte: 1,021–1,024) e meses com bruto MENOR que líquido na entrada (0,921 em fev, 0,898 em jun — impossível fisicamente) | quem mantém o ETL `wms_to_dw_volumetry_v04`. Enquanto isso: **conciliar a GR em peso LÍQUIDO** |
| 5 | Julho/2026 parcial no extrato | qualquer comparação com julho | extrato novo do fato quando fechar o mês |

Sem os itens 1 e 2, o teto prático da conciliação é o que já está medido:
**entrada explicada a 87% + resíduo dimensionado e localizado (SODEXO/015, dia a
dia); saída explicada a ~50–65% por estimativa declarada**. Com os itens 1 e 2,
os dois lados fecham no grão de dia × cliente. O item 3 só é necessário para o
1:1 documental.

---

## 4. Nota sobre "RMSPII" (contexto da P-10, em uma frase)

O WMS da RMSPII (instância `SLIN_RMSPII_PRD`) também registra movimento que o
DW atribui a **outras empresas do grupo** (CEFRI Mairinque, SuperFrio Ribeirão
Preto, e 22 linhas sem filial) — ~27,5 kt no semestre, com SODEXO, SAPORE e
ANGA. Esse movimento **não está** nas pastas 001/015/016 (provado pela coluna
`Empresa`) e **não está** no "RMSPII" do BI. Não afeta nenhum número desta
conciliação; só importa se alguém um dia comparar "tudo que o prédio movimenta"
com o BI — a diferença estará aí, e é atribuição de CNPJ, não volume.
