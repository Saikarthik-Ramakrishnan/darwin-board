/* Environmental adaptation trial. All displayed values come from the run export. */
(() => {
  const el = id => document.getElementById(`arena-${id}`);
  const svgNS = "http://www.w3.org/2000/svg";
  let run = null, step = 0, timer = null;
  const fmt = value => Number(value).toFixed(3);
  const text = (id, value) => { el(id).textContent = value; };
  function node(tag, attrs = {}, copy = "") {
    const item = document.createElementNS(svgNS, tag);
    Object.entries(attrs).forEach(([key, value]) => item.setAttribute(key, value));
    if (copy) item.textContent = copy;
    return item;
  }
  function label(svg, x, y, copy, attrs = {}) {
    svg.append(node("text", {x, y, fill:"var(--muted)", "font-size":12, ...attrs}, copy));
  }
  function path(svg, d, color = "var(--ink)", width = 2) {
    svg.append(node("path", {d, fill:"none", stroke:color, "stroke-width":width, "stroke-linejoin":"round"}));
  }
  function stop() { clearInterval(timer); timer = null; text("play", "Play"); }
  function renderMap() {
    const map = el("map"); map.replaceChildren();
    for (let row = 0; row <= 8; row++) {
      for (let col = 0; col <= 8; col++) {
        if (!row || !col) {
          const item = document.createElement("span"); item.className = "arena-map-label";
          item.textContent = !row && col ? `R${col}` : row ? `${row}C` : "";
          map.append(item); continue;
        }
        const entry = run.archive.find(c => c.resistor_index === col - 1 && c.capacitor_count === row);
        const button = document.createElement("button");
        button.type = "button"; button.className = "arena-niche"; button.disabled = !entry;
        button.setAttribute("aria-pressed", "false");
        if (entry) {
          button.classList.add("occupied");
          button.style.setProperty("--strength", `${Math.max(5, 32 / (1 + entry.score_db))}%`);
          button.textContent = entry.score_db.toFixed(1);
          button.title = `${entry.genotype}, ${fmt(entry.score_db)} dB stress score`;
          button.setAttribute("aria-label", button.title);
          button.addEventListener("click", () => {
            map.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", "false"));
            button.setAttribute("aria-pressed", "true");
            text("cell", `${entry.genotype} appeared in generation ${entry.generation}. Stress score ${fmt(entry.score_db)} dB; worst training case ${fmt(entry.worst_training_error_db)} dB. ${entry.parents.length ? `Parents: ${entry.parents.join(" and ")}.` : "Entered as an initial candidate or immigrant."}`);
          });
        } else { button.setAttribute("aria-label", `R${col}, ${row} capacitors: unexplored`); button.textContent = "·"; }
        map.append(button);
      }
    }
    text("cell", `${run.archive.length} of 64 niches occupied. A niche preserves a circuit family; occupancy does not mean every member meets tolerance.`);
  }
  function renderGeneration() {
    const index = Number(el("generation").value), g = run.generations[index];
    text("generation-label", index);
    const mutations = g.children.reduce((sum, c) => sum + c.mutations, 0);
    text("generation-detail", `${g.evaluated_routes} routes tested; ${g.occupied_cells} niches occupied. This generation made ${g.archive_updates} archive updates through ${g.children.length} measured children and ${mutations} gene mutations. Best genotype: ${g.best_genotype}.`);
    const svg = el("evolution-chart"); svg.replaceChildren();
    const best = run.generations.map(g => g.best_score_db);
    const max = Math.max(...best) * 1.15 || 1;
    const x = i => 54 + 440 * i / Math.max(1, best.length - 1);
    const y = value => 170 - 130 * value / max;
    path(svg, "M54 30 V170 H500", "var(--line-strong)", 1);
    label(svg, 10, 24, "dB"); label(svg, 54, 192, "0"); label(svg, 475, 192, String(best.length - 1));
    label(svg, 230, 204, "Generation");
    label(svg, 12, 45, max.toFixed(2)); label(svg, 24, 172, "0");
    path(svg, best.map((v, i) => `${i ? "L" : "M"}${x(i)} ${y(v)}`).join(" "), "var(--blue)", 2.5);
    svg.append(node("circle", {cx:x(index), cy:y(best[index]), r:5, fill:"var(--blue)"}));
    label(svg, x(index), Math.max(20, y(best[index]) - 12), `${fmt(best[index])} dB`, {"text-anchor":"middle", fill:"var(--ink)"});
  }
  function renderCircuit(s) {
    const svg = el("circuit"); svg.replaceChildren();
    const config = s.configuration;
    const capIndices = run.design.capacitor_nf.map((_, i) => i).filter(i => config.capacitor_mask & (1 << i));
    const cap = capIndices.reduce((sum, i) => sum + run.design.capacitor_nf[i], 0);
    label(svg, 20, 27, s.genotype, {"font-size":16, fill:"var(--ink)"});
    path(svg, "M24 90 H100 l8 -10 l12 20 l12 -20 l12 20 l12 -20 l8 10 H430");
    label(svg, 76, 64, `R${config.resistor_index + 1} · ${(run.design.resistor_ohms[config.resistor_index] / 1000).toFixed(1)} kΩ`);
    svg.append(node("circle", {cx:270, cy:90, r:4, fill:"var(--blue)"}));
    path(svg, "M270 90 V125 M248 125 H292 M248 135 H292 M270 135 V175 M250 175 H290 M257 181 H283 M263 187 H277", "var(--blue)");
    label(svg, 303, 137, `${cap.toFixed(2)} nF`);
    label(svg, 19, 115, "Vin"); label(svg, 395, 115, "Vout");
    label(svg, 24, 216, `Active branches: ${capIndices.map(i => `C${i + 1}`).join(", ")}`);
    label(svg, 302, 161, "nominal bank values", {"font-size":11});
  }
  function renderResponse(s) {
    const svg = el("response"); svg.replaceChildren();
    const curves = [run.target_response_db, s.response_db, s.fixed_response_db];
    const bottom = Math.min(-24, Math.floor(Math.min(...curves.flat()) / 5) * 5);
    const x = i => 48 + i * 448 / (run.frequencies_hz.length - 1);
    const y = v => 25 + Math.min(1, Math.max(0, v / bottom)) * 165;
    for (let tick = 0; tick >= bottom; tick -= 10) {
      path(svg, `M48 ${y(tick)} H500`, "var(--line)", 1); label(svg, 13, y(tick) + 4, String(tick));
    }
    label(svg, 13, 14, "dB"); label(svg, 48, 216, `${Math.round(run.frequencies_hz[0])} Hz`);
    label(svg, 493, 216, `${Math.round(run.frequencies_hz.at(-1))} Hz`, {"text-anchor":"end"});
    curves.forEach((curve, i) => {
      const p = node("path", {d:curve.map((v,j) => `${j ? "L" : "M"}${x(j)} ${y(v)}`).join(" "), fill:"none", stroke:["var(--muted)", "var(--blue)", "var(--red)"][i], "stroke-width": i ? 2.5 : 1.5});
      if (!i) p.setAttribute("stroke-dasharray", "5 4"); svg.append(p);
    });
  }
  function renderStep() {
    const s = run.mission[step], env = s.environment;
    el("step").value = step;
    el("step").setAttribute("aria-valuetext", `${step + 1}: ${env.name}`);
    text("step-title", env.name);
    text("step-number", `${step + 1} / ${run.mission.length}`);
    const faults = [...env.open_capacitors.map(i => `C${i + 1} open`), ...env.resistor_scales.map(([i, scale]) => `R${i + 1} at ${scale} times its value`)];
    text("step-detail", `${env.temperature_c} °C, ${(env.load_ohms / 1000).toFixed(0)} kΩ load. ${faults.length ? faults.join("; ") + "." : "No component faults."}`);
    text("outcome", `${fmt(s.error_db)} dB error · ${s.error_db <= run.meta.limit_db ? "Within tolerance" : "Outside tolerance"}`);
    el("outcome").dataset.pass = String(s.error_db <= run.meta.limit_db);
    text("probes", `${s.changed ? "Route changed and confirmed." : "Route retained."} ${s.probes.length} sweeps. Fixed circuit: ${fmt(s.fixed_error_db)} dB.`);
    renderCircuit(s); renderResponse(s);
  }
  function render() {
    el("results").hidden = false;
    el("empty").hidden = true;
    text("metrics", `${run.mission_summary.adaptive.pass_percent.toFixed(0)}% of replay steps within 0.5 dB.`);
    renderMap();
    el("generation").max = run.generations.length - 1;
    el("generation").value = run.generations.length - 1;
    renderGeneration();
    el("step").max = run.mission.length - 1;
    step = 0; renderStep();
    const names = {nominal:"Nominal selection, same candidates", robust:"Stress-selected elite", random:"Random search, stress objective", bayesian:"Existing Bayesian tuner, reference habitat"};
    el("comparison").replaceChildren();
    for (const [key, value] of Object.entries(run.static_comparison)) {
      const tr = document.createElement("tr");
      [names[key], `${fmt(value.mean_error_db)} dB`, `${fmt(value.p95_error_db)} dB`, `${value.pass_percent.toFixed(1)}%`, key === "bayesian" ? run.meta.bayesian_training_sweeps : run.meta.training_sweeps_per_method].forEach(copy => {
        const td = document.createElement("td"); td.textContent = copy; tr.append(td);
      });
      el("comparison").append(tr);
    }
    text("comparison-note", `Nominal and stress selection share the evaluated population. Random search uses the same number of training sweeps. The existing tuner uses its original 24-sweep budget. Static evaluation excludes faults. In the separate deployment replay, a same-size reserve selected by score alone passes ${run.mission_summary.topk.pass_percent.toFixed(1)}% of steps, compared with ${run.mission_summary.adaptive.pass_percent.toFixed(1)}% for the diverse archive. Neither experiment establishes hardware performance.`);
    text("status", `${run.meta.route_budget} circuits measured. ${run.archive.length} circuit families kept. Tested on ${run.meta.holdout_cases} unseen cases.`);
  }
  async function runTrial() {
    if (el("run").disabled) return;
    const cutoff = Number(el("cutoff").value), seed = Number(el("seed").value);
    if (!Number.isFinite(cutoff) || cutoff < 100 || cutoff > 10000 || !Number.isInteger(seed) || seed < 0 || seed > 2147483647) {
      const message = "Enter a cutoff from 100 to 10000 Hz and a non-negative integer seed up to 2147483647.";
      el("status").dataset.error = "true"; text("status", message);
      document.dispatchEvent(new CustomEvent("darwin:arena-status", {detail:{loading:false, message}})); return;
    }
    stop(); el("run").disabled = true; el("export").disabled = true; el("results").hidden = true;
    el("empty").hidden = true;
    document.dispatchEvent(new CustomEvent("darwin:arena-status", {detail:{loading:true, message:"Measuring circuit families…"}}));
    el("status").dataset.error = "false";
    text("status", "Evolving circuit families, then evaluating the frozen archive on unseen conditions…");
    try {
      if (location.protocol === "file:") throw new Error("Start the visualizer server and open http://127.0.0.1:8765 to run the arena.");
      const response = await fetch("/api/arena", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({cutoff_hz:cutoff, seed, budget:Number(el("budget").value)})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The arena could not finish this run.");
      run = data; render(); el("export").disabled = false;
      document.dispatchEvent(new CustomEvent("darwin:arena", {detail:run}));
    } catch (error) {
      el("status").dataset.error = "true"; text("status", error.message);
      el("empty").hidden = false;
      document.dispatchEvent(new CustomEvent("darwin:arena-status", {detail:{loading:false, message:error.message}}));
    }
    finally { el("run").disabled = false; document.dispatchEvent(new CustomEvent("darwin:arena-ready")); }
  }
  el("run").addEventListener("click", runTrial);
  window.DarwinArena = {run:runTrial, getRun:() => run, showStep:index => {
    if (!run) return;
    stop(); step = Math.max(0, Math.min(run.mission.length - 1, index)); renderStep();
    document.getElementById("arena-tab").click(); el("step").focus();
  }, busy:() => el("run").disabled,
  capture:() => ({run, step, generation:el("generation").value, cutoff:el("cutoff").value, seed:el("seed").value, budget:el("budget").value}),
  load:data => {
    stop(); run = data; render(); el("export").disabled = false;
    el("cutoff").value = data.meta.cutoff_hz; el("seed").value = data.meta.seed; el("budget").value = data.meta.route_budget;
    document.dispatchEvent(new CustomEvent("darwin:arena", {detail:run}));
  }, restore:saved => {
    stop(); run = saved.run; el("cutoff").value = saved.cutoff; el("seed").value = saved.seed; el("budget").value = saved.budget;
    if (run) {
      render(); step = saved.step; renderStep(); el("export").disabled = false;
      el("generation").value = saved.generation; renderGeneration();
      document.dispatchEvent(new CustomEvent("darwin:arena", {detail:run}));
    } else {
      el("results").hidden = true; el("empty").hidden = false; el("export").disabled = true;
      text("status", "The population learns on two boards, then faces conditions it has never seen.");
      document.dispatchEvent(new CustomEvent("darwin:arena-clear"));
    }
  }};
  el("step").addEventListener("input", () => { if (run) { stop(); step = Number(el("step").value); renderStep(); } });
  el("generation").addEventListener("input", () => { if (run) renderGeneration(); });
  el("play").addEventListener("click", () => {
    if (!run) return;
    if (timer) { stop(); return; }
    if (step === run.mission.length - 1) step = 0;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      step = Math.min(step + 1, run.mission.length - 1); renderStep(); return;
    }
    renderStep(); text("play", "Pause");
    timer = setInterval(() => { step++; renderStep(); if (step === run.mission.length - 1) stop(); }, 1600);
  });
  el("export").addEventListener("click", () => {
    if (!run) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], {type:"application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = `${run.evidence.run_id}-arena.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  document.querySelectorAll(".view-tab").forEach(tab => tab.addEventListener("click", () => { if (tab.id !== "arena-tab") stop(); }));
})();
