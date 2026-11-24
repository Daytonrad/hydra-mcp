/** An error that stays until dismissed, instead of a red line that is easy to miss. */
export function ErrorBanner({ text, onClose }: { text: string; onClose: () => void }) {
  return (
    <div className="callout callout-error" role="alert">
      <span>{text}</span>
      <button className="chip-x" onClick={onClose} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}
