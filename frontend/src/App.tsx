import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Dashboard } from "./pages/Dashboard";
import { Projects } from "./pages/Projects";
import { ProjectDetail } from "./pages/ProjectDetail";
import { Profile } from "./pages/Profile";
import { NotFound } from "./pages/NotFound";
import { ProjectBugs } from "./pages/ProjectBugs";
import { CreateBug } from "./pages/CreateBug";
import { BugDetails } from "./pages/BugDetails";
import { ApiTesting } from "./pages/ApiTesting";
import { ApiRuns } from "./pages/ApiRuns";
import { ApiRunDetails } from "./pages/ApiRunDetails";
import { LoadTesting } from "./pages/LoadTesting";
import { CreateLoadTest } from "./pages/CreateLoadTest";
import { LoadTestDetails } from "./pages/LoadTestDetails";
import { LoadRuns } from "./pages/LoadRuns";
import { LoadRunDetails } from "./pages/LoadRunDetails";
import { LoadCompare } from "./pages/LoadCompare";
import { Automation } from "./pages/Automation";
import { AutomationSuiteBuilder } from "./pages/AutomationSuiteBuilder";
import { AutomationRuns } from "./pages/AutomationRuns";
import { AutomationRunDetails } from "./pages/AutomationRunDetails";
import { AutomationSchedules } from "./pages/AutomationSchedules";
import { AutomationCompare } from "./pages/AutomationCompare";
import { AdminSystem } from "./pages/AdminSystem";
import { Integrations } from "./pages/Integrations";
import { Notifications } from "./pages/Notifications";
import { ProjectQADashboard } from "./pages/ProjectQADashboard";
import { Reports } from "./pages/Reports";

function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/login"
            element={
              <RedirectIfAuthenticated>
                <Login />
              </RedirectIfAuthenticated>
            }
          />
          <Route
            path="/register"
            element={
              <RedirectIfAuthenticated>
                <Register />
              </RedirectIfAuthenticated>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects"
            element={
              <ProtectedRoute>
                <Projects />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:projectId/bugs/new"
            element={<ProtectedRoute><CreateBug /></ProtectedRoute>}
          />
          <Route
            path="/projects/:projectId/bugs/:bugId"
            element={<ProtectedRoute><BugDetails /></ProtectedRoute>}
          />
          <Route
            path="/projects/:projectId/bugs"
            element={<ProtectedRoute><ProjectBugs /></ProtectedRoute>}
          />
          <Route path="/projects/:projectId/api-testing" element={<ProtectedRoute><ApiTesting /></ProtectedRoute>} />
          <Route path="/projects/:projectId/api-testing/collections/:collectionId" element={<ProtectedRoute><ApiTesting /></ProtectedRoute>} />
          <Route path="/projects/:projectId/api-testing/requests/:requestId" element={<ProtectedRoute><ApiTesting /></ProtectedRoute>} />
          <Route path="/projects/:projectId/api-testing/runs" element={<ProtectedRoute><ApiRuns /></ProtectedRoute>} />
          <Route path="/projects/:projectId/api-testing/runs/:runId" element={<ProtectedRoute><ApiRunDetails /></ProtectedRoute>} />
          <Route path="/projects/:projectId/load-testing" element={<ProtectedRoute><LoadTesting /></ProtectedRoute>} />
          <Route path="/projects/:projectId/load-testing/create" element={<ProtectedRoute><CreateLoadTest /></ProtectedRoute>} />
          <Route path="/projects/:projectId/load-testing/runs" element={<ProtectedRoute><LoadRuns /></ProtectedRoute>} />
          <Route path="/projects/:projectId/load-testing/runs/:runId" element={<ProtectedRoute><LoadRunDetails /></ProtectedRoute>} />
          <Route path="/projects/:projectId/load-testing/compare" element={<ProtectedRoute><LoadCompare /></ProtectedRoute>} />
          <Route path="/projects/:projectId/load-testing/:testId" element={<ProtectedRoute><LoadTestDetails /></ProtectedRoute>} />
          <Route path="/projects/:projectId/automation" element={<ProtectedRoute><Automation /></ProtectedRoute>} />
          <Route path="/projects/:projectId/automation/suites/:suiteId" element={<ProtectedRoute><AutomationSuiteBuilder /></ProtectedRoute>} />
          <Route path="/projects/:projectId/automation/runs" element={<ProtectedRoute><AutomationRuns /></ProtectedRoute>} />
          <Route path="/projects/:projectId/automation/runs/:runId" element={<ProtectedRoute><AutomationRunDetails /></ProtectedRoute>} />
          <Route path="/projects/:projectId/automation/schedules" element={<ProtectedRoute><AutomationSchedules /></ProtectedRoute>} />
          <Route path="/projects/:projectId/automation/compare" element={<ProtectedRoute><AutomationCompare /></ProtectedRoute>} />
          <Route path="/projects/:projectId/qa-dashboard" element={<ProtectedRoute><ProjectQADashboard /></ProtectedRoute>} />
          <Route path="/projects/:projectId/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/projects/:projectId/integrations" element={<ProtectedRoute><Integrations /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
          <Route path="/admin/system" element={<ProtectedRoute><AdminSystem /></ProtectedRoute>} />
          <Route
            path="/projects/:id"
            element={
              <ProtectedRoute>
                <ProjectDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
