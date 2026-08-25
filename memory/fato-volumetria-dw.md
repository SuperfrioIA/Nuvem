---
name: fato-volumetria-dw
description: docs/Analise/fato.csv é a FATO_VOLUMETRIA do DW — a tabela que o Power BI consome; grão dia × filial × cliente × operação, sem grão de documento
metadata:
  type: reference
---

`docs/Analise/fato.csv` (32 MB, 142.909 linhas, extrato de 16/jul/2026) é a
`FATO_VOLUMETRIA` do DW — **a fonte que o Power BI da controladoria consome**.
Confirmado batendo número contra print: SODEXO jan-jul/26 dá 38.779,3 t no fato
contra as 38.780 t lidas do relatório. É o lado "BI" de qualquer conciliação,
sem depender de print.

- **Grão:** dia × instância WMS × filial × cliente × operação. `NK_CALENDARIO` é
  a data do movimento; `NK_OPERACAO` ∈ {`Recebimento`, `Expedição`,
  `Cross Docking`}. Medidas: `PESO_BRUTO`, `PESO_LIQUIDO`, `QUANTIDADE`, `ITENS`,
  `LPNS`, `VEICULOS`, `PALETES` (esta vem zerada na RMSPII).
- **Não tem grão de documento** — não há GEM nem NF. Conciliar guia por guia com
  o DataHub é impossível só com este arquivo; exigiria extrato novo do DW.
- **`NK_CLIENTE` é a raiz do CNPJ** — mesma chave que a Nuvem usa
  (`serie_datahub.resolver_cliente`), então o de-para de cliente é direto.
  `NK_WMS_CLIENTE` (o nome) vem **vazio** para vários clientes, incluindo a GR;
  agrupar por nome do fato não funciona, por código sim.
- **`RMSPII` no DW é UM CNPJ** (`06975242000187`, instância `SLIN_RMSPII_PRD`),
  enquanto o DataHub publica três pastas de filial (001/015/016). O de-para certo
  é *um CNPJ no DW ↔ três códigos de filial na origem* — a leitura de 06/ago ("o
  BI agrega as três") está correta no efeito, mas imprecisa na forma.
  **Provado em 10/ago** (coluna `Empresa` da fonte + cadastro Protheus) e com
  ressalva nova: a MESMA instância também alimenta as filiais MAQ, RPII e uma
  VAZIA no fato (~27,5 kt/semestre fora do BI-RMSPII) — ver
  [[depara-filial-rmspii-dw]].
- **Cobertura:** out/2021 a jul/2026, 24 filiais. **Julho/2026 está parcial** (o
  extrato é de 16/07) — nunca comparar jan-jul contra este arquivo sem dizer isso.
  Resolvido em 14/ago com uma segunda extração: `data/fato2.csv` (14/ago 07:39)
  tem julho fechado + agosto parcial, mas só ~3,9 k linhas — é **corte delta**,
  com histórico anterior incompleto (junho traz 82 linhas contra 2.353 no
  original). Nenhum dos dois serve sozinho.

### Unir duas extrações: por `PK_FATO_VOLUMETRIA`, a mais nova vencendo

`PK_FATO_VOLUMETRIA` é chave primária estável entre extrações, então
`{**antiga, **nova}` dá histórico longo + mês fechado sem dupla contagem
(145.601 PKs a partir de 142.909 + 3.917, com 1.225 em comum). Três coisas que
essa união revelou e que valem para qualquer extração futura:

- **O último dia de uma extração é sempre parcial.** As 3 linhas da RMSPII que
  mudaram entre as duas extrações são *todas* de 16/07, o dia em que a primeira
  rodou (16:33). Uma delas quase dobrou: PIMENTA VERDE, recebimento de 17,0 t →
  31,8 t. Descartar o último dia, ou declará-lo.
- **O DW revisa número retroativamente, e nos DOIS sentidos.** 111 PKs mudaram
  de medida na `FATO_VOLUMETRIA`; as maiores são MDLZ_PRD/CWBII com **−846,9 t**
  num único dia. Número do DW não é imutável depois de publicado.
  **Medido de novo em 25/ago/2026, agora nas tabelas de catering
  (`FATO_VOL_EXP_CAT_V01`), e para CIMA:** comparando linha por linha o CSV de
  21/ago contra o DW de 25/ago em jan–jul/2026, **306 linhas de 38.827 (0,79%)**
  tiveram `QTDE_VLR_SEPARADO` alterado, somando **+391.943,15**. Nove das dez
  medidas conferidas ficaram byte a byte idênticas — só o **valor separado**
  mudou, que é a medida que amadurece por último (depende da separação física
  ser concluída e valorizada). A distribuição cresce com a proximidade: jan 9,
  fev 4, mar 10, abr 42, mai 57, jun 86, **jul 98** — quanto mais recente o mês,
  mais revisão pendente. Oito linhas saíram de vazio/zero para ter valor. Todas
  carregam `DW_DATA_ALTERACAO` do mesmo instante do rebuild. **Consequência
  prática: extração em arquivo envelhece em silêncio** — quem lê o CSV de
  21/ago está com o valor separado desatualizado e não tem como saber. É o
  argumento mais concreto a favor de ler o DW ao vivo com carga incremental por
  `DW_DATA_ALTERACAO`, que é o que a V3.5 faz.
- **`NOME_FANTASIA` em `clientesDw.csv` é truncado em 20 caracteres**
  ("SODEXO DO BRASIL COM", "GR SERVICOS E ALIMEN"). Quando `len(fant) >= 20`,
  usar `RAZAO_SOCIAL` — é a única versão completa.

**Why:** economiza o caminho inteiro de "pedir print para a controladoria" e
elimina o erro de ler número de imagem, que já causou a comparação
banana-com-manga de 06/ago.
**How to apply:** para qualquer conciliação de volumetria, usar este arquivo como
lado do BI e o `fato` filtrado por `NK_OPERACAO` conforme a grandeza (entrada =
`Recebimento`, saída = `Expedição`). Ver [[conciliacao-rmspii-primeira-passada]]
para o resultado da RMSPII e [[chaves-nf-entrada-datahub]] para o limite do lado
do DataHub.
