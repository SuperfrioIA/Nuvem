// Utilitarios compartilhados entre frontend/admin.html e frontend/nuvem.html
// (Lote P5.5; visao executiva consolidada na nuvem no V1.0) -- extraidos do
// admin.html pra nao duplicar/dessincronizar a mesma formula em duas telas.
// Sem framework, sem build step: script comum incluido via <script src> antes
// do script proprio de cada pagina.

const API = "/api/admin";

// login/sessao: as duas paginas usam os mesmos ids de DOM (login, app,
// senhaInput, loginErro, btnEntrar, btnSair) -- aoEntrar() e a funcao que
// cada pagina passa pra carregar o proprio conteudo depois da sessao ok.
async function api(path, options = {}) {
  const resp = await fetch(API + path, { credentials: "same-origin", ...options });
  if (resp.status === 401) {
    mostrarLogin();
    throw new Error("não autenticado");
  }
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    throw new Error(corpo.detail || `erro ${resp.status}`);
  }
  return resp.status === 204 ? null : resp.json();
}

function mostrarLogin() {
  document.getElementById("login").classList.remove("oculto");
  document.getElementById("app").classList.add("oculto");
}

function mostrarApp(aoEntrar) {
  document.getElementById("login").classList.add("oculto");
  document.getElementById("app").classList.remove("oculto");
  if (aoEntrar) aoEntrar();
}

async function verificarSessao(aoEntrar) {
  const { autenticado } = await api("/me");
  if (autenticado) mostrarApp(aoEntrar); else mostrarLogin();
}

function iniciarLoginPadrao(aoEntrar) {
  document.getElementById("btnEntrar").addEventListener("click", async () => {
    const senha = document.getElementById("senhaInput").value;
    const erro = document.getElementById("loginErro");
    erro.textContent = "";
    try {
      const form = new FormData();
      form.append("senha", senha);
      await fetch(API + "/login", { method: "POST", body: form, credentials: "same-origin" })
        .then(async r => { if (!r.ok) throw new Error((await r.json()).detail || "erro"); });
      mostrarApp(aoEntrar);
    } catch (e) {
      erro.textContent = "Senha incorreta.";
    }
  });

  document.getElementById("btnSair").addEventListener("click", async () => {
    await fetch(API + "/logout", { method: "POST", credentials: "same-origin" });
    mostrarLogin();
  });

  verificarSessao(aoEntrar);
}

function escaparHtml(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Abrevia pra milhoes com 3 algarismos significativos (ex.: 36,6 / 1,57 /
// 4,28) -- mesma regra usada no resumo executivo do backend (resumo_poc.py).
function formatarMilhoesExec(valor) {
  const emMilhoes = Number((valor / 1_000_000).toPrecision(3));
  return emMilhoes.toLocaleString("pt-BR");
}

// kg -> toneladas (/1000) -> mil toneladas (/1000), 1 casa fixa. Unidade
// executiva de peso da empresa e tonelada, nao kg -- decisao de 30/jul/2026.
function formatarPesoExecutivo(pesoKg) {
  const milToneladas = pesoKg / 1_000_000;
  return `${milToneladas.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mil t`;
}

function formatarToneladasDetalhado(pesoKg) {
  const toneladas = pesoKg / 1000;
  return `${toneladas.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} toneladas`;
}

function formatarMoeda(valor) {
  return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatarNumeroKpi(valor, unidade) {
  const texto = Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  return unidade ? `${texto} ${unidade}` : texto;
}

// Rotulo de filial pra tela: "016 · RMSPIV" quando a sigla confirmada veio do
// backend (backend/services/filiais_datahub.py, a fonte unica do de-para de
// exibicao), so o codigo quando nao veio (ex.: 002, de-para pendente).
function rotuloFilial(codigo, sigla) {
  if (!codigo) return "—";
  return sigla ? `${codigo} · ${sigla}` : String(codigo);
}

const MESES_ABREV = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

function competenciaCurta(competencia) {
  const partes = String(competencia || "").split("-");
  const idx = parseInt(partes[1], 10);
  if (partes.length !== 2 || !idx || idx < 1 || idx > 12) return competencia || "-";
  return `${MESES_ABREV[idx]}/${partes[0]}`;
}

// Cards executivos, nesta ordem -- "registros" fica de fora da visao
// principal (aparece na area tecnica/qualidade dos dados). O card "Volume
// total" foi removido no V1.2: a coluna Volume mistura embalagens (CXS, PCT,
// UND... e KGS) e nao consolida -- os volumes aparecem separados por
// embalagem, num card proprio renderizado pela nuvem.html.
const KPIS_EXECUTIVOS = [
  { chave: "valor_total", titulo: "Valor total movimentado", formatar: k => `R$ ${formatarMilhoesExec(k.valor)} mi` },
  { chave: "peso_bruto", titulo: "Peso bruto movimentado", formatar: k => formatarPesoExecutivo(k.valor) },
  { chave: "clientes", titulo: "Quantidade de clientes", formatar: k => `${k.valor} ${k.valor === 1 ? "cliente" : "clientes"}` },
];

// Rótulo legível do tipo de estoque (V2.2) -- nasceu no linhagem.html e veio
// pra cá no V2.5, quando o cockpit ganhou o filtro por tipo: a mesma tabela de
// rótulos em duas telas é exatamente o que este arquivo existe pra evitar.
//
// NULL (traço) é dimensão que não se aplica (célula anterior ao lote, upload
// manual, medida derivada) — diferente de NAO_CLASSIFICADO, que é valor da
// fonte que não casou com nenhuma palavra-chave (ver
// backend/services/tipo_estoque.py). Confundir os dois esconderia qual dos
// dois aconteceu.
const ROTULO_TIPO_ESTOQUE = {
  CONGELADO: "Congelado",
  SECO: "Seco",
  HORTIFRUTI: "Hortifruti",
  UTENSILIOS: "Utensílios",
  NAO_CLASSIFICADO: "Não classificado",
};

// Abrevia contagens pro card de volumes: mil/milhoes com 3 algarismos
// significativos, inteiro abaixo de mil.
function formatarContagemExec(valor) {
  if (valor >= 1_000_000) return `${formatarMilhoesExec(valor)} mi`;
  if (valor >= 1_000) return `${Number((valor / 1_000).toPrecision(3)).toLocaleString("pt-BR")} mil`;
  return Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}
