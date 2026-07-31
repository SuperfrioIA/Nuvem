# V1 — Critérios de aceite por macro-lote

Criado em 30/jul/2026 (Bloco A / V1.0). Cada bloco só fecha quando os critérios do
seu(s) macro-lote(s) estiverem atendidos, a suíte completa estiver verde, o
`docs/V1_PLANO.md` estiver atualizado e o relatório de verificação
(`docs/V1_RELATORIO_VERIFICACAO.md`) estiver preenchido por verificação
independente. Status possíveis na verificação: atendido · parcial · não atendido
· bloqueado.

Critérios transversais (valem pra todo bloco):

- Compatibilidade preservada: porta 8002, Docker Compose, Postgres, migrations,
  upload manual, endpoints e telas existentes continuam funcionando;
- Nenhuma soma de medidas incompatíveis; nenhuma unidade inventada;
- Conteúdo externo (SharePoint ou qualquer fonte) nunca entra por `innerHTML` sem
  escape; URL externa só vira link após validação de esquema `http`/`https`;
- Nenhum segredo em log, commit ou resposta de API;
- Documentação atualizada junto com o código.

---

## V1.0 — Transição para produto (Bloco A)

- [ ] `docs/V1_ESCOPO.md`, `docs/V1_PLANO.md`, `docs/V1_CRITERIOS_ACEITE.md` e
      `docs/V1_ARQUITETURA.md` criados; `V1_PLANO.md` é a fonte única do status;
- [ ] README, MEMORY e CLAUDE.md registram a mudança de fase; documentação
      histórica permanece disponível, separada do plano ativo, sem remoção;
- [ ] Nenhuma tela ativa exibe "POC" ou nomenclatura temporária;
- [ ] Peso exibido em toneladas em card, detalhamento e texto executivo
      (cálculo interno segue em kg);
- [ ] Visão executiva organizada: contexto → cards → leitura executiva →
      detalhamento por cliente; qualidade e origem em bloco separado;
- [ ] Filiais confirmadas exibem sigla oficial junto do código (001 · RMSPII,
      015 · RMSPIII, 016 · RMSPIV); filial sem de-para confirmado fica só código;
- [ ] Dívida do painel duplicado de KPIs resolvida (render em um lugar só);
- [ ] Suíte completa verde; nenhuma migration nova (schema inalterado).

## V1.1 — Catálogo semântico (Bloco B)

- [ ] Conceitos canônicos e campos de fonte modelados conforme a seção 6 do
      direcionamento (fonte, família, nome original, conceito, unidades original
      e canônica, categoria de unidade, transformação, agregação, granularidade,
      dimensões, status, versão, vigência, responsável);
- [ ] Mapeamentos configuráveis e versionados — nenhum `if fonte == ...` no código;
- [ ] Tela administrativa de consulta/gestão do catálogo;
- [ ] Migrations aditivas rodando em banco novo e em banco existente sem perda;
- [ ] Seeds idempotentes; testes cobrindo modelo, seeds e tela (API).

## V1.2 — Compatibilidade de medidas (Bloco B)

- [ ] Conversões seguras só dentro da mesma categoria (ex.: t/g/lb → kg);
- [ ] Soma de medidas incompatíveis **bloqueada** com mensagem clara;
- [ ] Valores sem compatibilidade conhecida aparecem separados por
      unidade/categoria, com a limitação informada — nunca consolidados;
- [ ] Unidade desconhecida tratada como categoria própria (não vira kg por padrão);
- [ ] Auditoria do que foi convertido/bloqueado; testes de cada regra;
- [ ] Confirmado fora: cadastro de produto e conversão por SKU/embalagem.

## V1.3 — Persistência e série histórica (Bloco C)

- [ ] Competências históricas do DataHub processadas e persistidas como agregados
      na camada existente (execuções → medidas recebidas → canônicas), com
      linhagem preservada;
- [ ] Granularidade mínima competência × filial × cliente × métrica; fonte sem
      cliente fica sem cliente (não inventa) e restringe análises dependentes;
- [ ] Consultas por intervalo lendo do Postgres (sem tocar o SharePoint na leitura);
- [ ] Consolidação mensal e anual; comparação mês a mês; acumulado do ano;
- [ ] Idempotência: reprocessar a mesma competência 2× não duplica nem corrompe;
      competência corrente republicada substitui, não soma;
- [ ] Prevenção de dupla contagem testada (inclusive `DADOS_GERAIS` meia
      competência declarada, se a família entrar).

## V1.4 — Laboratório: seleção e perfil (Bloco D)

- [ ] Tela de seleção de fontes (pastas, arquivos, família, filiais, clientes,
      intervalo de competências) com limites de tamanho/quantidade/tempo;
- [ ] Perfil determinístico calculado em código antes de qualquer IA (colunas,
      tipos, nulos, distintos, min/max, somas permitidas, unidades, categorias,
      duplicidades, chaves candidatas, cobertura temporal, filiais, clientes,
      granularidade provável, qualidade, limitações, amostra segura);
- [ ] Sessão de análise persistida; testes do perfil sobre arquivos sintéticos.

## V1.5 — Laboratório: chat (Bloco E)

- [ ] Provedor de IA aprovado, validado antes de qualquer envio; limites de
      tamanho; preferência por agregados/perfil/amostra reduzida;
- [ ] Mensagens sugeridas (entender / descobrir / comparar / validar) + campo livre;
- [ ] Tudo rastreável: usuário, data, fontes, versões, filtros, perfil, mensagens,
      respostas, modelo, parâmetros, feedback, status, decisão final;
- [ ] Proteção contra prompt injection em células e conteúdo externo; resposta da
      IA tratada como não confiável (escape, sem execução);
- [ ] Fallback quando a IA estiver indisponível; testes com IA mockada.

## V1.6 — Insight aprovado (Bloco E)

- [ ] Aprovar/descartar análise; aprovação gera especificação completa (seção 10
      do direcionamento) sem publicar nada automaticamente;
- [ ] Auditoria de quem aprovou, quando e com que evidência.

## V1.7 — Cockpit executivo (Bloco F)

- [ ] Filtros globais de período, filial e cliente obedecidos por todos os cards,
      gráficos, tabelas e resumos;
- [ ] Visões: consolidado, série histórica, comparação de filiais e clientes,
      ranking, participação, acumulado, variação mensal, qualidade/cobertura,
      drill-down, origem e linhagem;
- [ ] KPIs iniciais só com métricas confiáveis (peso em toneladas, valor
      movimentado, quantidade de clientes, participação do maior cliente,
      operações quando semanticamente válida, aprovados no Laboratório);
- [ ] Nenhum "volume total" com unidades incompatíveis;
- [ ] Peso: card abreviado ("4,3 mil t"), detalhamento completo ("4.281,7
      toneladas"); percentuais nunca somados diretamente;
- [ ] Qualidade e origem separadas da área principal.

## V1.8 — Produção e entrega (Bloco G)

- [ ] Acesso, auditoria e logs definidos; backup rodando e testado (restauração
      incluída); limites e timeouts; tratamento de falhas;
- [ ] Testes de integração e regressão; migrations validadas em banco novo E em
      banco existente (clone da VM);
- [ ] Deploy documentado com runbook e rollback; checklist executado;
- [ ] Verificação independente final e relatório de entrega.
