/* A guided, isolated simulation. Closing restores the visitor's original run. */
(() => {
  const el = name => document.getElementById(`tutorial-${name}`);
  const dialog = el("dialog");
  let snapshot, demo, index = 0, controller, target;
  const steps = [
    {view:"lab", target:".controls", title:"Choose a response", copy:"The cutoff is the frequency where the signal drops by about 3 dB. This demo follows a simulated circuit built for a 1.2 kHz target."},
    {view:"lab", stage:"commissioned", target:".workspace", title:"Find a working circuit", copy:"The search measures resistor and capacitor combinations. The plot compares the selected circuit with the target; the drawing shows the parts it uses."},
    {view:"lab", stage:"fault", target:"#response-chart", title:"A component fails", copy:"One capacitor branch is opened in the simulation. Its response moves away from the target. The health check detects that change."},
    {view:"lab", stage:"recovered", target:".status-strip", title:"Recover with a measured backup", copy:"The controller tries a reserved route and measures it again before accepting the change. The error here comes from this demo's actual simulation."},
    {view:"lab", stage:"recovered", target:"#evolution-lineage", details:"#search-title", title:"Read the search history", copy:"Each round records parents, mutations, and measured survivors. Open a generation during normal use to inspect the circuits it kept."},
    {view:"lab", stage:"recovered", target:"#reserve-list", details:"#reserve-title", title:"Inspect the recovery routes", copy:"Backups are measured before a failure. This record shows which alternatives were checked and which component failures they could cover."},
    {view:"sequence", target:".sequence-layout", title:"Replay the complete run", copy:"Replay follows the winning circuit from search through failure and recovery. Select any step to see its wiring, genotype, and response error."},
    {view:"arena", arenaStep:0, target:".arena-replay", title:"Try an unfamiliar board", copy:"The arena evolves circuit families across temperature, load, and wear. It freezes the archive before testing it on new simulated boards."},
    {view:"arena", arenaStep:6, target:".arena-replay", title:"Face two persistent faults", copy:"Here a capacitor has opened and the original resistor has drifted. Compare the adaptive response with the circuit left fixed. Scrub the timeline to inspect each change."},
    {view:"arena", target:"#arena-comparison", details:"#arena-comparison", title:"Check the evidence", copy:"The comparison includes unseen cases and a random-search baseline. Results can get worse. Training measurements and test results remain separate."},
    {view:"graph", target:".graph-layout", title:"Follow a circuit's connections", copy:"Each node is a measured circuit. Lines record parentage; dashed paths record recovery. Select a node to read its components or follow its relatives. Local graph isolates its neighbours."},
    {view:"graph", target:"#obsidian-send", title:"Keep the experiment in Obsidian", copy:"Send to Obsidian creates linked circuit notes in a dedicated vault folder. Native Graph view and Backlinks can explore them. This walkthrough never exports automatically. Finish restores your original run."}
  ];
  function clearTarget() { if (target) target.classList.remove("tutorial-target"); target = null; }
  function show() {
    clearTarget();
    document.querySelectorAll("details").forEach(item => { item.open = false; });
    const step = steps[index];
    window.DarwinLab.view(step.view);
    if (step.stage) window.DarwinLab.stage(step.stage);
    if (step.arenaStep !== undefined) window.DarwinArena.showStep(step.arenaStep);
    if (step.details) document.querySelector(step.details)?.closest("details")?.setAttribute("open", "");
    target = document.querySelector(step.target);
    if (target) {
      target.classList.add("tutorial-target");
      target.scrollIntoView({block:"center", behavior:"instant"});
    }
    el("title").textContent = step.title; el("copy").textContent = step.copy;
    el("progress").textContent = `Demo walkthrough · ${index + 1} of ${steps.length}`;
    el("back").disabled = index === 0; el("next").disabled = false;
    el("next").textContent = index === steps.length - 1 ? "Finish" : "Next";
    el("next").focus({preventScroll:true});
  }
  function finish() {
    controller?.abort(); controller = null; clearTarget(); dialog.close();
    if (snapshot) {
      window.DarwinArena.restore(snapshot.arena);
      window.DarwinLab.restore(snapshot.lab);
      window.DarwinGraph.restore(snapshot.graph);
      document.querySelectorAll("details").forEach((item, i) => { item.open = snapshot.details[i]; });
      window.scrollTo(snapshot.x, snapshot.y);
      snapshot = null;
    }
    demo = null; el("start").focus({preventScroll:true});
  }
  async function start() {
    if (window.DarwinLab.busy() || window.DarwinArena.busy() || window.DarwinGraph.busy()) return;
    snapshot = {lab:window.DarwinLab.capture(), arena:window.DarwinArena.capture(), graph:window.DarwinGraph.capture(),
                details:Array.from(document.querySelectorAll("details"), d => d.open), x:scrollX, y:scrollY};
    dialog.showModal(); el("error").hidden = true; el("back").disabled = true; el("next").disabled = true;
    el("progress").textContent = "Demo walkthrough"; el("title").textContent = "Preparing a simulation";
    el("copy").textContent = "Your current run will be restored when you leave.";
    controller = new AbortController();
    try {
      if (location.protocol === "file:") throw new Error("Open the dashboard through its local server to start the walkthrough.");
      const response = await fetch("/api/tutorial", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}", signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not prepare the demo.");
      if (!dialog.open) return;
      demo = data; window.DarwinLab.load(demo.lab); window.DarwinArena.load(demo.arena);
      index = 0; show();
    } catch (error) {
      if (error.name === "AbortError") return;
      el("title").textContent = "The demo could not start";
      el("error").hidden = false; el("error").textContent = error.message;
      el("close").focus();
    }
  }
  el("start").addEventListener("click", start);
  el("close").addEventListener("click", finish);
  dialog.addEventListener("cancel", event => { event.preventDefault(); finish(); });
  el("next").addEventListener("click", () => { if (index === steps.length - 1) finish(); else { index++; show(); } });
  el("back").addEventListener("click", () => { if (index > 0) { index--; show(); } });
})();
