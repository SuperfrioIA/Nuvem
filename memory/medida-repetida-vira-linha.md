---
name: medida-repetida-vira-linha
description: Medida que se repete (as 3 faixas da saída) entra como LINHA dentro da hierarquia, não como coluna; coluna é do tempo
metadata:
  type: feedback
---

Quando a mesma medida existe em mais de uma versão — as três faixas da saída
(`Solicitado pelo cliente`, `Atendido pelo estoque`, `Separado fisicamente`) —
ela entra como **nível da árvore**, abrindo em linhas dentro do cliente. Coluna
é do tempo (mês). Pedido da Maria em 18/ago/2026, na matriz do artefato:
*"dentro do cliente precisa abrir mais 3 linhas"* … *"se não fica indo pro
lado"*.

**Why:** a versão com as três faixas como colunas de total ficou com 1.416 px de
tabela e rolagem horizontal — ela lê a matriz na largura da tela, e o que sai do
campo de visão some. Como linha, a comparação fica na vertical, empilhada, e a
largura cai pra 1.158 px. O mesmo pedido veio junto de *"tem muito dado, muita
informação, está confuso"*: ela cortou três gráficos e um resumo executivo para
sobrar **uma tabela só**. Densidade ela aceita; tela com muitos blocos, não.

**How to apply:** na hierarquia da matriz de saída, unidade → cliente → faixa →
tipo de saída. As três faixas ficam sempre na ordem do relatório (é leitura, não
ranking) e **não somam** entre si — dizer isso na tela. O nível de cima mostra a
faixa escolhida no botão, e a dica de cada faixa compara com o **solicitado**,
não com o pai. Ver [[respostas-enxutas]], [[layout-saida-mercadorias]] e
[[validar-tela-no-navegador]].
