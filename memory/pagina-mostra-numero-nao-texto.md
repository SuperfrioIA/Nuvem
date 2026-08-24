---
name: pagina-mostra-numero-nao-texto
description: Maria (21/ago/2026) — página de dado mostra o número e, no máximo, uma linha dizendo o que o gráfico é; método, ressalva e classificação vão para uma seção só de procedência
metadata:
  type: feedback
---

Em 21/ago/2026 a Maria mandou tirar os cartões de comentário das telas de dado
do radar: *"retire essa e outras informações que são geradas, acaba deixando as
páginas muito poluídas, muito cheias de informação, ninguém quer ler, só querem
saber o número e no máximo uma explicação do que é o gráfico, que é o que já
fica com os gráficos."*

**Why:** eu vinha escrevendo o raciocínio na tela — listas de 5 a 9 marcadores
por seção, explicando escopo, limitação e decisão. Isso é o que eu preciso para
não errar, não o que ela precisa para decidir. Ela lê rápido, em várias sessões
ao mesmo tempo, e parede de texto no meio do número atrasa a leitura em vez de
apoiar. É a mesma raiz de [[respostas-enxutas]], aplicada à tela em vez do chat.

**How to apply:**
1. **Página de dado = número.** KPI, gráfico, tabela. Uma linha de `desc` por
   cartão dizendo o que aquilo é — e só. Se a ressalva não muda o que o número
   significa, ela não entra.
2. **Ressalva que muda a leitura do número fica onde ela é lida**: dentro da
   linha do próprio cartão (curta) ou num aviso que só aparece quando o caso
   ocorre — como o de pallet, que aparece apenas quando a medida escolhida é
   Pallets.
3. **Método, procedência, de-para e classificação vão para uma seção só disso**
   (no radar, "Fontes & método"). Quem precisa procura; quem não precisa não
   tropeça. Não é para apagar o rigor — é para não espalhá-lo.
4. **Não repetir o mesmo aviso em várias seções.** Um lugar, e as outras
   apontam para ele.
5. Vale para artefato novo também, não só para o radar. Ver
   [[radar-recebimento-fonte-dw]] e [[modo-laboratorio-poc]].

Removidos nessa passada: "Lendo isto ao lado do painel do BI" (Volumetria),
"Operações que não se chamam entrada" (Tipo de operação), "Por que existe
NAO_CLASSIFICADO" (Tipo de estoque) e as listas longas da Conciliação, que
foram para um marcador curto cada.
