import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { CasesPage } from "./pages/CasesPage";
import { InvestigatePage } from "./pages/InvestigatePage";
import { SearchPage } from "./pages/SearchPage";
import { ExportPage } from "./pages/ExportPage";
import { AuditPage } from "./pages/AuditPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/cases" replace />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/investigate" element={<InvestigatePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="*" element={<Navigate to="/cases" replace />} />
      </Route>
    </Routes>
  );
}
