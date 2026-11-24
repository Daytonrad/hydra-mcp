import { FormEvent, useEffect, useState } from "react";
import { Account, api, ApiError, SetupGuide, TokenStatus } from "../api";
import { SetupWizard } from "../components/SetupWizard";
import { useLoad } from "../useLoad";

const EMPTY: Account = { id: "", upstream_id: "", alias: "", identity: "", enabled: true };

export function Accounts() {
  const { data, error, reload, setError } = useLoad(api.accounts);
  const upstreams = useLoad(api.upstreams);
  const tokens = useLoad(api.accountsStatus);
  const [draft, setDraft] = useState<Account>(EMPTY);
  const [notice, setNotice] = useState<string | null>(null);
  const [wizard, setWizard] = useState<{ account: Account; guide: SetupGuide } | null>(null);

  // Refresh once the login tab is done. The callback page posts "hydra-mcp:linked" to its
  // opener, but providers that send Cross-Origin-Opener-Policy (Google does) sever that link,
  // so coming back to this tab (focus) refreshes too. The message carries nothing secret and
  // only triggers a reload, so its origin is not checked (the Vite dev server is another one).
  useEffect(() => {
    const refresh = () => {
      void tokens.reload();
      void reload();
    };
    const onMessage = (e: MessageEvent) => {
      if (e.data === "hydra-mcp:linked") {
        setNotice(null);
        refresh();
      }
    };
    window.addEventListener("message", onMessage);
    window.addEventListener("focus", refresh);
    return () => {
      window.removeEventListener("message", onMessage);
      window.removeEventListener("focus", refresh);
    };
  }, [tokens.reload, reload]);

  async function connect(a: Account, opened?: Window | null) {
    // Same tab: the provider sends the browser back to the admin page once logged in.
    const tab = opened ?? null;
    try {
      const { authorize_url } = await api.linkAccount(a.id);
      if (tab) tab.location.href = authorize_url;
      else window.location.href = authorize_url;
      setWizard(null);
      setError(null);
      setNotice(`Log in as the "${a.alias}" identity in the new tab, then come back here.`);
    } catch (err) {
      tab?.close();
      if (err instanceof ApiError && err.status === 409 && err.data.guide) {
        // No automatic registration at this provider (Google): walk through the one-time setup.
        setWizard({ account: a, guide: err.data.guide as SetupGuide });
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function disconnect(a: Account) {
    if (!window.confirm(`Forget the stored token of "${a.id}"?`)) return;
    await api.unlinkAccount(a.id).catch((err: Error) => setError(err.message));
    await tokens.reload();
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.putAccount(draft);
      setDraft(EMPTY);
      await reload();
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    }
  }

  async function toggle(a: Account) {
    await api.putAccount({ ...a, enabled: !a.enabled }).catch((err: Error) => setError(err.message));
    await reload();
  }

  async function remove(id: string) {
    if (!window.confirm(`Delete account "${id}"?`)) return;
    await api.deleteAccount(id).catch((err: Error) => setError(err.message));
    await reload();
  }

  return (
    <section>
      <h2>Accounts</h2>
      <p className="muted">
        One row per identity, e.g. <code>gmail-work</code> and <code>gmail-perso</code> on the same
        upstream. <strong>Connect</strong> logs in at the provider for broker mode; the proxy keeps
        the token encrypted and uses it for the clients you grant.
      </p>
      {error && <p className="error">{error}</p>}
      {notice && <p className="ok">{notice}</p>}
      {wizard && (
        <SetupWizard
          upstreamId={wizard.account.upstream_id}
          guide={wizard.guide}
          submitLabel={`Save and sign in as "${wizard.account.alias}"`}
          openTab={false}
          onSaved={(tab) => connect(wizard.account, tab)}
          onClose={() => setWizard(null)}
        />
      )}
      <table>
        <thead>
          <tr>
            <th>Id</th>
            <th>Upstream</th>
            <th>Alias</th>
            <th>Identity</th>
            <th>Enabled</th>
            <th>Broker connection</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data?.map((a) => (
            <tr key={a.id}>
              <td>{a.id}</td>
              <td>{a.upstream_id}</td>
              <td>{a.alias}</td>
              <td>{a.identity}</td>
              <td>
                <input type="checkbox" checked={a.enabled} onChange={() => void toggle(a)} />
              </td>
              <td>
                <Connection status={tokens.data?.[a.id]} />
              </td>
              <td className="actions">
                <button onClick={() => void connect(a)}>
                  {tokens.data?.[a.id] ? "Reconnect" : "Connect"}
                </button>
                {tokens.data?.[a.id] && (
                  <button onClick={() => void disconnect(a)}>Disconnect</button>
                )}
                <button onClick={() => setDraft(a)}>Edit</button>
                <button className="danger" onClick={() => void remove(a.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="card" onSubmit={(e) => void save(e)}>
        <h3>Add or update an account</h3>
        <label>
          Id
          <input
            required
            placeholder="gmail-work"
            value={draft.id}
            onChange={(e) => setDraft({ ...draft, id: e.target.value })}
          />
        </label>
        <label>
          Upstream
          <select
            required
            value={draft.upstream_id}
            onChange={(e) => setDraft({ ...draft, upstream_id: e.target.value })}
          >
            <option value="">Choose…</option>
            {upstreams.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Alias (what the model sees)
          <input
            required
            placeholder="work"
            value={draft.alias}
            onChange={(e) => setDraft({ ...draft, alias: e.target.value })}
          />
        </label>
        <label>
          Identity hint
          <input
            placeholder="you@company.com"
            value={draft.identity}
            onChange={(e) => setDraft({ ...draft, identity: e.target.value })}
          />
        </label>
        <button type="submit">Save</button>
      </form>
    </section>
  );
}

function Connection({ status }: { status?: TokenStatus }) {
  if (!status) return <span className="muted">not connected</span>;
  const who = status.identity || "connected";
  if (status.expires_at === null) return <span className="ok">{who}</span>;
  // Access tokens are short-lived and refreshed on use; "expired" alone is not a problem.
  const left = Math.round((status.expires_at * 1000 - Date.now()) / 60000);
  return (
    <span className="ok" title={`access token ${left > 0 ? `valid ${left} min` : "refreshed on next use"}`}>
      {who}
    </span>
  );
}
