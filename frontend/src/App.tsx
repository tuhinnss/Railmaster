import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { PlanProvider } from "./context/PlanContext";
import Overview from "./pages/Overview";
import TaskQueue from "./pages/TaskQueue";
import WeeklyPlan from "./pages/WeeklyPlan";

const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
  marginRight: 16,
  fontWeight: isActive ? 700 : 400,
  textDecoration: "none",
  color: isActive ? "#0f172a" : "#475569",
});

export default function App() {
  return (
    <BrowserRouter>
      <PlanProvider>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "16px 20px", fontFamily: "system-ui, sans-serif" }}>
          <nav style={{ marginBottom: 20, paddingBottom: 12, borderBottom: "1px solid #e2e8f0" }}>
            <NavLink to="/" end style={navLinkStyle}>
              Overview
            </NavLink>
            <NavLink to="/tasks" style={navLinkStyle}>
              Task Queue
            </NavLink>
            <NavLink to="/plan" style={navLinkStyle}>
              Weekly Plan
            </NavLink>
          </nav>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/tasks" element={<TaskQueue />} />
            <Route path="/plan" element={<WeeklyPlan />} />
          </Routes>
        </div>
      </PlanProvider>
    </BrowserRouter>
  );
}
