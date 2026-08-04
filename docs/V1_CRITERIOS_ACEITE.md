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

- [x] `docs/V1_ESCOPO.md`, `docs/V1_PLANO.md`, `docs/V1_CRITERIOS_ACEITE.md` e
      `docs/V1_ARQUITETURA.md` criados; `V1_PLANO.md` é a fonte única do status;
- [x] README, MEMORY e CLAUDE.md registram a mudança de fase; documentação
      histórica permanece disponível, separada do plano ativo, sem remoção;
- [x] Nenhuma tela ativa exibe "POC" ou nomenclatura temporária;
- [x] Peso exibido em toneladas em card, detalhamento e texto executivo
      (cálculo interno segue em kg);
- [x] Visão executiva organizada: contexto → cards → leitura executiva →
      detalhamento por cliente; qualidade e origem em bloco separado;
- [x] Filiais confirmadas exibem sigla oficial junto do código (001 · RMSPII,
      015 · RMSPIII, 016 · RMSPIV); filial sem de-para confirmado fica só código;
- [x] Dívida do painel duplicado de KPIs resolvida (render em um lugar só);
- [x] Suíte completa verde; nenhuma migration nova (schema inalterado).

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco A" (atendido, 8
achados de documentação corrigidos ou registrados antes do commit).

## V1.1 — Catálogo semântico (Bloco B)

- [x] Conceitos canônicos e campos de fonte modelados conforme a seção 6 do
      direcionamento (fonte, família, nome original, conceito, unidades original
      e canônica, categoria de unidade, transformação, agregação, granularidade,
      dimensões, status, versão, vigência, responsável);
- [x] Mapeamentos configuráveis e versionados — nenhum `if fonte == ...` no código;
- [x] Tela administrativa de consulta/gestão do catálogo;
- [x] Migrations aditivas rodando em banco novo e em banco existente sem perda;
- [x] Seeds idempotentes; testes cobrindo modelo, seeds e tela (API).

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco B" (atendido; 5 de
7 ressalvas corrigidas antes do commit, 2 registradas como limitação).

## V1.2 — Compatibilidade de medidas (Bloco B)

- [x] Conversões seguras só dentro da mesma categoria (ex.: t/g/lb → kg);
- [x] Soma de medidas incompatíveis **bloqueada** com mensagem clara;
- [x] Valores sem compatibilidade conhecida aparecem separados por
      unidade/categoria, com a limitação informada — nunca consolidados;
- [x] Unidade desconhecida tratada como categoria própria (não vira kg por padrão);
- [x] Auditoria do que foi convertido/bloqueado; testes de cada regra;
- [x] Confirmado fora: cadastro de produto e conversão por SKU/embalagem.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco B".

## V1.3 — Persistência e série histórica (Bloco C)

- [x] Competências históricas do DataHub processadas e persistidas como agregados
      na camada existente (execuções → medidas recebidas → canônicas), com
      linhagem preservada;
- [x] Granularidade mínima competência × filial × cliente × métrica; fonte sem
      cliente fica sem cliente (não inventa) e restringe análises dependentes;
- [x] Consultas por intervalo lendo do Postgres (sem tocar o SharePoint na leitura);
- [x] Consolidação mensal e anual; comparação mês a mês; acumulado do ano;
- [x] Idempotência: reprocessar a mesma competência 2× não duplica nem corrompe;
      competência corrente republicada substitui, não soma;
- [x] Prevenção de dupla contagem testada (inclusive `DADOS_GERAIS` meia
      competência declarada, se a família entrar) — ressalva original (controle
      de processamento por nome de arquivo, não por identidade estável) ficou
      superada pela reestruturação do DataHub em 4 unidades (31/jul/2026) e foi
      **corrigida em 02/ago/2026** pelo lote de identidade (chave por `item_id`,
      de-para qualificado por unidade); nunca chegou a acontecer em produção.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco C".

## V1.4 — Laboratório: seleção e perfil (Bloco D)

- [x] Tela de seleção de fontes (pastas, arquivos, família, filiais, clientes,
      intervalo de competências) com limites de tamanho/quantidade/tempo;
- [x] Perfil determinístico calculado em código antes de qualquer IA (colunas,
      tipos, nulos, distintos, min/max, somas permitidas, unidades, categorias,
      duplicidades, chaves candidatas, cobertura temporal, filiais, clientes,
      granularidade provável, qualidade, limitações, amostra segura);
- [x] Sessão de análise persistida; testes do perfil sobre arquivos sintéticos.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco D" (reprovado na
primeira passada — 3 defeitos reais corrigidos antes do commit, ver seção);
identidade do arquivo (`item_id`) e de-para qualificado por unidade corrigidos
no lote de 02/ago/2026 (`memory/reestruturacao-datahub-4-unidades.md`).

## V1.5 — Laboratório: chat (Bloco E)

- [x] Provedor de IA aprovado, validado antes de qualquer envio; limites de
      tamanho; preferência por agregados/perfil/amostra reduzida;
- [x] Mensagens sugeridas (entender / descobrir / comparar / validar) + campo livre;
- [x] Tudo rastreável: usuário, data, fontes, versões, filtros, perfil, mensagens,
      respostas, modelo, parâmetros, feedback, status, decisão final;
- [x] Proteção contra prompt injection em células e conteúdo externo; resposta da
      IA tratada como não confiável (escape, sem execução);
- [x] Fallback quando a IA estiver indisponível; testes com IA mockada.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco E" (1 achado
crítico + 2 altos + 1 médio corrigidos antes do commit).

## V1.6 — Insight aprovado (Bloco E)

- [x] Aprovar/descartar análise; aprovação gera especificação completa (seção 10
      do direcionamento) sem publicar nada automaticamente;
- [x] Auditoria de quem aprovou, quando e com que evidência.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco E".

## V1.7 — Cockpit executivo (Bloco F)

- [x] Filtros globais de período, filial e cliente obedecidos por todos os cards,
      gráficos, tabelas e resumos — ressalva: cada filtro aceita um valor por vez
      ou "todos" (F2, baixo, registrado no `V1_PLANO.md`); a seção 5.7 do
      direcionamento pede múltiplos valores, fica pendência conhecida;
- [x] Visões: consolidado, série histórica, comparação de filiais e clientes,
      ranking, participação, acumulado, variação mensal, qualidade/cobertura,
      drill-down, origem e linhagem;
- [x] KPIs iniciais só com métricas confiáveis (peso em toneladas, valor
      movimentado, quantidade de clientes, participação do maior cliente,
      operações quando semanticamente válida, aprovados no Laboratório);
- [x] Nenhum "volume total" com unidades incompatíveis;
- [x] Peso: card abreviado ("4,3 mil t"), detalhamento completo ("4.281,7
      toneladas"); percentuais nunca somados diretamente;
- [x] Qualidade e origem separadas da área principal.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco F" (achado F1,
alto, corrigido antes do commit; F2 registrado como limitação).

## V1.8 — Produção e entrega (Bloco G)

- [x] Acesso, auditoria e logs definidos; backup rodando e testado (restauração
      incluída); limites e timeouts; tratamento de falhas — ressalva: destino
      externo do backup (fora da VM) e identidade por pessoa (segue senha
      única) ficam pendências declaradas, decisão explícita da Maria;
- [x] Testes de integração e regressão; migrations validadas em banco novo E em
      banco existente (clone do schema legado da VM, `LEGADO_DDL` em
      `tests/test_migracao.py`);
- [x] Deploy documentado com runbook e rollback; checklist executado
      (`scripts/verificar_v1.py`, rodado contra o stack local — subir contra a
      VM fica para quando a Maria decidir fazer o deploy do bloco);
- [x] Verificação independente final e relatório de entrega.

Evidência: `docs/V1_RELATORIO_VERIFICACAO.md`, seção "Bloco G" (G1, G2 e G3).
