---
name: rmspii-julho-2026-sodexo
description: A queda de 40,7% do throughput da RMSPII em julho/2026 é a saída da SODEXO (94%), não a operação — e a concentração na SAPORE saltou para 80,4%
metadata:
  type: project
---

Julho/2026 fechado na RMSPII (rótulo do DW, instância `SLIN_RMSPII_PRD`),
medido sobre a união das duas extrações do fato — ver [[fato-volumetria-dw]]:

| | jul/2026 | jun/2026 | jul/2025 |
|---|---:|---:|---:|
| dias com movimento | 29 (de 31) | 30 | 31 |
| entrada | 9.638,1 t | 15.229,4 t | 19.704,0 t |
| saída | 9.285,5 t | 16.686,5 t | 17.634,8 t |
| throughput | 18.923,6 t | 31.916,0 t | 37.338,8 t |

- **Throughput −40,7% contra junho, e 94,0% disso é a SODEXO** (12.393,0 t →
  184,6 t, −12.208,3 t). Com a GR (−1.212,9 t) passa de 103% da variação, porque
  a SAPORE *cresceu* 5,3% (+718,1 t) no mesmo mês. **A queda não é operacional** —
  qualquer leitura que trate esses −40,7% como piora de operação está errada.
- **O risco real é concentração:** SAPORE foi de 47,6% para **80,4%** da entrada
  (em jul/2025 a líder era a própria SODEXO, com 38,7%). A unidade ficou
  mono-cliente em um mês. Falta confirmar com a operação se a saída da SODEXO é
  perda de contrato ou migração de filial — a resposta muda a leitura inteira.
- **Sinal operacional independente do mix:** carga média por veículo na expedição
  caiu de 6,50 para **5,06 t** (−22,2%; era 6,64 t em jul/2025), e o peso por item
  de saída caiu 25,3% (232,9 → 174,0 kg). Na carga média de junho, as 9.285,5 t
  teriam saído em ~1.429 veículos em vez de 1.835: **~406 viagens a mais**.
- **09/07 (qui): recebimento de 0,5 t** contra média de 418,6 t em dia útil, mas
  com 48 veículos e 159,8 t de saída. **Não mudou entre as extrações de 16/jul e
  14/ago** — não é carga atrasada do DW, é dado que nasceu assim e não se corrigiu.
  Conferir no WMS; se houve movimento não lançado, julho está subestimado na origem.
- Os 2 dias sem movimento são os domingos 19 e 26/07 — e os 31 dias existem na
  base em outras unidades, então não é falha de carga. A RMSPII operou nos outros
  dois domingos.
- Vazamento da instância (P-10) em julho: MAQ 1.311,7 t + RPII 136,0 t = 1.447,7 t
  = 7,7% do throughput, fora do rótulo RMSPII — ver [[depara-filial-rmspii-dw]].

**Why:** é o primeiro mês fechado com leitura de causa, e a conclusão é
contraintuitiva — o número que assusta (−40,7%) é o menos importante, e o que
importa (concentração e ocupação de veículo) não aparece em nenhum KPI de volume.

**How to apply:** qualquer painel de volumetria da RMSPII que mostre a variação de
julho sem decompor por cliente vai ser lido como colapso operacional. Decompor por
cliente é obrigatório nesse recorte. Ver [[nao-ler-mes-parcial]] para o motivo de
não repetir a leitura antes do mês fechar.
