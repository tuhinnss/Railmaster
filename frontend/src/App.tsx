import { useEffect, useState } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { PlanProvider } from "./context/PlanContext";
import ChooseView from "./pages/ChooseView";
import ControlOffice from "./pages/ControlOffice";
import CorridorTraffic from "./pages/CorridorTraffic";
import Overview from "./pages/Overview";
import PrintPlan from "./pages/PrintPlan";
import ReportDefect from "./pages/ReportDefect";
import TaskQueue from "./pages/TaskQueue";
import WeeklyPlan from "./pages/WeeklyPlan";
import WhatIf from "./pages/WhatIf";

type Role = "control" | "field";

// Who is looking decides which pages the nav offers. This is a view
// switcher, not access control: there is no login and every route stays
// reachable by URL -- the build spec leaves auth and roles out of scope.
// The control office owns the whole block allocation (there is no separate
// planner view for now), so it lands on the Overview.
const ROLES: Record<Role, { label: string; summary: string; links: { to: string; label: string }[] }> = {
  control: {
    label: "Control office",
    summary:
      "See the full block allocation, and grant, delay, reschedule or cancel blocks; the plan re-optimises around every decision.",
    links: [
      { to: "/overview", label: "Overview" },
      { to: "/plan", label: "Weekly Plan" },
      { to: "/control", label: "Block Decisions" },
      { to: "/tasks", label: "Task Queue" },
      { to: "/what-if", label: "What-if" },
      { to: "/traffic", label: "Corridor Traffic" },
    ],
  },
  field: {
    label: "Field staff",
    summary: "Report a defect found on the line and see where the plan puts it.",
    links: [
      { to: "/report", label: "Report Defect" },
      { to: "/tasks", label: "Task Queue" },
    ],
  },
};

const ROLE_KEY = "railmaster.viewAs";

// Remembering the last view is a per-browser convenience; storage can be
// blocked (private windows, cleared site data), and then nothing is remembered.
function storedRole(): Role | null {
  try {
    const r = localStorage.getItem(ROLE_KEY);
    if (r && r in ROLES) return r as Role;
  } catch {
    // storage unavailable
  }
  return null;
}

const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
  marginRight: 16,
  fontWeight: isActive ? 700 : 400,
  textDecoration: "none",
  color: isActive ? "#0f172a" : "#475569",
  whiteSpace: "nowrap" as const,
});

function Shell() {
  const [chosen, setChosen] = useState<Role | null>(storedRole);
  const role = chosen ?? "control";
  const location = useLocation();
  const navigate = useNavigate();

  const switchRole = (next: Role) => {
    setChosen(next);
    try {
      localStorage.setItem(ROLE_KEY, next);
    } catch {
      // storage unavailable
    }
  };

  // Opening a page directly (a bookmark, a shared link) switches to a view
  // that has it, so the nav always matches the page on screen.
  useEffect(() => {
    const path = location.pathname;
    if (ROLES[role].links.some((l) => l.to === path)) return;
    const owner = (Object.keys(ROLES) as Role[]).find((r) => ROLES[r].links.some((l) => l.to === path));
    if (owner) switchRole(owner);
  }, [location.pathname]); // not `role`: a view just picked on the first page must not be undone here

  // The first page is the view chooser itself, so it has no nav.
  const onChooser = location.pathname === "/";

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "16px 20px", fontFamily: "system-ui, sans-serif" }}>
      {/* Hidden when printing, so /print comes out as just the document. */}
      {!onChooser && (
        <nav
          className="no-print"
          style={{
            marginBottom: 20,
            paddingBottom: 12,
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            flexWrap: "wrap",
            rowGap: 6,
            alignItems: "center",
          }}
        >
          {ROLES[role].links.map((l) => (
            <NavLink key={l.to} to={l.to} style={navLinkStyle}>
              {l.label}
            </NavLink>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "#64748b", whiteSpace: "nowrap" }}>
            Viewing as <strong style={{ color: "#0f172a" }}>{ROLES[role].label}</strong> ·{" "}
            <Link to="/" style={{ color: "#475569" }}>
              change
            </Link>
          </span>
        </nav>
      )}
      <Routes>
        <Route
          path="/"
          element={
            <ChooseView
              views={(Object.keys(ROLES) as Role[]).map((key) => ({
                key,
                label: ROLES[key].label,
                summary: ROLES[key].summary,
                pages: ROLES[key].links.map((l) => l.label),
              }))}
              current={chosen}
              onChoose={(key) => {
                switchRole(key);
                navigate(ROLES[key].links[0].to);
              }}
            />
          }
        />
        <Route path="/overview" element={<Overview />} />
        <Route path="/plan" element={<WeeklyPlan />} />
        <Route path="/tasks" element={<TaskQueue />} />
        <Route path="/what-if" element={<WhatIf />} />
        <Route path="/traffic" element={<CorridorTraffic />} />
        <Route path="/report" element={<ReportDefect />} />
        <Route path="/control" element={<ControlOffice />} />
        <Route path="/print" element={<PrintPlan />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <PlanProvider>
        <Shell />
      </PlanProvider>
    </BrowserRouter>
  );
}
