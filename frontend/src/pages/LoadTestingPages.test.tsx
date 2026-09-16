import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../context/ToastContext";
import { AuthProvider } from "../context/AuthContext";
import type { LoadRunDetail } from "../types/loadTesting";
import { LoadCompare } from "./LoadCompare";
import { LoadRunDetails } from "./LoadRunDetails";

const mocks = vi.hoisted(() => ({ getRun: vi.fn(), stop: vi.fn(), baseline: vi.fn(), report: vi.fn(), list: vi.fn(), compare: vi.fn() }));
vi.mock("../api/loadTesting", async () => {
  const actual = await vi.importActual<typeof import("../api/loadTesting")>("../api/loadTesting");
  return { ...actual, getLoadRun: mocks.getRun, stopLoadRun: mocks.stop, markLoadBaseline: mocks.baseline, downloadLoadReport: mocks.report, listLoadRuns: mocks.list, compareLoadRuns: mocks.compare };
});

const run: LoadRunDetail = {
  id: "run-1", load_test_id: "test-1", project_id: "project-1", run_number: 1, run_key: "LOAD-RUN-001", load_test_name: "Checkout baseline", status: "RUNNING", result_status: null,
  started_at: "2026-01-01T00:00:00Z", completed_at: null, virtual_users: 10, spawn_rate: 2, duration_seconds: 30,
  total_requests: 100, successful_requests: 99, failed_requests: 1, requests_per_second: 20, failure_rate: 1,
  avg_response_time: 100, min_response_time: 30, max_response_time: 400, median_response_time: 80, p50_response_time: 80,
  p75_response_time: 100, p90_response_time: 130, p95_response_time: 160, p99_response_time: 250,
  status_distribution: { "2xx": 99, "5xx": 1 }, error_summary: { "HTTP 5xx": 1 }, threshold_results: [],
  config_snapshot: {}, is_baseline: false, error_message: null, created_by: "user-1", created_at: "2026-01-01T00:00:00Z",
  metrics: [{ id: "metric-1", timestamp: "2026-01-01T00:00:01Z", active_users: 10, requests_per_second: 20, failure_rate: 1, avg_response_time: 100, p50: 80, p90: 130, p95: 160, p99: 250, total_requests: 100, failed_requests: 1 }],
  endpoints: [], errors: [],
};

describe("load testing pages", () => {
  beforeEach(() => { vi.clearAllMocks(); mocks.getRun.mockResolvedValue({ data: run }); mocks.stop.mockResolvedValue({ data: { ...run, status: "STOPPING" } }); vi.spyOn(window, "confirm").mockReturnValue(true); });

  it("polls and presents live metrics, separate charts, stop, report, and bug controls", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/projects/project-1/load-testing/runs/run-1"]}><AuthProvider><ToastProvider><Routes><Route path="/projects/:projectId/load-testing/runs/:runId" element={<LoadRunDetails />} /></Routes></ToastProvider></AuthProvider></MemoryRouter>);
    expect(await screen.findByText(/Live metrics refresh/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /p95 over time/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /requests_per_second over time/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /active_users over time/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /failure_rate over time/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create bug" })).toHaveAttribute("href", "/projects/project-1/bugs/new?source_load_run=run-1");
    await user.click(screen.getByRole("button", { name: "Stop run" }));
    await waitFor(() => expect(mocks.stop).toHaveBeenCalledWith("run-1"));
  });

  it("selects two completed runs and displays a descriptive comparison", async () => {
    const candidate = { ...run, id: "run-2", run_number: 2, run_key: "LOAD-RUN-002", status: "COMPLETED" as const, result_status: "PASS" as const };
    const baseline = { ...run, status: "COMPLETED" as const, result_status: "PASS" as const, is_baseline: true };
    mocks.list.mockResolvedValue({ data: { items: [candidate, baseline], page: 1, page_size: 20, total: 2, total_pages: 1 } });
    mocks.compare.mockResolvedValue({ data: { run_a: baseline, run_b: candidate, metrics: [{ metric: "p95_response_time", run_a: 160, run_b: 180, difference: 20, percent_change: 12.5 }] } });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/projects/project-1/load-testing/compare"]}><AuthProvider><ToastProvider><Routes><Route path="/projects/:projectId/load-testing/compare" element={<LoadCompare />} /></Routes></ToastProvider></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Compare" })).toBeEnabled(); await user.click(screen.getByRole("button", { name: "Compare" }));
    expect(await screen.findByText("p95 response time")).toBeInTheDocument(); expect(screen.getByText("+20.00 (12.5%)")).toBeInTheDocument();
  });
});
