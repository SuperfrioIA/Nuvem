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
| D-7 | Banda escolhida na saída | A saída é lida na banda oficial *Separado Fisicamente*, não em *Corte Físico* nem nos totais da guia — decisão do V2.3, e a coluna do `Peso Bruto` muda de posição por unidade (31 com 36 colunas, 29 na SANCA) | depende de qual banda o BI usa — **a confirmar** |
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

- `docs/Analise/saida/conciliacao_slin_x_dw.xlsx` — três abas (SLIN, DW,
  Comparação) no grão competência × cliente, com o status por linha e o peso
  cancelado como coluna explicativa. Fora do git (`docs/Analise/` é ignorada).
- `memory/conciliacao-rmspii-primeira-passada.md` e `memory/fato-volumetria-dw.md`.

---

## 4. Pendências registradas (diferença ainda sem explicação)

### Fechadas em 10/ago/2026

| # | Como fechou |
|---|---|
| P-0 | **Negativa.** Zero linhas sem raiz de CNPJ em junho, e o total do arquivo já está abaixo — o balde não explica o padrão. A causa é a guia cancelada (seção 3.1) |
| P-1 | **A fonte do BI é a `FATO_VOLUMETRIA` do DW** (`docs/Analise/fato.csv`), operação `Recebimento`; os números do print conferem contra ela. O sinal contrário se explica pela guia cancelada, que o DW conta e o export de itens não publica |
| P-2 | **Fechada pela correlação por cliente** (seção 3.1): o cancelamento acompanha o gap cliente a cliente, inclusive na FLV 7, que era o caso que derrubava D-1 |

### Abertas

| # | Pendência | O que falta |
|---|---|---|
| P-3 | O botão "Operação" do relatório do BI **não mudou** o gráfico quando testado em 06/ago | Perdeu urgência: dá para comparar direto contra o `fato.csv`, sem depender do relatório. Ainda vale reproduzir com quem mantém o BI |
| P-4 | Nenhuma comparação de **saída** foi feita ainda | Depende de `scripts/processar_saida.py` rodar na VM — sem ele não há célula de saída no banco. Checar antes qual banda o BI usa (D-7) |
| P-5 | O lado Nuvem desta tabela veio da **planilha**, não do banco | Rodar `scripts/conciliacao.py` na VM e substituir. Se o número do banco divergir da soma da planilha, **isso é defeito nosso** e vira lote de correção |
| P-6 | **A filial `015` não publica `GUIAS_ENTRADA`** — sem esse export não dá para medir o cancelamento dela, e é exatamente onde a SODEXO fica subcoberta (38 %). São as 1.634,4 t que sobram | Pedir o export de `GUIAS_ENTRADA` da 015 (e os arquivos de `ENTRADA_MERCADORIAS` dela de julho e agosto, que também não existem) |
| P-7 | **Não está confirmado que o DW conte cada guia cancelada** — a conclusão vem de os números baterem | Extrato do DW no grão de documento (GEM), ou confirmação de quem mantém o relatório |
| P-8 | **Decisão de produto ainda não tomada:** o que a Nuvem faz com a guia cancelada | Contar como o DW conta (vira lote de código) ou declarar a diferença na tela (vira nota no Cockpit). É decisão da Maria |

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
