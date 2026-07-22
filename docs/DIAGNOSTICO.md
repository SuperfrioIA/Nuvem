# Diagnóstico e proposta — Revisão arquitetural (ETAPA 1)

Data: 22/jul/2026. Revisões do mesmo dia: (a) decisão de negócio do take or pay
incorporada (seção 7) — **aprovada**, incluindo o bloqueio do R6 pelo relatório
detailed do DW, sem proxy por volumetria; (b) correções técnicas da revisão da Maria
incorporadas: Alembic no lugar de ALTERs no init_db, versionamento real de modelos,
fonte lógica separada do modelo, linhagem canônica por medida recebida, ocorrências
idempotentes, identidade de contratos por vigência, validação de foto por modelo/fonte.

Status: **Lotes R0 e R1 implementados em 22/jul/2026.** R0 = testes + Alembic +
baseline + validação anti-drift + limite de upload (25 testes). **R1 = fontes lógicas
+ versionamento real dos modelos** (escopo mínimo pedido pela Maria): `modelo_versoes`
imutável, `modelos_importacao.fonte_id`, `execucoes.modelo_versao_id`,
`catalogo_fontes.ativo`, migration 0002 convertendo modelos atuais em v1 (dados
preservados), upload usando a versão padrão e reprocessamento amarrado à versão
original; 31 testes verdes + clone do banco R0 real migrado. Adiado no R1 (risco H):
seed dos 5 modelos canônicos + vínculo `catalogo_fontes.modelo_id` — fechado no R1.1.
**R2 fechado em 22/jul/2026**, escopo enxuto pedido pela Maria (diferente do preview
original da seção 6 abaixo: sem precedência de fonte, sem validação de data única):
`medidas_recebidas` (append-only) + `medida_linhagem` (N:N) + colunas de origem em
`medidas` (`medida_recebida_id`, `origem_tipo`, `regra_codigo`, `regra_versao`,
`calculado_em`), migration 0003. Detalhes no Lote R2 do docs/PLANO.md. R3–R6 não
autorizados.

Contexto: revisão pedida a partir do realinhamento estratégico — a Nuvem IA evolui de
"detector de anomalias com nuvem de bolinhas" para **cockpit corporativo de gestão das
filiais**, mantendo a POC catering RMSP como primeira fatia vertical. Este documento é
o entregável da ETAPA 1 (diagnóstico); a ETAPA 2 (implementação) só começa após
aprovação explícita.

---

## 1. Resumo executivo

**O que está adequado.** A base é melhor do que a lista de riscos do prompt de revisão
sugere. A camada fina existe de verdade (nada de segundo DW — o parser agrega no
boundary e joga fora o grão fino), os modelos de importação são um mecanismo bom e já
provado com as 5 fontes reais, o de-para com pendências nunca descarta em silêncio, a
ocupação composta **já está corretamente bloqueada** atrás de regra validada (Lote 9 do
PLANO exige fechar a regra antes de construir), e os cálculos são 100% determinísticos
em código — nenhuma IA no caminho.

**O que precisa mudar.** Quatro problemas estruturais são reais e dois deles bloqueiam
a POC como planejada:

1. **Linhagem inexistente em `medidas`** — o risco se confirma, e é pior que o
   descrito: `medidas.conector_id` aponta sempre pro mesmo conector (`upload_manual`),
   então nem a linhagem grosseira que existe distingue pos_sum de capacidade1HDR. Não
   dá pra responder "qual fonte/execução produziu este valor". O conflito de capacidade
   existe hoje e foi aceito conscientemente no Lote 8 ("upsert substitui o mais
   recente") — mas sem registro de quem venceu.
2. **Status de contrato viraria número** — o Lote 9.5 planeja "status do contrato"
   como métrica em `medidas_cliente` (`valor NUMERIC NOT NULL`). É exatamente o erro de
   tratar estado categórico como medida numérica. Precisa de redesenho **antes** de
   construir o 9.5, não depois.
3. **O z-score não responde nenhuma das 3 perguntas da POC** — "cobertura 124%" é
   violação de limite, "sem contrato vigente" é conformidade, "uso × contratado" é
   comparação com referência. São detectores de regra, não anomalia histórica. Pior:
   ocupação e comercial começam a acumular histórico agora, então ficam em
   `historico_curto` (mínimo 6 competências) até ~2027 — o motor atual ficará mudo
   justamente sobre o núcleo da POC.
4. **Os 5 modelos de importação do Lote 8 não estão em lugar nenhum versionado** —
   foram criados via UI no banco do worktree local. Não existem na VM nem na main, o
   mapeamento JSONB (que é o contrato de limpeza de cada fonte) não está no git, e
   nenhum código jamais preenche `catalogo_fontes.modelo_id` (fica NULL pra sempre; o
   vínculo fonte→execuções do catálogo está morto).

Além disso: **zero testes automatizados** no repo, e o `init_db()` só faz
`CREATE TABLE IF NOT EXISTS` — não existe mecanismo pra adicionar coluna em tabela
existente, o que bloqueia qualquer lote de evolução de schema. Esses dois vêm primeiro.

**O que não precisa mudar.** PostgreSQL, FastAPI, Docker, 2 containers, porta 8002, o
parser, o formato canônico dos conectores, o seed idempotente, a retenção de arquivos.
Nenhuma reescrita.

---

## 2. Estado atual real (arquitetura encontrada no código)

**Fluxo implementado:** upload no admin → `backend/conectores/upload_manual.py` aplica
o modelo (csv/xlsx, filtros, soma/soma_colunas/razão, divisor, formato largo) e agrega
por armazém×competência×métrica → `backend/ingestao.py` resolve de-para (sem match →
`depara_pendencias`), faz upsert em `medidas` → `backend/motor.py` recalcula **todos**
os scores (delete+insert, janela 24, mínimo 6, `|z|>=2`) na mesma requisição. Arquivo
original retido em disco (`backend/armazenamento.py`), referenciado em `execucoes`.

**Banco:** 12 tabelas criadas em `backend/database.py` (as 9 documentadas +
`clientes`, `catalogo_fontes`, `catalogo_colunas`). Sem framework de migração;
evolução = só tabela nova.

**O que existe só como intenção:**

- A interface `Conector` (`backend/conectores/base.py`) nunca é instanciada;
  `backend/routers/admin.py` chama as funções do módulo direto. A tabela `conectores`
  é decorativa (não há toggle, não há dispatch por `config`). Lote 2 pendente — ok,
  mas a ARQUITETURA descreve como se existisse.
- APScheduler: citado na ARQUITETURA como parte do container, mas não está nem no
  `requirements.txt` (Lote 4).
- Reprocesso delete+insert por conector×competência: documentado, não implementado.
  Hoje só upsert — linha que some da fonte persiste no banco.
- Tela da nuvem, painel de cobertura, exibição de scores: não existem (scores só via
  API).

**Divergências doc × código (pequenas, corrigíveis já):**

| Onde | Diz | Real |
|---|---|---|
| README.md | Lotes 1, 3, 7 feitos | 7.1, 8 e 8.5 também |
| MEMORY.md / memória do projeto | "próximo: Lote 8" | Lote 8 feito em 22/jul |
| docs/ARQUITETURA.md (schema) | 9 tabelas | 12 |
| docs/ARQUITETURA.md (containers) | "FastAPI + APScheduler embutido" | sem scheduler |
| docs/PILOTO.md ("dados que entram") | ocupação % entra como métrica | decisão do Lote 8: entram as parcelas; % é derivada (Lote 9) |

---

## 3. Matriz de riscos

Prioridade: **P1** bloqueia a POC · **P2** não bloqueia a POC, bloqueia expansão ·
**P3** melhoria futura.

| # | Risco | Evidência | Impacto | Prioridade | Recomendação | Quando |
|---|---|---|---|---|---|---|
| A | Linhagem: `medidas` não sabe de qual fonte/execução veio o valor; fontes distintas sobrescrevem-se em silêncio | `database.py:95-105` (unique métrica×armazém×competência, só `conector_id`); `ingestao.py:39-48` (upsert sobrescreve); pos_sum e capacidade1HDR gravam as mesmas `capacidade_*` (PLANO Lote 8) | Auditoria impossível ("de onde veio o 124%?"); a POC promete drill-down até a evidência | **P1** (parcial: `execucao_id` é barato e destrava o resto) | `execucao_id` em `medidas` + tabela fina `medidas_recebidas` por execução + precedência de fonte por métrica | Lote novo, antes da tela |
| B | Catálogo semântico: `metricas` = só nome+unidade; `get_or_create_metrica` cria métrica nova por typo de modelo, sem unidade | `database.py:49-57`; `ingestao.py:9-15` | Sem direção/descrição/agregação, a tela e os detectores não sabem interpretar a métrica; typo cria métrica fantasma | **P2** (núcleo é barato, junto do A) | Núcleo agora: descrição, direção desejável, tipo de agregação (fluxo/foto/razão), ativo; **remover** a criação implícita | Lote novo |
| C | Categórico como número: status de contrato viraria `valor NUMERIC` em `medidas_cliente` e passaria pelo z-score | Lote 9.5 do PLANO (ainda não construído — o risco é o desenho) | "Vencido-operando" como 1/0 no mesmo motor de volumetria = insight falso | **P1** (bloqueia a pergunta 2 da POC bem-feita) | Tabela `contratos` (datas, posições, tipo de acordo); status **derivado on-read** por código; `medidas_cliente` só fatos numéricos | Redesenho antes do 9.5 |
| D | Ocupação composta sem regra validada | Lote 9 do PLANO **já exige** fechar a regra com a Maria antes de codar | — | ok | Manter o gate como está; nada a fazer agora | — |
| E | Motor único: z-score não responde as 3 perguntas executivas; ocupação/comercial ficam `historico_curto` até ~2027 | `motor.py` (um mecanismo, um arquivo); PILOTO.md perguntas 1-3 são limite/conformidade | A tela da POC não teria o que acender | **P1** | Detectores como funções separadas emitindo `ocorrencias` (z-score vira um deles); 2-3 regras de limite/conformidade pra POC. Sem framework | Lote novo, antes da tela |
| F | Governança: métrica criada livremente pela esteira; fórmula por filial não existe (ok) | `ingestao.py:9-15` | Catálogo polui sozinho | **P2** | Resolve junto do B (métrica precisa existir previamente) | Lote B |
| G | Segurança/operação — classificação detalhada abaixo | `auth.py`, `Dockerfile`, ausência de backup | — | misto | Item a item abaixo | — |
| H | **Modelos de importação não versionados**: os 5 modelos do Lote 8 só existem no banco do worktree local; `catalogo_fontes.modelo_id` nunca é escrito por código nenhum | grep no backend: nenhum `UPDATE catalogo_fontes`; commit `f65d2d5` só muda parser/UI; `seed_catalogo.py:17` | Na VM não há como carregar dado real sem remapear na mão; o contrato de limpeza das fontes está fora do git | **P1** (operacional) | `seed_modelos.py` com os 5 mapeamentos como literais (padrão seed_depara) + vínculo do `modelo_id` no catálogo | Primeiro lote |
| I | Campo `pendencias` da resposta de upload é `lidas - gravadas` (negativo com 2+ métricas; não conta pendências reais) | `admin.py:232`; bug já anotado no PLANO Lote 3 | Número enganoso na UI | **P2** | Contar de verdade os agregados que caíram em pendência em `gravar_agregados` | Junto do lote A |
| J | Zero testes; `init_db` sem capacidade de ALTER | Sem diretório de testes, sem pytest no requirements; `database.py:24` | Qualquer lote de schema é voo cego; migration safety é princípio do projeto | **P1** (pré-requisito dos demais lotes) | pytest + testes do parser (função pura) e da ingestão; bloco de `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` idempotente no `init_db` | Primeiro lote |
| K | Fontes "foto do dia": arquivo com 2 dias do mesmo mês **soma em dobro** (o acumulador soma tudo da mesma competência) | `upload_manual.py:242-262`; disciplina "1 upload = 1 dia" é só convenção | Número silenciosamente errado. **"Não somar duas fotografias do mesmo mês" virou regra de negócio confirmada (seção 7)** — deixa de ser só proteção técnica | **P1** (promovido em 22/jul) | Validação de data única como propriedade **do modelo/fonte** (upload manual de fechamento exige 1 data; rejeita com mensagem clara), preservando a data exata da foto. A futura integração diária (`dw_api`, Lote 10) traz múltiplas datas e **seleciona o fechamento por regra** — a trava não pode bloquear esse caminho | Lote R2 |
| L | Docs desatualizados (tabela da seção 2) | — | Sessões futuras leem estado errado | **P2** | Atualização pequena e segura | Imediato |
| M | Hierarquia: `armazens` não conhece "família RMSP"; comparação familiar da POC não tem suporte em dado | `database.py:41-47` | Tela teria a família hardcoded | **P2** | Coluna `familia TEXT NULL` em `armazens` (não a árvore corporativa inteira) | Lote B |

**Classificação do risco G (segurança/operação):**

| Item | Estado real | Classificação |
|---|---|---|
| Senha única no admin | Decisão fechada; cookie HMAC assinado com expiração, httponly, samesite=lax — razoável pro escopo | Aceito na POC |
| Sem limite de tamanho de upload | `await arquivo.read()` carrega tudo em memória (`admin.py:186`) | **Obrigatório antes da POC com usuários** (limite simples, ex. 50 MB) |
| Backup externo + restauração | Não existe (Lote 4 planejado). O de-para/modelos/explicações não são rederiváveis | **Obrigatório antes da POC com usuários** |
| Autoria (quem subiu/alterou) | `execucoes.origem='manual'`, sem identidade — senha compartilhada não identifica ninguém | Antes da POC: campo "quem" digitado nos registros que nascem agora (explicações/planos). Auth individual: **antes da expansão** |
| HTTPS / reverse proxy | Porta 8002 direta, HTTP puro; senha viaja em claro na rede interna | **Antes da expansão corporativa** |
| Trilha de auditoria | Só `execucoes` | **Antes da expansão** |
| Scheduler no processo da API | Ainda nem existe; worker único já garantido no Dockerfile | Aceito na POC; revisar na expansão |
| Monitoramento | `restart: unless-stopped` e olho no log | Antes da expansão |
| VM compartilhada | Decisão consciente (Conciliador + Hub + Nuvem) | Aceito; revisar na expansão |

---

## 4. Arquitetura incremental proposta

O desenho-alvo mantém tudo que existe e insere três peças pequenas. Nenhum
microsserviço, nenhuma troca de banco, o parser e o admin continuam como estão.

```
conectores (upload_manual, sharepoint depois)
   │  formato canônico {metrica, armazem_na_fonte, competencia, valor}
   ▼
MEDIDAS_RECEBIDAS  ← nova: 1 linha por execução × métrica × armazém × competência
   │                  (a resposta de "qual fonte, qual execução, quando, qual modelo")
   ▼  publicação canônica (precedência de fonte por métrica, determinística)
MEDIDAS  ← a tabela atual, mesmo contrato de leitura + execucao_id (de onde veio o valor vigente)
   │
   ├─► derivadas (Lote 9: gravadas em medidas com regra versionada — só após regra validada)
   ▼
DETECTORES (funções separadas, mesmo gatilho pós-ingestão):
   1. z-score histórico (motor.py atual, intocado)
   2. limite de negócio (ex.: cobertura contratual > 100%)
   3. conformidade (ex.: cliente com movimento sem contrato vigente / vencido-operando)
   4. qualidade/cobertura (competência esperada ausente)
   │
   ▼
OCORRENCIAS  ← nova: o que a tela acende (tipo, severidade, regra que disparou, contexto)
   │            scores continua existindo como cache do detector 1
   ▼
COCKPIT (Lote 5 revisado: primeira tela = as 3 perguntas executivas do catering;
         a nuvem completa é uma visualização, vem junto ou depois)
   │
   ├─ EXPLICACOES (registro do gestor, nunca altera o valor)
   └─ PLANOS_ACAO (responsável, prazo, status, evidência)

IA narradora (futuro): lê ocorrencias + medidas do contexto — pacote pequeno já pronto
por construção; narrativa persistida. Nada a construir agora.
```

**Por que `medidas_recebidas` e não só uma coluna a mais:** o conflito existe hoje
(capacidade por duas fontes) e a pergunta "houve conflito? qual valor a outra fonte
deu?" só se responde guardando o que cada execução entregou. É a mesma camada fina —
agregado por armazém×mês, kilobytes — não é DW. E `medidas` continua sendo a única
tabela que a tela lê; ninguém a jusante muda.

**Sobre a IA narradora:** o desenho acima já a deixa pronta sem nenhuma abstração
extra — `ocorrencias` é exatamente o "pacote pequeno e estruturado de achados
calculados". Nada específico pra ela agora.

---

## 5. Proposta de schema

**Tabelas novas (4 agora, 2 depois):**

| Tabela | Chave/grão | Justificativa |
|---|---|---|
| `medidas_recebidas` | unique (execucao_id, metrica_id, armazem_id, competencia); colunas: valor, recebido_em, **data_referencia DATE NULL** | Linhagem por execução; resolve conflito de fontes de forma auditável. Reprocesso = delete por execução. `data_referencia` = data exata da fotografia em métricas tipo foto (decisão do take or pay: preservar a data do fechamento) |
| `contratos` | **id técnico** + `chave_na_fonte` (PK_OCUPACAO_COM — **a fonte não traz número de contrato nem de aditivo**; a chave técnica do DW por linha é o melhor identificador disponível, limitação explícita, nada inventado); cliente_id, armazem_id, data_inicial, data_final, garantia_minima, unidade, modalidade (TIPO_ACORDO: P=take-or-pay / L=locação), execucao_id da carga | **A identidade do contrato é a vigência, não a competência de foto** (a foto pertence à ocupação). Múltiplos contratos/aditivos preservados como linhas próprias. **Sobreposição de vigência gera ocorrência**; aditivo **não** é tratado automaticamente como ambiguidade — pode substituir, alterar ou complementar (regra pendente, seção 8). Status e garantia vigente na data de fechamento **derivados on-read** — nunca persistidos como número. Substitui o desenho do 9.5 |
| `ocorrencias` | **chave determinística UNIQUE** (regra_codigo + contexto: metrica/cliente/armazem/competencia); colunas: regra_codigo, regra_versao, severidade_atual, status (aberta/resolvida), primeira_deteccao, ultima_deteccao, data_resolucao, contexto/detalhe JSONB | Ciclo de vida idempotente: reexecutar o detector sobre problema ainda aberto **atualiza** a ocorrência (ultima_deteccao, severidade_atual), nunca duplica (garantido pela UNIQUE); problema que deixa de ser detectado é marcado resolvido com data. Tipos incluem qualidade (fechamento ausente/atrasado) e sobreposição contratual. Futuro insumo da IA narradora |
| `modelo_versoes` (R1) | modelo_id × versao; mapeamento JSONB **imutável**, criado_em | Versionamento real: editar modelo = criar versão nova; `modelos_importacao` aponta a versão ativa; `execucoes` referencia a **versão exata** usada. Os 5 modelos atuais entram como versão 1. Desenho detalhado após o R0 |
| `medidas_cliente` | unique (metrica_id, cliente_id, armazem_id, competencia) + execucao_id + **data_referencia DATE NULL** | Já prevista (9.5); entra **só com fatos numéricos** (volumetria, posições ocupadas). É onde a ocupação física de fechamento por cliente vai morar **quando a fonte existir** (seção 7 — hoje não existe) |
| `explicacoes` (lote posterior) | ocorrencia_id ou contexto (armazem×metrica×competencia); texto, autor, criado_em | Explicação nunca toca `medidas` |
| `planos_acao` (lote posterior) | explicacao/ocorrencia; descricao, responsavel, prazo, status, evidencia, timestamps | Idem |

**Tabelas alteradas (ALTER aditivo, idempotente, sem tocar dado existente):**

| Tabela | Mudança | Justificativa |
|---|---|---|
| `medidas` | `+ medida_recebida_id INTEGER NULL REFERENCES medidas_recebidas` (canônica publicada de uma recebida), `+ regra_codigo TEXT NULL` / `+ regra_versao TEXT NULL` / `+ calculado_em TIMESTAMPTZ NULL` (canônica derivada), `+ data_referencia DATE NULL` | Linhagem mínima sem árvore de dependências: medida vinda de fonte aponta a **medida recebida exata** (execução, modelo/versão e fonte lógica vêm por ela); medida derivada carrega código da regra + versão + data do cálculo. NULL nas linhas históricas — sem migração destrutiva |
| `metricas` | `+ descricao TEXT, direcao TEXT (maior_melhor/menor_melhor/neutra), agregacao TEXT (fluxo/foto/razao), ativo BOOLEAN DEFAULT true, fonte_preferencial_id INTEGER NULL REFERENCES catalogo_fontes` | Núcleo do catálogo semântico. **A precedência canônica aponta pra fonte lógica** (`catalogo_fontes.chave`, ex.: `capacidade`), nunca pra modelo ou versão de modelo — trocar a versão do modelo não muda a precedência. Versão/vigência/responsável/fórmula: evolução documentada, **não** criados agora |
| `armazens` | `+ familia TEXT NULL` | "RMSP" agrupa as 4 filiais da POC; não é a árvore corporativa |
| `catalogo_fontes` | assume o papel de **fonte lógica** — a `chave` já é o código estável (volumetria, ocupacao_fisica, capacidade, ocupacao_comercial, ocupacao_manual); `modelos_importacao` ganha `fonte_id` apontando pra cá (R1) | Fonte lógica separada do modelo: a fonte é o conceito estável; modelos e versões são a mecânica de importação. Substitui o `modelo_id` solto de hoje (que nenhum código preenche) pelo caminho fonte → modelo → versões → execuções |

**Código alterado (sem mudar comportamento de leitura):** `gravar_agregados` grava em
`medidas_recebidas` e publica em `medidas` conforme precedência **por fonte lógica**;
`get_or_create_metrica` deixa de criar métrica implicitamente; `motor.py` intocado,
ganha vizinhos (detectores) que escrevem `ocorrencias`.

**Migrations:** todas as mudanças acima entram como migrations incrementais do
Alembic (adotado no R0), nunca como ALTERs no `init_db`.

**O que deliberadamente NÃO se cria:** tabela de metas (não há metas definidas),
tabela genérica de regras (2-3 detectores em código versionado bastam), domínios
corporativos, narrativas, hierarquia companhia/empresa/regional, versionamento de
métrica. Tudo isso tem caminho aberto sem reescrita quando chegar.

---

## 6. Plano de implementação (lotes pequenos, um por vez)

Agrupados por módulo, na ordem que minimiza retrabalho. Os lotes 4, 5, 9 e 10 do PLANO
atual continuam valendo — este plano se encaixa antes/entre eles.

**Lote R0 (revisado — ÚNICO AUTORIZADO em 22/jul) — Alicerce: testes + Alembic + docs**
· toca: raiz do repo, `requirements.txt`, `backend/database.py`, `backend/main.py`,
`backend/routers/admin.py`, `alembic/` (novo), `tests/` (novo), docs
**Alembic** como mecanismo de migração — o `init_db` **não** vira um conjunto
crescente de ALTERs; fica só com os seeds idempotentes. Baseline gerada do schema
atual (12 tabelas, DDL manual — não há models SQLAlchemy); banco existente (VM/local)
recebe `alembic stamp` da baseline (detecção automática no startup: schema legado
presente + sem `alembic_version` → stamp) e depois `upgrade head`; banco novo nasce
direto por `upgrade head`. Teste de upgrade (banco vazio → head → schema idêntico ao
do `init_db` atual) e orientação de rollback (`downgrade` onde viável; baseline é
destrutivo, só dev). pytest com Postgres real: parser (função pura), ingestão
idempotente, motor recalculável, e os 5 fluxos de upload como teste de
compatibilidade. Limite de tamanho de upload. Correção das divergências de docs
(seção 2).
*Conclusão:* suíte em 1 comando; `upgrade head` em banco vazio ≡ schema atual; VM
atualiza sem perder dado (stamp + upgrade); os 5 uploads passam igual antes; docs
batem com o código.

**Lote R1 (revisado) — Fontes lógicas + versionamento real dos modelos** · toca:
migration nova, `database.py`, `admin.py`, `admin.html`
Fonte lógica = `catalogo_fontes` (a `chave` é o código estável). `modelos_importacao`
ganha `fonte_id`; nova `modelo_versoes` com mapeamento **imutável** por versão;
**editar modelo = criar versão nova** e mover o ponteiro de versão ativa — a
configuração histórica nunca é alterada; `execucoes` passa a referenciar a versão
exata usada. Os 5 mapeamentos atuais (extraídos do banco do worktree lote-8) entram
como **versão 1** via seed. **O desenho detalhado será apresentado após o R0
validado, antes de construir.**
*Conclusão:* banco zerado → 5 fontes com modelo v1 ativo; editar cria v2 sem tocar a
v1; execução antiga segue apontando a v1; catálogo lista execuções por fonte.

**Lote R2 — Linhagem** · toca: migration nova, `ingestao.py`, `admin.py`
`medidas_recebidas` + linhagem canônica em `medidas` (`medida_recebida_id` pra
publicadas de fonte; `regra_codigo`/`regra_versao`/`calculado_em` pra derivadas) +
`data_referencia` (data exata da foto) + publicação com precedência por **fonte
lógica** + conserto do campo `pendencias` + validação de data única **por
modelo/fonte** (upload manual de fechamento exige 1 data; não trava a futura
ingestão diária do `dw_api`, que seleciona o fechamento por regra).
*Conclusão:* teste de conflito: subir capacidade por pos_sum e por HDR → as duas
recebidas registradas, canônica é a da fonte preferencial, independente da ordem de
upload; re-upload idempotente; arquivo de fechamento com 2 datas é rejeitado com
mensagem clara; uploads existentes seguem funcionando (smoke).

**Lote R3 — Catálogo de métricas (núcleo)** · toca: `database.py`, `ingestao.py`, `admin.html`
Colunas novas em `metricas` + seed com descrição/direção/agregação das 12 métricas +
fim da criação implícita + lista de métricas no admin (read-only).
*Conclusão:* modelo referenciando métrica inexistente é rejeitado com mensagem clara;
catálogo visível.

**Lote R4 — Contratos e estados categóricos** · toca: migration nova, parser (tipo de
modelo "contratos"), `admin.py`
Tabela `contratos` com identidade por **vigência** (id técnico + PK_OCUPACAO_COM como
chave da fonte — a fonte não traz número de contrato/aditivo, limitação explícita),
carregada do ocupacaoComercial.csv; derivação on-read do status e da **garantia
mínima vigente na data de fechamento** por cliente×filial; "vencido-operando" (regra
dos 60 dias sobre o fato) por código. **Sobreposição de vigência gera ocorrência**
(R5); aditivo não é automaticamente ambiguidade — a semântica
(substitui/altera/complementa) é regra pendente (seção 8); nada é escolhido nem
somado automaticamente sem essa regra.
*Conclusão:* Sapore/Sodexo/Convida com status correto derivado; garantia vigente por
competência consultável; múltiplos contratos preservados; nenhum status persistido
como número. **Substitui a parte de contrato do Lote 9.5**; `medidas_cliente`
(volumetria por cliente) continua como 9.5 reduzido.

**Lote R5 — Detectores e ocorrências** · toca: migration nova, `motor.py` (vizinhos)
`ocorrencias` com **ciclo de vida idempotente** (chave determinística UNIQUE por
regra+contexto; reexecução atualiza `ultima_deteccao`/`severidade_atual`, nunca
duplica; problema que some é resolvido com data) + detector de limite (cobertura>100%,
parametrizado por métrica) + detector de conformidade (operando sem contrato /
vencido-operando) + detector de qualidade de dados (competência esperada ausente;
**fechamento ausente ou atrasado**; sobreposição contratual do R4); z-score passa a
emitir ocorrência quando `fora_padrao`, com código e versão da regra.
*Conclusão:* rodada gera as ocorrências que reproduzem os 3 achados reais da análise
(RMSPIII 124%, RMSPII 7.034 vencidas, Convida sem contrato); rodar 2× não duplica
nenhuma.

**Lote R6 — Take or pay por cliente** · **bloqueado por dado** (não é código; ver
seção 7). Depende de ocupação física de fechamento em cliente×filial×competência,
que nenhuma fonte atual fornece pras RMSP — o insumo é o relatório detailed
(posição×cliente) que hoje só existe pra RPI no DW; o pedido já está no Lote 0 e
**passa a ser bloqueador deste lote**. Sem proxy por volumetria. Quando a fonte
existir: ingestão em `medidas_cliente` (com `data_referencia`) + as 4 métricas
derivadas da seção 7 por código determinístico. Enquanto isso, a tela apresenta
contratado (comercial) e ocupação física agregada por filial **separados**.
*Conclusão:* quantidade faturável, excedente, garantia não utilizada e utilização da
garantia calculados por cliente×competência, batendo com conferência manual; nenhum
valor financeiro (sem tarifa).

**Depois (ordem a combinar):** Lote 5 (tela — primeira versão = cockpit das 3
perguntas lendo `ocorrencias`+`medidas`; a nuvem de bolinhas junto ou logo depois),
Lote 4 (rotina+backup — obrigatório antes de usuários), explicações+planos de ação,
Lote 9 (composta, gate mantido), 9.5 restante, Lote 2/10.

Dependências: R0 → R1 → R2 → R3 → R4/R5 (R4 e R5 podem inverter) → R6 (bloqueado por
dado externo). Cada lote fecha com smoke test dos importadores existentes.

---

## 7. Take or pay — regra confirmada e verificação de grão (22/jul/2026)

### A regra

A ocupação física usada no take or pay é a **do fechamento do mês, por cliente e
filial**:

```
quantidade_faturavel_take_or_pay = max(garantia_minima_contratada_vigente,
                                       ocupacao_fisica_fechamento)
```

Exemplos: contratado 1.000 / físico 900 → faturável 1.000; contratado 1.000 / físico
1.200 → faturável 1.200. A competência representa o mês do fechamento; a **data exata
da fotografia** usada como fechamento é preservada (coluna `data_referencia`, seção 5).

### O modelo do dashboard corporativo (referência de semântica)

O painel corporativo separa quatro perspectivas — **ocupação física e ocupação
econômica não são sinônimos** e não devem ser tratadas como tal no catálogo de
métricas:

| Perspectiva | Exemplo observado | Composição observada |
|---|---|---|
| Capacidade vendável | 424.777 | — |
| Ocupação econômica | 420.797 (99%) | comercial 207.380 + operacional 213.417 (soma fecha) |
| Take-or-pay e locações | 188.529 (44%) | locado 78.627 + take or pay 110.819 = **189.446 ≠ 188.529** |
| Ocupação física | 312.320 (74%) | operacional 233.693 + locado 78.627 (soma fecha) |

A diferença de **917** no card take-or-pay e locações **não será implementada como
soma aparente**: pode ser sobreposição, regra anti-dupla contagem, diferença de
filtro, exclusão contratual ou regra interna do Power BI — registrada como pendência
(seção 8, item 3). Esse modelo reforça o desenho já proposto (perspectivas separadas,
risco D) e alimenta as descrições do catálogo de métricas (R3).

### Verificação do grão nas fontes atuais

O cálculo exige ocupação física de fechamento em **cliente × filial × competência**.
Verificado coluna a coluna nas 5 fontes da POC (`backend/seed_catalogo.py`):

| Fonte | Grão real | Tem cliente? | Serve? |
|---|---|---|---|
| pos_sum (ocupação física) | filial × câmara, foto do dia | **não** — não existe coluna de cliente | não |
| Ocupação manual | dia × filial × cliente × local | sim, mas só cobre operações **fora do WMS** (na família, só RMSP — caso Frimesa) | parcial — não representa o total físico do cliente |
| Fato volumetria | dia × filial × cliente × operação | sim, mas é movimentação — **vetado como proxy** por decisão | não |
| Ocupação comercial | contrato (filial × cliente) | sim — dá a **garantia mínima** (o outro lado da fórmula), não a física | só o lado contratado |
| Capacidade HDR | filial | não | não |

**Conclusão: indisponível hoje para RMSP/RMSPII/RMSPIII/RMSPV.** Conforme a decisão:
sem proxy, cálculo indisponível, e a POC apresenta contratado e ocupação física
agregada por filial **separados**. A fonte que resolve é o relatório **detailed**
(posição × cliente, foto do dia) — hoje só existe pra RPI no DW; o pedido ao time do
DW já rastreado no Lote 0 **passa a ser bloqueador do Lote R6**.

### Métricas derivadas permitidas (quando o dado existir — Lote R6)

Por cliente × competência, determinísticas, em código:

```
quantidade_faturavel_take_or_pay = max(garantia_minima, ocupacao_fisica_fechamento)
excedente_sobre_garantia         = max(ocupacao_fisica_fechamento - garantia_minima, 0)
garantia_nao_utilizada           = max(garantia_minima - ocupacao_fisica_fechamento, 0)
utilizacao_da_garantia           = ocupacao_fisica_fechamento / garantia_minima
```

**Sem valor financeiro** enquanto não houver tarifa e demais regras comerciais.

### Modelagem temporal

- Contrato e ocupação avaliados na **mesma competência**: garantia mínima vigente na
  data de fechamento × fotografia física correspondente ao fechamento.
- Data exata da fotografia preservada (`data_referencia`).
- Ausência ou atraso de fechamento = ocorrência de **qualidade de dados** (detector
  do R5), nunca silêncio.
- **Não somar duas fotografias do mesmo mês** (regra confirmada — risco K promovido
  a P1, validação no R2). A validação de data única pertence ao **modelo/fonte**
  (upload manual de fechamento); a futura integração diária do DW (`dw_api`) traz
  múltiplas datas e **seleciona** o fechamento por regra — a trava não bloqueia esse
  caminho.
- Mais de um contrato/aditivo vigente pro mesmo cliente×filial: **não escolher nem
  somar automaticamente** — ocorrência de ambiguidade até regra explícita validada.

---

## 8. Decisões de negócio pendentes

1. **Precedência de capacidade:** quando pos_sum e capacidade1HDR divergem, qual é a
   canônica? (Hoje: vence quem subiu por último, sem registro.)
2. **Vigência no comercial:** a regra temporal fechou (garantia vigente na data de
   fechamento — seção 7), mas a métrica agregada `comercial_vigente` hoje soma tudo
   sem filtrar DATA_FINAL. Com a tabela `contratos` o filtro vira automático —
   confirmar o destino do vencido (sai da soma? vira `comercial_vencido_operando`?)
   e a separação take-or-pay (P) × locação (L) nas métricas agregadas.
3. **Divergência de 917 no card "Take-or-pay e Locações" do dashboard corporativo**
   (locado 78.627 + take or pay 110.819 = 189.446 ≠ 188.529 exibido): sobreposição?
   anti-dupla contagem? filtro? exclusão contratual? regra do Power BI? **Não somar
   às cegas** até a regra ser explicada pelo dono do painel.
4. **Semântica de aditivos e sobreposição contratual** pro mesmo cliente×filial: um
   aditivo pode substituir, alterar ou complementar o contrato — a regra não está
   disponível na fonte (que nem traz número de contrato/aditivo). Até a regra ser
   validada: sobreposição de vigência gera ocorrência e nada é escolhido nem somado
   automaticamente.
5. **Definição operacional de "fechamento":** a foto de maior data dentro do mês? A
   partir de quantos dias de distância do fim do mês o fechamento conta como
   "atrasado" (ocorrência de qualidade)?
6. **Tarifas e regras comerciais** do take or pay — sem elas, nenhum valor financeiro
   é calculado (só quantidades).
7. **Regra da ocupação composta + anti-dupla contagem** (caso Frimesa) — já pendente
   no Lote 9.
8. **Cross Docking** (148 linhas do fato fora das duas métricas de volumetria) —
   métrica própria ou continua fora?
9. **Severidade dos limites executivos:** cobertura > 100% é alerta ou crítico?
   Existe limite de ocupação física acordado (ex.: 95%)?
10. **Autoria na POC:** com senha única, explicações/planos levam um campo "quem
    registrou" digitado, ou espera auth individual?
11. Do Lote 0 (já rastreadas): dono do comercial de Barueri, pedidos ao DW (o
    relatório detailed posição×cliente pras RMSP agora **bloqueia o take or pay** —
    Lote R6), contrato da planilha de ocupação.
