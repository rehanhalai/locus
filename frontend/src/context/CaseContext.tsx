import React, { createContext, useContext, useEffect, useState } from "react";
import { useCaseStore } from "../stores/useCaseStore";
import { api } from "../api/client";

interface CaseContextType {
  activeCaseId: string | null;
  activeCaseNumber: string | null;
  activeCaseName: string | null;
  investigatorName: string;
  backendOnline: boolean;
  checkBackendHealth: () => Promise<void>;
}

const CaseContext = createContext<CaseContextType | undefined>(undefined);

export function CaseProvider({ children }: { children: React.ReactNode }) {
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const investigatorName = useCaseStore((s) => s.investigatorName);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);

  const checkBackendHealth = async () => {
    try {
      const health = await api.checkHealth();
      setBackendOnline(health.status === "online");
    } catch {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <CaseContext.Provider
      value={{
        activeCaseId,
        activeCaseNumber,
        activeCaseName,
        investigatorName,
        backendOnline,
        checkBackendHealth,
      }}
    >
      {children}
    </CaseContext.Provider>
  );
}

export function useCase() {
  const context = useContext(CaseContext);
  if (!context) {
    throw new Error("useCase must be used within a CaseProvider");
  }
  return context;
}
