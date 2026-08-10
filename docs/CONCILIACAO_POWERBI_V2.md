# Conciliação Nuvem IA × Power BI — V2.6

Entregável do lote V2.6 (07/ago/2026). **Os números não precisam bater; precisam
ser rastreáveis.** Toda diferença aqui tem uma de duas coisas: explicação com
causa nomeada, ou pendência registrada com o que falta para fechá-la.

Partida: `memory/conciliacao-rmspii-primeira-passada.md` (levantamento de
06/ago/2026, feito direto no SharePoint pelo Graph — a VM exigia login e não
havia credencial na conversa). Este documento não repete aquele levantamento: usa
os números dele e organiza o método para as próximas passadas.

Lado Nuvem produzido por **`scripts/conciliacao.py`** (somente leitura, roda na
VM): total por competência, total por unidade física com o agregado do BI, e
ranking por cliente agrupado pela raiz do CNPJ.

> **Atualização de 10/ago/2026 — o gap tem causa nomeada.** Uma segunda passada,
> agora contra a fonte que o Power BI realmente consome (`docs/Analise/fato.csv`,
> a `FATO_VOLUMETRIA` do DW) em vez de prints, isolou a origem da diferença:
> **guia de entrada cancelada**. Ver a **seção 3.1**. Isso fecha P-0, P-1 e P-2 e
> descarta D-2 e D-3. As seções 1 e 2 ficam como estão — são o registro da
> primeira passada, e os números do BI que elas usam foram **confirmados** contra
> o DW (SODEXO jan–jul: 38.779,3 t no fato contra 38.780 t no print).
>
> **Atualização de 10/ago/2026 (segunda passada do dia, sessão autônoma) — a
> SAÍDA foi medida e os de-paras foram provados.** Ver a **seção 3.2** (saída:
> gap de 8,1% com causa parcial), a **seção 3.3** (de-para de filial e a
> descoberta MAQ/RPII) e a **seção 3.4** (de-para de cliente). Fecha P-4, P-5 e
> a pendência D-7 (banda); dimensiona P-6; abre P-9, P-10 e P-11. Relatório
> completo e planilha (12 abas):
> `docs/Analise/saida/relatorio_conciliacao_volumetria_20260810.md` e
> `docs/Analise/saida/conciliacao_slin_x_dw.xlsx`.

---

## 1. A armadilha que precisa ser dita antes de qualquer número

**No Power BI, o filtro "Unidade: RMSPII" agrega três filiais físicas** — `001`,
`015` e `016`, que na Nuvem são RMSPII, RMSPIII e RMSPIV. Comparar a RMSPII da
Nuvem com a "RMSPII" do BI dá **2,68× de diferença** (40.490 t contra 108.525 t)
e manda todo mundo procurar um defeito que não existe.

Isso é coerente com `memory/filiais-catering-poc.md`: a controladoria enxerga as
três juntas. `scripts/conciliacao.py --unidade RMSPII_AGREGADA` produz a leitura
do BI; sem esse flag, cada unidade aparece separada.

Segunda armadilha, da mesma família: **comparar períodos diferentes**. A primeira
passada comparou Nuvem até julho com Power BI até agosto — "banana com manga", a
Maria pegou o erro. Regra registrada em
`memory/comparar-mesmo-periodo-nos-dois-lados.md`: conferir linha por linha, no
mesmo recorte, e nunca inferir um mês por subtração de dois acumulados de print.

---

## 2. Tabela Nuvem × Power BI — peso de entrada, jan–jul/2026

Recorte: `--de 2026-01 --ate 2026-07 --unidade RMSPII_AGREGADA`. Lado Nuvem da
passada de 06/ago (somado do SharePoint); lado BI dos prints da Maria.

| Fonte | 001 (RMSPII) | 015 (RMSPIII) | 016 (RMSPIV) | Total |
|---|---:|---:|---:|---:|
| Nuvem | 40.490 t | 23.768 t | 29.992 t | **94.250 t** |
| Power BI ("RMSPII" agregada) | — | — | — | **108.525 t** |
| **Diferença** | | | | **14.275 t (13,2 %), Nuvem abaixo** |

### Por cliente (raiz do CNPJ, WYDA=CUCINARE já unificado)

| Cliente | Nuvem (t) | Power BI (t) | Diferença | % |
|---|---:|---:|---:|---:|
| SAPORE S.A. | 37.257 | 44.192 | 6.935 | 15,7 % |
| SODEXO DO BRASIL | 34.878 | 38.780 | 3.902 | 10,1 % |
| GR SERVIÇOS E ALIMENTAÇÃO | 11.770 | 14.322 | 2.552 | 17,8 % |
| CUCINARE / WYDA | 3.824 | 4.479 | 655 | 14,6 % |
| NOVITA ALIMENTAÇÃO | 2.782 | 2.843 | 61 | 2,1 % |
| PIMENTA VERDE | 2.556 | 2.606 | 50 | 1,9 % |
| CONVIDA REFEIÇÕES | 683 | 702 | 19 | 2,7 % |
| FLV 7 RESTAURANTES | 324 | 416 | 92 | 22,2 % |
| OG DO BRASIL | 175 | 184 | 9 | 4,9 % |
| **Total** | **94.250** | **108.525** | **14.275** | **13,2 %** |

Duas notas de precisão sobre a tabela acima, levantadas na revisão independente:

- a coluna Nuvem **soma 94.249**, não 94.250: o total da linha é o da seção
  anterior (soma por unidade), e a diferença de 1 t é arredondamento das linhas
  por cliente — não é divergência de dado;
- **falta a linha do balde "sem cliente identificado"**, que
  `scripts/conciliacao.py` imprime. Na passada de 06/ago ele não foi apurado por
  cliente; se na próxima passada ele for maior que zero, o Total deixa de
  reconciliar com a coluna até essa linha entrar. É a diferença D-4/D-5
  aparecendo como número.

**Células que dependem da VM e não foram preenchidas por estimativa:** saída,
total movimentado e saldo (o par de saída só existe depois do deploy do V2.3, que
ainda não aconteceu), e a re-medição do lado Nuvem pelo banco em vez de pela
planilha. Rodar `scripts/conciliacao.py` na VM depois do deploy fecha as duas.

---

## 3. Diferenças conhecidas, com causa nomeada

Estas explicam diferença **sem serem defeito**. Cada uma tem o efeito esperado no
sinal da diferença — e é comparando o sinal esperado com o observado que se
descobre que ainda falta explicação (seção 4).

| # | Diferença | Causa | Efeito esperado |
|---|---|---|---|
| D-1 | `Operação` soma tudo | Decisão 6: a Nuvem não usa `Operação` como dimensão, então devolução e transferência entram no peso movimentado. Devolução é **39 %** das linhas na amostra (`memory/operacao-e-tipo-estoque.md`) | **Nuvem MAIOR** que o BI, se o BI isolar Recebimento |
| D-2 | Famílias não integradas | A V2 lê `ENTRADA_MERCADORIAS` e `SAIDA_MERCADORIAS`. `DADOS_GERAIS`, `OCORRENCIAS_ENTREGAS`, `GUIAS_SAIDA`, `ESTOQUE_POR_LOTE`, `PALLETS_EXCEDENTES` e a família `(UA)` ficam fora (decisões 7 e da seção 6 da proposta V3) | ~~**Nuvem MENOR**, se o BI usar alguma delas~~ — **medido em 10/ago: a `(UA)` não é fonte extra.** Junho soma **13.524,045 t nas duas famílias**, valor idêntico. Não explica nada do gap |
| D-3 | Grão de UA × grão de item | A família `ENTRADA_MERCADORIAS (UA)` tem os mesmos rótulos de coluna com grão de UA. Tratá-la como a integrada **dobraria** quantidade — é por isso que ela está fora | confirmado no dado (10/ago): 30.356 linhas na `(UA)` contra 18.026 na integrada, **mesmo peso total** — é o mesmo movimento no grão de palete |
| D-4 | Balde "sem cliente identificado" | Cliente sem cadastro na Nuvem cai num balde próprio, exibido como número separado por causa (D5.1 do V2.3). No BI o valor está dentro do cliente | **por cliente**: Nuvem menor; **no total**: igual |
| D-5 | RMRJ não tem coluna de cliente | O layout de 18 colunas da RJ não publica cliente (conferido no dado, 06/ago) — toda a RMRJ cai no balde, sem CNPJ para cadastrar | **por cliente**: Nuvem menor; **no total**: igual |
| D-6 | RMSPV não tem cliente na **saída** | Layout de 34 colunas (conferido em 10 arquivos, 06/ago) | idem D-5, na direção saída |
| D-7 | Banda escolhida na saída | A saída é lida na banda oficial *Separado Fisicamente*, não em *Corte Físico* nem nos totais da guia — decisão do V2.3, e a coluna do `Peso Bruto` muda de posição por unidade (31 com 36 colunas, 29 na SANCA) | ~~depende de qual banda o BI usa — a confirmar~~ **medido em 10/ago: a banda NÃO explica o gap da saída.** Jan–jun RMSPII: Solicitado 86.251,4 / Atendido 84.394,3 / Separado 85.150,1 t — 1,3% entre a maior e a menor, contra gap de 8,1% ante o DW. Trocar de banda move no máximo 1.101 t dos 7.544 t |
| D-8 | Sem valor na saída | Não existe coluna de valor em `SAIDA_MERCADORIAS` em nenhuma unidade (decisão D1 do V2.3) | comparação de **valor** só existe na entrada |
| D-9 | Escopo temporal da saída | Só 2026 (decisão D3 do V2.3). Competência anterior fica `null`, nunca zero | comparação de saída **só vale de jan/2026 em diante** |
| D-10 | Nome de cliente | WYDA (BI) = CUCINARE PRO ALIMENTAÇÃO (Nuvem) — nome comercial × razão social, confirmado pela Maria. E a fonte tem a mesma raiz de CNPJ com até 3 grafias diferentes | some ao agrupar pela **raiz do CNPJ**, nunca pelo nome |
| D-11 | Filial homônima | **Quatro** unidades têm o mesmo nome de cadastro "Barueri/SP": RMSPII, RMSPIII, RMSPIV e RMSPV (`backend/seed_depara.py`) — inclusive a RMSPIV, que é a `016` e entra no agregado "RMSPII" do BI. CWBIII e CWBIV compartilham "São José dos Pinhais/PR" | risco de comparar a unidade errada — usar **sigla**, nunca nome. É por isso que `scripts/conciliacao.py` recebe e imprime sigla |

---

---

## 3.1 A causa do gap: guia de entrada cancelada (10/ago/2026)

**A Nuvem só conta entrada que virou item; o Power BI conta também a entrada que
foi cancelada.** A guia cancelada permanece no WMS com cliente, NF, peso e valor
no cabeçalho — e o DW conta esse movimento —, mas **não gera nenhuma linha de
item**, e o export `ENTRADA_MERCADORIAS` que a Nuvem lê é uma lista de itens.
A Nuvem soma item, o DW soma movimento; por isso a Nuvem fica sistematicamente
embaixo, com o sinal contrário ao que D-1 previa.

Isso já estava registrado como característica da fonte desde 30/jul
(`memory/chaves-nf-entrada-datahub.md`: "guias canceladas existem e não têm linha
de item"). O que faltava era medir.

### Recorte da medição

Jan–jun/2026, entrada, peso bruto, RMSPII (`001`+`015`+`016` do lado da fonte;
filial `RMSPII` do lado do DW). Julho ficou de fora porque o extrato do
`fato.csv` é de 16/jul — mês parcial não entra em comparação.

| | t |
|---|---:|
| Nuvem (`ENTRADA_MERCADORIAS`, 18 arquivos) | 85.958,4 |
| DW / Power BI (`FATO_VOLUMETRIA`, `Recebimento`) | 98.886,8 |
| **Gap** | **12.928,4 (13,1 %)** |
| Guias canceladas medidas (só `001` e `016`) | **11.294,0 — 87 % do gap** |
| Sobra sem explicação | 1.634,4 |

São **1.801 guias canceladas**, R$ 171,0 mi de valor de nota. O gap aparece nos
seis meses, sempre no mesmo sentido (8,9 % a 17,0 %).

### O que sustenta a conclusão: a correlação por cliente

Quem quase não cancela quase não diverge; quem cancela às centenas diverge muito.
**FLV 7 — o menor cliente com movimento e o de maior gap relativo — bate em
100 %.** Isso é o que P-2 pedia e não é coincidência de total.

| Cliente | Guias canceladas | Cancelado (t) | Gap (t) | Cobertura |
|---|---:|---:|---:|---:|
| SAPORE | 767 | 5.957,7 | 5.617,8 | 106 % |
| SODEXO | 155 | 1.476,7 | 3.924,7 | 38 % |
| GR SERVIÇOS | 489 | 2.874,3 | 2.549,7 | 113 % |
| CUCINARE / WYDA | 215 | 732,6 | 637,3 | 115 % |
| FLV 7 | 58 | 92,6 | 92,7 | 100 % |
| PIMENTA VERDE | 39 | 85,5 | 44,4 | 193 % |
| NOVITA | 39 | 56,8 | 38,8 | 146 % |
| CONVIDA | 25 | 11,0 | 15,5 | 71 % |
| OG DO BRASIL | 14 | 6,8 | 7,5 | 91 % |

### Não é devolução

Do peso cancelado: 8.299,5 t em `NÃO TROCA NOTA DE ARMAZENAGEM`, 2.933,4 t em
`ENTRADA NORMAL/NF ARMAZENAGEM`, e **devolução é 38,7 t — 0,3 %**. A leitura de
D-1 (devolução como origem da diferença) está morta como explicação do gap.

### Descartado com número, não por argumento

| Hipótese | O que a medição mostrou |
|---|---|
| Família `(UA)` como fonte extra (D-2/D-3) | Junho soma **13.524,045 t nas duas famílias** — mesmo movimento, grão de palete |
| Cliente sem CNPJ / balde (P-0) | **Zero linhas** sem raiz de CNPJ válida em junho. E o *total* do arquivo já está abaixo: atribuição de cliente não move o total |
| Peso bruto × líquido | Mesmo gap no líquido (83.737,0 × 97.506,2 t, 14,1 %) — não é tara nem definição de peso |
| Corte de data na virada do mês | Os seis meses vão no mesmo sentido; se fosse competência × data de movimento, alternariam |
| Filtro de operação | A soma da Nuvem já inclui todas as operações, devolução e transferência interna inclusive |

### Limite da prova

É explicação de **ordem de grandeza e de padrão**, não casamento documento a
documento: o `fato.csv` é agregado por dia × cliente × operação, sem grão de
documento. As coberturas acima de 100 % indicam que o DW **não** conta todas as
canceladas — a leitura provável é que guia cancelada e reemitida entre uma vez
só. Fechar 1:1 exige extrato do DW no grão de GEM.

### Artefatos

- `docs/Analise/saida/conciliacao_slin_x_dw.xlsx` — **12 abas** desde 10/ago
  (entrada, saída, bandas, guias sem item, de-paras), cada uma com grão e bloco
  "como ler". Fora do git (`docs/Analise/` é ignorada).
- `memory/conciliacao-rmspii-primeira-passada.md` e `memory/fato-volumetria-dw.md`.

### Complemento de 10/ago (sessão autônoma) — a sobra de 1.634,4 t da entrada

- **É toda SODEXO.** Resíduo por cliente após cancelado: SODEXO **+2.448,0 t**;
  os demais entre −339,9 (SAPORE) e +4,6 t. Resíduos negativos = guia
  cancelada-e-reemitida contada uma vez só no DW.
- **A 015 é 100% SODEXO na entrada** (23.768,0 t; nenhum outro cliente tem
  linha lá) e **não publica `GUIAS_ENTRADA` nem `GUIAS_SAIDA`** (inventário ao
  vivo, 10/ago). A taxa de cancelamento da SODEXO medível em 001+016 (≈ 11,8%)
  aplicada à 015 dá ≈ 3,2 kt — mesma ordem da sobra. Consistente, não provado
  (P-6).
- Resíduo mensal após cancelado: −0,5% a +4,0% do DW, sinal alternante.

---

## 3.2 A saída: gap de 8,1% com causa parcial (10/ago/2026)

Jan–jun/2026, peso bruto: **Nuvem 85.150,1 × DW 92.694,3 → gap 7.544,2 t
(8,1%)** (líquido: 6,9%). A leitura direta do SharePoint (36 arquivos, banda
*Separado Fisicamente*) reproduziu o número do banco da VM **exato** — a
ingestão da saída está fiel à fonte.

O que foi medido e o que só dá para estimar:

1. **Banda não é causa** — ver D-7 (fechada).
2. **O mecanismo "guia sem item" existe na saída**: 402 canceladas + 125
   cortadas integralmente (Corte Contábil=1) em 001+016. **Mas todas têm
   `Peso Líq.` = 0 na fonte** — na saída o peso nasce na separação; a guia
   cancelada não carrega peso no cabeçalho como na entrada. **A tonelagem
   cancelada de saída não é mensurável com o que o SLIN publica.**
3. **Estimativa** (contagem × peso médio da guia efetiva do mesmo cliente):
   ≈ 3.014 t líq em 001+016, +≈ 643 t extrapolando a SODEXO da 015 → ≈ 3,7 kt
   dos 7,5 kt. **SAPORE fecha em ~104%** (239 canceladas + 71 cortadas, maior
   cancelador — espelho da entrada).
4. **Anomalia de peso bruto na GR (lado DW)**: Expedição da GR com
   bruto/líquido = **1,109** contra 1,022 na fonte e 1,022 no próprio DW na
   entrada. No líquido o gap da GR cai de 18,6% para 11,6% — ≈ 1,1 kt do gap
   é definição de peso, não volume (P-11).
5. **Resíduo sem causa ≈ 2,6–3,0 kt (≈ 3% do DW)**, sistemático (positivo nos
   seis meses): GR ≈ 1 kt, PIMENTA ≈ 0,6 kt (gap relativo 14–45% ao mês!),
   SODEXO ≈ 0,6 kt, CUCINARE ≈ 0,3 kt → P-9.

---

## 3.3 De-para de filial: provado, com descoberta (10/ago/2026)

- **Na fonte:** a coluna `Empresa` da `SAIDA_MERCADORIAS` tem um único valor
  por pasta — `001/001`, `001/015`, `001/016` (3,3 mi de linhas). Pasta =
  empresa/filial SLIN.
- **No DW:** tudo isso vira **um** CNPJ (`06975242000187`, Log Frio 0001-87)
  via instância `SLIN_RMSPII_PRD`. No Protheus, RMSPIII (008002 = 0002-68) e
  RMSPIV (008003 = 0003-49) têm CNPJs próprios que **não existem no fato** — o
  DW colapsa as três filiais físicas no 0001-87. O de-para correto continua
  sendo *um CNPJ no DW ↔ três pastas na origem*, e a chave real é a
  **instância**, não o CNPJ das filiais.
- **Descoberta:** a mesma instância SLIN gera linhas no fato para **outras
  filiais DW**: MAQ (57046955000369 = CEFRI Mairinque/MAQII — SODEXO 9.226,7 t
  + ANGA ALIMENTAÇÃO 6.550,2 t em jan–jun), RPII (02060862000569 = SuperFrio
  Ribeirão Preto — SAPORE 11.107,4 t) e **22 linhas com filial vazia** (SODEXO
  668,4 t, mai–jun/26). Esse movimento fica **fora** do "RMSPII" do BI e
  **fora** das pastas 001/015/016. Não afeta o gap medido, mas é ~27,5 kt que
  qualquer comparação "tudo da RMSPII" encontraria (P-10).

## 3.4 De-para de cliente: fechado (10/ago/2026)

- **`NK_CLIENTE` (raiz do CNPJ) resolve 10/10 clientes do recorte na
  `DIM_CLIENTE`** (`clientesDw.csv`, 61.182 registros) = 100% do peso.
- `NK_WMS_CLIENTE` vem **vazio** no fato para 7/10 clientes (1.497 linhas,
  40.474 t = 21,1% do peso) — e vazio **também na dim** para os mesmos 7. A dim
  não recupera o nome do WMS; recupera razão social/fantasia/CNPJ pela raiz.
- A razão social da dim **não é confiável** em 2 de 10: `04596502` = "WYDA"
  (é CUCINARE PRO ALIMENTAÇÃO — nome comercial no campo de razão social) e
  `60691250` = "50861-CARREFOUR TIETE - LCR" (nome de loja; na fonte é LC
  ADMINISTRACAO DE RESTAURANTES). Reforça D-10: agrupar e nomear **sempre pela
  raiz do CNPJ**.

---

## 4. Pendências registradas (diferença ainda sem explicação)

### Fechadas em 10/ago/2026

| # | Como fechou |
|---|---|
| P-0 | **Negativa.** Zero linhas sem raiz de CNPJ em junho, e o total do arquivo já está abaixo — o balde não explica o padrão. A causa é a guia cancelada (seção 3.1) |
| P-1 | **A fonte do BI é a `FATO_VOLUMETRIA` do DW** (`docs/Analise/fato.csv`), operação `Recebimento`; os números do print conferem contra ela. O sinal contrário se explica pela guia cancelada, que o DW conta e o export de itens não publica |
| P-2 | **Fechada pela correlação por cliente** (seção 3.1): o cancelamento acompanha o gap cliente a cliente, inclusive na FLV 7, que era o caso que derrubava D-1 |

### Fechadas em 10/ago/2026 (segunda passada, sessão autônoma)

| # | Como fechou |
|---|---|
| P-4 | **Saída comparada** (seção 3.2): Nuvem 85.150,1 × DW 92.694,3, gap 7.544,2 t (8,1%). Não dependeu da VM: leitura direta do SharePoint + `fato.csv`. A banda foi testada junto (D-7 fechada) |
| P-5 | **O lado Nuvem foi confirmado pelo banco**: entrada 85.958,4 t e saída 85.150,0 t no `scripts/conciliacao.py` da VM = leitura direta do SharePoint (saída reproduzida em 10/ago com 85.150,1 t). Ingestão fiel à fonte nas duas direções |

### Abertas

| # | Pendência | O que falta |
|---|---|---|
| P-3 | O botão "Operação" do relatório do BI **não mudou** o gráfico quando testado em 06/ago | Perdeu urgência: dá para comparar direto contra o `fato.csv`, sem depender do relatório. Ainda vale reproduzir com quem mantém o BI |
| P-6 | **A filial `015` não publica `GUIAS_ENTRADA` nem `GUIAS_SAIDA`** (confirmado ao vivo em 10/ago) — e a 015 é **100% SODEXO** na entrada. A sobra de 1.634,4 t da entrada é toda SODEXO (+2.448,0 t de resíduo, compensado por resíduos negativos de reemissão); a taxa de cancelamento da SODEXO medível em 001+016 (≈ 11,8%) aplicada à 015 dá ≈ 3,2 kt — mesma ordem. Consistente, **não provado** | Pedir o export de `GUIAS_ENTRADA`/`GUIAS_SAIDA` da 015 (e os `ENTRADA_MERCADORIAS` dela de julho/agosto, que também não existem) |
| P-7 | **Não está confirmado que o DW conte cada guia cancelada** — a conclusão vem de os números baterem. Procurado em 10/ago nos dicionários (`apartado/volumetriaExemploIce.csv`) e nas dimensões: **nada** sobre cancelamento; o fato não tem grão de documento nem flag. Reforço indireto: resíduo mensal da entrada após cancelado fica em −0,5% a +4,0% com sinal alternante, e coberturas >100% (SAPORE 106%, GR 113%) indicam reemissão contada uma vez | Extrato do DW no grão de documento (GEM/GSM), ou confirmação da lógica do ETL `wms_to_dw_volumetry_v04` com quem mantém o DW |
| P-8 | **Decisão de produto ainda não tomada:** o que a Nuvem faz com a guia cancelada — agora vale também para a saída (cancelada + corte integral) | Contar como o DW conta (vira lote de código) ou declarar a diferença na tela (vira nota no Cockpit). É decisão da Maria |
| P-9 | **Resíduo da saída sem causa: ≈ 2,6–3,0 kt (≈ 3% do DW)**, sistemático nos seis meses, concentrado em GR (≈ 1 kt), PIMENTA (≈ 0,6 kt; gap relativo 14–45% ao mês), SODEXO (≈ 0,6 kt) e CUCINARE (≈ 0,3 kt). A tonelagem de guia cancelada/cortada de saída tem `Peso Líq.` = 0 na fonte — só dá para **estimar** por contagem × peso médio (seção 3.2) | Extrato do DW no grão de GSM, ou o peso **solicitado** das guias canceladas/cortadas direto do WMS. Sensibilidade: se a guia cancelada for maior que a média, parte do resíduo desaparece |
| P-10 | **A instância `SLIN_RMSPII_PRD` alimenta outras filiais do DW** — MAQ (CEFRI Mairinque: SODEXO 9,2 kt + ANGA 6,6 kt), RPII (SuperFrio Ribeirão Preto: SAPORE 11,1 kt) e **22 linhas com filial vazia** (SODEXO 0,7 kt, mai–jun/26) — fora do "RMSPII" do BI e fora das pastas 001/015/016 (seção 3.3) | Confirmar com a controladoria: esse movimento aparece em qual visão do BI? As linhas de filial vazia aparecem em algum lugar? Que filial SLIN as gera (002? outra)? |
| P-11 | **Anomalia de peso bruto na GR (lado DW):** Expedição com bruto/líquido = 1,109 contra 1,022 na fonte e 1,022 no próprio DW na entrada da GR — ≈ 1,1 kt do gap da GR é definição de peso, não volume | Perguntar a quem mantém o DW de onde vem o `PESO_BRUTO` da Expedição (o da fonte? o da NF? calculado?) |

---

## 5. Método para a próxima passada

1. Escolher **um** recorte e usá-lo dos dois lados (mesmos meses, mesma unidade,
   mesma direção). Nunca inferir mês por subtração de acumulado de print.
2. Lado Nuvem: `python3 scripts/conciliacao.py --de AAAA-MM --ate AAAA-MM
   [--unidade RMSPII_AGREGADA]` na VM.
3. Lado BI: print com os filtros **visíveis** na imagem (unidade, meses,
   operação) — filtro que não aparece no print não pode ser assumido.
4. Comparar **total primeiro**. Se o total bate e o per-cliente não, a causa está
   em D-4/D-5/D-10 (atribuição de cliente), não em volume.
5. Toda diferença que sobrar entra na seção 4 com o que falta para fechá-la.
   Diferença sem explicação **não vira nota de rodapé**: vira pendência.
6. Auditar até o arquivo quando precisar: `/linhagem` leva de célula →
   execução → arquivo de origem.

---

## 6. O que este documento não faz

- **Não conclui que a Nuvem está certa ou errada.** O gap tem causa nomeada
  desde 10/ago (guia cancelada, seção 3.1), mas qual dos dois lados *deveria*
  contar o cancelamento é decisão de produto, não de dado — está em P-8.
- **As seções 1 e 2 não foram reescritas.** Elas são o registro da primeira
  passada (06/ago, jan–jul, contra prints). A medição nova está na seção 3.1, com
  recorte próprio (jan–jun, contra o DW) — os dois recortes convivem de
  propósito, e o número do BI usado na primeira passada foi confirmado contra o
  DW. As células que exigem a VM continuam pendentes, não estimadas.
- **Não ajusta nada para os números baterem.** Nenhuma métrica, filtro ou
  de-para foi mudado por causa desta comparação — se algum ajuste for
  necessário, ele vira lote com plano próprio.
