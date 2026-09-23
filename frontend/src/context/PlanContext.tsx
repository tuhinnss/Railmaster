import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchPlan } from "../api/client";
import type { PlanResponse } from "../types";

interface PlanContextValue {
  plan: PlanResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const PlanContext = createContext<PlanContextValue | null>(null);

export function PlanProvider({ children }: { children: ReactNode }) {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchPlan("WEEKLY")
      .then(setPlan)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PlanContext.Provider value={{ plan, loading, error, refresh: load }}>
      {children}
    </PlanContext.Provider>
  );
}

export function usePlan(): PlanContextValue {
  const ctx = useContext(PlanContext);
  if (!ctx) throw new Error("usePlan must be used within a PlanProvider");
  return ctx;
}
