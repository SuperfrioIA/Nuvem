# Nuvem IA

Projeto interno SuperFrio (CSC). Leia antes de qualquer coisa:

1. [docs/V3_PLANO.md](docs/V3_PLANO.md) — **fonte única do status da V3, que é a
   fase atual** (lotes V3.0–V3.8, onde a construção está, o contrato fechado e
   as decisões abertas). Ler antes de codar; atualizar o status ao fechar um
   lote.
2. [docs/V2_PLANO.md](docs/V2_PLANO.md) — **fonte única do que a V2 entregou**
   (lotes V2.1–V2.8). **V2 congelada** — é o que está em produção na VM, e não
   se mexe mais nela (Maria, 24/ago/2026). Especificação:
   [docs/proposta_v3_volumetria.md](docs/proposta_v3_volumetria.md) — o nome
   diz "v3" por acidente histórico, mas é a especificação da **V2**; a
   `proposta_v2_...` é só registro do raciocínio inicial.
3. [docs/V1_PLANO.md](docs/V1_PLANO.md) — **fonte única do que a V1 entregou**
   (blocos A–G / macro-lotes V1.0–V1.8) e das limitações que ela declarou. V1
   fechada e implantada.
4. [docs/V1_NUVEM_IA_DIRECIONAMENTO.md](docs/V1_NUVEM_IA_DIRECIONAMENTO.md) — o
   direcionamento completo da V1 (produto, arquitetura, regras, macro-lotes).
   Resumos operacionais: [docs/V1_ESCOPO.md](docs/V1_ESCOPO.md),
   [docs/V1_CRITERIOS_ACEITE.md](docs/V1_CRITERIOS_ACEITE.md),
   [docs/V1_ARQUITETURA.md](docs/V1_ARQUITETURA.md).
5. [MEMORY.md](MEMORY.md) + `memory/` — estado e decisões vivas do projeto (autoritativo).
6. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — desenho técnico da base (15/jul/2026),
   válido no que não conflita com o V1_ARQUITETURA.
7. Histórico (consultar, não é plano ativo): [docs/POC_ATUAL.md](docs/POC_ATUAL.md)
   (POC DataHub P0–P6, encerrada em 30/jul/2026), [docs/ENTREGA_POC.md](docs/ENTREGA_POC.md)
   (balanço, limitações e riscos), [docs/PLANO.md](docs/PLANO.md) (plano de produto
   0–11/R0–R3 — nenhum lote autorizado automaticamente) e
   [docs/HISTORICO.md](docs/HISTORICO.md) (prompts originais).

## Regras para IA

- Antes de iniciar processos, rodar testes ou validar algo localmente, ler
  `docs/EXECUCAO_LOCAL.md` — fonte oficial do método real de subir, testar e
  encerrar o projeto nesta máquina.
- Fase atual: **construção da V3 — volumetria de catering lendo o DW Oracle**
  (aberta em 24/ago/2026; **V3.0 a V3.3 em 24/ago, V3.4 (login) e V3.5 (fonte
  Oracle) em 25/ago, V3.5.1 (fuso de exibição), V3.6 (deploy) e V3.7 (recorte
  por dia) em 26/ago**. O V3.6 foi **executado em 26/ago/2026: a V3 está em
  produção na VM, porta 8003**, e a V2 saiu do ar. **V3.7, V3.8 e V3.8.1 subiram na
  VM em 27/ago**, e o **histórico completo (2023–2026) está em produção nas duas
  tabelas** — 202.087 linhas no recebimento e 232.089 na expedição, com as duas
  cargas `ok` e as dimensões recalculadas sobre 3,6 anos (aceite no
  `docs/V3_PLANO.md`). O V3.8.1 saiu de a carga do histórico ter falhado numa
  linha só: soltou as duas colunas de cliente que não identificam a linha
  (migration 0024) e fez o `--sondar` medir **preenchimento**, não só identidade.
  **V3.7.1** (filtros com caixas de seleção) e **V3.7.2** (os dois movimentos na
  mesma matriz) foram **feitos em 27/ago/2026 e validados no navegador**, e ainda
  **não subiram na VM** — procedimento em `docs/DEPLOY.md`, seção "V3.7.1 +
  V3.7.2". Do **V3.9** em diante nada está autorizado; status e aceite em
  `docs/V3_PLANO.md`). O código novo vive em `catering/`; a fonte é o DW, **não**
  o SharePoint DataHub. Não construir código sem pedido explícito da Maria, e a
  autorização é **por lote**.
- **A IA não conecta no DW.** Ele é produção. O V3.5 construiu a leitura inteira
  contra driver falso, e a prova de leitura real é um comando que a Maria roda
  (`python -m catering.carga --fonte oracle --sondar`).
- **Ampliar a janela da carga é ampliar o contrato inteiro** (aprendido no
  V3.8.1, 27/ago/2026). Nulabilidade e unicidade foram medidas em 2026 e não
  valem para 2023–2025 só porque a coluna é a mesma: a chave quebrou na 0023 e a
  nulabilidade quebrou na 0024, na mesma semana e pela mesma causa. Antes de
  mexer no piso, o `--sondar` tem que sair certo nas **duas** seções —
  `identidade` e `preenchimento`. Coluna obrigatória é a que identifica a linha
  ou a coloca na tela; fora dessas, vazio na fonte é fato, não defeito nosso
  (a regra está escrita no `catering/contrato.py`).
- **O terceiro movimento da tela não é um movimento do dado** (V3.7.2,
  27/ago/2026). `Entrada + saída` vive em `recorte.MOVIMENTOS_DA_TELA` e **não**
  em `contrato.MOVIMENTOS`, que é o conjunto do DADO — o CHECK da migration 0019,
  o contrato de colunas e o nome da tabela de origem da carga. Juntar os dois
  faria a carga aceitar um movimento que não tem tabela. E a visão conjunta é
  **só da Matriz**: ela agrega, então pode somar; a planilha mostra linha crua e
  o download leva a linha inteira, e as duas tabelas têm 36 e 46 colunas — os
  dois recusam com 400, de propósito.
- **`DW_ANO_MINIMO` é o piso da CARGA (padrão 2023 desde o V3.8) e
  `CAT_ABERTURA_DE` é onde a TELA abre (padrão janeiro do ano corrente).** Não
  confundir. O piso está no `WHERE` de **toda** rodada, não só da primeira: subi-lo
  faria as atualizações do DW em linha antiga pararem de chegar, e a nossa cópia
  do histórico congelaria divergindo da fonte em silêncio. A credencial (`DW_USER`,
  `DW_SENHA`) vive no `.env` — nunca no chat, em log, em teste ou em commit.
- O agendamento da carga **está LIGADO** desde 26/ago/2026
  (`scripts/carga_catering.sh`, no crontab da VM). As duas pendências
  do `docs/DEPLOY.md` estão fechadas — o serviço `nuvem-cat` existe no compose
  (V3.6) e o **cron é escrito em UTC** (`5 10` e `5 18` para 07h05/15h05 de
  Brasília), decidido para não mexer no fuso da VM, que é compartilhada com
  outros três projetos. Não "corrigir" para `5 7`: o motivo está no `DEPLOY.md`.
- **O recorte da tela é por DIA desde o V3.7** (`AAAA-MM-DD`, inclusivo nas duas
  pontas), com filtro de **dia do mês** (01..31) que corta dentro de todo mês do
  período. Não confundir com o piso da carga: `DW_ANO_MINIMO` é o que o banco
  guarda, `CAT_ABERTURA_DE` (padrão `ano-corrente`) é onde a tela abre. Coluna
  que deixou de ser o mês inteiro **tem que ser declarada** — cabeçalho com a
  faixa de dias, e aviso quando o filtro de dia está ativo.
- O app da V3 **exige login** desde o V3.4: `catering/seguranca/` (papel separado
  de identidade, para o AD entrar depois), e local ele precisa de `CAT_SECRET_KEY`
  no ambiente — ver `docs/EXECUCAO_LOCAL.md`, caminho C. Credencial vai para o
  `.env`, nunca no chat nem em commit.
- **A V2 está congelada e, desde 26/ago/2026, FORA DO AR** (o V3.6 removeu o
  serviço do compose; ela não é mais o que está em produção). `backend/`,
  `frontend/` e as migrations até a 0018 continuam **intactos** — a V3 não
  altera nem importa código de lá, e o desligamento foi por remoção de serviço,
  sem editar uma linha. **Nada foi apagado:** o bloco fica comentado no
  `docker-compose.yml`, o volume `nuvem_db_data` e as tabelas da V1/V2 seguem no
  banco. Reativar o laboratório é descomentar e `up -d`. Regra reaproveitada entra por **cópia com teste próprio**.
  **No V3.6 ela sai do ar** (decisão da Maria, 26/ago/2026: nenhuma das telas
  era usada) — e sai **sem edição de código**, removendo o serviço do compose.
  O bloco fica comentado no `docker-compose.yml`, e o código, o volume e as
  tabelas da V1/V2 continuam intactos: reativar o laboratório é descomentar.
  Duas falhas conhecidas da suíte (`test_volumetria.py` e
  `test_volumetria_router.py`, siglas antigas depois do `e5805b3`) são V2 e
  ficam como estão. O antigo só sai da VM depois da tela nova de pé.
- Contexto histórico do DataHub (**não é instrução para a V3**, que não o usa):
  se algum dia for preciso mexer na ingestão do DataHub, ler a seção "Lote de
  correção" do V1_PLANO — a identidade do arquivo é o `item_id` e a origem é
  `unidade/filial` (`RMSPII/001`), nunca o nome nem o código de filial sozinho.
- **Nada é alterado no SharePoint do DataHub** (Maria, 06/ago/2026). O cliente
  Graph é somente leitura por construção e a suíte tem guarda pra isso; a regra
  vale também pra qualquer escrita pelo sistema de arquivos — nunca rodar com o
  diretório de trabalho dentro da pasta sincronizada do DataHub.
- **Pendência com risco, medida em 26/ago/2026:** o banco de produção **não tem
  backup automático**. O crontab da VM tem o backup do *Conciliador* (outro
  projeto) e as duas cargas da V3, mas não a linha do `scripts/backup.sh` da
  Nuvem IA — documentada desde o Bloco G1 e nunca instalada. O único dump é o
  avulso de 26/ago 16h30. Ver `docs/DEPLOY.md`, seção de backup.
- Antes de criar/alterar arquivos: apresentar plano em texto simples e aguardar OK
  explícito. "Beleza" vago não é OK.
- Commits **sem** co-autor Anthropic (nada de `Co-Authored-By`).
- Comunicação em português, direta, sem emojis.
- Padrões: skill `superfrio` (identidade visual) e `superfrio-trabalho` (forma de
  trabalhar — lotes, princípios técnicos, deploy Docker).
