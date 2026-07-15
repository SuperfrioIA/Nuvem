# Histórico — como o projeto se desenrolou

Registro fiel dos prompts da Maria na conversa de origem (14–15/jul/2026, sessão Claude
Code no repo SuperfrioIA), na ordem, com o que saiu de cada um. Serve pra qualquer
sessão futura ter ciência de tudo o que foi falado — as conclusões detalhadas estão em
[CONCEITO.md](CONCEITO.md), [ARQUITETURA.md](ARQUITETURA.md) e [PILOTO.md](PILOTO.md).

---

## 1. A ideia nasce "com nuvens cinzas"

> "devo usar o fable para pensar em amadurecer uma ideia? Tenho uma ideia mas que está
> meio bagunçada, com nuvens cinzas ainda hahaha, devo usar o fable para amadurece-la?"

**→ Resultado:** decidimos amadurecer na conversa mesmo (ida-e-volta rápida) e escalar
pro Fable quando a coisa ficasse densa — o que aconteceu mais adiante.

## 2. O contexto completo (o prompt que fundou o projeto)

> "Contexto: a superfrio hoje tem wms, tms, erp, conciliador de estoque - todos esses
> tem seus bancos proprios guardando muitas informacoes de varios anos. Mas também temos
> controles por planilhas, por exemplo ira-ila, faturamento realizado aos clientes
> (contas a receber), relatorios da controladoria e etc.
>
> Pensando em construir um lugar (data warehouse?) para levarmos esses dados (nao sei se
> puxaria via api, se puxaria das pastas do sharepoint, se incluiria relatorios
> manualmente) dentro de um 'portal' e deixarmos com a visao tipo do 'mapa-ia', que
> teriamos as bolinhas, vinculando cada dado com outro dado e assim gerando
> resultados/insights, fazendo as coisas conversarem.
>
> Exemplo: temos relatorio de ocupação, volumetria e perdas - se em dezembro de 2023
> temos o dado de 50% acima da media de perdas, mas tambem temos que a volumetria
> aumentou 100%, entao a perda é 'justa', ou ao contrario, que temos em fevereiro de
> 2026, perda 30% acima do normal, mas a volumetria continuou o mesmo padrao, entao
> vemos que tem cagada no meio.
>
> Exemplo 2: se temos um relatorio de volumetria que mostra um padrão de 1 ano, temos a
> previsibilidade de que provavelmente no próximo mes, teremos um grande volume de
> movimentação do cliente, entao podemos nos precaver e contratar mais gente para a
> operação, para não quebrarmos.
>
> Exemplo 3: no relatorio de expedição do wms, temos que o cliente X da operação de
> catering, esta sempre pedindo 1-2-3-2-2 lotes de um produto, do qual ele nao para de
> comprar estoque e acaba perdendo por vencimento, porque acaba nao usando o produto,
> entao podemos mostrar esse risco e sinalizar.
>
> Enfim, no primeiro momento o objetivo nao é construir uma página, html, banco de
> dados. O objetivo é pensarmos em uma forma para juntar varias bases de dados e começar
> a fazer insights dela. Hoje temos milhares de b.i's centralizados, do qual precisam de
> interpretação, e sao individuais. Então queremos pegar esses dados e juntar tudo em um
> lugar e começar a ligar as coisas. No final ter uma nuvem (chamamos o mapa-ia de
> nuvem) gigante, interligando varias coisas."

**→ Resultado:** separação motor (cruzamento = valor) vs embalagem (grafo = navegação);
identificação de que os 3 exemplos são 3 capacidades distintas (validar anomalia /
prever / detectar padrão); o de-para (chaves comuns) apontado como os ~80% do trabalho;
recomendação de piloto = exemplo 1 (perdas × volumetria × ocupação).

## 3. Onde guardar

> "mas eu queria é saber onde vamos deixar isso tudo? Um Data Warehouse?"

**→ Resultado:** na época, resposta "sim, DW é o conceito" + separação bastidor
(dados) × vitrine (nuvem). Superado no item 6: o Pentaho já cumpre esse papel.

## 4. Como os insights nascem + a visão da tela

> "a minha pergunta é: como que os insights seriam criados? Alguem tem que analisar? Ou
> uma ia ficaria ligada e sendo alimentada para gerar insights? Ou seriamos capazes de
> construir um sistema que iria guspir eles?
>
> Penso em um mapa mental (igual ao do aplicativo obsidian), onde teriam essas pontas
> nas ramificações/conexões, cada bolinha ficaria maior de acordo com a quantidade de
> dados que temos nela. E quando alguem selecionar uma filial, um cliente, as bolinhas
> vao mudando conforme se tem dados ou nao, e eu imagino que se eu selecionar parametros
> dentro da bolinha de perdas, entao ja vai começar a me sugerir/piscar/mudar de cor
> outras bolinhas de outros assuntos que tambem devem ter algo de diferente, para que a
> pessoa pense 'ah, entao esta conectado que a perda teve aumento e volumetria diferente
> do normal', acho que o objetivo nao é criar regra para que o sistema/ia/motor
> interprete apenas os X fluxos que previamente foram desenhados, mas que dê para
> enxergarmos tudo, até o que nem se passa pela nossa cabeça. É um projeto absurdamente
> grande né? Parece ate uma coisa de outro mundo. Rsrsrs"

**→ Resultado:** a escada de mecanismos (humano olha → regras → triagem estatística →
IA narradora → mineração com validação humana); o "piscar" mapeado pra detecção de
anomalia contextual **sem regra por par de métricas** — exatamente o que ela descreveu;
aviso sobre correlações espúrias (máquina tria, humano valida); constatação de que a
parte "mágica" é a barata e o de-para é a montanha real.

## 5. Primeiro artefato

> "rascunhe com um artefato"

**→ Resultado:** rascunho visual v0.1 do piloto (identidade SuperFrio):
<https://claude.ai/code/artifact/a8829925-077b-4414-994a-25a5eb984aeb>

## 6. As reconsiderações de arquitetura (Pentaho + SharePoint + nada gigantesco)

> "Beleza, gostei da ideia. Vou reconsiderar algumas coisas:
> 1- não vamos pensar em data warehouse por enquanto, hoje na estrutura temos um pentaho
> como dw(middleware) que captura dados das bases de todos os sistemas. Então vamos
> fazer as requisições de dados por ele, e nao vamos guardar nada, para nao criar um
> segundo banco de dados gigantesco.
> 2 - dados gerados por maos de pessoas, que sao controlados por pdf e excel, ficarão
> disponiveis no sharepoint. Então buscaremos os dados desses sharepoints.
> 3- será possivel andar com isso? Pegando dados de um dw e pegando dados dos
> sharepoints, sem deixar nada guardado dentro da nossa plataforma da NUVEM? Para nao
> criarmos um novo banco de dados gigantesco.
> 4- eai com essa estrutura da nuvem, ao clicar em uma bolinha, poderia abrir uma tabela
> ao lado informando os dados que estao presentes (sei que talvez isso demore para
> carregar pois vai buscar os dados e etc)
> 5- nao sei até que ponto isso é bom e sustentavel, ficar fazendo muitas requisicoes em
> outro banco de dados, no sharepoint e jogando o resultado na tela, na minha percepcao
> isso demoraria para carregar.
> 6- e no final, entregariamos os insights, seja exportando xlsx com resultado, seja com
> um html mostrando o resultado, seja com email enviado automatico para x pessoas, seja
> a pessoa mesmo abrindo os dados e analisando no olho."

**→ Resultado:** conceito de **camada fina** (zero literal é impossível — de-para +
agregados + scores precisam viver em algum lugar, mas são KB, não um segundo DW; o bruto
fica na fonte); padrão híbrido de performance (rotina agendada calcula, tela lê pronto,
consulta ao vivo só no drill-down — dado é mensal, sem tempo real); regras de ouro do
SharePoint (Excel nunca PDF; contrato de planilha); as 4 torneiras de entrega. Artefato
atualizado pra v0.2 com essa arquitetura.

## 7. O técnico

> "beleza, vai ser esse padrão mesmo. Vamos arquitetar o técnico agora? Por enquanto
> precisamos deixar aberto para seguir no começo com os sharepoints, no inicio nao
> teremos de fato integrações com o dw, mas temos que ja deixar estruturado para
> recebe-las. Acho que podemos ter um painel admin para ligar/desligar as integrações,
> as consultar no sharepoint e afins. Faz sentido? Acho até que é um projeto fora do
> portal/hub/plataforma superfrio&icestar, será na mesma vm que esta o conciliador de
> estoque e o portal, mas é um container é a parte, no começo podemos usar o banco
> postgres."

**→ Resultado:** arquitetura de conectores plugáveis (interface única; SharePoint,
upload manual, Pentaho futuro); Receita 3 do Hub (app separado, card no portal); 2
containers na VM (porta 8002); schema de 7 tabelas; admin com toggle/de-para/log.
Decisões fechadas em seguida: **upload manual E Graph API ambos prontos, alternáveis no
admin** (Graph aguarda app registration da TI — caminho crítico); **senha única só no
/admin**; nome do repo.

## 8. Este repositório

> "crie um novo repositorio em documentos/nuvem-ia e gere e coloque lá os MDs desse
> projeto para trabalharmos lá"
>
> "importante adicionar todos os prompts que dei de inicio aqui, que 'desenrolamos' o
> projeto, para que a outra sessao tenha ciencia de tudo o que foi falado."

**→ Resultado:** este repo (`Documents/nuvem-ia`, git iniciado em main) com README,
CLAUDE.md, MEMORY.md + memory/, docs/ (CONCEITO, ARQUITETURA, PILOTO, HISTORICO) e
.gitignore. Estado: **fase de arquitetura, nenhum código construído** — construir só
com pedido explícito.
