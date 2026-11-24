import { FormEvent, useEffect, useState } from "react";
import { getToken, setToken, UNAUTHORIZED_EVENT } from "./api";
import { Tab } from "./nav";
import { Accounts } from "./pages/Accounts";
import { Clients } from "./pages/Clients";
import { Connections } from "./pages/Connections";
import { Overview } from "./pages/Overview";
import { Upstreams } from "./pages/Upstreams";

/** Raw servers and accounts, including ones without a login yet (router mode, debugging). */
function Advanced() {
  return (
    <>
      <Upstreams />
      <Accounts />
    </>
  );
}

const TABS = {
  home: { label: "Home", Page: Overview },
  connections: { label: "Connections", Page: Connections },
  clients: { label: "Clients", Page: Clients },
  advanced: { label: "Advanced", Page: Advanced },
} as const satisfies Record<Tab, unknown>;

/** `hydra-mcp serve` prints /admin/#token=…: one click logs in, then the token leaves the URL. */
function takeTokenFromHash(): boolean {
  const m = window.location.hash.match(/token=([^&]+)/);
  if (!m) return false;
  setToken(decodeURIComponent(m[1]));
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return true;
}

function Login({ onLogin, rejected }: { onLogin: () => void; rejected: boolean }) {
  const [value, setValue] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setToken(value.trim());
    onLogin();
  }
  return (
    <form className="card login" onSubmit={submit}>
      <h2>Open the admin page</h2>
      {rejected && <p className="callout callout-warn">That admin token was not accepted. Paste the current one.</p>}
      <p className="muted">
        Easiest: open the <strong>admin page</strong> link that <code>hydra-mcp serve</code> prints in the terminal, it
        logs you in directly. Or paste the token printed by:
      </p>
      <pre>hydra-mcp admin-token</pre>
      <label>
        Admin token
        <input autoFocus type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} />
      </label>
      <button type="submit" className="primary">
        Open
      </button>
    </form>
  );
}

export function App() {
  const [authed, setAuthed] = useState(() => takeTokenFromHash() || getToken() !== "");
  const [rejected, setRejected] = useState(false);
  // The tab lives in the URL hash (#clients): reload and the back button keep your place, and
  // pages can link to each other with a plain <a href="#clients">.
  const fromHash = (): Tab => {
    // Back from a provider sign-in (?connected=…): always Connections, to name the account.
    if (new URLSearchParams(window.location.search).has("connected")) return "connections";
    const h = window.location.hash.replace(/^#\/?/, "");
    return h in TABS ? (h as Tab) : "home";
  };
  const [tab, setTabState] = useState<Tab>(fromHash);
  useEffect(() => {
    const onHash = () => {
      if (takeTokenFromHash()) setAuthed(true);
      setTabState(fromHash());
    };
    // Wrong or rotated admin token: back to the login card instead of errors on every page.
    const onUnauthorized = () => {
      setAuthed(false);
      setRejected(true);
    };
    window.addEventListener("hashchange", onHash);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    };
  }, []);
  useEffect(() => {
    document.title = authed ? `${TABS[tab].label} · hydra-mcp` : "hydra-mcp admin";
  }, [tab, authed]);
  const setTab = (t: Tab) => {
    window.location.hash = t;
    setTabState(t);
  };
  const { Page } = TABS[tab];

  return (
    <div className="layout">
      <header>
        <h1>
          <Logo />
          hydra-mcp
        </h1>
        {authed && (
          <nav>
            {(Object.keys(TABS) as Tab[]).map((t) => (
              <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>
                {TABS[t].label}
              </button>
            ))}
          </nav>
        )}
        {authed && (
          <button
            className="ghost logout"
            title="Forget the admin token in this browser"
            onClick={() => {
              setToken("");
              setRejected(false);
              setAuthed(false);
            }}
          >
            Log out
          </button>
        )}
      </header>
      <main>
        {authed ? (
          <Page key={tab} />
        ) : (
          <Login
            rejected={rejected}
            onLogin={() => {
              setRejected(false);
              setAuthed(true);
            }}
          />
        )}
      </main>
    </div>
  );
}

/** Three heads, one body. */
function Logo() {
  return (
    <svg className="logo" viewBox="0 0 32 32" aria-hidden>
      <path d="M16 30 V18 M16 18 C16 12 8 12 7 7 M16 18 C16 12 24 12 25 7 M16 18 V6" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
      <circle cx="7" cy="6" r="3.2" fill="var(--accent)" />
      <circle cx="16" cy="5" r="3.2" fill="var(--accent)" />
      <circle cx="25" cy="6" r="3.2" fill="var(--accent)" />
    </svg>
  );
}
