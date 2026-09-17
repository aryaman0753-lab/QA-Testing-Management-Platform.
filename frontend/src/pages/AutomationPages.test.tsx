import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { ToastProvider } from "../context/ToastContext";
import { Automation } from "./Automation";

const mocks = vi.hoisted(() => ({ suites: vi.fn(), statistics: vi.fn(), schedules: vi.fn(), environments: vi.fn() }));
vi.mock("../api/automation", async () => {
  const actual = await vi.importActual<typeof import("../api/automation")>("../api/automation");
  return { ...actual, listAutomationSuites: mocks.suites, getAutomationStatistics: mocks.statistics, listAutomationSchedules: mocks.schedules };
});
vi.mock("../api/apiTesting", async () => {
  const actual = await vi.importActual<typeof import("../api/apiTesting")>("../api/apiTesting");
  return { ...actual, listApiEnvironments: mocks.environments };
});

const page = { items: [{ id: "suite-1", project_id: "project-1", name: "Lifecycle", description: "", environment_id: "env-1", status: "ACTIVE", auto_create_bugs: true, max_retries: 1, allowed_hosts: ["qa.example.com"], created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 20, total_pages: 1 };
const stats = { total_suites: 1, active_schedules: 1, total_runs: 10, pass_rate: 80, failure_rate: 20, average_duration_ms: 1250, recent_runs: [], recent_failures: [], failed_trends: [{ date: "2026-01-01", count: 2 }] };

describe("automation dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.suites.mockResolvedValue({ data: page });
    mocks.statistics.mockResolvedValue({ data: stats });
    mocks.schedules.mockResolvedValue({ data: { ...page, items: [] } });
    mocks.environments.mockResolvedValue({ data: [{ id: "env-1", project_id: "project-1", name: "QA", classification: "QA", variables: [], created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }] });
  });

  it("shows suite/run analytics and applies dashboard filters", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/projects/project-1/automation"]}><AuthProvider><ToastProvider><Routes><Route path="/projects/:projectId/automation" element={<Automation />} /></Routes></ToastProvider></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole("link", { name: "Lifecycle" })).toBeInTheDocument();
    expect(screen.getByText("80.0%")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Failed runs by date" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Status"), "FAILED");
    await waitFor(() => expect(mocks.statistics).toHaveBeenLastCalledWith("project-1", expect.objectContaining({ status: "FAILED" })));
  });
});
