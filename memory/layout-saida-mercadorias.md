---
name: layout-saida-mercadorias
description: SAIDA_MERCADORIAS tem cabeçalho em dois níveis e três bandas repetidas — a banda oficial é Separado Fisicamente, mas a coluna do Peso Bruto MUDA por unidade (31 com 36 colunas, 29 com 34)
metadata:
  type: project
---

Perfilado em 06/08/2026 lendo `SAIDA_MERCADORIAS_016_2606_f1.xlsx` direto do Graph, e
**reconferido no mesmo dia em 10 arquivos das quatro unidades** (abertura do V2.3), o
que derrubou parte do que estava escrito aqui. Aba `SLIN`.

**Cabeçalho em dois níveis.** Linha 5 traz as bandas, linha 6 traz os rótulos:

```text
linha 5:  [0] GSM  [+9] Produto  [+14] Solicitado pelo Cliente
          [+20] Atendido pelo Estoque  [+26] Separado Fisicamente  [+32] Dados de Separação

linha 6:  Cliente · Cliente CNPJ · Estoque · Empresa · GSM · Operação · Data Solicitação
          Data Saída · Status Separação · Item · Código · Descrição · Pedido · Destinatário
          (Volume · EMB · Fração · EMB · Peso Liquido · Peso Bruto) x 3 bandas
          Corte Físico · Início · Final · Separador
```

**A posição do Peso Bruto NÃO é fixa — depende do layout da unidade:**

| Unidade | Colunas | `Cliente`/`Cliente CNPJ` | Banda *Separado Fisicamente* | `Peso Bruto` |
|---|---:|---|---:|---:|
| RMSPII, CWB3, RJ | 36 | sim | col 26 | **col 31** |
| SANCA | 34 | **não** | col 24 | **col 29** |

O layout de 34 da SANCA é estável nas três competências dela (2606, 2607, 2608).
**Ler a coluna 31 num arquivo da SANCA leria `Início`, um timestamp, como peso.**

**Não existe coluna de valor na saída, em nenhuma unidade** — os rótulos terminam em
`Corte Físico / Início / Final / Separador`. Por isso o V2.3 tem cinco métricas, não
seis: `valor_mercadoria_saida` não tem produtor possível.

**Cliente na saída x na entrada** — não são a mesma coisa, e é fácil trocar:
a RJ **tem** cliente na saída e **não tem** na entrada (18 colunas); a SANCA é o
inverso, tem na entrada (20 colunas) e não tem na saída.

**Partes.** As três bandas somaram `101.816` / `101.792` / `101.577` kg em 8.000 linhas
— 0,23% entre o pedido e o separado, nível de atendimento de graça, métrica futura.
São até 18 MB por parte, `_f1` + `_f2`, e as duas casam na mesma
`(codigo_origem, competencia)` — acionam `_abortar_se_origens_colidem`
(`processamento_datahub.py`), então concatenar é pré-requisito. **`_f1` e `_f2` são
DISJUNTOS** (interseção zero em dois pares conferidos) — ao contrário do
`DADOS_GERAIS`, onde `_f2` é cópia. **A CWB3 publica sem sufixo `_fN`** e 12 das 130
competências têm parte única: o padrão de nome precisa aceitar 1..N partes.

**Escopo.** 248 arquivos, 2,60 GB, competências 2110..2608. Só 2026: 72 arquivos,
616 MB. `Status Separação` = `Concluído` em 296.586 linhas amostradas, **nenhum
`Cancelado`** — o filtro entra como defesa, não como saneamento.

**`GUIAS_SAIDA` não serve para volumetria.** Cabeçalho na linha 2, 31 colunas, 0,2 MB
— mas **não tem `Peso Bruto`** (só `Peso Líq.`) e **não tem CNPJ do cliente**, só o
nome. Grão de guia. Serve para produtividade de separação, não para volumetria.
**E não serve nem para medir cancelamento em toneladas** (conferido em 10/ago/2026,
12 arquivos 001+016 jan–jun): TODA guia com `Status Separação = Cancelado` (402) ou
cortada integralmente (`Corte Contábil = 1`, 125) tem `Peso Líq.` **zero** — na saída
o peso nasce na separação, diferente da `GUIAS_ENTRADA`, onde o cabeçalho da guia
cancelada mantém peso e valor. Só publica 001 e 016 (015 não tem). Ver
[[conciliacao-saida-rmspii]].

**Why:** o leitor de `ENTRADA_MERCADORIAS` busca coluna **por nome** com "primeira
ocorrência ganha" (`backend/services/entrada_mercadorias.py`), o que nesta família
leria a banda errada em silêncio. E validar só a linha 6 não basta: os rótulos são
idênticos nos dois layouts, só as posições mudam.

**How to apply:** o leitor localiza a banda na **linha 5** e lê `Peso Bruto` no
deslocamento `+5` a partir do início dela, conferindo que o rótulo naquela posição é
mesmo `Peso Bruto` antes de ler qualquer linha. Nunca posição chumbada. Validar linha
5 **e** linha 6. Ler uma parte por vez (pico de memória ~2x no download) e agregar em
streaming — um arquivo tem 99.628 linhas. Plano do lote:
[[../docs/V2_3_PLANO_EXECUCAO.md]]; ver também [[operacao-e-tipo-estoque]] (o
`Estoque` da saída traz valores novos, e `CONG FLV (CUCINARE)` vira pendência).
