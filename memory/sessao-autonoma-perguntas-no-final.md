---
name: sessao-autonoma-perguntas-no-final
description: Quando a Maria pede pra "deixar a sessão rodando" enquanto ela está ausente, ela quer decisões tomadas e o trabalho seguindo — perguntas ficam pra um relatório no final, não pausas no meio
metadata:
  type: feedback
---

Em 07/ago/2026, ao autorizar a V2.4 mesmo com a V2.3 pendente de verificação,
a Maria pediu explicitamente: "vamos deixar você rodando enquanto estou
ausente... deixe perguntas para o final sempre que possível, para deixar a
sessão codando". Isso veio depois de uma pergunta minha (via `AskUserQuestion`)
sobre como proceder com a V2.3 pendente — ela respondeu escolhendo a opção
mais direta ("autorizar V2.4 mesmo com V2.3 pendente") e emendou o pedido de
autonomia.

Na prática, isso significou: continuar implementando decisões de design não
triviais (ex.: fórmula de `total`/`saldo` na volumetria, forma dos endpoints
novos) registrando a decisão tomada e a razão dela na documentação do lote,
em vez de parar pra perguntar cada uma — e só levantar a pergunta de fato
pendente (ex.: "essa fórmula está certa pro negócio?") no relatório final,
junto com o resto do resultado.

**Why:** ela quer aproveitar o tempo ausente pra ter o máximo de progresso
real quando voltar, e cada pausa pra pergunta interrompe esse fluxo sem
necessidade quando uma decisão razoável e documentada resolve.
**How to apply:** quando ela pedir explicitamente pra "deixar rodando"/"seguir
sozinho" num trecho de trabalho grande, tratar isso como autorização para
decisões de design não destrutivas e reversíveis (nomes de campo, fórmulas,
forma de resposta de endpoint) sem pausar — documentar a decisão e a
alternativa não escolhida, e reservar perguntas de verdade bloqueantes
(decisão de produto/negócio sem resposta óbvia, ou ação arriscada/irreversível)
para o fechamento do relatório. Isso NÃO estende a ações arriscadas ou
irreversíveis (deploy, commit, tocar na VM de prod) — essas continuam exigindo
autorização explícita mesmo em modo autônomo, como ela mesma reforçou nesta
sessão ("não vá para a VM sem minha autorização").
