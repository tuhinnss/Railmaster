import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { PlanProvider } from "./context/PlanContext";
import CorridorTraffic from "./pages/CorridorTraffic";
import Overview from "./pages/Overview";
import PrintPlan from "./pages/PrintPlan";
import TaskQueue from "./pages/TaskQueue";
import TimeDistance from "./pages/TimeDistance";
import WeeklyPlan from "./pages/WeeklyPlan";
import WhatIf from "./pages/WhatIf";

const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
  marginRight: 16,
  fontWeight: isActive ? 700 : 400,
  textDecoration: "none",
  color: isActive ? "#0f172a" : "#475569",
  whiteSpace: "nowrap" as const,
});

export default function App() {
  return (
    <BrowserRouter>
      <PlanProvider>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "16px 20px", fontFamily: "system-ui, sans-serif" }}>
          {/* Hidden when printing, so /print comes out as just the document. */}
          <nav
            className="no-print"
            style={{ marginBottom: 20, paddingBottom: 12, borderBottom: "1px solid #e2e8f0", display: "flex", flexWrap: "wrap", rowGap: 6 }}
          >
            <NavLink to="/" end style={navLinkStyle}>
              Overview
            </NavLink>
            <NavLink to="/plan" style={navLinkStyle}>
              Weekly Plan
            </NavLink>
            <NavLink to="/tasks" style={navLinkStyle}>
              Task Queue
            </NavLink>
            <NavLink to="/time-distance" style={navLinkStyle}>
              Time–Distance
            </NavLink>
            <NavLink to="/what-if" style={navLinkStyle}>
              What-if
            </NavLink>
            <NavLink to="/traffic" style={navLinkStyle}>
              Corridor Traffic
            </NavLink>
          </nav>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/plan" element={<WeeklyPlan />} />
            <Route path="/tasks" element={<TaskQueue />} />
            <Route path="/time-distance" element={<TimeDistance />} />
            <Route path="/what-if" element={<WhatIf />} />
            <Route path="/traffic" element={<CorridorTraffic />} />
            <Route path="/print" element={<PrintPlan />} />
          </Routes>
        </div>
      </PlanProvider>
    </BrowserRouter>
  );
}
