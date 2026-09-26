// The app's front door: pick who you are, then land on that view's first
// page. A view is only a set of pages -- there is no login in this
// prototype, and the build spec leaves auth and roles out of scope.

export interface ViewOption<K extends string> {
  key: K;
  label: string;
  summary: string;
  pages: string[];
}

export default function ChooseView<K extends string>({
  views,
  current,
  onChoose,
}: {
  views: ViewOption<K>[];
  current: K | null;
  onChoose: (key: K) => void;
}) {
  return (
    <div style={{ maxWidth: 860, margin: "40px auto 0" }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Railmaster</h1>
      <p style={{ fontSize: 14, color: "#475569", marginTop: 0 }}>
        Automatic block planning — maintenance work merged into shared track blocks, planned week by week.
      </p>

      <h2 style={{ fontSize: 15, marginTop: 32, marginBottom: 12 }}>View as</h2>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        {views.map((v) => (
          <button
            key={v.key}
            onClick={() => onChoose(v.key)}
            style={{
              flex: "1 1 240px",
              // A button centres its content vertically; cards of different
              // text lengths would then start their titles at different heights.
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-start",
              textAlign: "left",
              cursor: "pointer",
              background: "white",
              border: v.key === current ? "2px solid #0f172a" : "1px solid #cbd5e1",
              borderRadius: 10,
              padding: v.key === current ? "15px 17px" : "16px 18px",
              fontFamily: "inherit",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ fontSize: 17, fontWeight: 700, color: "#0f172a" }}>{v.label}</span>
              {v.key === current && <span style={{ fontSize: 11, color: "#64748b" }}>last used</span>}
            </div>
            <div style={{ fontSize: 13, color: "#475569", margin: "6px 0 10px" }}>{v.summary}</div>
            <div style={{ fontSize: 11.5, color: "#94a3b8" }}>{v.pages.join(" · ")}</div>
          </button>
        ))}
      </div>

      <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 20 }}>
        No login in this prototype: a view only chooses which pages you see, and you can change it at any time.
      </p>
    </div>
  );
}
