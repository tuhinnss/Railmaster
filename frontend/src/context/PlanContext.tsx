import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchPlan } from "../api/client";
import type { PlanResponse } from "../types";

interface PlanContextValue {
  plan: PlanResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  // Refetches without the loading state, so a page that just changed the
  // plan (a report, a control decision) keeps its content on screen, and
  // resolves to the new plan so that page can say what changed.
  reload: () => Promise<PlanResponse>;
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

  const reload = useCallback(
    () =>
      fetchPlan("WEEKLY").then((next) => {
        setPlan(next);
        setError(null);
        return next;
      }),
    []
  );

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PlanContext.Provider value={{ plan, loading, error, refresh: load, reload }}>
      {children}
    </PlanContext.Provider>
  );
}

export function usePlan(): PlanContextValue {
  const ctx = useContext(PlanContext);
  if (!ctx) throw new Error("usePlan must be used within a PlanProvider");
  return ctx;
}
