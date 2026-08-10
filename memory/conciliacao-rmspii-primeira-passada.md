---
name: conciliacao-rmspii-primeira-passada
description: Conciliação RMSPII (entrada) — a diferença de 13% contra o Power BI é guia de entrada CANCELADA, que tem peso mas não gera linha de item; medida em 1.801 guias / 11.294 t em jan-jun/26
metadata:
  type: project
---

Duas passadas: levantamento inicial em 06/ago/2026 (contra prints do Power BI) e
verificação em 07/ago/2026 contra a fonte que o BI realmente consome
(`docs/Analise/fato.csv`, ver [[fato-volumetria-dw]]) + leitura do DataHub pelo
Graph, somente leitura.

**Relação com o lote V2.6** (`docs/CONCILIACAO_POWERBI_V2.md`, entregue em
07/ago): aquele documento fixou o método e registrou as pendências a partir dos
números de 06/ago. Esta verificação **fecha P-0, P-1 e P-2 e descarta D-2/D-3**:
não é balde de cliente sem CNPJ nem fonte extra — é guia cancelada. O documento
do V2.6 ainda não reflete isto; atualizá-lo é a primeira coisa a fazer na próxima
passada. Seguem abertas P-3 (botão "Operação" do relatório, agora menos
importante — dá para comparar direto contra o `fato.csv`), P-4 (saída) e P-5 (o
lado Nuvem vir do banco em vez da planilha).

**Causa identificada: guia de entrada cancelada.** Ela continua no WMS com
cliente, NF, peso e valor no cabeçalho, e o DW conta esse movimento — mas **não
gera nenhuma linha de item**, e o export `ENTRADA_MERCADORIAS` que a Nuvem lê é
uma lista de itens. A Nuvem soma item, o DW soma movimento; por isso a Nuvem fica
sistematicamente embaixo. Ver [[chaves-nf-entrada-datahub]], que já registrava a
existência das canceladas sem item desde 30/jul — o que faltava era medir.

**Números (jan-jun/2026, entrada, peso bruto, RMSPII = filiais 001+015+016):**

| | t |
|---|---:|
| Nuvem (ENTRADA_MERCADORIAS) | 85.958,4 |
| DW / Power BI (FATO_VOLUMETRIA, Recebimento) | 98.886,8 |
| Gap | **12.928,4 (13,1%)** |
| Guias canceladas medidas (só 001 e 016) | **11.294,0 — 87% do gap** |

1.801 guias canceladas, R$ 171,0 mi de valor de nota. O gap aparece nos seis
meses, sempre no mesmo sentido (8,9% a 17,0%).

**A correlação por cliente é o que fecha o argumento** — quem "confere" quase não
cancela, quem tem gap alto cancela às centenas. FLV 7 (menor cliente com
movimento, maior gap relativo) bate em 100%:

| Cliente | Guias | Cancelado (t) | Gap (t) | Cobertura |
|---|---:|---:|---:|---:|
| SAPORE | 767 | 5.957,7 | 5.617,8 | 106% |
| SODEXO | 155 | 1.476,7 | 3.924,7 | 38% |
| GR SERVIÇOS | 489 | 2.874,3 | 2.549,7 | 113% |
| CUCINARE/WYDA | 215 | 732,6 | 637,3 | 115% |
| FLV 7 | 58 | 92,6 | 92,7 | 100% |
| PIMENTA VERDE | 39 | 85,5 | 44,4 | 193% |
| NOVITA | 39 | 56,8 | 38,8 | 146% |
| CONVIDA | 25 | 11,0 | 15,5 | 71% |
| OG DO BRASIL | 14 | 6,8 | 7,5 | 91% |

**Não é devolução:** do peso cancelado, 8.299,5 t são `NÃO TROCA NOTA DE
ARMAZENAGEM` e 2.933,4 t `ENTRADA NORMAL/NF ARMAZENAGEM`; devolução é 38,7 t
(0,3%). A hipótese antiga da decisão 6 (devolução explicaria a diferença) está
morta — e a direção do gap sempre foi a contrária à que ela previa.

**Descartado com número, não por argumento:**

- **Família `(UA)` como fonte extra:** junho soma **13.524,045 t nas duas**
  famílias. São 30.356 linhas contra 18.026 — o mesmo movimento quebrado por
  palete. (Era a hipótese 2.)
- **Cliente sem CNPJ:** zero linhas sem raiz válida em junho; e o *total* do
  arquivo já está abaixo, então atribuição de cliente não explicaria nada.
- **Peso bruto x líquido:** mesmo gap no líquido (83.737 x 97.506 t, 14,1%) — não
  é tara nem definição de peso.
- **Corte de data na virada do mês:** os seis meses vão no mesmo sentido; se fosse
  competência x data de movimento, alternariam.
- **Filtro de operação:** a soma da Nuvem já inclui todas as operações.

**Ainda aberto (1.634 t, 13% do gap):** a filial `015` **não tem export de
`GUIAS_ENTRADA`** — sem ele não dá para medir as canceladas dela, e é exatamente
onde a SODEXO fica subcoberta (38%). O `ENTRADA_MERCADORIAS` da 015 também para
em junho (sem 2607/2608), o que puxa julho para baixo do lado da Nuvem.

**Resolvido antes:** `WYDA` (BI) e `CUCINARE PRO ALIMENTAÇÃO` (raiz `04596502`)
são o mesmo cliente — nome comercial x razão social. E nomes de cliente vêm
fragmentados na fonte (GR com 3 grafias; NOVITA, PIMENTA VERDE, CONVIDA e LC com
2 cada): agrupar por raiz de CNPJ resolve, por nome cru não.

**Limite da prova:** é explicação de ordem de grandeza e de padrão, não casamento
documento a documento — o `fato.csv` é agregado por dia × cliente × operação.
Coberturas acima de 100% dizem que o DW não conta *todas* as canceladas
(provavelmente guia cancelada e reemitida entra uma vez só). Fechar 1:1 exigiria
extrato do DW no grão de GEM.

**Why:** o V2.6 entregou o método com o gap ainda sem causa; a causa apareceu no
dia seguinte, com número. Sem este registro a próxima passada repetiria hipóteses
já mortas (balde de cliente, família UA, devolução).
**How to apply:** a decisão pendente é de produto, não técnica — o que fazer com
a guia cancelada: contar como o DW conta, ou declarar a diferença na tela. Pedir
à controladoria o export de `GUIAS_ENTRADA` da 015 e os arquivos de julho/agosto
dela antes de tentar fechar os 13% restantes. Ver
[[comparar-mesmo-periodo-nos-dois-lados]] e
[[confirmar-sigla-antes-de-citar-filial]].
