---
name: radar-recebimento-fonte-dw
description: Em 21/ago/2026 o artefato Radar de Recebimento saiu do SharePoint DataHub e passou a ler duas extrações do DW (FATO_VOL_REC_CAT / FATO_VOL_EXP_CAT); kit de build versionado em Documents\analises\_build_radar
metadata:
  type: project
---

O artefato **Radar de Recebimento**
(`https://claude.ai/code/artifact/394080d5-0798-4847-b75e-bd1219843f6e`) trocou
de fonte em 21/ago/2026, a pedido da Maria. Antes lia o SharePoint DataHub via
Graph, arquivo por arquivo; agora lê `docs/Analise/dm_volumetriaRecebimento.csv`
e `dm_volumetriaExpedicao.csv` — extrações diretas do DW, processo
`catering_to_dw_volumetry_v01` (tabelas `FATO_VOL_REC_CAT` e
`FATO_VOL_EXP_CAT`), salvos em **21/ago/2026** — as linhas foram carregadas no
DW entre 20 e 21/ago. **Cuidado com essa data:** eu afirmei "extraídas em
20/ago" olhando o `DW_DATA_INCLUSAO` da PRIMEIRA linha, e a Maria pegou o erro.
Agora nome de arquivo, data do arquivo e faixa de carga saem do payload
(`identidade` no `dados_radar.json`), nunca escritos à mão na tela.

**Onde fica o que constrói:** `C:\Users\maria.watanabe\Documents\analises\_build_radar\`
— `radar_template.html` (a tela), `ler_dw_volumetria.py` (carregador),
`build_radar.py` (monta o HTML final em `..\radar_recebimento.html`),
`monta_conciliacao.py` + `bi_mov.json` → `conciliacao.json` (o lado BI),
`montserrat_b64.txt` e `logo_branco_b64.txt` (assets embutidos). Fora do
repositório, como manda [[modo-laboratorio-poc]]. Ciclo: `ler_dw_volumetria.py`
→ `build_radar.py` → `node --check check.js` → navegador → publicar no MESMO
URL. Antes disso o kit vivia só no scratchpad temporário de uma sessão — foi
copiado para não morrer com o Temp.

**Decisões da leitura** (Maria, 21/ago): as **6 unidades** da base entram (o RJ
finalmente com cliente); unidade = `NOME_UND`; armazém = instância + filial
SLIN; cliente = `NK_CLIENTE` (raiz do CNPJ) com razão social canonizada pela
grafia de maior peso e **nenhuma raiz unida a outra** (o BI mantém separadas —
FLV e Cucinare deixaram de ser unidas); data = `DATA_SOLIC`; **todo status
entra**, com Cancelado e NF-e Emitida declarados na tela; tipo de estoque pela
mesma regra de palavra-chave do backend V2.2, replicada no carregador.

**O que a troca provou (peso bruto, RMSPII):**
- A base nova **reproduz** a base antiga do DataHub em fev–jul: diferença de
  −0,36% a +0,21%, e jun em 0,00%. Trocar a fonte não mexeu no número.
- **Janeiro melhorou 38,9%** (9.712,9 → 13.493,5 t): faltava o arquivo da
  filial 015 no DataHub, e com ele a SODEXO inteira. Janeiro deixa de ser mês
  "não usar".
- O gap do recebimento contra o BI (11–17%) **é a guia cancelada**, confirmado:
  base + cancelada já medida fecha jul em −0,01% e jun em −0,15%. A base nova
  traz 1 linha cancelada em 36 mil — é a base da guia concluída. Março (−4,0%)
  e maio (−2,0%) seguem abertos.
- A **expedição fecha** (o lado que antes não fechava): RMSPII entre −0,6% e
  +1,8% em jan–mai e jul, Curitiba dentro de 2% nos oito meses. Junho da RMSPII
  em −5,4% e a SANCA em jun/jul seguem abertos.

**O que a base nova NÃO tem:** nota fiscal (nem para contagem), SKU distinto (a
fonte só dá `QTDE_SKU` por guia) e quantidade de pallet na expedição. Em troca
entrou `NUM_GEM`, que o `fato.csv` não tem — contagem de guia voltou a ser
possível. Ver [[depara-filial-rmspii-dw]], [[fato-volumetria-dw]],
[[conciliacao-rmspii-primeira-passada]] e [[guia-entrada-ler-por-data]].

**Não conciliado ainda:** RJ (23,8 kt de recebimento), Mairinque (8,0 kt) e
Ribeirão (4,7 kt) não têm referência na extração do `fato.csv` que serve de
lado BI — para fechá-las basta uma extração nova do fato incluindo as unidades.

---

**Ampliado em 21/ago/2026, na mesma conversa.**

- **O DataHub saiu de TUDO na tela.** A Maria foi explicita: "precisamos
  esquecer a parte do datahub... Se caso estiver em outras telas, precisa parar
  de trazer dados do datahub. Nao pode considerar." Sairam as duas colunas que
  ainda vinham dele na Conciliacao: a base antiga por item e a guia cancelada
  medida em `GUIAS_ENTRADA`. O `conciliacao.json` agora so tem o lado
  `FATO_VOLUMETRIA`, que tambem e DW. A tela nao nomeia mais o DataHub em
  nenhum lugar. **Isso vale para o artefato, nao para o produto:** o
  `backend/` da V2 continua ingerindo o DataHub por arquitetura -- mudar isso
  seria outra decisao, com lote.
- **Consequencia medida:** sem a coluna de cancelada, o gap do recebimento
  contra o BI deixa de ser decomposto. A tela passa a declarar o que da para
  provar so com DW: a diferenca e sistematica (-8,9% a -16,8% na RMSPII), tem o
  mesmo sinal todo mes, e a expedicao fecha no mesmo periodo e nas mesmas
  unidades -- logo nao e periodo, de-para nem unidade. **Quantificar a guia
  cancelada exige uma extracao do DW que a inclua**; a `FATO_VOL_REC_CAT` traz
  so a concluida. E o proximo pedido ao time do DW.
- **Secao `Volumetria` nova**, no formato do painel do BI que a Maria mandou:
  grafico de evolucao (movimentacao / recebimento / expedicao, com rotulo em
  cada ponto, alternando mes-dia e normal-acumulado) e grafico de colunas por
  categoria (unidade / cliente / operacao, duas barras por categoria). **Nao
  existe "ano anterior"** na extracao (jan-ago/2026), entao as duas series sao
  os MOVIMENTOS, nao os anos -- comparar com 2025 exige extracao nova. Budget
  ficou fora por decisao dela.
- **Matriz com os dois movimentos juntos** (`Entrada + saida`): niveis unidade
  -> cliente -> movimento, sem abrir tipo de operacao (abrir os dois lados dava
  29 tipos por cliente). O total da linha e movimentacao -- giro contado duas
  vezes, que e a leitura do BI, nao saldo. Nao ficou poluido: 6 unidades, 14
  clientes, 2 movimentos.
- Numeros do periodo, peso liquido: recebimento **156.747,7 t**, expedicao
  **160.735,5 t**, movimentacao **317.483,2 t**.
- **Unidade e exibida pela SIGLA, nao pelo nome** (Maria, 21/ago: "nos
  controlamos por sigla, nao por nome -- 'rio de janeiro' = rmrj"). A sigla vem
  de `NK_WMS_FILIAL` (identica a `NK_QLS_FILIAL` em 100% das linhas) e o de-para
  sigla <-> `NOME_UND` e **1:1** nas duas bases, sem linha vazia:
  `RMSPII` = RMSPII - BARUERI, `RMRJ` = RIO DE JANEIRO, `RMSPV` = **RMSPIV -
  SANCA**, `MAQ` = MAIRINQUE, `CWBIII` = UNIDADE CURITIBA, `RPII` = SF RPII -
  RIBEIRAO. O nome do DW ficou na ultima coluna do de-para, para nao perder
  rastreabilidade. Efeito colateral bom: com sigla, o de-para contra o
  `fato.csv` virou identidade (RMSPII/CWBIII/RMSPV).
- **A SANCA e a unica sigla decidida fora da fonte: exibe RMSPIV.** A fonte
  discorda de si mesma nessa unidade -- `NOME_UND` diz "RMSPIV - SANCA", a
  instancia diz `SLIN_RMSPIV_PRD` e `NK_WMS_FILIAL` diz **RMSPV**. A Maria
  decidiu **RMSPIV** em 21/ago/2026 ("pode deixar RMSPIV"), e isso e regra de
  negocio, nao leitura. Vive numa constante explicita (`SIGLA_EXIBIDA` no
  carregador), a tela mostra a sigla da fonte numa coluna propria do de-para, e
  a conciliacao casa RMSPIV <-> RMSPV do fato. Nenhuma outra unidade tem
  excecao. Ver [[confirmar-sigla-antes-de-citar-filial]].

