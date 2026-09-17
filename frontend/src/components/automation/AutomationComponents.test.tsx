import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ApiEnvironment } from "../../types/apiTesting";
import type { AutomationStepResult, AutomationSuite } from "../../types/automation";
import { StepResult } from "../../pages/AutomationRunDetails";
import { AutomationError } from "./AutomationShared";
import { ScheduleEditor } from "./ScheduleEditor";
import { newStep, StepEditor } from "./StepEditor";

const suite: AutomationSuite = {
  id: "suite-1", project_id: "project-1", name: "Lifecycle", description: "", environment_id: "env-qa",
  status: "ACTIVE", auto_create_bugs: false, max_retries: 1, allowed_hosts: ["qa.example.com"],
  created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", cases: [],
};
const environments: ApiEnvironment[] = [
  { id: "env-qa", project_id: "project-1", name: "QA", classification: "QA", variables: [], created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  { id: "env-prod", project_id: "project-1", name: "Production", classification: "PRODUCTION", variables: [], created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
];

describe("automation components", () => {
  it("builds each supported step type and submits assertion configuration", async () => {
    expect(["HTTP_REQUEST", "ASSERTION", "EXTRACT_VARIABLE", "SET_VARIABLE", "DELAY", "CONDITION"].map((type) => newStep(type as Parameters<typeof newStep>[0]).step_type)).toHaveLength(6);
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<StepEditor initial={newStep()} requests={[]} onSave={save} onClose={() => undefined} />);
    expect(screen.getByLabelText("Request URL")).toHaveAttribute("placeholder", "${base_url}/users/${user_id}");
    await user.selectOptions(screen.getByLabelText("Step type"), "ASSERTION");
    expect(screen.getByText(/Assertions inspect the most recent response/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Source"), "JSON_PATH");
    await user.type(screen.getByLabelText("Target"), "$.data.id");
    await user.click(screen.getByRole("button", { name: "Save step" }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({
      step_type: "ASSERTION",
      config: { assertions: [expect.objectContaining({ source: "JSON_PATH", target: "$.data.id" })] },
    }));
  });

  it("validates cron input and blocks production schedules", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    const { unmount } = render(<ScheduleEditor suites={[suite]} environments={environments} onSave={save} onClose={() => undefined} />);
    await user.clear(screen.getByLabelText(/Cron expression/));
    await user.type(screen.getByLabelText(/Cron expression/), "invalid");
    await user.click(screen.getByRole("button", { name: "Save schedule" }));
    expect(screen.getByRole("alert")).toHaveTextContent("five-field cron expression");
    expect(save).not.toHaveBeenCalled();
    unmount();

    render(<ScheduleEditor initial={{ suite_id: suite.id, environment_id: "env-prod", cron_expression: "0 9 * * *", timezone: "UTC", enabled: true }} suites={[suite]} environments={environments} onSave={save} onClose={() => undefined} />);
    expect(screen.getByText(/targets production/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save schedule" })).toBeDisabled();
  });

  it("renders final attempt assertions and masked extracted variables", () => {
    const result: AutomationStepResult = {
      id: "result-1", run_id: "run-1", case_id: "case-1", step_id: "step-1", case_name: "Read user", step_name: "Validate user",
      step_type: "ASSERTION", order_index: 1, status: "FAILED", attempt: 2, is_final: true,
      request_method: "GET", resolved_url: "https://qa.example.com/users/123", status_code: 200, response_time_ms: 42,
      assertions: [{ source: "JSON_PATH", expected: "active", actual: "disabled", passed: false, failure_message: "Assertion did not match." }],
      extracted_variables: { token: "********" }, error_message: "One or more assertions failed.", error_kind: "ASSERTION",
      started_at: "2026-01-01T00:00:00Z", completed_at: "2026-01-01T00:00:01Z",
    };
    render(<StepResult result={result} />);
    expect(screen.getByText(/Attempt 2/)).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByText("********")).toBeInTheDocument();
    expect(screen.getByText(/Secret values are masked/)).toBeInTheDocument();
  });

  it("provides a retry action for recoverable dashboard errors", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();
    render(<AutomationError message="Unable to load automation" retry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load automation");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
