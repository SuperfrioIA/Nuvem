---
name: conciliacao-rmspii-primeira-passada
description: Primeira comparação Nuvem x Power BI (RMSPII, entrada, jan-jul/26) — achado principal e pendências abertas, prep pro lote V2.6
metadata:
  type: project
---

Levantamento de 06/ago/2026, feito puxando direto do SharePoint (Graph, somente
leitura, mesmo padrão do levantamento da proposta V3) em vez do app — a VM exige
login e não havia credencial disponível na conversa.

**Achado principal:** no Power BI, o filtro "Unidade: RMSPII" agrega as **três
filiais físicas** (`001` + `015` + `016` — RMSPII+RMSPIII+RMSPIV na Nuvem), não
só a `001`. Confirmado batendo o total: somando só `001` dava 40.490 t contra os
108.525 t do BI (jan-jul/26, peso bruto de entrada/Recebimento) — 2,68x de
diferença. Somando as três filiais, o total sobe para **94.250 t**, reduzindo o
gap pra ~13%. Isso é coerente com [[filiais-catering-poc]]: "a controladoria
enxerga as três juntas como RMSPII".

**Números (jan-jul/26, peso bruto de entrada, toneladas) — os dois lados no
mesmo período (correção de 06/ago: a primeira passada comparou Nuvem até julho
com Power BI até agosto, "banana com manga" — a Maria pegou o erro):**

| Fonte | 001 | 015 | 016 | Total |
|---|---:|---:|---:|---:|
| Nuvem (SharePoint, soma de `Peso Bruto`) | 40.490 | 23.768 | 29.992 | **94.250** |
| Power BI (RMSPII agregada, jan-jul via acumulado do gráfico) | — | — | — | **108.525** |

Gap ainda aberto: **~14.275 t (13%)**, Nuvem abaixo do BI — direção **contrária**
à esperada pela decisão 6 (`Operação` soma tudo incluindo devolução/transferência
deveria deixar a Nuvem **maior**, não menor).

**Resolvido (confirmado pela Maria em 06/ago):** `WYDA` no Power BI e `CUCINARE
PRO ALIMENTAÇÃO LTDA` (raiz CNPJ `04596502`) na Nuvem são **o mesmo cliente** —
nome comercial vs razão social. Não é cliente faltando de nenhum dos dois lados;
é diferença de rótulo entre os dois sistemas. Ajustar o de-para/exibição de
nome de cliente quando o V2.6 for aberto.

**Per-cliente jan-jul, os dois lados no mesmo período** (Power BI com filtro
"Mês: Seleções múltiplas" = jan-jul, print de 06/ago; raiz de CNPJ do lado da
Nuvem, WYDA=CUCINARE já unificado):

| Cliente (raiz CNPJ) | Nuvem (t) | Power BI (t) | Diferença | % |
|---|---:|---:|---:|---:|
| SAPORE S.A. | 37.257 | 44.192 | 6.935 | 15,7% |
| SODEXO DO BRASIL | 34.878 | 38.780 | 3.902 | 10,1% |
| GR SERVIÇOS E ALIMENTAÇÃO | 11.770 | 14.322 | 2.552 | 17,8% |
| CUCINARE / WYDA | 3.824 | 4.479 | 655 | 14,6% |
| NOVITA ALIMENTAÇÃO | 2.782 | 2.843 | 61 | 2,1% |
| PIMENTA VERDE | 2.556 | 2.606 | 50 | 1,9% |
| CONVIDA REFEIÇÕES | 683 | 702 | 19 | 2,7% |
| FLV 7 RESTAURANTES | 324 | 416 | 92 | 22,2% |
| OG DO BRASIL | 175 | 184 | 9 | 4,8% |
| CARREFOUR TIETE | 0 | 0 | 0 | — |
| **Total** | **94.250** | **108.525** | **14.275** | **13,2%** |

**Padrão observado, não explicado ainda:** quatro clientes (NOVITA, PIMENTA
VERDE, CONVIDA, OG DO BRASIL) batem quase exato (1,9%–4,8%). Cinco clientes
(SAPORE, SODEXO, GR SERVIÇOS, CUCINARE/WYDA, FLV 7) têm gap de 10%–22%, sem
correlação clara com o tamanho do cliente (FLV 7 é pequeno e tem o maior gap
relativo). Não é o padrão "cliente grande = mais devolução" que a decisão 6
previa (e a direção do gap é a contrária: Nuvem menor, não maior). Candidatos a
investigar no V2.6: linhas com `Cliente CNPJ` que não bate exatamente na raiz
(cliente sem CNPJ cadastrado cairia fora da minha soma por CNPJ, mas dentro da
soma por nome do Power BI), ou fonte adicional que o Power BI usa e a
`ENTRADA_MERCADORIAS` do DataHub não cobre.

**Ainda pendente:**

1. O botão "Operação" do relatório do Power BI **não mudou** o gráfico "por
   Categoria" quando testado (ficou idêntico ao agrupamento por Cliente) — sinal
   de que os filtros desse relatório podem não estar isolando "Recebimento" tão
   limpo quanto o rótulo sugere. Não dá pra confirmar quanto do gap de 13% é
   isso vs. cliente sem CNPJ/erro de leitura vs. fonte diferente (ex. família
   `(UA)`, fora do escopo da V2 — decisão 7).

**Nomes de cliente fragmentados na fonte** (mesma raiz de CNPJ, grafias
diferentes entre arquivos): GR SERVICOS/SERVIÇOS E ALIMENTAÇÃO/ALIMENTOS (raiz
`02905110`, 3 grafias), NOVITA, PIMENTA VERDE, CONVIDA, LC ADMINISTRAÇÃO (2
grafias cada). Agrupar por raiz do CNPJ (como `serie_datahub.resolver_cliente`
já faz) resolve; agrupar por nome de cliente cru, não.

**Why:** essa é a primeira tentativa real de conciliação (V2.6 ainda não
autorizado) — vale registrar pra não repetir o levantamento do zero e pra não
reabrir a pergunta "por que a Nuvem está menor" sem lembrar que já reduzimos o
gap de 2,68x pra 13% e sabemos exatamente o que falta decidir.
**How to apply:** ao abrir o V2.6, começar daqui em vez de do zero. Perguntar à
Maria sobre WYDA/CUCINARE antes de aprofundar o gap de 13%. Ver
[[confirmar-sigla-antes-de-citar-filial]] pro erro que gerou a primeira hipótese
errada (não é a mesma coisa, mas está relacionado).
