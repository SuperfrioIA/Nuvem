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
- **Cobertura:** out/2021 a jul/2026, 24 filiais. **Julho/2026 está parcial** (o
  extrato é de 16/07) — nunca comparar jan-jul contra este arquivo sem dizer isso.

**Why:** economiza o caminho inteiro de "pedir print para a controladoria" e
elimina o erro de ler número de imagem, que já causou a comparação
banana-com-manga de 06/ago.
**How to apply:** para qualquer conciliação de volumetria, usar este arquivo como
lado do BI e o `fato` filtrado por `NK_OPERACAO` conforme a grandeza (entrada =
`Recebimento`, saída = `Expedição`). Ver [[conciliacao-rmspii-primeira-passada]]
para o resultado da RMSPII e [[chaves-nf-entrada-datahub]] para o limite do lado
do DataHub.
