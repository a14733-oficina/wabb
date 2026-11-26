// WABB – interface (HTML, CSS e JavaScript). Todos os dados vêm da API FastAPI (/api).
// Se a página for aberta noutro servidor (ex.: Live Server do VS Code), usa a API em localhost:8000.
const local = ["localhost", "127.0.0.1"].includes(location.hostname);
const API = window.API_BASE || (local && location.port !== "8000" ? "http://localhost:8000/api" : "/api");
const app = document.getElementById("app");
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const d1 = v => v == null ? "—" : Number(v).toFixed(1).replace(".", ",");
const sg = v => v == null ? "—" : (v > 0 ? "+" : "") + d1(v);
const pct = v => v == null ? "—" : (v * 100).toFixed(1).replace(".", ",") + "%";
const ini = n => n.split(" ").map(w => w[0]).join("").slice(0, 2);
const fmtDate = d => new Date(d).toLocaleDateString("pt-PT", { day: "numeric", month: "short", year: "numeric" });
const ico = (name, cls = "") => {
  const paths = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    sliders: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
    chart: '<path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 5-7"/>',
    target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    user: '<circle cx="12" cy="8" r="3"/><path d="M5 21a7 7 0 0 1 14 0"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14-5L4 8"/><path d="M4 4v4h4M4 13a8 8 0 0 0 14 5l2-2"/><path d="M20 20v-4h-4"/>'
  };
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.chart}</svg>`;
};
let token = 0;
let loggedUser = null;

function authView(error = "") {
  app.innerHTML = `<section class="auth-shell">
    <div class="auth-card panel">
      <div class="eye">Observatório NBA</div><h1 class="auth-title">WABB</h1>
      <p class="mut">Entra para explorar jogadores, estatísticas e mapas de calor.</p>
      <div class="auth-tabs"><button class="on" data-auth="login">Iniciar sessão</button><button data-auth="register">Criar conta</button></div>
      <form id="auth-form"><label>Nome de utilizador</label><input id="auth-user" autocomplete="username" minlength="3" required>
      <label>Palavra-passe</label><input id="auth-pass" type="password" autocomplete="current-password" minlength="6" required>
      <p id="auth-error" class="auth-error">${esc(error)}</p><button class="btn" type="submit">Entrar</button></form>
      <small class="mut">A conta é guardada apenas na base de dados local do WABB.</small>
    </div></section>`;
  let mode = "login";
  const form = $("#auth-form");
  $("#auth-error").style.display = error ? "block" : "none";
  $(".auth-tabs").querySelectorAll("button").forEach(button => button.onclick = () => {
    mode = button.dataset.auth;
    $(".auth-tabs").querySelectorAll("button").forEach(b => b.classList.toggle("on", b === button));
    $("#auth-pass").autocomplete = mode === "register" ? "new-password" : "current-password";
    $("#auth-form .btn").textContent = mode === "register" ? "Criar conta" : "Entrar";
  });
  form.onsubmit = async event => {
    event.preventDefault();
    const errorBox = $("#auth-error");
    errorBox.style.display = "none";
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const response = await fetch(`${API}/auth/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: $("#auth-user").value, password: $("#auth-pass").value }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Não foi possível autenticar.");
      loggedUser = data;
      route();
    } catch (error) { errorBox.textContent = error.message; errorBox.style.display = "block"; button.disabled = false; }
  };
}

async function bootstrapAuth() {
  try { const response = await fetch(`${API}/auth/me`); if (response.ok) loggedUser = await response.json(); } catch (_) { /* servidor tratado pela mensagem normal */ }
  const logout = document.getElementById("logout");
  if (loggedUser) {
    logout.hidden = false;
    logout.textContent = `Sair · ${loggedUser.username}`;
    logout.onclick = async () => { await fetch(`${API}/auth/logout`, { method: "POST" }); loggedUser = null; logout.hidden = true; authView(); };
    route();
  } else authView();
}

async function get(url) {
  const r = await fetch(API + url);
  if (!r.ok) throw new Error(`Erro ${r.status} em ${API}${url}`);
  return r.json();
}
const photo = (p, cls = "ph") =>
  `<div class="${cls}"><span>${esc(ini(p.name))}</span>${p.photo_url ? `<img src="${esc(p.photo_url)}" alt="${esc(p.name)}" loading="lazy" onerror="this.remove()">` : ""}</div>`;
const nav = on => $("#n1").className = on ? "on" : "";
const isFav = slug => localStorage.getItem(`wabb:fav:${slug}`) === "1";
const toggleFav = slug => {
  const next = !isFav(slug);
  localStorage.setItem(`wabb:fav:${slug}`, next ? "1" : "0");
  return next;
};
const compareList = () => JSON.parse(localStorage.getItem("wabb:compare") || "[]");
const toggleCompare = slug => {
  let list = compareList();
  list = list.includes(slug) ? list.filter(x => x !== slug) : [...list, slug].slice(-2);
  localStorage.setItem("wabb:compare", JSON.stringify(list));
  return list;
};
const fail = e => { app.innerHTML = `<div class="panel card"><h2>Ocorreu um erro</h2><p class="mut">${esc(e.message)}. Verifique se a API está a correr (<code>uvicorn app.main:app --reload</code> na pasta backend) e se executou <code>python -m app.seed</code>. Abra o site em http://localhost:8000.</p><a class="btn" href="#jogadores">Voltar</a></div>`; };

async function plot(id, url) {
  const target = document.getElementById(id);
  try {
    if (!window.Plotly) throw new Error("Plotly não foi carregado");
    const response = await fetch(API + url);
    if (!response.ok) throw new Error(`Erro ${response.status} ao carregar ${API + url}`);
    const fig = await response.json();
    if (!fig || !fig.data) throw new Error("A API não devolveu um gráfico válido");
    await window.Plotly.newPlot(target, fig.data, fig.layout || {}, { displayModeBar: false, responsive: true });
  } catch (error) {
    console.error("Erro no gráfico:", id, error);
    target.innerHTML = `<div class="mut" style="padding:20px">Não foi possível carregar este gráfico: ${esc(error.message)}</div>`;
  }
}

/* ---------- Lista de jogadores (paginada) ---------- */
async function list() {
  nav(true);
  const f = await get("/filters");
  const opts = a => a.map(v => `<option>${esc(v)}</option>`).join("");
  app.innerHTML = `
  <div class="row"><div><div class="eye">O jogo, jogador a jogador</div><h1 class="big">Explorar jogadores</h1>
  <div class="mut">Encontre um jogador. Conheça o percurso. Leia o jogo para lá do resultado.</div></div><span class="badge">Época mais recente</span></div>
  <div class="layout"><aside class="panel filters"><div class="section-title">${ico("sliders")}<b>Filtros</b></div>
    <label>Equipa</label><select id="ft"><option value="">Todas as equipas</option>${opts(f.teams)}</select>
    <label>Posição</label><select id="fp"><option value="">Todas as posições</option>${opts(f.positions)}</select>
    <label>Nacionalidade</label><select id="fn"><option value="">Todos os países</option>${opts(f.nationalities)}</select>
    <label>Jogos mínimos na época</label><select id="fg"><option value="0">Todos</option><option value="5">5 ou mais</option><option value="10">10 ou mais</option><option value="20">20 ou mais</option><option value="40">40 ou mais</option></select>
    <hr style="border:0;border-top:1px solid var(--line);margin:18px 0"><button class="link icon-btn" id="rs">${ico("refresh")} Repor filtros</button></aside>
  <div><div class="panel search"><span class="search-icon">${ico("search")}</span><input id="q" type="search" placeholder="Pesquisar por nome de jogador..." aria-label="Pesquisar jogador"></div>
  <div class="row" style="margin:16px 0 10px"><b id="cnt"></b>
    <span class="mut">Ordenar por <select id="so" class="sel"><option value="pts">Pontos</option><option value="reb">Ressaltos</option><option value="ast">Assistências</option><option value="stl">Roubos</option><option value="blk">Cortes</option><option value="plus_minus">+/-</option><option value="age">Idade</option><option value="name">Nome</option></select></span></div>
  <div class="panel scroll"><table><thead><tr><th>Jogador</th><th class="l">Equipa</th><th class="l">Posição</th><th>Idade</th><th>J</th><th>PTS</th><th>RES</th><th>AST</th><th>ROU</th><th>COR</th><th>PB</th><th>+/-</th><th>Ação</th></tr></thead><tbody id="tb"></tbody></table></div>
  <div class="row" style="margin-top:12px;align-items:center"><span class="sm" id="rng" style="margin:0"></span><span><button class="btn nav-btn" id="pv" aria-label="Página anterior">←</button> <button class="btn nav-btn" id="nx" aria-label="Página seguinte">→</button></span></div>
  <p class="sm">J jogos · PTS pontos · RES ressaltos · AST assistências · ROU roubos de bola · COR cortes · PB perdas de bola · +/- saldo de pontos. Médias por jogo.</p></div></div>`;
  let timer, page = 1, total = 0;
  const LIMIT = 25;
  const draw = async () => {
    const qs = new URLSearchParams({ q: $("#q").value, team: $("#ft").value, position: $("#fp").value, nationality: $("#fn").value,
      min_games: $("#fg").value, sort: $("#so").value, page, limit: LIMIT });
    const r = await get("/players?" + qs);
    total = r.total;
    $("#cnt").textContent = total + (total === 1 ? " jogador" : " jogadores");
    $("#rng").textContent = total ? `A mostrar ${(page - 1) * LIMIT + 1}–${Math.min(page * LIMIT, total)} de ${total}` : "";
    $("#pv").disabled = page <= 1; $("#nx").disabled = page * LIMIT >= total;
    $("#tb").innerHTML = r.items.length ? r.items.map((p, i) => `<tr class="rowlink ${i === 0 && page === 1 ? "hl" : ""}" data-slug="${esc(p.slug)}">
      <td><a class="pl" href="#${esc(p.slug)}">${photo(p)}<span><b>${esc(p.name)}</b><small class="num">${p.number != null ? "#" + p.number + " · " : ""}NBA</small></span></a><button class="fav ${isFav(p.slug) ? "on" : ""}" data-slug="${esc(p.slug)}" aria-label="${isFav(p.slug) ? "Remover dos favoritos" : "Adicionar aos favoritos"}">${isFav(p.slug) ? "★" : "☆"}</button></td>
      <td class="l">${esc(p.team)}<small class="num">${esc(p.team_abbr)}</small></td><td class="l mut">${esc(p.position)}</td>
      <td class="num mut">${p.age ?? "—"}</td><td class="num mut">${p.games ?? "—"}</td><td class="num"><b class="${i === 0 && page === 1 ? "acc" : ""}">${d1(p.pts)}</b></td>
      <td class="num mut">${d1(p.reb)}</td><td class="num mut">${d1(p.ast)}</td><td class="num mut">${d1(p.stl)}</td><td class="num mut">${d1(p.blk)}</td><td class="num mut">${d1(p.tov)}</td><td class="num mut">${sg(p.plus_minus)}</td><td><button class="compare-pick ${compareList().includes(p.slug) ? "on" : ""}" data-slug="${esc(p.slug)}">${compareList().includes(p.slug) ? "Selecionado" : "Comparar"}</button></td></tr>`).join("")
      : `<tr><td colspan="13" class="l mut">Nenhum jogador encontrado. Altere a pesquisa ou os filtros. Se a lista estiver vazia, execute <code>python -m app.ingest_league</code>.</td></tr>`;
  };
  const reset = () => { page = 1; draw(); };
  ["ft", "fp", "fn", "fg", "so"].forEach(i => $("#" + i).onchange = reset);
  $("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(reset, 250); };
  $("#rs").onclick = () => { $("#q").value = ""; ["ft", "fp", "fn"].forEach(i => $("#" + i).value = ""); $("#fg").value = "0"; reset(); };
  $("#pv").onclick = () => { page--; draw(); };
  $("#nx").onclick = () => { page++; draw(); };
  $("#tb").addEventListener("click", e => {
    if (e.target.closest("button") || e.target.closest("a")) return;
    const row = e.target.closest("tr[data-slug]");
    if (row) location.hash = row.dataset.slug;
  });
  $("#tb").addEventListener("click", e => {
    const button = e.target.closest(".fav");
    if (!button) return;
    e.preventDefault();
    e.stopPropagation();
    const active = toggleFav(button.dataset.slug);
    button.textContent = active ? "★" : "☆";
    button.classList.toggle("on", active);
    button.setAttribute("aria-label", active ? "Remover dos favoritos" : "Adicionar aos favoritos");
  });
  $("#tb").addEventListener("click", e => {
    const button = e.target.closest(".compare-pick");
    if (!button) return;
    e.preventDefault();
    e.stopPropagation();
    const list = toggleCompare(button.dataset.slug);
    document.querySelectorAll(`.compare-pick[data-slug="${button.dataset.slug}"]`).forEach(x => { x.classList.toggle("on", list.includes(button.dataset.slug)); x.textContent = list.includes(button.dataset.slug) ? "Selecionado" : "Comparar"; });
    if (list.length === 2) {
      window.open("/comparacao.html?players=" + encodeURIComponent(list.join("|")), "_blank");
    }
  });
  draw();
}

const tabs = (p, shots) => `<div class="tabs"><a class="${shots ? "" : "on"}" href="#${esc(p.slug)}">${ico("user")} Perfil</a><a class="${shots ? "on" : ""}" href="#${esc(p.slug)}-lancamentos">${ico("target")} Análise de lançamentos</a></div>`;

/* ---------- Perfil ---------- */
async function profile(slug) {
  nav(true);
  const p = await get("/players/" + slug), S = p.seasons;
  app.innerHTML = `<div class="crumb"><a href="#jogadores">← Jogadores</a> / <span style="color:var(--ink)">${esc(p.name)}</span></div>
  <div class="panel dossier"><div>${photo(p, "ph big")}<div class="row sm" style="text-transform:uppercase;letter-spacing:1.5px"><span>${esc(p.team)}</span><b class="acc num">${p.number != null ? "#" + p.number : ""}</b></div></div>
  <div><div class="eye">Dossiê do jogador / NBA</div><h1 style="font-size:clamp(44px,8vw,84px);font-weight:700;margin:14px 0 6px">${esc(p.name)}</h1><div class="mut">${esc(p.full_name)}</div>
  <div class="facts"><div><small>Nascimento</small><b>${p.birth_date ? fmtDate(p.birth_date) : "—"}</b></div><div><small>Idade</small><b>${p.age != null ? p.age + " anos" : "—"}</b></div>
  <div><small>Altura</small><b>${p.height_cm ? (p.height_cm / 100).toFixed(2).replace(".", ",") + " m" : "—"}</b></div><div><small>Peso</small><b>${p.weight_kg ? p.weight_kg + " kg" : "—"}</b></div>
  <div><small>Nacionalidade</small><b>${esc(p.nationality)}</b></div><div><small>Posição</small><b>${esc(p.position)}</b></div>
  <div><small>Número da camisola</small><b>${p.number != null ? "#" + p.number : "—"}</b></div><div><small>Equipa atual</small><b>${esc(p.team)}</b></div>
  <div><small>Ano do draft</small><b>${p.draft?.year || "—"}</b></div><div><small>Ronda do draft</small><b>${p.draft?.round ? p.draft.round + "ª ronda" : "—"}</b></div><div><small>Escolha do draft</small><b>${p.draft?.number ? "#" + p.draft.number : "Não escolhido / sem dados"}</b></div></div></div></div>
  ${tabs(p, false)}
  <div class="row"><div><h2 style="font-size:28px;font-weight:700">A época em números</h2><div class="mut" style="margin-top:6px">Fase regular · médias por jogo</div></div>
  <div><select id="se" class="sel">${S.map(s => `<option>${s.season}</option>`).join("")}</select> <a class="btn" href="#${esc(p.slug)}-lancamentos">Analisar lançamentos ↗</a></div></div>
  <div class="kpis" id="kp"></div>
  <div class="two"><div class="panel card"><h2>${ico("chart")} Percurso na NBA</h2><ul class="tl">${p.career.map(c => `<li><small class="num">${esc(c.period)}</small><b>${esc(c.team)}</b><small>${esc(c.note)}</small></li>`).join("")}</ul></div>
  <div class="panel card"><div class="row"><h2>Estatísticas por época</h2><span class="badge">Fase regular</span></div><div class="scroll"><table><thead><tr><th>Época</th><th>Eq.</th><th>J</th><th>MIN</th><th>PTS</th><th>RES</th><th>AST</th><th>ROU</th><th>COR</th><th>PB</th><th>LC%</th><th>3P%</th><th>+/-</th></tr></thead><tbody id="st"></tbody></table></div>
  <p class="sm">— sem dados disponíveis para essa época.</p></div></div>`;
  let si = 0;
  const up = () => {
    if (!S.length) { $("#kp").innerHTML = `<p class="mut">Sem estatísticas disponíveis para este jogador.</p>`; return; }
    const r = S[si], k = (l, v, sub, acc) => `<div class="panel kpi"><small>${l}</small><div class="v ${acc ? "acc" : ""}">${v}</div><small style="text-transform:none;letter-spacing:0">${sub}</small></div>`;
    $("#kp").innerHTML =
      k("Pontos", d1(r.pts), "por jogo", 1) +
      k("Ressaltos", d1(r.reb), "por jogo") +
      k("Assistências", d1(r.ast), "por jogo") +
      k("Roubos de bola", d1(r.stl), "por jogo") +
      k("Cortes", d1(r.blk), "por jogo") +
      k("Perdas de bola", d1(r.tov), "por jogo") +
      k("Faltas", d1(r.pf), "por jogo") +
      k("Lançamentos de campo", d1(r.fg_pct) + "%", "LC%", 1) +
      k("Lançamentos de 3", d1(r.tp_pct) + "%", "3P%") +
      k("Jogos", r.games, "na fase regular") +
      k("Minutos", d1(r.minutes), "por jogo") +
      k("Saldo de pontos (+/-)", sg(r.plus_minus), "por jogo", 1);
    $("#st").innerHTML = S.map((s, i) => `<tr class="${i === si ? "hl" : ""}"><td class="num ${i === si ? "acc" : ""}">${s.season}</td><td class="num">${esc(s.team)}</td><td class="num">${s.games}</td><td class="num">${d1(s.minutes)}</td><td class="num ${i === si ? "acc" : ""}">${d1(s.pts)}</td><td class="num">${d1(s.reb)}</td><td class="num">${d1(s.ast)}</td><td class="num">${d1(s.stl)}</td><td class="num">${d1(s.blk)}</td><td class="num">${d1(s.tov)}</td><td class="num">${d1(s.fg_pct)}</td><td class="num">${d1(s.tp_pct)}</td><td class="num">${sg(s.plus_minus)}</td></tr>`).join("");
  };
  $("#se").onchange = e => { si = e.target.selectedIndex; up(); };
  up();
}

/* ---------- Análise de lançamentos ---------- */
async function shots(slug) {
  nav(true);
  const p = await get("/players/" + slug);
  app.innerHTML = `<div class="crumb"><a href="#jogadores">← Jogadores</a> / <a href="#${esc(slug)}">${esc(p.name)}</a> / <span style="color:var(--ink)">Análise de lançamentos</span></div>
  <div class="row"><div><div class="eye">O jogo sob outra perspetiva</div><h1 class="big">Análise de lançamentos</h1><div class="mut">A distribuição e a eficácia dos lançamentos, zona a zona.</div></div>
  <div class="panel pl" style="padding:14px 18px">${photo(p)}<span><b>${esc(p.name)}</b><small>${esc(p.team)} · ${esc(p.position)}${p.number != null ? " · #" + p.number : ""}</small></span></div></div>
  ${tabs(p, true)}
  <div class="row" style="align-items:center"><div><small class="mut">Época</small><br><select id="se" class="sel"></select></div><span class="badge" id="sim"></span></div>
  <div class="kpis" id="kp"></div>
  <div class="two eq"><div class="panel card"><h2>${ico("target")} Volume de lançamentos</h2><div class="mut" style="margin:-8px 0 8px">Tentativas · onde lança mais</div><div id="h1"></div></div>
  <div class="panel card"><h2>${ico("target")} Eficácia por zona</h2><div class="mut" style="margin:-8px 0 8px">Percentagem de acerto · células com 3+ lançamentos</div><div id="h2"></div></div></div>
  <div class="two eq" style="margin-top:20px;grid-template-columns:1.4fr 1fr"><div class="panel card"><div class="row"><div><h2>${ico("chart")} Evolução por época</h2><div class="mut">Média por jogo</div></div>
  <div class="seg" id="sg"></div></div><div id="tr"></div></div>
  <div class="panel card"><h2>${ico("target")} Zona a zona</h2><table><thead><tr><th>Zona</th><th>Tent.</th><th>Conv.</th><th>LC%</th></tr></thead><tbody id="zt"></tbody></table></div></div>
  <div class="panel card" style="margin-top:20px"><h2>${ico("chart")} Distância dos lançamentos</h2><div class="mut" style="margin:-8px 0 8px">Gráfico gerado com Seaborn</div><img id="dist" class="dist" style="max-width:640px" alt="Distribuição da distância dos lançamentos"></div>
  <div class="note">ⓘ Como ler · As cores representam a densidade e a eficácia dos lançamentos por zona do campo. Os mapas excluem lances livres.</div>`;
  let season = null, stat = "pts";
  const STATS = { pts: "PTS", reb: "RES", ast: "AST", stl: "ROU", blk: "COR", tov: "PB", plus_minus: "+/-", fg_pct: "LC%", tp_pct: "3P%" };
  const load = async () => {
    const q = season ? "?season=" + encodeURIComponent(season) : "";
    const s = await get(`/players/${slug}/shots/summary${q}`);
    season = s.season;
    $("#se").innerHTML = s.seasons.map(x => `<option ${x === season ? "selected" : ""}>${x}</option>`).join("");
    $("#sim").textContent = !s.available ? "Sem lançamentos" : s.simulated ? "Lançamentos simulados" : "Dados reais da NBA";
    const k = (l, v, sub, acc) => `<div class="panel kpi"><small>${l}</small><div class="v num ${acc ? "acc" : ""}" style="font-size:26px">${v}</div><small style="text-transform:none;letter-spacing:0">${sub}</small></div>`;
    $("#kp").innerHTML = k("Lançamentos tentados", s.attempts, "na época selecionada") + k("Lançamentos convertidos", s.made, "na época selecionada") +
      k("Eficácia global · LC%", pct(s.fg_pct), `${s.made} / ${s.attempts}`, 1) + k("Eficácia de 3 pontos · 3P%", pct(s.tp_pct), `${s.tp_made} / ${s.tp_attempts}`);
    $("#zt").innerHTML = s.zones.map(z => `<tr><td class="l">${esc(z.zone)}</td><td class="num">${z.att}</td><td class="num">${z.made}</td><td class="num ${z.zone === "Área pintada" ? "acc" : ""}">${pct(z.pct)}</td></tr>`).join("") +
      `<tr><td class="l"><b>Total</b></td><td class="num"><b>${s.attempts}</b></td><td class="num"><b>${s.made}</b></td><td class="num"><b>${pct(s.fg_pct)}</b></td></tr>`;
    if (!s.available) {
      $("#h1").innerHTML = $("#h2").innerHTML = `<p class="mut">Sem dados de lançamentos para esta época. É necessária ligação à NBA (stats.nba.com).</p>`;
      $("#dist").style.display = "none";
      return;
    }
    $("#dist").style.display = "";
    $("#dist").src = `${API}/players/${slug}/shots/distance.png${q}`;
    plot("h1", `/players/${slug}/shots/heatmap${q}${q ? "&" : "?"}mode=volume`);
    plot("h2", `/players/${slug}/shots/heatmap${q}${q ? "&" : "?"}mode=efficiency`);
  };
  const trend = () => {
    $("#sg").innerHTML = Object.entries(STATS).map(([k, l]) => `<button class="${k === stat ? "on" : ""}" data-k="${k}">${l}</button>`).join("");
    $("#sg").querySelectorAll("button").forEach(b => b.onclick = () => { stat = b.dataset.k; trend(); });
    plot("tr", `/players/${slug}/trend?stat=${stat}`);
  };
  $("#se").onchange = e => { season = e.target.value; load(); };
  await load(); trend();
}

/* ---------- Rotas: #jogadores | #slug | #slug-lancamentos ---------- */
async function route() {
  if (!loggedUser) { authView(); return; }
  const my = ++token;
  const h = location.hash.slice(1) || "jogadores";
  const m = h.match(/^(.*?)(-lancamentos)?$/);
  try {
    if (h === "jogadores") await list();
    else if (m[2]) await shots(m[1]);
    else await profile(h);
  } catch (e) { if (my === token) fail(e); }
  window.scrollTo(0, 0);
}
addEventListener("hashchange", route);
bootstrapAuth();
