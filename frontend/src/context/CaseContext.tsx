import type { ReactNode } from "react";
import { createContext, useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCaseStore } from "../stores/useCaseStore";
import { api } from "../api/client";

interface CaseContextType {
  activeCaseId: string | null;
  activeCaseNumber: string | null;
  activeCaseName: string | null;
  investigatorName: string;
  backendOnline: boolean;
  checkBackendHealth: () => void;
}

const CaseContext = createContext<CaseContextType | undefined>(undefined);

export function CaseProvider({ children }: { children: ReactNode }) {
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const investigatorName = useCaseStore((s) => s.investigatorName);

  const { data: healthData, refetch } = useQuery({
    queryKey: ["backend-health"],
    queryFn: () => api.checkHealth(),
    refetchInterval: 10000,
    staleTime: 5000,
  });

  const backendOnline = healthData?.status === "online";

  return (
    <CaseContext.Provider
      value={{
        activeCaseId,
        activeCaseNumber,
        activeCaseName,
        investigatorName,
        backendOnline,
        checkBackendHealth: () => {
          void refetch();
        },
      }}
    >
      {children}
    </CaseContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCase() {
  const context = useContext(CaseContext);
  if (!context) {
    throw new Error("useCase must be used within a CaseProvider");
  }
  return context;
}
