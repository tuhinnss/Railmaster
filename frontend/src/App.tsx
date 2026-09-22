import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import BlockPlans from "./pages/BlockPlans";
import Corridors from "./pages/Corridors";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">Dashboard</Link> | <Link to="/plans">Block Plans</Link> |{" "}
        <Link to="/corridors">Corridors</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/plans" element={<BlockPlans />} />
        <Route path="/corridors" element={<Corridors />} />
      </Routes>
    </BrowserRouter>
  );
}
