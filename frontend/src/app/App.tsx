import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppProviders } from "@/app/providers";
import { ScaffoldPage } from "@/pages/ScaffoldPage";

export function App() {
  return (
    <AppProviders>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<ScaffoldPage />} />
          <Route path="*" element={<ScaffoldPage />} />
        </Routes>
      </BrowserRouter>
    </AppProviders>
  );
}
