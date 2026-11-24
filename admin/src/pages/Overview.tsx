import { api } from "../api";
import { useLoad } from "../useLoad";

/**
 * Home: where you are in the setup (connect, grant, paste), what needs attention, and the one
 * URL your AI apps use. Every line links to the page that fixes it.
 */
export function Overview() {
  const status = useLoad(api.status);
  const accounts = useLoad(api.accounts);
  const tokens = useLoad(api.accountsStatus);
  const clients = useLoad(api.clients);
  const keyed = useLoad(api.clientsWithKey);

  const loaded = accounts.data && tokens.data && clients.data && keyed.data;
  const connected = (accounts.data ?? []).filter((a) => tokens.data?.[a.id]);
  const broken = (accounts.data ?? []).filter((a) => tokens.data && !tokens.data[a.id]);
  const services = new Set(connected.map((a) => a.upstream_id)).size;
  const granted = (clients.data ?? []).filter((c) => c.grants.length > 0);
  const withKey = (clients.data ?? []).filter((c) => keyed.data?.includes(c.id));

  const steps = [
    {
      done: connected.length > 0,
      title: "Connect your accounts",
      text:
        connected.length > 0
          ? `${connected.length} account${connected.length > 1 ? "s" : ""} on ${services} service${services > 1 ? "s" : ""}.`
          : "Pick a connector (Atlassian, Gmail, GitHub…) and log in on its own page.",
      href: "#connections",
      cta: connected.length > 0 ? "Add another" : "Add a connector",
    },
    {
      done: granted.length > 0,
      title: "Decide which app sees which account",
      text:
        granted.length > 0
          ? `${granted.map((c) => c.name).join(", ")} ${granted.length > 1 ? "have" : "has"} access.`
          : "Create a client (Claude Code, Cursor, VS Code) and drag accounts into it: read only or read + write.",
      href: "#clients",
      cta: "Open Clients",
    },
    {
      done: withKey.length > 0,
      title: "Paste the setup into your AI app",
      text:
        withKey.length > 0
          ? `Key issued for ${withKey.map((c) => c.name).join(", ")}.`
          : "In Clients, press Get setup: you get a key and a ready-to-paste config for your app.",
      href: "#clients",
      cta: "Get setup",
    },
  ];
  const next = steps.findIndex((s) => !s.done);

  return (
    <section>
      <div className="page-head">
        <div>
          <h2>{next === -1 ? "All set" : "Get started"}</h2>
          <p className="muted">
            {next === -1
              ? "Your AI apps reach every granted account through one URL. Come back here when something needs attention."
              : "Three steps, about five minutes. Each one has its own page."}
          </p>
        </div>
      </div>

      {broken.length > 0 && (
        <div className="card attention">
          <strong>
            {broken.length} account{broken.length > 1 ? "s" : ""} need{broken.length > 1 ? "" : "s"} a reconnect
          </strong>
          <p className="muted small">
            Their token expired or was revoked at the provider. Your AI apps get an error for them until you reconnect:{" "}
            {broken.map((a) => a.alias).join(", ")}.
          </p>
          <a className="button" href="#connections">
            Reconnect in Connections →
          </a>
        </div>
      )}

      {loaded && (
        <ol className="card checklist">
          {steps.map((s, i) => (
            <li key={s.title} className={s.done ? "done" : i === next ? "current" : ""}>
              <span className="check" aria-hidden>
                {s.done ? "✓" : i + 1}
              </span>
              <div>
                <strong>{s.title}</strong>
                <p className="muted small">{s.text}</p>
              </div>
              <a className={`button ${i === next ? "primary" : ""}`} href={s.href}>
                {s.cta}
              </a>
            </li>
          ))}
        </ol>
      )}

      {status.data && (
        <div className="card">
          <h3>Your hydra-mcp URL</h3>
          <p className="muted small">
            One endpoint for every app. Each app authenticates with its own key, and sees only the accounts you granted it.
          </p>
          <div className="copy-row">
            <code>{status.data.broker_endpoint}</code>
            <button onClick={() => void navigator.clipboard.writeText(status.data!.broker_endpoint)}>Copy</button>
          </div>
          <p className="muted small">
            hydra-mcp {status.data.version} · modes {status.data.modes.join(" + ")} · public URL{" "}
            <code>{status.data.public_url}</code>
          </p>
          <details>
            <summary>Router mode: one URL per account (advanced)</summary>
            <p className="muted small">
              Your app logs in directly at the provider and hydra-mcp never stores the token. No per-app grants in this
              mode.
            </p>
            {Object.keys(status.data.endpoints).length === 0 ? (
              <p className="muted small">No router endpoints yet.</p>
            ) : (
              <table>
                <tbody>
                  {Object.entries(status.data.endpoints).map(([id, url]) => (
                    <tr key={id}>
                      <td>{id}</td>
                      <td>
                        <code>{url}</code>
                      </td>
                      <td>
                        <button onClick={() => void navigator.clipboard.writeText(url)}>Copy</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </details>
        </div>
      )}
      {(status.error || accounts.error) && <p className="error">{status.error || accounts.error}</p>}
    </section>
  );
}
