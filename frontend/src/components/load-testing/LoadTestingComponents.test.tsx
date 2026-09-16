import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { LoadMetric, LoadTest } from "../../types/loadTesting";
import { LoadTestForm, newLoadTest } from "./LoadTestForm";
import { RunConfirmationModal } from "./RunConfirmationModal";
import { ThresholdEditor } from "./ThresholdEditor";
import { TimeSeriesChart } from "./TimeSeriesChart";

const environment = { id: "env-1", project_id: "project-1", name: "QA", classification: "QA" as const, variables: [], created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const test: LoadTest = { ...newLoadTest("env-1"), id: "test-1", project_id: "project-1", target_type: "URL", name: "Checkout baseline", target_url: "https://qa.example.com/checkout", environment_name: "QA", environment_classification: "QA", status: "DRAFT", created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };

describe("load testing components", () => {
  it("edits nullable performance thresholds", async () => {
    const changed = vi.fn();
    render(<ThresholdEditor value={test.thresholds} onChange={changed} />);
    fireEvent.change(screen.getByLabelText("Maximum p95"), { target: { value: "500" } });
    expect(changed).toHaveBeenLastCalledWith(expect.objectContaining({ max_p95_ms: 500 }));
  });

  it("applies a safe profile and submits a load definition", async () => {
    const submitted = vi.fn(); const user = userEvent.setup();
    render(<LoadTestForm initial={{ ...newLoadTest("env-1"), name: "Scenario", target_url: "https://qa.example.com/health" }} environments={[environment]} requests={[]} busy={false} onSubmit={submitted} onCancel={() => undefined} />);
    await user.selectOptions(screen.getByLabelText("Profile"), "SMOKE"); await user.click(screen.getByRole("button", { name: "Save load test" }));
    expect(submitted).toHaveBeenCalledWith(expect.objectContaining({ profile: "SMOKE", virtual_users: 1, duration_seconds: 30, target_rps: 1 }));
  });

  it("shows production risk and requires an explicit action", async () => {
    const confirm = vi.fn(); const user = userEvent.setup();
    render(<RunConfirmationModal test={{ ...test, environment_classification: "PRODUCTION" }} busy={false} onCancel={() => undefined} onConfirm={confirm} />);
    expect(screen.getByText(/degrade or interrupt real services/i)).toBeInTheDocument(); await user.click(screen.getByRole("button", { name: /I understand/ })); expect(confirm).toHaveBeenCalledWith(true);
  });

  it("renders a time-series chart with an accessible label", () => {
    const metric: LoadMetric = { id: "m1", timestamp: "2026-01-01T00:00:00Z", active_users: 5, requests_per_second: 10, failure_rate: 0, avg_response_time: 100, p50: 80, p90: 120, p95: 140, p99: 180, total_requests: 10, failed_requests: 0 };
    render(<TimeSeriesChart metrics={[metric, { ...metric, id: "m2", timestamp: "2026-01-01T00:00:02Z", p95: 160 }]} />);
    expect(screen.getByRole("img", { name: /p95 over time/i })).toBeInTheDocument(); expect(screen.getByText(/Peak 160/)).toBeInTheDocument();
  });
});
