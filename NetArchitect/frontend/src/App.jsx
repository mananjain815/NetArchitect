import { useEffect, useMemo, useState } from "react";

const API = "http://localhost:8000";

const initial = {
  profile: "custom",
  name: "Custom Network",
  endpoints: 300,
  distance_m: 80,
  access_distance_m: 90,
  bandwidth_mbps: 1000,
  access_bandwidth_mbps: 1000,
  requested_media: "auto",
  site_count: 1,
  building_count: 1,
  sites: [],
  root_cidr: "192.168.0.0/16",
  subnet_requests: [
    { name: "STAFF", hosts: 150 },
    { name: "GUEST", hosts: 100 },
    { name: "SERVERS", hosts: 50 }
  ],
  autonomous_systems: 1,
  external_routing_domain: false,
  resiliency: "medium",
  wan_service: "p2p",
  max_latency_ms: null
};

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/health`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  const totalHosts = useMemo(
    () => form.subnet_requests.reduce((sum, item) => sum + Number(item.hosts || 0), 0),
    [form.subnet_requests]
  );

  function update(key, value) {
    setForm(current => ({ ...current, [key]: value, ...(key === "site_count" ? { sites: [] } : {}) }));
  }

  async function chooseProfile(profile) {
    update("profile", profile);
    if (profile === "custom") {
      setForm(current => ({ ...current, profile: "custom", name: "Custom Network" }));
      setResult(null);
      return;
    }
    try {
      const response = await fetch(`${API}/api/profiles/${profile}`);
      if (!response.ok) throw new Error("Could not load preset.");
      setForm(await response.json());
      setResult(null);
      setError("");
    } catch {
      setError("Could not load the preset. Check that the backend is running.");
    }
  }

  async function analyze(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          endpoints: Number(form.endpoints),
          distance_m: Number(form.distance_m),
          bandwidth_mbps: Number(form.bandwidth_mbps),
          site_count: Number(form.site_count),
          building_count: Number(form.building_count),
          access_distance_m: Number(form.access_distance_m),
          access_bandwidth_mbps: Number(form.access_bandwidth_mbps),
          max_latency_ms: form.max_latency_ms === null || form.max_latency_ms === "" ? null : Number(form.max_latency_ms),
          autonomous_systems: Number(form.autonomous_systems),
          subnet_requests: form.subnet_requests.map(x => ({
            name: x.name,
            hosts: Number(x.hosts)
          }))
        })
      });
      const data = await response.json();
      if (!response.ok) {
        const d = data.detail;
        throw new Error(Array.isArray(d) ? d.map(x => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join(" | ") : d || "Analysis failed.");
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Unable to connect to NetArchitect API.");
    } finally {
      setLoading(false);
    }
  }

  function updateSubnet(index, key, value) {
    setForm(current => ({
      ...current,
      subnet_requests: current.subnet_requests.map((item, i) =>
        i === index ? { ...item, [key]: value } : item
      )
    }));
  }

  function addSubnet() {
    setForm(current => ({
      ...current,
      subnet_requests: [...current.subnet_requests, { name: `VLAN_${current.subnet_requests.length + 1}`, hosts: 25 }]
    }));
  }

  function removeSubnet(index) {
    setForm(current => ({
      ...current,
      subnet_requests: current.subnet_requests.filter((_, i) => i !== index)
    }));
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">N</div><div><b>NetArchitect</b><small>NETWORK DESIGN ENGINE</small></div></div>
        <div className="side-label">WORKSPACE</div>
        <div className="nav-item active">▦ <span>Network designer</span></div>
        <div className="nav-item">⌘ <span>Decision engine</span></div>
        <div className="nav-item">▤ <span>Configuration exports</span></div>
        <div className="nav-item">✓ <span>Validation & testing</span></div>
        <div className="sidebar-bottom">
          <span className={`status-dot ${apiOnline ? "online" : ""}`}></span>
          <span>{apiOnline ? "Backend connected" : "Backend offline"}</span>
          <small>v2.0.0</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><span className="eyebrow">CIC-307 · COMPUTER NETWORKS MINI-PROJECT</span><h1>Network designer</h1><p>Translate network requirements into explainable architecture and device configurations.</p></div>
          <div className="top-pill"><span className={`status-dot ${apiOnline ? "online" : ""}`}></span>{apiOnline ? "API connected" : "API disconnected"}</div>
        </header>

        <section className="profile-grid">
          {[
            ["campus_lan", "Campus LAN", "3 buildings · 1,600 endpoints", "▥"],
            ["metro_man", "Metro MAN", "HQ + 2 remote sites · 15–35km", "⌁"],
            ["global_wan", "Global WAN", "4 cities + cloud · 2,000 IoT", "◎"],
            ["custom", "Custom design", "Define your own requirements", "+"]
          ].map(([id, title, desc, icon]) => (
            <button key={id} className={`profile-card ${form.profile === id ? "selected" : ""}`} onClick={() => chooseProfile(id)}>
              <span className="profile-icon">{icon}</span><b>{title}</b><small>{desc}</small>
            </button>
          ))}
        </section>

        <form className="workspace-grid" onSubmit={analyze}>
          <section className="panel input-panel">
            <div className="panel-heading"><div><span className="eyebrow">INPUT CONFIGURATION</span><h2>Network parameters</h2></div><span className="step-tag">01 / INPUT</span></div>
            <label>Network name<input value={form.name} onChange={e => update("name", e.target.value)} required /></label>
            <div className="field-grid">
              <label>Endpoints<input type="number" min="1" value={form.endpoints} onChange={e => update("endpoints", e.target.value)} required /></label>
              <label>Backbone / WAN link (m)<input type="number" min="0" step="1" value={form.distance_m} onChange={e => update("distance_m", e.target.value)} required /></label>
              <label>Access run (m)<input type="number" min="1" value={form.access_distance_m} onChange={e => update("access_distance_m", e.target.value)} required /></label>
              <label>Buildings (campus)<input type="number" min="1" value={form.building_count} onChange={e => update("building_count", e.target.value)} required /></label>
              <label>Bandwidth (Mbps)<input type="number" min="1" value={form.bandwidth_mbps} onChange={e => update("bandwidth_mbps", e.target.value)} required /></label>
              <label>Number of sites<input type="number" min="1" value={form.site_count} onChange={e => update("site_count", e.target.value)} required /></label>
              <label>Root IPv4 network<input value={form.root_cidr} onChange={e => update("root_cidr", e.target.value)} required /></label>
              <label>Autonomous systems<input type="number" min="1" value={form.autonomous_systems} onChange={e => update("autonomous_systems", e.target.value)} required /></label>
            </div>
            <div className="field-grid">
              <label>Requested media<select value={form.requested_media} onChange={e => update("requested_media", e.target.value)}><option value="auto">Auto (engine decides)</option><option value="copper">Copper (Cat6a)</option><option value="om4">OM4 multimode</option><option value="os2">OS2 single-mode</option></select></label>
              <label>WAN service<select value={form.wan_service} onChange={e => update("wan_service", e.target.value)}><option value="p2p">Point-to-point</option><option value="evpl">EVPL (metro Ethernet)</option><option value="ipsec">IPsec VPN</option></select></label>
              <label>Latency budget (ms, optional)<input type="number" min="0" step="0.1" value={form.max_latency_ms ?? ""} onChange={e => update("max_latency_ms", e.target.value)} /></label>
            </div>
            <label>Resiliency requirement<select value={form.resiliency} onChange={e => update("resiliency", e.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
            <label className="check-row"><input type="checkbox" checked={form.external_routing_domain} onChange={e => update("external_routing_domain", e.target.checked)} /> External routing domain / cloud boundary</label>

            <div className="subnet-heading"><div><h3>Subnet requirements</h3><small>Host counts are allocated using VLSM.</small></div><button type="button" className="text-button" onClick={addSubnet}>＋ Add subnet</button></div>
            <div className="subnet-list">
              {form.subnet_requests.map((item, index) => (
                <div className="subnet-row" key={index}>
                  <input aria-label="Subnet name" value={item.name} onChange={e => updateSubnet(index, "name", e.target.value)} required />
                  <input aria-label="Required hosts" type="number" min="1" value={item.hosts} onChange={e => updateSubnet(index, "hosts", e.target.value)} required />
                  <button type="button" className="remove-button" onClick={() => removeSubnet(index)} aria-label="Remove subnet">×</button>
                </div>
              ))}
            </div>
            <div className="subnet-total"><span>Total requested subnet hosts</span><b>{totalHosts.toLocaleString()}</b></div>
            {error && <div className="error-box">{error}</div>}
            <button className="primary-button" type="submit" disabled={loading || !apiOnline}>{loading ? "Analyzing network…" : "Run architecture analysis →"}</button>
            {!apiOnline && <small className="hint">Start the FastAPI backend to enable analysis.</small>}
          </section>

          <section className="panel result-panel">
            <div className="panel-heading"><div><span className="eyebrow">ENGINE OUTPUT</span><h2>Architecture overview</h2></div><span className="step-tag">02 / OUTPUT</span></div>
            {!result ? (
              <div className="empty-state"><div className="empty-icon">⌁</div><h3>Awaiting network analysis</h3><p>Select a preset or enter custom requirements, then run the architecture engine. Your recommendations, subnet allocations and Cisco configurations will appear here.</p></div>
            ) : (
              <div className="results">
                <div className="recommendation-grid">
                  <div className="metric-card"><small>PHYSICAL MEDIA</small><b>{result.media.medium}</b><span>{result.media.transceiver}</span></div>
                  <div className="metric-card"><small>ROUTING PROTOCOL</small><b>{result.routing.protocol}</b><span>{result.topology.tier}</span></div>
                  <div className="metric-card"><small>VLSM SUBNETS</small><b>{result.vlsm.allocations.length}</b><span>{result.vlsm.root_network}</span></div>
                  <div className="metric-card"><small>REQUESTED HOSTS</small><b>{totalHosts.toLocaleString()}</b><span>Across all requested networks</span></div>
                </div>

                <div className="result-section"><h3>VLSM allocation</h3><div className="table-wrap"><table><thead><tr><th>Subnet</th><th>Network / CIDR</th><th>Gateway</th><th>Broadcast</th></tr></thead><tbody>{result.vlsm.allocations.map(item => <tr key={item.name}><td>{item.name}</td><td>{item.cidr}</td><td>{item.gateway || "—"}</td><td>{item.broadcast}</td></tr>)}</tbody></table></div></div>

                <div className="result-section"><h3>Explainable decisions</h3>{result.report.decisions.map((item, i) => <div className="decision" key={i}><div><b>{item.area}</b><span>{item.decision}</span></div><p>{item.reason}</p></div>)}</div>

                {result.warnings.length > 0 && <div className="warning-box"><b>Review warnings</b>{result.warnings.map((w, i) => <p key={i}>• {w}</p>)}</div>}

                <div className="result-section"><h3>Cabling plan</h3><div className="table-wrap"><table><thead><tr><th>A</th><th>Port</th><th>B</th><th>Port</th><th>Subnet</th></tr></thead><tbody>{result.configs.cabling.map((c, i) => <tr key={i}><td>{c.a}</td><td>{c.if_a}</td><td>{c.b}</td><td>{c.if_b}</td><td>{c.subnet}</td></tr>)}</tbody></table></div></div>

                <div className="result-section"><h3>Configuration exports</h3><div className="export-list">
                  {Object.entries(result.configs.devices).map(([fname, text]) => <button type="button" className="export-button" key={fname} onClick={() => downloadText(fname, text)}><span>▤ <b>{fname}</b></span><span>Download ↓</span></button>)}
                  <button type="button" className="export-button" onClick={() => downloadText(`${form.profile}_full_config.txt`, result.configs.bundle)}><span>▤ <b>All devices (bundle)</b></span><span>Download ↓</span></button>
                  <button type="button" className="export-button" onClick={() => downloadText(`${form.profile}_rationale.md`, result.report.markdown)}><span>▤ <b>Rationale log (.md)</b></span><span>Download ↓</span></button>
                </div><small className="hint">{result.configs.notes.join(" ")}</small></div>
              </div>
            )}
          </section>
        </form>
        <footer>NetArchitect · Algorithmic Network Planning & Explainable Architecture Engine <span>Academic prototype · Verify configs before deployment</span></footer>
      </main>
    </div>
  );
}
