---
name: cockpit-hub-integracao
description: Decisões fechadas com o time do Hub SuperFrio sobre como o cockpit executivo (nuvem-ia, Bloco F/V1.7) se integra ao Hub — link direto, filtros na URL, duas telas separadas, SSO pendente
metadata:
  type: project
---

O Hub SuperFrio & IceStar vai **linkar direto** as duas telas do cockpit
(`/cockpit` e `/linhagem`), não embutir via iframe — decisão dos dois lados,
fechada em 03/ago/2026 antes do Bloco F começar.

**Por quê:**
- O sandbox de iframe do Hub usa `allow-same-origin`, pensado pra apps que
  vivem no mesmo repositório do Hub e passam pela mesma revisão de PR — o
  nuvem-ia é domínio e deploy diferentes.
- Nenhum dos dois lados tem autenticação compartilhada hoje: o Hub tem JWT
  próprio (login por usuário, sem propagação pra app externo); o nuvem-ia
  tem senha única de admin. Um iframe mostraria a tela de login do nuvem-ia
  dentro do frame do Hub, sem resolver nada que um link simples não resolva.
- Mesmo padrão já em produção no Hub pro app "Contas Recorrentes" (repo/auth
  próprios, cadastrado como app separado só linkado).

**Como aplicar:**
- Os filtros globais do cockpit (período/filial/cliente) são representados
  como query string (`?de=&ate=&filial=&cliente=`) nas duas telas — o Hub não
  injeta parâmetro nenhum hoje (nem filial, nem período; não tem conceito de
  escopo por filial no modelo de permissão dele), então não há risco de
  colisão de convenção. Isso abre a porta pro Hub, no futuro, linkar direto
  pra uma visão já filtrada (ex.: card "Cockpit — RMSPII").
- `/cockpit` (visão executiva) e `/linhagem` (grão mínimo/drill-down) são
  **rotas top-level independentes**, não uma sub-rota da outra — o modelo de
  permissão do Hub só concede acesso por app inteiro (sem escopo dentro do
  mesmo app cadastrado). Duas telas = dois cards/apps distintos no Hub, cada
  um com sua própria role quando isso existir — a linhagem expõe dado mais
  granular (execução de processamento, arquivo do SharePoint) do que a
  executiva, e só dois cards separados permitem dar acesso diferenciado hoje.
- Modo `embed` (`?embed=1`, oculta menu/nav do nuvem-ia) foi desenhado no
  cockpit mas **não é o próximo passo** — só faz sentido no dia em que existir
  autenticação compartilhada entre Hub e nuvem-ia. Não é trabalho perdido,
  só adiado.
- **Autenticação/SSO entre Hub e nuvem-ia é pendência dos dois lados**, não
  bloqueante pro link direto. SSO real (Entra/AD) está no roadmap do Hub como
  degrau futuro, e mesmo esse degrau é só autenticação — não há previsão de
  mapear grupos pra permissões ainda.

Ver [[projeto-nuvem-ia]] pro resto do Bloco F; `docs/V1_PLANO.md` tem o
registro formal completo.
