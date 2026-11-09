import * as React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppProviders } from "@/app/providers";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppLayout } from "@/components/layout/AppLayout";
import { PageLoading } from "@/components/shared/PageLoading";

// Route-level code-splitting: lazy load pages on demand
const DashboardPage = React.lazy(() =>
  import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);
const ProjectsPage = React.lazy(() =>
  import("@/pages/ProjectsPage").then((m) => ({ default: m.ProjectsPage }))
);
const ProjectDetailPage = React.lazy(() =>
  import("@/pages/ProjectDetailPage").then((m) => ({ default: m.ProjectDetailPage }))
);
const HandoversPage = React.lazy(() =>
  import("@/pages/HandoversPage").then((m) => ({ default: m.HandoversPage }))
);
const ReviewStudioPage = React.lazy(() =>
  import("@/pages/ReviewStudioPage").then((m) => ({ default: m.ReviewStudioPage }))
);
const HandoverPortalPage = React.lazy(() =>
  import("@/pages/HandoverPortalPage").then((m) => ({ default: m.HandoverPortalPage }))
);
const CopilotPage = React.lazy(() =>
  import("@/pages/CopilotPage").then((m) => ({ default: m.CopilotPage }))
);
const HandoverVisualizationsPage = React.lazy(() =>
  import("@/pages/HandoverVisualizationsPage").then((m) => ({
    default: m.HandoverVisualizationsPage,
  }))
);
const PipelineRunPage = React.lazy(() =>
  import("@/pages/PipelineRunPage").then((m) => ({ default: m.PipelineRunPage }))
);
const GovernancePage = React.lazy(() =>
  import("@/pages/GovernancePage").then((m) => ({ default: m.GovernancePage }))
);
const SettingsPage = React.lazy(() =>
  import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage }))
);
const DevComponentsPage = React.lazy(() =>
  import("@/pages/DevComponentsPage").then((m) => ({ default: m.DevComponentsPage }))
);
const LoginPage = React.lazy(() =>
  import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage }))
);
const NotFoundPage = React.lazy(() =>
  import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage }))
);

export function App() {
  return (
    <ErrorBoundary>
      <AppProviders>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <React.Suspense fallback={<PageLoading />}>
            <Routes>
              {/* Public Auth Route */}
              <Route path="/login" element={<LoginPage />} />

              {/* Protected Application Routes */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                  <Route path="/handovers" element={<HandoversPage />} />
                  <Route path="/handovers/:handoverId" element={<ReviewStudioPage />} />
                  <Route path="/handovers/:handoverId/review" element={<ReviewStudioPage />} />
                  <Route path="/handovers/:handoverId/portal" element={<HandoverPortalPage />} />
                  <Route path="/handovers/:handoverId/copilot" element={<CopilotPage />} />
                  <Route
                    path="/handovers/:handoverId/timeline"
                    element={<HandoverVisualizationsPage />}
                  />
                  <Route
                    path="/handovers/:handoverId/topology"
                    element={<HandoverVisualizationsPage />}
                  />
                  <Route
                    path="/handovers/:handoverId/visualizations"
                    element={<HandoverVisualizationsPage />}
                  />
                  <Route
                    path="/handovers/:handoverId/pipeline"
                    element={<PipelineRunPage />}
                  />
                  <Route path="/governance" element={<GovernancePage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/dev/components" element={<DevComponentsPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Route>

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </React.Suspense>
        </BrowserRouter>
      </AppProviders>
    </ErrorBoundary>
  );
}
