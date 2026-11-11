import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Boxes,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Package,
  Play,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Ticket,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import WorkflowGraph from "./WorkflowGraph";
type Obj = Record<string, any>;
const api = async (path: string, opts: RequestInit = {}) => {
  const token = localStorage.getItem("token");
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts.headers,
    },
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
};
export default function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [role, setRole] = useState(localStorage.getItem("role") || "operator");
  const [input, setInput] = useState(
    "Find orders delayed more than five days, identify affected customers, and prepare a support ticket for each.",
  );
  const [active, setActive] = useState("Overview");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState("");
  const [selectedData, setSelectedData] = useState<{
    kind: string;
    id: string;
  } | null>(null);
  const [reviseOpen, setReviseOpen] = useState(false);
  const [revisionText, setRevisionText] = useState("");
  const [run, setRun] = useState("");
  const qc = useQueryClient();
  const dash = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api("/api/dashboard"),
    enabled: !!token,
  });
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api("/api/runs"),
    enabled: !!token,
  });
  const detail = useQuery({
    queryKey: ["detail", run],
    queryFn: () => api(`/api/runs/${run}`),
    enabled: !!token && !!run,
  });
  const data = useQuery({
    queryKey: ["data", active, page, search, sort],
    queryFn: () =>
      api(
        `/api/data/${active === "Orders" ? "orders" : active === "Customers" ? "customers" : active === "Inventory" ? "inventory" : "tickets"}?limit=20&offset=${page * 20}&search=${encodeURIComponent(search)}&sort_by=${encodeURIComponent(sort)}`,
      ),
    enabled:
      !!token &&
      ["Orders", "Customers", "Inventory", "Tickets"].includes(active),
  });
  const recordDetail = useQuery({
    queryKey: ["record-detail", selectedData],
    queryFn: () => {
      const kind = selectedData?.kind;
      const path =
        kind === "Customers"
          ? "customers"
          : kind === "Orders"
            ? "orders"
            : kind === "Inventory"
              ? "inventory"
              : "tickets";
      return api(`/api/${path}/${selectedData?.id}`);
    },
    enabled: !!token && !!selectedData && selectedData.kind === active,
  });
  const start = useMutation({
    mutationFn: () =>
      api("/api/runs", {
        method: "POST",
        body: JSON.stringify({ request: input }),
      }),
    onSuccess: (x) => {
      setRun(x.id);
      qc.invalidateQueries();
    },
  });
  const act = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: "approve" | "reject" }) =>
      api(`/api/proposals/${id}/${verb}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries();
      if (run) qc.invalidateQueries({ queryKey: ["detail", run] });
    },
  });
  const revise = useMutation({
    mutationFn: ({ id, message }: { id: string; message: string }) =>
      api(`/api/proposals/${id}/revise`, {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
    onSuccess: (x) => {
      setReviseOpen(false);
      setRevisionText("");
      setRun(x.new_run_id);
      qc.invalidateQueries();
    },
  });
  useEffect(() => {
    if (!token || !run) return;
    const controller = new AbortController();
    let stopped = false;
    let lastEventId = 0;
    const pump = async () => {
      try {
        const response = await fetch(`/api/runs/${run}/stream`, {
          headers: {
            Authorization: `Bearer ${token}`,
            ...(lastEventId ? { "Last-Event-ID": String(lastEventId) } : {}),
          },
          signal: controller.signal,
        });
        if (!response.ok || !response.body)
          throw new Error("Workflow event stream unavailable");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffered = "";
        while (!stopped) {
          const { value, done } = await reader.read();
          buffered += decoder.decode(value || new Uint8Array(), {
            stream: !done,
          });
          const blocks = buffered.split("\n\n");
          buffered = blocks.pop() || "";
          for (const block of blocks) {
            const id = block.match(/^id: (\d+)$/m);
            if (id) lastEventId = Math.max(lastEventId, Number(id[1]));
            if (block.includes("event:")) {
              qc.invalidateQueries({ queryKey: ["detail", run] });
              qc.invalidateQueries({ queryKey: ["runs"] });
              qc.invalidateQueries({ queryKey: ["dashboard"] });
            }
          }
          if (done) break;
        }
      } catch (e) {
        if (!stopped) {
          await new Promise((r) => setTimeout(r, 1200));
          if (!stopped) pump();
        }
      }
    };
    pump();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [token, run, qc]);
  const signIn = async (value: string) => {
    const x = await api("/api/auth/session", {
      method: "POST",
      body: JSON.stringify({ token: value }),
    });
    localStorage.setItem("token", x.token);
    localStorage.setItem("role", x.role);
    setRole(x.role);
    setToken(x.token);
  };
  const stats = { ...dash.data?.counts, ...dash.data };
  const nav = [
    ["Overview", LayoutDashboard],
    ["Workspace", Activity],
    ["Approvals", ShieldCheck],
    ["Orders", Package],
    ["Customers", Users],
    ["Inventory", Boxes],
    ["Tickets", Ticket],
    ["Evaluations", FileCheck2],
    ["Settings", Settings2],
  ] as const;
  const current = detail.data;
  const proposal = current?.proposal;
  const tableRows = useMemo(() => {
    const rows = [...(data.data?.items || [])];
    const q = search.trim().toLowerCase();
    const filtered = q
      ? rows.filter((row: Obj) =>
          Object.values(row).some((v) =>
            String(v ?? "")
              .toLowerCase()
              .includes(q),
          ),
        )
      : rows;
    if (sort)
      filtered.sort((a: Obj, b: Obj) =>
        String(a[sort] ?? "").localeCompare(String(b[sort] ?? ""), undefined, {
          numeric: true,
        }),
      );
    return filtered;
  }, [data.data, search, sort]);
  const pageSize = 20;
  const pageRows = tableRows;
  const matchingTotal = data.data?.total || 0;
  if (!token) return <Login onLogin={signIn} />;
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <div className="mark">O</div>
          <div>
            <b>OpsAgent</b>
            <small>OPERATIONS INTELLIGENCE</small>
          </div>
        </div>
        <div className="tenant">
          <span className="dot" /> NORTHSTAR COMMERCE <ChevronRight size={14} />
        </div>
        <label className="nav-label">WORKSPACE</label>
        <nav>
          {nav.map(([label, Icon]) => (
            <button
              key={label}
              className={active === label ? "selected" : ""}
              onClick={() => setActive(label)}
            >
              <Icon size={17} />
              {label}
              {label === "Approvals" && dash.data?.pending_approvals > 0 && (
                <i>{dash.data.pending_approvals}</i>
              )}
            </button>
          ))}
        </nav>
        <div className="aside-bottom">
          <div className="local">
            <span /> LOCAL DEMO <b>●</b>
            <small>Synthetic data · isolated</small>
          </div>
          <button
            className="profile"
            onClick={() => {
              localStorage.removeItem("token");
              localStorage.removeItem("role");
              setToken("");
            }}
          >
            <div className="avatar">OP</div>
            <div>
              <b>Local {role === "operator" ? "Operator" : "Auditor"}</b>
              <small>
                {role === "operator" ? "Approval access" : "Read-only access"}
              </small>
            </div>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span>Northstar Commerce</span>
            <ChevronRight size={13} />
            <b>{active}</b>
          </div>
          <div className="head-right">
            <span className="healthy">
              <i /> LOCAL DEMO INSTANCE
            </span>
            <button
              className="icon-btn"
              onClick={() => qc.invalidateQueries()}
              aria-label="Refresh"
            >
              <RefreshCw size={16} />
            </button>
            <div className="avatar">OP</div>
          </div>
        </header>
        <div className="content">
          <div className="welcome">
            <div>
              <div className="eyebrow">
                TUESDAY, NOVEMBER 10, 2026 <span>·</span> LOCAL ENVIRONMENT
              </div>
              <h1>
                {active === "Overview" ? "Good morning, Operator" : active}
              </h1>
              <p>
                {active === "Overview"
                  ? "Your operations are ready for review. Here’s what’s happening today."
                  : "Inspect the local Northstar Commerce workspace."}
              </p>
            </div>
            <div className="tag">
              <span /> SYNTHETIC DATA
            </div>
          </div>
          {active === "Overview" || active === "Workspace" ? (
            <>
              <div className="metrics">
                {[
                  [
                    "Total orders",
                    stats.orders || 0,
                    Package,
                    "Synthetic demo records",
                  ],
                  [
                    "Delayed orders",
                    stats.delayed_orders || 0,
                    Clock3,
                    "More than five days overdue",
                  ],
                  [
                    "Low stock products",
                    stats.low_stock || 0,
                    Boxes,
                    "At or below reorder threshold",
                  ],
                  [
                    "Open support tickets",
                    stats.open_tickets || 0,
                    Ticket,
                    "Open or in progress",
                  ],
                  [
                    "Pending approvals",
                    stats.pending_approvals || 0,
                    ShieldCheck,
                    "Requires operator review",
                  ],
                  [
                    "Verified runs",
                    stats.verified_runs || 0,
                    FileCheck2,
                    "Passed independent evaluation",
                  ],
                ].map(([label, val, Icon, note]: any) => (
                  <div className="metric" key={label}>
                    <div className="metric-top">
                      <span>{label}</span>
                      <Icon size={17} />
                    </div>
                    <strong>{val}</strong>
                    <small>
                      <em>{note}</em>
                    </small>
                  </div>
                ))}
              </div>
              <div className="columns">
                <section className="card agent-card">
                  <div className="card-title">
                    <div>
                      <div className="eyebrow">AGENT WORKSPACE</div>
                      <h2>What can I help you with?</h2>
                    </div>
                    <div className="ai-icon">
                      <Activity size={18} />
                    </div>
                  </div>
                  <p className="muted">
                    Describe a business task. OpsAgent will gather evidence,
                    prepare changes, and wait for your approval before anything
                    is written.
                  </p>
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    aria-label="Business request"
                  />
                  <div className="prompt-foot">
                    <span>
                      <LockKeyhole size={13} /> Writes always require approval
                    </span>
                    <span>{input.length}/4000</span>
                  </div>
                  <div className="suggestions">
                    <span>TRY A WORKFLOW</span>
                    <button
                      onClick={() =>
                        setInput(
                          "Find orders delayed more than five days, identify affected customers, and prepare a support ticket for each.",
                        )
                      }
                    >
                      Delayed orders <ArrowUpRight size={12} />
                    </button>
                    <button
                      onClick={() =>
                        setInput(
                          "Check whether order ORD-000001 can be fulfilled with current inventory and prepare a reservation if possible.",
                        )
                      }
                    >
                      Reserve stock <ArrowUpRight size={12} />
                    </button>
                    <button
                      onClick={() =>
                        setInput(
                          "Find unresolved high-priority delivery complaints for delayed orders and prepare escalation of matching tickets to urgent priority.",
                        )
                      }
                    >
                      Escalate tickets <ArrowUpRight size={12} />
                    </button>
                  </div>
                  <button
                    className="primary run-btn"
                    onClick={() => {
                      setRun("");
                      start.mutate();
                    }}
                    disabled={start.isPending}
                  >
                    <Play size={15} fill="currentColor" />
                    {start.isPending ? "Running…" : "Run workflow"}
                    <span>⌘ ↵</span>
                  </button>
                  {start.error && (
                    <p className="error">{(start.error as Error).message}</p>
                  )}
                </section>
                <section className="card activity-card">
                  <div className="card-title">
                    <div>
                      <div className="eyebrow">LIVE ACTIVITY</div>
                      <h2>Recent workflows</h2>
                    </div>
                    <button
                      className="text-btn"
                      onClick={() => setActive("Workspace")}
                    >
                      View all <ArrowUpRight size={13} />
                    </button>
                  </div>
                  {(runs.data?.items || []).slice(0, 5).map((r: Obj) => (
                    <button
                      className="run-row"
                      key={r.id}
                      onClick={() => setRun(r.id)}
                    >
                      <div className={"run-ico " + r.status}>
                        <Activity size={15} />
                      </div>
                      <div className="run-info">
                        <b>{r.request}</b>
                        <small>
                          {new Date(r.created_at).toLocaleString()} · {r.model}
                        </small>
                      </div>
                      <span className={"status " + r.status}>
                        {r.status.replace("_", " ")}
                      </span>
                    </button>
                  ))}
                  {!runs.data?.items?.length && (
                    <div className="empty">
                      <Clock3 />
                      <b>No workflows yet</b>
                      <span>Start an agent run to see it here.</span>
                    </div>
                  )}
                </section>
              </div>
              {current && (
                <section className="card details">
                  <div className="card-title">
                    <div>
                      <div className="eyebrow">
                        RUN DETAILS · {current.id.slice(0, 8)}
                      </div>
                      <h2>{current.status.replace("_", " ")}</h2>
                    </div>
                    <button
                      className="icon-btn"
                      onClick={() => setRun("")}
                      aria-label="Close"
                    >
                      <X size={16} />
                    </button>
                  </div>
                  {current.error && (
                    <div className="error-box">{current.error}</div>
                  )}
                  {current.report && <p>{current.report}</p>}
                  {proposal && (
                    <>
                      <h3>
                        Proposed changes · {proposal.payload.length} actions
                      </h3>
                      <div className="proposals">
                        {proposal.payload.map((a: Obj) => (
                          <div className="proposal" key={a.action_id}>
                            <div>
                              <b>
                                {a.subject ||
                                  (a.action_type === "reserve_inventory"
                                    ? `Reserve ${a.quantity} × ${a.sku}`
                                    : `Escalate ${a.ticket_number}`)}
                              </b>
                              <span>
                                {a.customer_name ||
                                  a.order_number ||
                                  a.ticket_number}{" "}
                                · {a.category || a.action_type} ·{" "}
                                {a.priority || a.new_priority}
                              </span>
                              <p>
                                {a.action_type === "reserve_inventory"
                                  ? `Before: ${a.before_available - a.before_reserved} available to reserve. After: ${a.before_available - a.before_reserved - a.quantity} available; ${a.before_reserved + a.quantity} reserved.`
                                  : a.action_type === "update_ticket_priority"
                                    ? `Priority: ${a.old_priority} → ${a.new_priority}.`
                                    : a.action_type === "create_support_ticket"
                                      ? `Before: no active ${a.category} ticket for this order. After approval: create one ${a.priority} priority ticket.`
                                      : a.description || a.reason}
                              </p>
                              <small>{a.reason}</small>
                            </div>
                          </div>
                        ))}
                      </div>
                      {proposal.status === "pending" && role === "operator" && (
                        <div className="actions">
                          <button
                            className="danger"
                            onClick={() =>
                              act.mutate({ id: proposal.id, verb: "reject" })
                            }
                            disabled={act.isPending}
                          >
                            <X size={15} /> Reject
                          </button>
                          <button
                            className="primary"
                            onClick={() =>
                              act.mutate({ id: proposal.id, verb: "approve" })
                            }
                            disabled={act.isPending}
                          >
                            <Check size={15} /> Approve all{" "}
                            {proposal.payload.length} actions
                          </button>
                        </div>
                      )}
                      {act.error && (
                        <p className="error">{(act.error as Error).message}</p>
                      )}
                      {proposal.status === "pending" && role === "operator" && (
                        <div className="revision-request">
                          <button
                            className="text-btn"
                            onClick={() => setReviseOpen(!reviseOpen)}
                          >
                            {reviseOpen ? "Cancel revision" : "Request changes"}
                          </button>
                          {reviseOpen && (
                            <>
                              <textarea
                                aria-label="Requested modifications"
                                maxLength={1000}
                                value={revisionText}
                                onChange={(e) =>
                                  setRevisionText(e.target.value)
                                }
                                placeholder="Describe what should change; the current proposal will be superseded and replanned."
                              />
                              <button
                                className="primary"
                                disabled={
                                  revisionText.trim().length < 4 ||
                                  revise.isPending
                                }
                                onClick={() =>
                                  revise.mutate({
                                    id: proposal.id,
                                    message: revisionText.trim(),
                                  })
                                }
                              >
                                Replan with changes
                              </button>
                            </>
                          )}
                          {revise.error && (
                            <p className="error">
                              {(revise.error as Error).message}
                            </p>
                          )}
                        </div>
                      )}
                      {proposal.status === "pending" && role !== "operator" && (
                        <p className="muted">
                          Read-only auditor: an operator must approve or revise
                          this proposal.
                        </p>
                      )}
                    </>
                  )}
                  <div className="eyebrow graph-label">EXECUTION GRAPH</div>
                  <WorkflowGraph
                    events={current.events || []}
                    status={current.status}
                  />
                  {current.events?.map((e: Obj) => (
                    <div className="event" key={e.id}>
                      <span className="event-dot" />
                      <b>{e.kind.replaceAll("_", " ")}</b>
                      <small>
                        {new Date(e.created_at).toLocaleTimeString()}
                      </small>
                      <code>{JSON.stringify(e.payload).slice(0, 180)}</code>
                    </div>
                  ))}
                </section>
              )}
            </>
          ) : ["Orders", "Customers", "Inventory", "Tickets"].includes(
              active,
            ) ? (
            <section className="card table-card">
              <div className="card-title">
                <div>
                  <div className="eyebrow">BUSINESS DATA</div>
                  <h2>
                    {active}{" "}
                    <small className="count">
                      {matchingTotal} matching records
                    </small>
                  </h2>
                </div>
              </div>
              <div className="data-controls">
                <label>
                  <Search size={14} />
                  <input
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPage(0);
                    }}
                    placeholder={`Search ${active.toLowerCase()}…`}
                    aria-label={`Search ${active.toLowerCase()}`}
                  />
                </label>
                <label>
                  Sort by{" "}
                  <select
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    <option value="">Default</option>
                    {Object.keys(data.data?.items?.[0] || {}).map((k) => (
                      <option key={k} value={k}>
                        {k.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {Object.keys(data.data?.items?.[0] || {})
                        .slice(0, 7)
                        .map((k) => (
                          <th key={k}>{k.replaceAll("_", " ")}</th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((r: Obj, i: number) => (
                      <tr key={r.id || i}>
                        {Object.keys(r)
                          .slice(0, 7)
                          .map((k, column) => (
                            <td key={k}>
                              {column === 0 && r.id ? (
                                <button
                                  className="record-link"
                                  onClick={() =>
                                    setSelectedData({
                                      kind: active,
                                      id: String(r.id),
                                    })
                                  }
                                >
                                  {String(r[k] ?? "—")}
                                </button>
                              ) : (
                                String(r[k] ?? "—")
                              )}
                            </td>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!data.data && (
                  <div className="empty">Loading business records…</div>
                )}
                {data.data && matchingTotal === 0 && (
                  <div className="empty">No matching records.</div>
                )}
                <div className="pagination">
                  <span>
                    Showing {matchingTotal ? page * pageSize + 1 : 0}–
                    {Math.min((page + 1) * pageSize, matchingTotal)} of{" "}
                    {matchingTotal}
                  </span>
                  <button
                    onClick={() => setPage(Math.max(0, page - 1))}
                    disabled={page === 0}
                    aria-label="Previous page"
                  >
                    <ChevronLeft size={15} />
                  </button>
                  <button
                    onClick={() =>
                      setPage(
                        Math.min(
                          Math.ceil(tableRows.length / pageSize) - 1,
                          page + 1,
                        ),
                      )
                    }
                    disabled={(page + 1) * pageSize >= matchingTotal}
                    aria-label="Next page"
                  >
                    <ChevronRight size={15} />
                  </button>
                </div>
              </div>
              {selectedData?.kind === active && recordDetail.data && (
                <section className="record-detail">
                  <div className="card-title">
                    <h3>Record details</h3>
                    <button
                      className="icon-btn"
                      onClick={() => setSelectedData(null)}
                      aria-label="Close record details"
                    >
                      <X size={15} />
                    </button>
                  </div>
                  <div className="record-fields">
                    {Object.entries(recordDetail.data).map(([key, value]) => (
                      <div className="record-field" key={key}>
                        <dt className="capitalize">
                          {key.replaceAll("_", " ")}
                        </dt>
                        <dd>
                          <RecordValue
                            name={key}
                            value={value}
                            onNavigate={(kind, id) => {
                              setActive(kind);
                              setSelectedData({ kind, id });
                            }}
                          />
                        </dd>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </section>
          ) : active === "Evaluations" ? (
            <EvaluationList />
          ) : active === "Settings" ? (
            <Settings />
          ) : (
            <section className="card empty">
              <FileCheck2 />
              <b>{active} dashboard</b>
              <span>
                Results are based on committed business records, never
                model-generated claims.
              </span>
              {active === "Approvals" &&
                (runs.data?.items || [])
                  .filter((r: Obj) => r.status === "awaiting_approval")
                  .map((r: Obj) => (
                    <button
                      className="run-row"
                      onClick={() => setRun(r.id)}
                      key={r.id}
                    >
                      {r.request} <ChevronRight />
                    </button>
                  ))}
            </section>
          )}
          <footer>
            <span>
              OpsAgent <b>v0.1.0</b>
            </span>
            <span>All business data is synthetic and stored locally</span>
            <button>
              <CircleHelp size={14} /> Help & docs
            </button>
          </footer>
        </div>
      </main>
    </div>
  );
}
function Login({ onLogin }: { onLogin: (v: string) => Promise<void> }) {
  const [value, setValue] = useState("local-operator-token");
  const [error, setError] = useState("");
  return (
    <div className="login">
      <div className="login-box">
        <div className="mark">O</div>
        <div className="eyebrow">NORTHSTAR COMMERCE</div>
        <h1>Sign in to OpsAgent</h1>
        <p>Local reference environment · Synthetic data</p>
        <label>Local access credential</label>
        <input value={value} onChange={(e) => setValue(e.target.value)} />
        <button
          className="primary"
          onClick={() => onLogin(value).catch((e) => setError(e.message))}
        >
          Continue <ChevronRight size={16} />
        </button>
        {error && <small className="error">{error}</small>}
        <small>
          Demo operator: <code>local-operator-token</code>
          <br />
          Read-only auditor: <code>local-auditor-token</code>
        </small>
      </div>
    </div>
  );
}

function Settings() {
  const query = useQuery({
    queryKey: ["public-config"],
    queryFn: () => api("/api/config/public"),
  });
  const x = query.data || {};
  const runtime = x.runtime || {};
  return (
    <section className="card settings">
      <div className="eyebrow">LOCAL CONFIGURATION</div>
      <h2>Settings</h2>
      <p className="muted">
        Effective runtime values. Change them in the service environment and
        restart the backend.
      </p>
      <dl>
        <dt>Provider</dt>
        <dd>{x.provider || "Loading…"}</dd>
        <dt>Model</dt>
        <dd>{x.model || "Loading…"}</dd>
        <dt>Temperature</dt>
        <dd>{runtime.temperature ?? "—"}</dd>
        <dt>Context size</dt>
        <dd>{runtime.num_ctx ?? "—"} tokens</dd>
        <dt>Maximum output</dt>
        <dd>{runtime.max_tokens ?? "—"} tokens</dd>
        <dt>Model timeout</dt>
        <dd>{runtime.model_timeout_seconds ?? "—"} seconds</dd>
        <dt>Execution timeout</dt>
        <dd>{runtime.execution_timeout_seconds ?? "—"} seconds</dd>
        <dt>Maximum planning iterations</dt>
        <dd>{runtime.max_iterations ?? "—"}</dd>
        <dt>Maximum tool calls</dt>
        <dd>{runtime.max_tool_calls ?? "—"}</dd>
        <dt>Maximum proposed actions</dt>
        <dd>{runtime.max_proposed_actions ?? "—"}</dd>
        <dt>Repeated call limit</dt>
        <dd>{runtime.max_identical_tool_calls ?? "—"}</dd>
        <dt>Malformed response retries</dt>
        <dd>{runtime.max_response_retries ?? "—"}</dd>
        <dt>Evaluation time</dt>
        <dd>{x.as_of || "Loading…"}</dd>
        <dt>Business data</dt>
        <dd>{x.synthetic_data ? "Synthetic and local" : "Unknown"}</dd>
        <dt>Write policy</dt>
        <dd>
          {x.writes_require_approval ? "Human approval required" : "Unknown"}
        </dd>
      </dl>
    </section>
  );
}
function EvaluationList() {
  const query = useQuery({
    queryKey: ["evaluations"],
    queryFn: () => api("/api/evaluations"),
  });
  const [open, setOpen] = useState("");
  const detail = useQuery({
    queryKey: ["evaluation", open],
    queryFn: () => api(`/api/evaluations/${open}`),
    enabled: !!open,
  });
  const exportJson = async (id: string) => {
    const value = await api(`/api/evaluations/${id}/export`);
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `business-operations-agent-evaluation-${id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className="card activity-card">
      <div className="card-title">
        <div>
          <div className="eyebrow">OBJECTIVE CHECKS</div>
          <h2>Independent evaluation results</h2>
        </div>
      </div>
      {(query.data?.items || []).map((item: Obj) => (
        <div key={item.id}>
          <button
            className="run-row"
            onClick={() => setOpen(open === item.id ? "" : item.id)}
            aria-expanded={open === item.id}
          >
            <div className={"run-ico " + item.status}>
              <FileCheck2 size={15} />
            </div>
            <div className="run-info">
              <b>{item.scenario_id.replaceAll("_", " ")}</b>
              <small>
                {item.mode} · {item.run_id.slice(0, 8)} ·{" "}
                {new Date(item.created_at).toLocaleString()}
              </small>
            </div>
            <span className={"status " + item.status}>{item.status}</span>
          </button>
          {open === item.id && detail.data && (
            <div className="evaluation-detail">
              <button className="text-btn" onClick={() => exportJson(item.id)}>
                Export JSON
              </button>
              <pre>{JSON.stringify(detail.data.result, null, 2)}</pre>
            </div>
          )}
        </div>
      ))}
      {!query.data?.items?.length && (
        <div className="empty">
          <FileCheck2 />
          <b>No completed evaluations</b>
          <span>Evaluation records appear after a workflow is verified.</span>
        </div>
      )}
    </section>
  );
}

function RecordValue({
  name,
  value,
  onNavigate,
}: {
  name: string;
  value: any;
  onNavigate: (kind: string, id: string) => void;
}) {
  const singular =
    name === "customer" ? "Customers" : name === "order" ? "Orders" : null;
  const plural =
    name === "orders"
      ? "Orders"
      : name === "tickets"
        ? "Tickets"
        : name === "order_items" || name === "reservations"
          ? "Orders"
          : null;
  const identifier = (item: Obj) =>
    name === "order_items" || name === "reservations" ? item.order_id : item.id;
  const label = (item: Obj) =>
    item.full_name ||
    item.order_number ||
    item.ticket_number ||
    item.sku ||
    item.id ||
    "Open record";
  if (singular && value?.id)
    return (
      <button
        className="record-link"
        onClick={() => onNavigate(singular, String(value.id))}
      >
        {label(value)}
      </button>
    );
  if (plural && Array.isArray(value) && value.length)
    return (
      <div className="linked-records">
        {value.map((item: Obj, index: number) => {
          const id = identifier(item);
          return id ? (
            <button
              className="record-link"
              key={id}
              onClick={() => onNavigate(plural, String(id))}
            >
              {label(item)}
            </button>
          ) : (
            <span key={index}>{JSON.stringify(item)}</span>
          );
        })}
      </div>
    );
  return Array.isArray(value) ||
    (typeof value === "object" && value !== null) ? (
    <pre>{JSON.stringify(value, null, 2)}</pre>
  ) : (
    String(value ?? "—")
  );
}
