# Arquitetura — Nuvem IA

Status: fechada em 15/jul/2026; revisada no mesmo dia após análise de escalabilidade.
Construção em lotes desde então — ver docs/PLANO.md pro status vivo de cada lote.

## Posição na infra

- App **separado** do Portal SuperFrio & IceStar (Receita 3 do CONTRIBUTING do Hub):
  repo, banco e deploy próprios; o Hub só cadastra um card (`tipo = url`, nova aba).
- Mesma VM do Conciliador (porta 80) e do Hub (8001). Nuvem IA: **porta 8002**.

## Containers (docker-compose próprio)

| Serviço | Conteúdo |
|---|---|
| `nuvem-app` | FastAPI (API + estáticos); o APScheduler (rotina 1×/dia) entra no Lote 4 — ainda não está no container |
| `nuvem-db` | Postgres 16, volume nomeado (a camada fina) |

Dockerfile faz `COPY backend/ frontend/` → mudou código = **rebuild**
(`docker compose up -d --build`). Frontend vanilla sem build step; ao mudar asset,
subir o `?v=` no HTML.

O `nuvem-app` roda com **worker único**: o APScheduler vive no processo da API e, com
múltiplos workers do uvicorn, a rotina dispararia em duplicata.

## Deploy na VM (checklist)

Validado na VM real em 20/jul/2026 (Lotes 1/3/7): sobe na 8002, admin autentica e o seed
do Lote 7 traz as 31 filiais ativas. O passo a passo executável fica em docs/DEPLOY.md;
o checklist abaixo é o resumo com as decisões:

1. **Pré-requisito — deploy key da VM pro repo Nuvem**: a VM usa uma deploy key por repo,
   com apelido de host no `~/.ssh/config` (a do Conciliador é a default `github.com`).
   Criada a `nuvem_deploy` com apelido `github-nuvem` (20/jul/2026), cadastrada como
   deploy key read-only no repo. Detalhe em docs/DEPLOY.md.
2. `git clone git@github-nuvem:SuperfrioIA/Nuvem.git nuvemIA` em `/home/ubuntu` (mesma VM
   do Conciliador porta 80 e do Hub porta 8001).
3. Criar `.env` de produção na VM (**nunca commitado**) com `POSTGRES_PASSWORD`,
   `ADMIN_PASSWORD`, `SECRET_KEY` reais (gerar novos, não reusar os de teste local) e
   `UPLOADS_HOST_PATH` apontando pra uma pasta persistente fora do container — ver
   `.env.example`.
4. Confirmar Docker + Compose na VM (`docker compose version` — devem já estar, usados
   por Conciliador/Hub) e que a porta 8002 está livre (`ss -tlnp | grep 8002` ou
   equivalente).
5. `docker compose up -d --build`.
6. Validar **na própria VM antes de abrir pra rede**: `curl http://localhost:8002/admin`
   (GET; a rota não aceita HEAD/`-I`), `docker compose logs nuvem-app` sem erro de
   conexão com o Postgres, login no admin funcionando, `GET /api/admin/armazens` trazendo
   as 31 filiais ativas do Lote 7 (32 semeadas, MRS inativa).
7. **Só depois de validado**, abrir pra rede. Em 20/jul/2026 a 8002 já respondeu de outra
   máquina sem chamado — aparentemente cai numa faixa/regra do Security Group já liberada
   na VM (como a 8001 do Hub). Se uma porta futura não responder, aí sim abrir chamado com
   a **Valcann** pra liberá-la na rede interna.

Nota: até o Lote 5 (frontend, "a nuvem") ser construído, `/` redireciona pra `/admin` —
abrir a porta agora dá acesso só ao admin, não à tela final. Não é bug.

## Conectores (o coração)

Interface única que todo conector implementa:

```
conector.testar()            → ok/erro
conector.buscar(competencia) → [{metrica, armazem_na_fonte, competencia, valor}]
conector.detalhar(...)       → opcional; reservado pra fontes com grão fino (Pentaho)
```

`armazem_na_fonte` = como a fonte chama o armazém (era `valor_na_fonte`; renomeado
porque dois campos "valor" com significados diferentes é convite a bug).

O motor só conhece o formato canônico — não sabe de onde o dado veio. Conector é
**registro** na tabela `conectores` (tipo + config JSONB + ativo); ligar/desligar é um
toggle no admin, não deploy.

| Conector | v1 | Nota |
|---|---|---|
| `upload_manual` | sim | tela de upload de xlsx no admin; entra pela mesma esteira |
| `sharepoint_excel` | sim (código) | Microsoft Graph; só funciona quando a TI criar o app registration (Entra ID, permissão `Sites.Selected`) — **caminho crítico externo**. Até lá, "testar conexão" acusa erro (esperado) |
| `pentaho_sql` | futuro | mais um conector; zero mudança em motor/tela/banco |

### `upload_manual` — modelos de importação

Relatórios reais não chegam como tabela limpa armazém×mês: vêm em grão mais fino
(posição×dia, SKU×lote), com várias colunas candidatas pra mesma dimensão (ex: filial
como SK Filial/ERP Filial/WMS Unidade/QLS Unidade) e cliente misturado nas linhas. Por
isso o `upload_manual` não tem um formato de arquivo fixo — tem **modelos de
importação**: mapeamento de colunas nomeado e reutilizável, salvo por relatório
(tabela `modelos_importacao`).

Ao mapear um relatório, o admin define:

- **armazém**: vem de uma coluna do arquivo, ou é um valor fixo digitado no upload
  (quando o relatório já vem recortado pra 1 filial e não tem essa coluna)
- **competência**: mesma lógica — coluna do arquivo (inclusive data completa, truncada
  pro mês) ou valor fixo digitado
- **métricas**: cada uma é soma direta de uma coluna, ou razão entre duas colunas
  (numerador/denominador) — a razão é o que permite métricas de nível/capacidade como
  ocupação; a razão das somas do período já dá o resultado certo mesmo com várias
  linhas por dia dentro do mês, sem precisar calcular percentual linha a linha
- **cliente**: se existir coluna de cliente, ela é reconhecida no modelo (documentação,
  mira a v2) mas não persiste — o processamento agrega (soma/razão) por
  armazém+competência+métrica, absorvendo cliente/SKU/posição/documento/etc.

Qualquer coluna do arquivo que não for mapeada simplesmente não entra no banco — nem
como dado, nem como cópia linha a linha. O modelo fica salvo (nomeado) pra reuso: nova
carga do mesmo relatório só escolhe o modelo, sem remapear (procura coluna por nome,
não por posição).

**Fora do parser:** export tipo matriz/pivô do Power BI (hierárquico, com linha de
subtotal e célula em branco = "herda de cima") — fonte deve exportar em formato tabela
plana antes de subir.

## Rotina de ingestão

- A rotina diária (e a execução manual) busca as **últimas 3 competências**, não só a
  corrente: planilha de ocupação é atualizada depois do fechamento e perdas fecham com
  atraso. O upsert idempotente torna a rebusca de graça.
- **Reprocessar competência = delete + insert por conector × competência.** Upsert
  corrige valor, mas não remove linha que sumiu da fonte ou trocou de armazém após
  acerto de de-para.
- Linha cujo `armazem_na_fonte` não tem de-para **não entra em `medidas` nem é
  descartada em silêncio**: vira registro em `depara_pendencias` e aparece como fila
  no admin. Resolver = cadastrar o de-para e reexecutar a competência.

## Schema (camada fina, Postgres)

| Tabela | Grão | Nota |
|---|---|---|
| `conectores` | 1/fonte | tipo, config JSONB, `ativo` |
| `armazens` | 1/filial | a dimensão |
| `depara_armazem` | conector × armazem_na_fonte | unique (conector, armazem_na_fonte); editável no admin |
| `depara_pendencias` | conector × armazem_na_fonte | valores vistos sem mapeamento; fila exibida no admin, some ao resolver |
| `metricas` | 1/métrica | nome, unidade |
| `medidas` | métrica × armazém × mês | **o fato.** unique na chave → upsert idempotente |
| `scores` | métrica × armazém × mês | média/desvio/z da janela 12–24m + estado; derivado e recalculável (cache de leitura, não fonte de verdade) |
| `modelos_importacao` | 1/relatório mapeado | conector, nome, `fonte_id` (fonte lógica, Lote R1), mapeamento JSONB — a partir do R1 é só a identidade + espelho congelado da v1; a config viva mora em `modelo_versoes` |
| `modelo_versoes` (Lote R1) | modelo × versão | versão **imutável** do modelo: mapeamento JSONB, `hash_config`, `ativo`, `padrao`, `criado_em`. Editar modelo = criar versão nova; ≤1 padrão por modelo (índice único parcial); CHECK padrão ⟹ ativo. Os 5 modelos canônicos da POC são semeados como v1 (Lote R1.1, `backend/seed_modelos.py`) |
| `execucoes` | 1/rodada | início, fim, status, linhas lidas/gravadas, erro, `modelo_id`, `modelo_versao_id` (versão exata usada, Lote R1), referência ao arquivo original retido — exibido no admin |
| `clientes` (Lote 7.1) | 1/cliente | lista curada dos clientes de catering (nk_erp, nome, flag) — o segmento do DW está errado, não serve de filtro |
| `catalogo_fontes` (Lote 8.5) | 1/família de relatório | chave estável, descrição, origem no DW, grão, `ativo` (Lote R1: é a **fonte lógica**) — a documentação viva do que o sistema vê |
| `catalogo_colunas` (Lote 8.5) | coluna × fonte | significado e papel de cada coluna do arquivo bruto no modelo de importação |

**Migrations (Lote R0):** o schema é criado e evoluído pelo **Alembic**
(`alembic/versions/`, baseline = as 12 tabelas acima); o `init_db()` só roda seeds
idempotentes. No startup: banco novo nasce da baseline, banco legado é validado
(tabelas + colunas obrigatórias) antes de receber o stamp — divergência aborta a
subida com erro claro, sem tocar o banco. Runbook e contingência em docs/DEPLOY.md.
A migration **0002** (Lote R1) acrescenta `modelo_versoes`, `modelos_importacao.fonte_id`,
`execucoes.modelo_versao_id` e `catalogo_fontes.ativo`, e converte os modelos atuais em
v1 preservando os dados — aditiva, roda por cima da baseline no `upgrade head`.

Princípios: persistir o fato, derivar a interpretação; idempotência (rodar 2× não
corrompe); validação no boundary (Excel/config), confiança interna.

## Testes (Lote R0)

Suíte pytest (`tests/`) com Postgres real, coberta: parser com os **mapeamentos
reais** dos 5 modelos do Lote 8 sobre arquivos sintéticos, ingestão
(de-para/pendência/upsert idempotente), motor (estados, limiar, recálculo
idempotente), migração (banco novo, legado válido, legado divergente aborta) e os
5 fluxos de upload ponta a ponta pela API, com limite de tamanho
(`UPLOAD_MAX_MB`, default 50 MB). Como rodar: docs/DEPLOY.md. Os dados de teste
são sintéticos — provam a mecânica, não substituem a validação visual dos
relatórios reais.

## Backup (requisito, não detalhe de implantação)

Quase tudo na camada fina é rederivável das fontes — **exceto o de-para** (conhecimento
que não existe em nenhum sistema; perder o volume = perder os ~80% de trabalho real) e
os fatos que entraram por `upload_manual`. Portanto:

- `pg_dump` diário do `nuvem-db`, copiado **pra fora da VM** (destino a combinar com a TI).
- Os xlsx do upload manual ficam retidos, referenciados na execução (`execucoes`) —
  é também o caminho de drill-down manual dessa fonte (a camada fina só guarda o
  consolidado; ver detalhe = abrir o arquivo original de novo). **Retenção começa já no
  Lote 1** (antecipada do que seria só Lote 4), senão os uploads anteriores ao Lote 4
  já teriam sumido.
  - Armazenamento começa **local** (pasta na VM, plugável) e migra pra **SharePoint**
    (Microsoft Graph, mesma credencial do `sharepoint_excel`) assim que o Entra ID for
    liberado — mantém a VM compartilhada enxuta.
  - Isso exige que o pedido à TI (Lote 0) inclua permissão de **escrita** (write) na
    concessão de acesso ao site, não só leitura (a leitura já era necessária pra buscar
    a planilha de ocupação).

## Motor

Python puro, sem libs de ML: por métrica × armazém, média e desvio-padrão da janela de
12–24 meses (excluindo o mês em análise); z-score vira estado (dentro/fora do padrão).

## Frontend

- `index.html` — a nuvem (vanilla JS, mesmo padrão do mapa-ia do portal); a bolinha
  distingue **fora do padrão** de **sem dado** — ausência de medida não é "normal"
- `admin.html` — conectores (toggle/testar/executar agora), upload de xlsx, CRUD do
  de-para, fila de pendências de de-para, log de execuções e **painel de cobertura**
  (matriz métrica × armazém × competência presente/ausente — sustenta o "números batem"
  quando uma planilha ainda não chegou)

## Auth

Senha única protegendo só o `/admin`. A nuvem em si aberta na rede interna. Evolução
futura: JWT padrão SuperFrio, sem retrabalho estrutural.

## Drill-down

Com fontes mensais, o detalhe da bolinha = série histórica da própria camada fina
(instantâneo). Consulta ao vivo na fonte só quando existir conector com grão fino —
a interface (`detalhar()`) já prevê, mas não se constrói antes da necessidade.

## Ordem de construção sugerida

1. **Pedido à TI** (app registration no Entra ID) — disparar cedo; é o caminho mais longo
2. **Congelar o contrato da planilha de ocupação** (aba/colunas fixas, com quem preenche)
3. Esqueleto: compose + banco + tabelas + admin com upload manual → primeiro dado real
4. Motor + scores
5. A nuvem (tela)

## Riscos e evoluções conhecidas

- **Dimensão cliente (v2, custo conhecido):** não é toggle nem conector — exige de-para
  de clientes, ajuste no motor e **segunda tabela-fato** (`medidas_cliente`, grão
  métrica × armazém × cliente × mês); fatos de grãos diferentes não dividem tabela.
  Continua agregado (milhões de linhas, não bilhões), mas entra só com decisão
  consciente, não como "é só plugar".
- **Sazonalidade / fadiga de alerta:** z-score contra janela mista acende a volumetria
  todo dezembro, previsivelmente — bolinha que acende quando todo mundo já sabia treina
  o usuário a ignorar as luzes. Ok no piloto (bolinhas acesas juntas = perda "justa");
  mitigar **antes** de escalar o nº de métricas: comparar com o mesmo mês dos anos
  anteriores, ou mediana/MAD no lugar de média/desvio (janela de ~12 pontos com 1
  anomalia no histórico infla o desvio e mascara as próximas).
- **O grão é o termostato:** o que mantém a camada fina fina é o grão armazém × mês.
  Toda proposta de reduzir grão (dia, cliente, SKU/lote) é o momento de atenção — se a
  pergunta é de investigação, a resposta é `detalhar()` na fonte, não linha nova aqui.

## Fora de escopo (por enquanto)

Previsão/sazonalidade; padrão de comportamento por cliente; alertas automáticos/e-mail;
IA narradora; integração Pentaho.
