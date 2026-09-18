import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { AuthProvider } from "../context/AuthContext";
import { ToastProvider } from "../context/ToastContext";
import { ProjectQADashboard } from "./ProjectQADashboard";
import { Reports } from "./Reports";

const mocks = vi.hoisted(() => ({ dashboard: vi.fn(), report: vi.fn(), exportReport: vi.fn() }));
vi.mock("../api/operations", async () => {
  const actual = await vi.importActual<typeof import("../api/operations")>("../api/operations");
  return { ...actual, getProjectDashboard: mocks.dashboard, getQAReport: mocks.report, exportQAReport: mocks.exportReport };
});

function wrapper(path: string, element: ReactNode) {
  return <MemoryRouter initialEntries={[path]}><AuthProvider><ToastProvider><Routes><Route path="/projects/:projectId/*" element={element} /></Routes></ToastProvider></AuthProvider></MemoryRouter>;
}

describe("operations pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.dashboard.mockResolvedValue({ data: { bugs: { open: 4 }, api_tests: { pass_rate: 92 }, automation: { failed_suites: 1, recent_runs: [] }, load_testing: { threshold_violations: 2, recent_runs: [] }, ci_cd: { failed_pipelines: 1, recent_executions: [{ run_id: "run-1", provider: "github", commit_sha: "abcdef123456", branch: "main", build_number: "10", status: "FAILED" }] } } });
    mocks.report.mockResolvedValue({ data: { test_execution: { pass_rate: 90 }, api_testing: { failures: 2 }, load_testing: { p95_ms: 450 }, bugs: { open: 4 }, automation: { flaky_tests: [{ step_id: "step-1", case_name: "Checkout", step_name: "Submit", executions: 10, pass_count: 7, fail_count: 3, failure_percentage: 30 }] } } });
  });

  it("renders unified project and CI metrics", async () => {
    render(wrapper("/projects/project-1/qa-dashboard", <ProjectQADashboard />));
    expect(await screen.findByText("92%")).toBeInTheDocument();
    expect(screen.getByText("github")).toBeInTheDocument();
    expect(screen.getByText("Failed CI runs")).toBeInTheDocument();
  });

  it("renders report summary and flaky candidates", async () => {
    render(wrapper("/projects/project-1/reports", <Reports />));
    expect(await screen.findByText("90%")).toBeInTheDocument();
    expect(screen.getByText("Checkout / Submit")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export PDF" })).toBeInTheDocument();
  });
});
