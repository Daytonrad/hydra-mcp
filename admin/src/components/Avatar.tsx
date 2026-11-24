/** A round, colored initial per connector: the same color for the same name on every page. */
export function hue(name: string): number {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

export function Avatar({ name, size = 28 }: { name: string; size?: number }) {
  return (
    <span
      className="avatar"
      aria-hidden
      style={{ width: size, height: size, fontSize: size * 0.45, ["--h" as string]: hue(name) }}
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}
