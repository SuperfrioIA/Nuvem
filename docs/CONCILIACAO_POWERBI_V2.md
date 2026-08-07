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
| D-2 | Famílias não integradas | A V2 lê `ENTRADA_MERCADORIAS` e `SAIDA_MERCADORIAS`. `DADOS_GERAIS`, `OCORRENCIAS_ENTREGAS`, `GUIAS_SAIDA`, `ESTOQUE_POR_LOTE`, `PALLETS_EXCEDENTES` e a família `(UA)` ficam fora (decisões 7 e da seção 6 da proposta V3) | **Nuvem MENOR**, se o BI usar alguma delas |
| D-3 | Grão de UA × grão de item | A família `ENTRADA_MERCADORIAS (UA)` tem os mesmos rótulos de coluna com grão de UA. Tratá-la como a integrada **dobraria** quantidade — é por isso que ela está fora | não aplicável (fora por construção) |
| D-4 | Balde "sem cliente identificado" | Cliente sem cadastro na Nuvem cai num balde próprio, exibido como número separado por causa (D5.1 do V2.3). No BI o valor está dentro do cliente | **por cliente**: Nuvem menor; **no total**: igual |
| D-5 | RMRJ não tem coluna de cliente | O layout de 18 colunas da RJ não publica cliente (conferido no dado, 06/ago) — toda a RMRJ cai no balde, sem CNPJ para cadastrar | **por cliente**: Nuvem menor; **no total**: igual |
| D-6 | RMSPV não tem cliente na **saída** | Layout de 34 colunas (conferido em 10 arquivos, 06/ago) | idem D-5, na direção saída |
| D-7 | Banda escolhida na saída | A saída é lida na banda oficial *Separado Fisicamente*, não em *Corte Físico* nem nos totais da guia — decisão do V2.3, e a coluna do `Peso Bruto` muda de posição por unidade (31 com 36 colunas, 29 na SANCA) | depende de qual banda o BI usa — **a confirmar** |
| D-8 | Sem valor na saída | Não existe coluna de valor em `SAIDA_MERCADORIAS` em nenhuma unidade (decisão D1 do V2.3) | comparação de **valor** só existe na entrada |
| D-9 | Escopo temporal da saída | Só 2026 (decisão D3 do V2.3). Competência anterior fica `null`, nunca zero | comparação de saída **só vale de jan/2026 em diante** |
| D-10 | Nome de cliente | WYDA (BI) = CUCINARE PRO ALIMENTAÇÃO (Nuvem) — nome comercial × razão social, confirmado pela Maria. E a fonte tem a mesma raiz de CNPJ com até 3 grafias diferentes | some ao agrupar pela **raiz do CNPJ**, nunca pelo nome |
| D-11 | Filial homônima | **Quatro** unidades têm o mesmo nome de cadastro "Barueri/SP": RMSPII, RMSPIII, RMSPIV e RMSPV (`backend/seed_depara.py`) — inclusive a RMSPIV, que é a `016` e entra no agregado "RMSPII" do BI. CWBIII e CWBIV compartilham "São José dos Pinhais/PR" | risco de comparar a unidade errada — usar **sigla**, nunca nome. É por isso que `scripts/conciliacao.py` recebe e imprime sigla |

---

## 4. Pendências registradas (diferença ainda sem explicação)

| # | Pendência | O que falta |
|---|---|---|
| P-0 | O padrão irregular de P-2 tem um candidato barato de checar antes dos outros | Comparar o **tamanho do balde "sem cliente identificado"** (que o script imprime) com a soma dos cinco gaps de 10–22 %. Linha com `Cliente CNPJ` que não casa na raiz cadastrada cai no balde da Nuvem e dentro do cliente no BI — produziria exatamente esse padrão |
| P-1 | **O gap de 13,2 % tem o sinal contrário ao previsto.** D-1 (devolução, 39 % das linhas) deveria deixar a Nuvem **maior**; ela está **menor**. Ou o relatório do BI não isola Recebimento como o rótulo sugere, ou o BI usa fonte que a `ENTRADA_MERCADORIAS` não cobre (D-2) | Confirmar com quem mantém o relatório do BI **qual fonte e qual filtro de operação** ele usa. Sem isso não se sabe quanto do gap é D-1 e quanto é D-2 |
| P-2 | **Quatro clientes batem quase exato (1,9–4,8 %) e cinco têm gap de 10–22 %**, sem correlação com tamanho (FLV 7 é pequeno e tem o maior gap relativo). Não é o padrão que D-1 previa | Investigar linhas com `Cliente CNPJ` que não casa na raiz cadastrada: elas caem no balde da Nuvem (D-4) e dentro do cliente no BI, o que produziria exatamente esse padrão irregular. `scripts/conciliacao.py` já imprime o balde como linha própria — comparar o tamanho dele com a soma dos cinco gaps |
| P-3 | O botão "Operação" do relatório do BI **não mudou** o gráfico quando testado em 06/ago | Reproduzir com quem mantém o relatório. Enquanto não reproduzir, tratar todo número de "Recebimento" do BI como **possivelmente não filtrado** |
| P-4 | Nenhuma comparação de **saída** foi feita ainda | Depende do deploy do V2.3 na VM. Rodar `scripts/conciliacao.py` e comparar com a saída do BI, checando antes qual banda o BI usa (D-7) |
| P-5 | O lado Nuvem desta tabela veio da **planilha**, não do banco | Rodar `scripts/conciliacao.py` na VM e substituir. Se o número do banco divergir da soma da planilha, **isso é defeito nosso** e vira lote de correção — é a checagem mais importante da próxima passada |

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

- **Não conclui que a Nuvem está certa ou errada.** O gap de 13,2 % continua
  aberto (P-1), com o sinal contrário ao previsto.
- **Não usa número novo de nenhum dos dois lados.** Os da tabela são os de
  06/ago/2026; as células que exigem a VM estão marcadas como pendentes, não
  estimadas.
- **Não ajusta nada para os números baterem.** Nenhuma métrica, filtro ou
  de-para foi mudado por causa desta comparação — se algum ajuste for
  necessário, ele vira lote com plano próprio.
