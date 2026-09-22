/* Recorded ancestry and confirmed recovery paths. No inferred similarity edges. */
(() => {
  const el = id => document.getElementById(`graph-${id}`);
  const svg = el("svg"), ns = "http://www.w3.org/2000/svg";
  let run, nodes = [], edges = [], lookup = new Map(), selected, layer;
  let camera = {x:0, y:0, k:1}, drag = null;
  function shape(tag, attrs = {}, copy = "") {
    const item = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => item.setAttribute(key, value));
    if (copy) item.textContent = copy;
    return item;
  }
  function layout() {
    const count = nodes.length;
    nodes.forEach((n, i) => {
      const angle = i * 2.399963;
      const radius = 35 + 230 * Math.sqrt(i / count);
      n.x = 450 + radius * Math.cos(angle); n.y = 300 + radius * Math.sin(angle);
    });
    // Finite, deterministic settling. The map stays still while it is inspected.
    for (let tick = 0; tick < 240; tick++) {
      const forces = nodes.map(n => ({x:(450 - n.x) * .003, y:(300 - n.y) * .003}));
      for (let i = 0; i < count; i++) for (let j = i + 1; j < count; j++) {
        let dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
        const squared = dx * dx + dy * dy + 1;
        const force = Math.min(5, 1800 / squared) / Math.sqrt(squared);
        forces[i].x += dx * force; forces[i].y += dy * force;
        forces[j].x -= dx * force; forces[j].y -= dy * force;
      }
      for (const edge of edges) {
        const a = lookup.get(edge.source), b = lookup.get(edge.target);
        const dx = b.x - a.x, dy = b.y - a.y, distance = Math.hypot(dx, dy) || 1;
        const force = (distance - 85) * .006;
        forces[a.index].x += dx / distance * force; forces[a.index].y += dy / distance * force;
        forces[b.index].x -= dx / distance * force; forces[b.index].y -= dy / distance * force;
      }
      const cool = 1 - tick / 300;
      nodes.forEach((n, i) => {
        n.x += Math.max(-6, Math.min(6, forces[i].x)) * cool;
        n.y += Math.max(-6, Math.min(6, forces[i].y)) * cool;
      });
    }
  }
  function positions() {
    nodes.forEach(n => {
      n.element.setAttribute("transform", `translate(${n.x},${n.y})`);
      n.dot.setAttribute("r", (n.deployed ? 7 : n.archived ? 5 : 3.5) / camera.k);
      n.hit.setAttribute("r", 12 / camera.k);
      n.label.setAttribute("x", 11 / camera.k); n.label.setAttribute("y", -10 / camera.k);
      n.label.style.fontSize = `${12 / camera.k}px`;
    });
    edges.forEach(e => {
      const a = lookup.get(e.source), b = lookup.get(e.target);
      e.element.setAttribute("x1", a.x); e.element.setAttribute("y1", a.y);
      e.element.setAttribute("x2", b.x); e.element.setAttribute("y2", b.y);
    });
    layer.setAttribute("transform", `translate(${camera.x},${camera.y}) scale(${camera.k})`);
  }
  function fit() {
    if (!nodes.length) return;
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
    const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
    const width = svg.clientWidth || 900, height = svg.clientHeight || 560;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const k = Math.min(2.5, (width - 65) / (right - left + 30), (height - 105) / (bottom - top + 30));
    camera = {k, x:width / 2 - (left + right) * k / 2, y:height / 2 - (top + bottom) * k / 2};
    positions();
  }
  function circuit(n) {
    const drawing = el("circuit"); drawing.replaceChildren();
    const r = run.design.resistor_ohms[n.configuration.resistor_index] / 1000;
    const cap = run.design.capacitor_nf.reduce((sum, c, i) => sum + ((n.configuration.capacitor_mask & (1 << i)) ? c : 0), 0);
    drawing.append(shape("path", {d:"M18 65 H65 l8 -10 l12 20 l12 -20 l12 20 l12 -20 l8 10 H302 M210 65 V95 M190 95 H230 M190 103 H230 M210 103 V125 M197 125 H223 M202 131 H218", fill:"none", stroke:"var(--ink)", "stroke-width":2}));
    drawing.append(shape("circle", {cx:210, cy:65, r:3, fill:"var(--blue)"}));
    drawing.append(shape("text", {x:63, y:38, fill:"var(--ink)", "font-size":16}, `${r} kΩ`));
    drawing.append(shape("text", {x:238, y:102, fill:"var(--blue)", "font-size":14}, `${Number(cap.toFixed(2))} nF`));
    return cap;
  }
  function select(id) {
    const n = lookup.get(id); if (!n) return;
    selected = id; el("picker").value = id;
    const connected = new Set([id]);
    edges.forEach(e => { if (e.source === id || e.target === id) { connected.add(e.source); connected.add(e.target); } });
    nodes.forEach(item => {
      item.element.classList.toggle("selected", item.id === id);
      item.element.classList.toggle("dim", !connected.has(item.id));
      item.element.setAttribute("tabindex", item.id === id ? "0" : "-1");
      item.label.textContent = item.id === id ? item.id : "";
    });
    edges.forEach(e => {
      const related = e.source === id || e.target === id;
      e.element.classList.toggle("related", related); e.element.classList.toggle("dim", !related);
    });
    el("name").textContent = id;
    el("role").textContent = n.deployed ? "Deployed during the trial" : n.archived ? "Kept in the circuit archive" : "Measured; outside the final archive";
    const cap = circuit(n), mask = n.configuration.capacitor_mask;
    const values = [
      ["Training stress score", `${n.score_db.toFixed(3)} dB`], ["Generation", n.generation],
      ["Components", `R${n.configuration.resistor_index + 1}, ${run.design.capacitor_nf.map((_, i) => mask & (1 << i) ? `C${i + 1}` : null).filter(Boolean).join(", ")}`],
      ["Total capacitance", `${Number(cap.toFixed(2))} nF`],
    ];
    const deployment = run.mission.filter(s => s.genotype === id);
    if (deployment.length) values.push(["Replay error range", `${Math.min(...deployment.map(s => s.error_db)).toFixed(3)} to ${Math.max(...deployment.map(s => s.error_db)).toFixed(3)} dB`]);
    el("values").replaceChildren();
    values.forEach(([key, value]) => {
      const item = document.createElement("div"), term = document.createElement("dt"), detail = document.createElement("dd");
      term.textContent = key; detail.textContent = value; item.append(term, detail); el("values").append(item);
    });
    const links = el("links"); links.replaceChildren();
    function group(title, items) {
      if (!items.length) return;
      const heading = document.createElement("h3"); heading.textContent = title; links.append(heading);
      items.forEach(([target, label]) => {
        const button = document.createElement("button"); button.type = "button"; button.textContent = label;
        button.addEventListener("click", () => { select(target); el("picker").focus(); }); links.append(button);
      });
    }
    group("Parents", [...new Set(n.parents)].map(parent => [parent, parent]));
    group("Children", nodes.filter(child => child.parents.includes(id)).map(child => [child.id, child.id]));
    group("Recovery paths", edges.filter(e => e.kind === "recovery" && (e.source === id || e.target === id)).map(e => [e.source === id ? e.target : e.source, `${e.source === id ? "To" : "From"} ${e.source === id ? e.target : e.source}: ${e.reason}`]));
    if (deployment.length) {
      const button = document.createElement("button"); button.type = "button"; button.textContent = "View in replay";
      button.addEventListener("click", () => window.DarwinArena.showStep(deployment[0].step)); links.append(button);
    }
    if (!n.parents.length) { const p = document.createElement("p"); p.textContent = n.generation === 0 ? "Entered in the initial population." : "Entered as an independent candidate."; links.append(p); }
  }
  function render(data) {
    run = data;
    nodes = run.circuit_graph.nodes.map((n, i) => ({...n, index:i}));
    edges = run.circuit_graph.edges.map(e => ({...e}));
    lookup = new Map(nodes.map(n => [n.id, n]));
    el("empty").hidden = true; el("results").hidden = false;
    const recoveries = edges.filter(e => e.kind === "recovery").length;
    el("count").textContent = `${nodes.length} measured circuits, ${recoveries} recovery ${recoveries === 1 ? "path" : "paths"}`;
    el("picker").replaceChildren();
    nodes.forEach(n => { const option = document.createElement("option"); option.value = n.id; option.textContent = n.id; el("picker").append(option); });
    layout(); svg.replaceChildren(); layer = shape("g"); svg.append(layer);
    edges.forEach(e => { e.element = shape("line", {class:`graph-edge ${e.kind}`}); layer.append(e.element); });
    nodes.forEach(n => {
      n.element = shape("g", {class:`graph-node${n.archived ? " archived" : ""}${n.deployed ? " deployed" : ""}`, "data-id":n.id, role:"button", "aria-label":`${n.id}, generation ${n.generation}, training error ${n.score_db.toFixed(3)} dB${n.deployed ? ", deployed" : n.archived ? ", kept" : ""}`});
      n.hit = shape("circle", {class:"hit", r:12}); n.element.append(n.hit);
      n.dot = shape("circle", {r:n.deployed ? 7 : n.archived ? 5 : 3.5}); n.element.append(n.dot);
      n.label = shape("text", {x:12, y:-12}); n.element.append(n.label);
      n.element.append(shape("title", {}, `${n.id}: ${n.score_db.toFixed(3)} dB`));
      n.element.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(n.id); } });
      layer.append(n.element);
    });
    fit(); select(run.mission[0].before_genotype);
  }
  function pointer(event) {
    const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  }
  svg.addEventListener("pointerdown", event => {
    if (!run || event.button !== 0) return;
    const point = pointer(event), id = event.target.closest("[data-id]")?.dataset.id;
    if (id) select(id);
    drag = {x:point.x, y:point.y, id}; svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", event => {
    if (!drag) return;
    const point = pointer(event), dx = point.x - drag.x, dy = point.y - drag.y;
    if (drag.id) { const n = lookup.get(drag.id); n.x += dx / camera.k; n.y += dy / camera.k; }
    else { camera.x += dx; camera.y += dy; }
    drag.x = point.x; drag.y = point.y; positions();
  });
  svg.addEventListener("pointerup", () => { drag = null; });
  svg.addEventListener("pointercancel", () => { drag = null; });
  svg.addEventListener("wheel", event => {
    if (!run) return;
    event.preventDefault(); const p = pointer(event);
    const scale = Math.max(.35, Math.min(4, camera.k * Math.exp(-event.deltaY * .0015)));
    camera.x = p.x - (p.x - camera.x) * scale / camera.k;
    camera.y = p.y - (p.y - camera.y) * scale / camera.k;
    camera.k = scale; positions();
  }, {passive:false});
  el("fit").addEventListener("click", fit);
  new ResizeObserver(() => { if (svg.clientWidth > 0 && run) fit(); }).observe(svg);
  el("picker").addEventListener("change", () => select(el("picker").value));
  el("build").addEventListener("click", () => window.DarwinArena.run());
  document.addEventListener("darwin:arena", event => render(event.detail));
  document.addEventListener("darwin:arena-status", event => {
    el("results").hidden = true; el("empty").hidden = false;
    el("build").disabled = event.detail.loading;
    el("status").textContent = event.detail.message;
  });
  document.addEventListener("darwin:arena-ready", () => { el("build").disabled = false; });
})();
