import { FormEvent, useState } from "react";
import { Connector, TokenOption } from "../api";
import { Avatar } from "./Avatar";

/** What signing in looks like for each kind of provider, in one sentence. */
export function signInText(c: Connector): string {
  switch (c.auth) {
    case "oauth_dcr":
    case "oauth":
      return `One click: hydra-mcp registers itself at ${c.vendor}, then you log in on ${c.vendor}'s own page.`;
    case "oauth_preregistered":
      return `${c.vendor} does not let apps register themselves: you create an OAuth app at ${c.vendor} once (the steps are shown next), then every account is one click.`;
    default:
      return `Paste a token created at ${c.vendor}.`;
  }
}

/**
 * Everything to know before (and after) connecting a library connector: what it is, what to
 * prepare, how several accounts are told apart, pitfalls, and the vendor's official docs.
 * The same text is in docs/connectors.md (generated from the same data).
 */
export function ConnectorGuide({
  connector: c,
  checkedAt,
  signInLabel,
  startWithToken = false,
  onSignIn,
  onToken,
  onClose,
}: {
  connector: Connector;
  checkedAt?: string;
  signInLabel: string;
  startWithToken?: boolean;
  onSignIn: () => void;
  onToken: (token: string) => Promise<void>;
  onClose: () => void;
}) {
  const g = c.guide;
  const [tokenOpen, setTokenOpen] = useState(startWithToken);

  return (
    <article className="card highlight guide">
      <div className="page-head">
        <div className="conn-head">
          <Avatar name={c.name} size={40} />
          <div>
            <h3>{c.name}</h3>
            <span className="muted small">
              {c.vendor} · {c.category}
              {c.status === "preview" && <span className="badge warn">Developer Preview</span>}
            </span>
          </div>
        </div>
        <button onClick={onClose}>Close</button>
      </div>

      {g && <p className="guide-summary">{g.summary}</p>}

      <div className={`callout ${c.auth === "oauth_preregistered" ? "callout-warn" : "callout-ok"}`}>
        <strong>How you sign in</strong>
        <span>{signInText(c)}</span>
        {g?.token && (
          <span>
            Or skip the login and paste a <em>{g.token.name}</em>.
          </span>
        )}
      </div>

      {g && (
        <div className="guide-cols">
          {g.before.length > 0 && (
            <section>
              <h4>Before you start</h4>
              <ul>
                {g.before.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </section>
          )}
          {g.accounts && (
            <section>
              <h4>Several accounts</h4>
              <p>{g.accounts}</p>
            </section>
          )}
        </div>
      )}

      {g && g.gotchas.length > 0 && (
        <details className="guide-more">
          <summary>Good to know ({g.gotchas.length})</summary>
          <ul>
            {g.gotchas.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </details>
      )}

      <section>
        <h4>Official documentation</h4>
        <ul className="linklist">
          {(g?.links ?? [{ label: `${c.vendor} docs`, url: c.docs }]).map((l) => (
            <li key={l.url}>
              <a href={l.url} target="_blank" rel="noreferrer">
                {l.label} ↗
              </a>
            </li>
          ))}
        </ul>
      </section>

      {tokenOpen && g?.token ? (
        <TokenForm option={g.token} provider={c.vendor} onSubmit={onToken} onCancel={() => setTokenOpen(false)} />
      ) : (
        <div className="actions">
          <button className="primary" onClick={onSignIn}>
            {signInLabel}
          </button>
          {g?.token && <button onClick={() => setTokenOpen(true)}>Use a token instead</button>}
        </div>
      )}
      {checkedAt && <p className="muted small">Checked against {c.vendor}'s documentation on {checkedAt}.</p>}
    </article>
  );
}

/** Paste a PAT / API key. The proxy tries it against the provider before saving anything. */
export function TokenForm({
  option,
  provider,
  submitLabel = "Check and connect",
  onSubmit,
  onCancel,
}: {
  option: TokenOption;
  provider: string;
  submitLabel?: string;
  onSubmit: (token: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(token.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="token-form" onSubmit={(e) => void submit(e)}>
      <h4>Connect with a {option.name}</h4>
      <ol className="steps">
        <li>
          <p>{option.how}</p>
          <a className="button" href={option.create_url} target="_blank" rel="noreferrer">
            Create it at {provider} ↗
          </a>
        </li>
        <li>
          <label>
            Paste it here
            <input
              type="password"
              required
              autoFocus
              autoComplete="off"
              spellCheck={false}
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </label>
          <p className="muted small">
            hydra-mcp tries it against {provider} first, then stores it encrypted on this machine. It is never shown again.
          </p>
        </li>
      </ol>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="primary" disabled={busy || !token.trim()}>
          {busy ? "Checking…" : submitLabel}
        </button>
        <button type="button" onClick={onCancel}>
          Back
        </button>
      </div>
    </form>
  );
}
