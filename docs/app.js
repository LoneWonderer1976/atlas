/* Atlas -- the page. Reads data.json (written by atlas/stats.py) and draws it. No state of its own
   beyond which tab is open. */
(function () {
  const $ = (id) => document.getElementById(id);
  const MI = 1609.344;
  const km = (m) => ((m || 0) / 1000).toFixed(1) + " km";
  const mi = (m) => ((m || 0) / MI).toFixed(1) + " mi";
  const dist = (m, sport) => (sport === "swim" ? Math.round(m || 0) + " m" : mi(m));
  const dur = (s) => { s = Math.round(s || 0); return s >= 3600 ? `${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}m` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`; };
  const hms = (s) => { s = Math.round(s || 0); return s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const ICON = { run: "🏃", walk: "🚶", cycle: "🚴", swim: "🏊", kayak: "🛶", other: "❓", all: "🌍" };
  const SPORTS = ["run", "walk", "cycle", "swim", "kayak"];
  const DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const when = (s) => { const d = new Date(s.replace(" ", "T")); return `${DAY[(d.getDay() + 6) % 7]} ${d.getDate()} ${d.toLocaleString("en-GB", { month: "short" })}, ${s.slice(11, 16)}`; };
  const dmy = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(2, 4)}`;
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const css = () => getComputedStyle(document.documentElement);
  const col = (name) => css().getPropertyValue("--" + name).trim();
  const minmi = (spk) => { const s = spk * MI / 1000; return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`; };

  let DATA = null, charts = {}, map = null, layer = null, bigmap = null, drawn = new Set();
  const rendered = new Set();

  async function load() {
    const r = await fetch("data.json?" + Date.now(), { cache: "no-store" });
    DATA = await r.json();
    rendered.clear();
    for (const c of Object.values(charts)) c.destroy();
    charts = {};
    $("updated").textContent = "updated " + new Date(DATA.built_at).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
    show(document.querySelector(".tabs button.on").dataset.tab);
  }

  function chart(id, cfg) {
    if (charts[id]) charts[id].destroy();
    Chart.defaults.color = col("muted");
    Chart.defaults.borderColor = col("grid");
    charts[id] = new Chart($(id), cfg);
    return charts[id];
  }

  /* ---------------- tabs ---------------- */
  function show(tab) {
    document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.id !== "tab-" + tab; });
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    if (!rendered.has(tab)) { rendered.add(tab); RENDER[tab](); }
    if (tab === "map" && bigmap) setTimeout(() => bigmap.invalidateSize(), 50);
    try { localStorage.setItem("atlas.tab", tab); } catch (e) { /* private mode */ }
  }
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));

  /* ---------------- overview ---------------- */
  function kpi(v, label, delta) {
    const d = delta == null ? "" : `<span class="delta ${delta >= 0 ? "up" : "down"}">${delta >= 0 ? "▲" : "▼"} ${esc(Math.abs(delta).toFixed(delta % 1 ? 1 : 0))}</span>`;
    return `<div class="kpi"><b>${v}${d}</b><span>${label}</span></div>`;
  }
  function overview() {
    const t = DATA.totals, tw = DATA.this_week || { n: 0, distance_m: 0, duration_s: 0, ascent_m: 0 }, lw = DATA.last_week || { n: 0, distance_m: 0, duration_s: 0, ascent_m: 0 };
    $("kpis").innerHTML = [
      kpi(km(t.distance_m), "all-time distance"), kpi(hms(t.duration_s), "all-time moving"),
      kpi(t.ascent_m.toLocaleString() + " m", "all-time climb"), kpi(`${DATA.streaks.current} wk`, `streak · longest ${DATA.streaks.longest}`),
    ].join("");
    $("week-label").textContent = tw.label ? "· " + tw.label : "";
    $("compare").innerHTML = [
      [tw.n, lw.n, "sessions", (v) => v], [tw.distance_m, lw.distance_m, "km", (v) => (v / 1000).toFixed(1)],
      [tw.duration_s, lw.duration_s, "time", (v) => hms(v)], [tw.ascent_m, lw.ascent_m, "climb m", (v) => Math.round(v)],
    ].map(([a, b, label, f]) => `<div><b>${f(a)}</b><small>${label}<br>last wk ${f(b)}</small></div>`).join("");
    const weeks = DATA.weeks.slice(-12);
    chart("ov-weeks", stackedWeeks(weeks));
    $("ov-sports").querySelector("tbody").innerHTML = SPORTS.filter((s) => t.sports[s]).map((s) => {
      const v = t.sports[s];
      return `<tr><td>${ICON[s]} ${s}</td><td class="num">${v.n}</td><td class="num">${dist(v.distance_m, s)}</td><td class="num">${hms(v.duration_s)}</td><td class="num">${v.ascent_m} m</td></tr>`;
    }).join("") || `<tr><td colspan="5" class="muted">nothing yet</td></tr>`;
    $("ov-latest").innerHTML = DATA.activities.slice(0, 5).map(cardHTML).join("") || `<p class="muted">No activities yet.</p>`;
    bindCards($("ov-latest"));
  }
  function stackedWeeks(weeks) {
    return {
      type: "bar",
      data: { labels: weeks.map((w) => w.key.slice(8, 10) + "/" + w.key.slice(5, 7)),
        datasets: SPORTS.map((s) => ({ label: s, data: weeks.map((w) => ((w.sports[s] || {}).distance_m || 0) / 1000), backgroundColor: col(s), stack: "d", borderRadius: 3 })) },
      options: { plugins: { legend: { display: true, position: "bottom", labels: { boxWidth: 10 } }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)} km` } } },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } }, animation: false },
    };
  }

  /* ---------------- cards ---------------- */
  function cardHTML(a, rankno) {
    const flagged = a.flags.length && a.sport !== "other" && !a.excluded;
    return `<div class="card ${a.excluded ? "struck" : ""}" data-id="${a.id}">
      ${rankno ? `<div class="rankno">${rankno}</div>` : `<div class="icon ${a.sport}">${ICON[a.sport] || ICON.other}</div>`}
      <div><div class="name">${rankno ? ICON[a.sport] + " " : ""}${esc(a.name || a.sport)}${flagged ? " ⚠" : ""}</div>
        <div class="meta">${when(a.start_local)} · ${dist(a.distance_m, a.sport)}${a.ascent_m ? " · " + Math.round(a.ascent_m) + " m ↑" : ""} · ${dur(a.duration_s)}${a.pace ? " · " + a.pace : ""}</div></div>
      <div class="right"><b>${a.score.toFixed(1)}</b><small>${a.rank ? "#" + a.rank : "—"}</small></div>
    </div>`;
  }
  function bindCards(root) { root.querySelectorAll(".card").forEach((el) => el.addEventListener("click", () => openSheet(+el.dataset.id))); }

  /* ---------------- records ---------------- */
  let recSport = "all";
  function chips(id, current, onPick, extra) {
    const opts = ["all", ...SPORTS.filter((s) => DATA.totals.sports[s]), ...(extra || [])];
    $(id).innerHTML = opts.map((s) => `<button class="chip ${s === current ? "on" : ""}" data-s="${s}">${ICON[s] || ""} ${s}</button>`).join("");
    $(id).querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => onPick(b.dataset.s)));
  }
  function recordsTab() {
    chips("rec-chips", recSport, (s) => { recSport = s; recordsTab(); });
    const recs = DATA.records.filter((r) => recSport === "all" || r.sport === recSport || r.sport === "all");
    const groups = {};
    for (const r of recs) (groups[r.sport] = groups[r.sport] || []).push(r);
    $("records").innerHTML = Object.entries(groups).map(([s, rs]) => `<div class="rec-group"><h3>${ICON[s]} ${s === "all" ? "Overall" : s}</h3><div class="recs">${
      rs.map((r, i) => `<div class="rec ${s}" data-key="${s}|${esc(r.label)}" data-kind="${r.kind}" data-id="${r.activity_id || ""}"><div class="r-label">${esc(r.label)}</div><div class="r-val">${esc(r.display)}</div><div class="r-sub">${esc(r.sub || "")} · ${dmy(r.date)}</div></div>`).join("")}</div></div>`).join("")
      || `<p class="muted">No records yet — they appear as activities land.</p>`;
    $("records").querySelectorAll(".rec").forEach((el) => el.addEventListener("click", () => {
      const series = DATA.progression[el.dataset.key];
      if (el.dataset.kind === "effort" && series) { document.querySelectorAll(".rec.on").forEach((x) => x.classList.remove("on")); el.classList.add("on"); progression(el.dataset.key, series); }
      else if (el.dataset.id) openSheet(+el.dataset.id);
    }));
    $("prog-wrap").hidden = true;
  }
  function progression(key, series) {
    const [sport, label] = key.split("|");
    $("prog-wrap").hidden = false;
    $("prog-title").textContent = `${ICON[sport]} ${label} — ${series.length} attempt${series.length === 1 ? "" : "s"}`;
    chart("prog-chart", {
      type: "line",
      data: { labels: series.map((p) => dmy(p.date)),
        datasets: [
          { label: "attempt", data: series.map((p) => p.seconds), showLine: false, pointRadius: 5, pointBackgroundColor: series.map((p) => p.improved ? col("accent") : col(sport)), ids: series.map((p) => p.activity_id) },
          { label: "record", data: series.map((p) => p.best), stepped: true, borderColor: col("accent"), borderWidth: 2, pointRadius: 0, fill: false },
        ] },
      options: { animation: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${hms(c.parsed.y)}` } } },
        scales: { y: { ticks: { callback: (v) => hms(v) }, reverse: false }, x: { grid: { display: false } } },
        onClick: (e, els) => { if (els.length && els[0].datasetIndex === 0) openSheet(series[els[0].index].activity_id); } },
    });
    $("prog-wrap").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ---------------- rankings ---------------- */
  let rankSport = "all";
  function rankings() {
    chips("rank-chips", rankSport, (s) => { rankSport = s; rankings(); });
    const rows = DATA.activities.filter((a) => a.rank && (rankSport === "all" || a.sport === rankSport))
      .sort((a, b) => a.score - b.score < 0 ? 1 : -1).slice(0, 50);
    $("rankings").innerHTML = rows.map((a, i) => cardHTML(a, rankSport === "all" ? a.rank : i + 1)).join("") || `<p class="muted">Nothing ranked yet.</p>`;
    bindCards($("rankings"));
  }

  /* ---------------- progress ---------------- */
  function progress() {
    chart("pr-weekly", stackedWeeks(DATA.weeks.slice(-26)));
    const months = DATA.months;
    chart("pr-monthly", {
      type: "bar",
      data: { labels: months.map((m) => m.label), datasets: SPORTS.map((s) => ({ label: s, data: months.map((m) => ((m.sports[s] || {}).distance_m || 0) / 1000), backgroundColor: col(s), stack: "d", borderRadius: 3 })) },
      options: { animation: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)} km` } } }, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } } },
    });
    chart("pr-climb", {
      type: "bar",
      data: { labels: months.map((m) => m.label), datasets: [{ data: months.map((m) => m.ascent_m), backgroundColor: col("accent"), borderRadius: 4 }] },
      options: { animation: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true } } },
    });
    const runs = DATA.trends.run;
    chart("pr-runhr", {
      type: "scatter",
      data: { datasets: [
        { label: "pace", data: runs.map((r) => ({ x: r.date, y: r.secs_per_km * MI / 1000 / 60, id: r.id })), yAxisID: "y", backgroundColor: col("run"), pointRadius: runs.map((r) => 3 + Math.min(6, r.distance_m / 2500)) },
        { label: "avg HR", data: runs.filter((r) => r.hr).map((r) => ({ x: r.date, y: r.hr, id: r.id })), yAxisID: "y2", backgroundColor: col("muted"), pointStyle: "triangle", pointRadius: 4 },
      ] },
      options: { animation: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } }, tooltip: { callbacks: { label: (c) => c.dataset.label === "pace" ? `${minmi(c.parsed.y * 60 * 1000 / MI)} /mi` : `${c.parsed.y} bpm` } } },
        scales: { x: { type: "category", labels: [...new Set(runs.map((r) => r.date))].sort(), ticks: { callback: (v, i, t) => { const l = [...new Set(runs.map((r) => r.date))].sort()[i]; return l ? dmy(l) : ""; }, maxTicksLimit: 8 }, grid: { display: false } },
          y: { position: "left", reverse: true, ticks: { callback: (v) => `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")}` }, title: { display: true, text: "min/mile" } },
          y2: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "bpm" } } },
        onClick: (e, els) => { if (els.length) { const d = charts["pr-runhr"].data.datasets[els[0].datasetIndex].data[els[0].index]; openSheet(d.id); } } },
    });
    const rides = DATA.trends.cycle;
    chart("pr-ridehr", {
      type: "scatter",
      data: { datasets: [
        { label: "km/h", data: rides.map((r) => ({ x: r.date, y: r.kmh, id: r.id })), yAxisID: "y", backgroundColor: col("cycle"), pointRadius: rides.map((r) => 3 + Math.min(6, r.distance_m / 8000)) },
        { label: "avg HR", data: rides.filter((r) => r.hr).map((r) => ({ x: r.date, y: r.hr, id: r.id })), yAxisID: "y2", backgroundColor: col("muted"), pointStyle: "triangle", pointRadius: 4 },
      ] },
      options: { animation: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } },
        scales: { x: { type: "category", labels: [...new Set(rides.map((r) => r.date))].sort(), ticks: { callback: (v, i) => { const l = [...new Set(rides.map((r) => r.date))].sort()[i]; return l ? dmy(l) : ""; }, maxTicksLimit: 8 }, grid: { display: false } },
          y: { position: "left", title: { display: true, text: "km/h" } }, y2: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "bpm" } } },
        onClick: (e, els) => { if (els.length) { const d = charts["pr-ridehr"].data.datasets[els[0].datasetIndex].data[els[0].index]; openSheet(d.id); } } },
    });
    const year = DATA.today.slice(0, 4);
    const acts = DATA.activities.filter((a) => !a.excluded && a.date.startsWith(year)).sort((a, b) => a.date < b.date ? -1 : 1);
    const labels = [...new Set(acts.map((a) => a.date))];
    const cum = {};
    for (const s of SPORTS) { let t = 0; cum[s] = labels.map((d) => { t += acts.filter((a) => a.date === d && a.sport === s).reduce((x, a) => x + a.distance_m, 0) / 1000; return t; }); }
    chart("pr-cum", {
      type: "line",
      data: { labels: labels.map(dmy), datasets: SPORTS.filter((s) => cum[s].length && cum[s][cum[s].length - 1] > 0).map((s) => ({ label: s, data: cum[s], borderColor: col(s), backgroundColor: col(s), pointRadius: 0, borderWidth: 2, tension: .2 })) },
      options: { animation: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } }, scales: { x: { ticks: { maxTicksLimit: 8 }, grid: { display: false } }, y: { beginAtZero: true } } },
    });
    const st = DATA.streaks;
    $("pr-streaks").innerHTML = [kpi(st.current + " wk", "current streak"), kpi(st.longest + " wk", "longest streak"),
      kpi(`${st.weeks_active}/${st.weeks_total}`, "weeks with a session"), kpi(`${Math.round(100 * st.weeks_active / Math.max(1, st.weeks_total))}%`, "consistency")].join("");
  }

  /* ---------------- log ---------------- */
  let logSport = "all", sortKey = "start_local", sortDir = -1;
  function logTab() {
    chips("log-chips", logSport, (s) => { logSport = s; logTab(); }, ["other"]);
    const rows = DATA.activities.filter((a) => logSport === "all" || a.sport === logSport)
      .sort((a, b) => { const x = a[sortKey], y = b[sortKey]; if (x == null) return 1; if (y == null) return -1; return (x < y ? -1 : x > y ? 1 : 0) * sortDir; });
    $("log").querySelectorAll("th").forEach((th) => { th.classList.toggle("sorted", th.dataset.k === sortKey); th.onclick = () => { if (sortKey === th.dataset.k) sortDir = -sortDir; else { sortKey = th.dataset.k; sortDir = th.dataset.k === "start_local" || th.classList.contains("num") ? -1 : 1; if (th.dataset.k === "secs_per_km" || th.dataset.k === "rank") sortDir = 1; } logTab(); }; });
    $("log").querySelector("tbody").innerHTML = rows.map((a) => `<tr data-id="${a.id}" class="${a.excluded ? "struck" : (a.flags.length && a.sport !== "other" ? "flagged" : "")}">
      <td>${dmy(a.date)}</td><td>${ICON[a.sport]}</td><td>${esc(a.name)}</td><td class="num">${dist(a.distance_m, a.sport)}</td><td class="num">${hms(a.duration_s)}</td>
      <td class="num">${a.pace || "—"}</td><td class="num">${Math.round(a.ascent_m)}</td><td class="num">${a.avg_hr ? Math.round(a.avg_hr) : "—"}</td><td class="num">${a.score.toFixed(1)}</td><td class="num">${a.rank || "—"}</td></tr>`).join("");
    $("log").querySelectorAll("tbody tr").forEach((tr) => tr.addEventListener("click", () => openSheet(+tr.dataset.id)));
    $("log-count").textContent = `${rows.length} activities.`;
  }

  /* ---------------- map ---------------- */
  async function mapTab() {
    if (!window.L) return;
    bigmap = L.map($("bigmap"));
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(bigmap);
    const acts = DATA.activities.filter((a) => a.has_track && !a.excluded);
    const group = L.featureGroup().addTo(bigmap);
    let n = 0;
    for (const a of acts) {
      try {
        const t = await (await fetch(`tracks/${a.id}.json`)).json();
        const line = L.polyline(t.points, { color: col(a.sport), weight: 3, opacity: .7 }).addTo(group);
        line.on("click", () => openSheet(a.id));
        n++;
        if (n === 1 || n % 10 === 0) bigmap.fitBounds(group.getBounds(), { padding: [16, 16] });
      } catch (e) { /* a missing track is a missing line */ }
    }
    if (n) bigmap.fitBounds(group.getBounds(), { padding: [16, 16] }); else bigmap.setView([50.9, -1.3], 9);
    $("map-note").textContent = `${n} tracks, coloured by sport. Tap a line for the activity.`;
  }

  /* ---------------- the sheet ---------------- */
  async function openSheet(id) {
    const a = DATA.activities.find((x) => x.id === id);
    if (!a) return;
    $("sheet-title").textContent = a.name || a.sport;
    $("sheet-sub").textContent = `${ICON[a.sport]} ${a.sport} · ${when(a.start_local)}${a.rank ? ` · #${a.rank} overall, #${a.sport_rank} ${a.sport}` : ""}`;
    $("sheet-stats").innerHTML = [
      [dist(a.distance_m, a.sport), "distance"], [hms(a.duration_s), "time"], [a.pace || "—", "pace"],
      [Math.round(a.ascent_m) + " m", "climb"], [a.avg_hr ? Math.round(a.avg_hr) + " bpm" : "—", "avg HR"], [a.max_hr ? Math.round(a.max_hr) + " bpm" : "—", "max HR"],
      [a.score.toFixed(1), "score"], [a.avg_cadence ? Math.round(a.avg_cadence) : "—", "cadence"], [a.calories ? Math.round(a.calories) : "—", "kcal"],
    ].map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join("");
    const recs = Object.fromEntries(DATA.records.filter((r) => r.kind === "effort" && r.sport === a.sport).map((r) => [r.label, r.activity_id]));
    const order = (DATA.targets[a.sport] || []).map((t) => t[1]);
    const eff = Object.entries(a.efforts).sort((x, y) => order.indexOf(x[0]) - order.indexOf(y[0]));
    $("sheet-efforts").innerHTML = eff.length ? `<div class="efforts"><table class="table"><thead><tr><th>best effort</th><th class="num">time</th><th class="num">pace</th></tr></thead><tbody>${
      eff.map(([label, secs]) => { const m = ((DATA.targets[a.sport] || []).find((t) => t[1] === label) || [0])[0];
        const spk = m ? secs / (m / 1000) : 0;
        const pace = !m ? "" : a.sport === "swim" ? `${hms(spk / 10)} /100m` : (a.sport === "run" || a.sport === "walk") ? `${minmi(spk)} /mi` : `${(3600 / spk).toFixed(1)} km/h`;
        return `<tr><td>${esc(label)}${recs[label] === a.id ? ' <span class="pb">PB</span>' : ""}</td><td class="num">${hms(secs)}</td><td class="num">${pace}</td></tr>`; }).join("")}</tbody></table></div>` : "";
    $("sheet-flags").innerHTML = (a.excluded ? [`<div class="flag">Struck: ${esc(a.excluded)}</div>`] : a.flags.map((f) => `<div class="flag">⚠ ${esc(f)}</div>`))
      .concat(a.relabelled ? [`<div class="flag">The watch called this "${esc(a.type_key)}" — relabelled ${esc(a.sport)}.</div>`] : []).join("");
    $("sheet").hidden = false;
    const mapEl = $("map");
    mapEl.hidden = !a.has_track;
    if (a.has_track && window.L) {
      if (!map) { map = L.map(mapEl, { zoomControl: false }); L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map); }
      if (layer) layer.remove();
      try {
        const t = await (await fetch(`tracks/${id}.json`)).json();
        layer = L.polyline(t.points, { color: col(a.sport), weight: 4 }).addTo(map);
        setTimeout(() => { map.invalidateSize(); map.fitBounds(layer.getBounds(), { padding: [16, 16] }); }, 50);
      } catch (e) { mapEl.hidden = true; }
    }
  }
  $("sheet-close").addEventListener("click", () => { $("sheet").hidden = true; });
  $("sheet").addEventListener("click", (e) => { if (e.target === $("sheet")) $("sheet").hidden = true; });

  const RENDER = { overview, records: recordsTab, rankings, progress, log: logTab, map: mapTab };
  try { const t = localStorage.getItem("atlas.tab"); if (t && RENDER[t]) { document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === t)); } } catch (e) { /* private mode */ }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
  load().catch((e) => { $("kpis").innerHTML = `<p class="muted">Could not load data.json: ${esc(e)}</p>`; });
})();
