import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import type { ApiRequest, ApiRun, ApiTestResult } from "../../types/apiTesting";
import { ApiRequestBuilder } from "./ApiRequestBuilder";
import { BodyEditor } from "./BodyEditor";
import { CollectionTree } from "./CollectionTree";
import { EnvironmentSelector } from "./EnvironmentSelector";
import { ResponseViewer } from "./ResponseViewer";

const mocks = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), execute: vi.fn(), remove: vi.fn() }));
vi.mock("../../api/apiTesting", async () => {
  const actual = await vi.importActual<typeof import("../../api/apiTesting")>("../../api/apiTesting");
  return { ...actual, createApiRequest: mocks.create, updateApiRequest: mocks.update, executeApiRequest: mocks.execute, deleteApiRequest: mocks.remove };
});

const request: ApiRequest = {
  id: "request-1", project_id: "project-1", collection_id: "collection-1", created_by: "qa",
  created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z", name: "List users",
  description: "", method: "GET", url: "https://api.example.com/users", headers: [], query_parameters: [], body: "",
  body_type: "NONE", authentication_type: "NONE", authentication_config: {}, assertions: [], extractors: [], position: 0,
};
const result: ApiTestResult = {
  id: "result-1", test_run_id: "run-1", request_id: request.id, request_name: request.name, method: "GET",
  resolved_url: request.url, status: "FAIL", status_code: 500, response_time_ms: 125, response_size: 42, redirects: 0,
  content_type: "application/json", response_headers: { "content-type": "application/json" }, response_body: '{"error":"failed"}',
  response_truncated: false, timing: { total_ms: 125 }, assertion_results: [{ assertion_type: "STATUS_CODE", passed: false, description: "Status code equals 200", expected: "200", actual: "500" }],
  assertions_total: 1, assertions_passed: 0, assertions_failed: 1, extracted_variable_names: [], error_message: null, executed_at: "2026-09-15T00:00:00Z",
};
const run: ApiRun = { id: "run-1", project_id: "project-1", run_number: 1, run_key: "API-RUN-001", collection_id: null, request_id: request.id, collection_name: null, request_name: request.name, status: "FAIL", requests_total: 1, requests_passed: 0, requests_failed: 1, duration_ms: 125, created_by: "qa", created_at: "2026-09-15T00:00:00Z", completed_at: "2026-09-15T00:00:01Z", results: [result] };

describe("API testing components", () => {
  beforeEach(() => vi.clearAllMocks());

  it("builds and saves method, parameters, auth, body, and assertions", async () => {
    mocks.update.mockResolvedValue({ data: { ...request, method: "POST" } }); const saved = vi.fn(); const user = userEvent.setup();
    render(<ToastProvider><ApiRequestBuilder request={request} draftCollectionId={null} environmentId="env-1" canManage canExecute onSaved={saved} onDeleted={() => undefined} /></ToastProvider>);
    await user.selectOptions(screen.getByLabelText("HTTP method"), "POST");
    fireEvent.change(screen.getByLabelText("Request URL"), { target: { value: "https://api.example.com/users/{{user_id}}" } });
    await user.click(screen.getByRole("button", { name: "+ Add row" }));
    await user.type(screen.getByLabelText("Key 1"), "expand"); await user.type(screen.getByLabelText("Value 1"), "profile");
    await user.click(screen.getByRole("button", { name: "headers" })); await user.click(screen.getByRole("button", { name: "+ Add row" }));
    await user.type(screen.getByLabelText("Key 1"), "Accept"); await user.type(screen.getByLabelText("Value 1"), "application/json");
    await user.click(screen.getByRole("button", { name: "Authorization" })); await user.selectOptions(screen.getByLabelText("Authentication type"), "BEARER");
    await user.type(screen.getByPlaceholderText("{{access_token}}"), "token-value");
    await user.click(screen.getByRole("button", { name: "body" })); await user.selectOptions(screen.getByLabelText("Body type"), "JSON");
    fireEvent.change(screen.getByLabelText("Request body"), { target: { value: '{"name":"Ada"}' } });
    await user.click(screen.getByRole("button", { name: "tests" })); await user.click(screen.getByRole("button", { name: "+ Add assertion" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalled());
    expect(mocks.update.mock.calls[0][1]).toMatchObject({ method: "POST", body_type: "JSON", authentication_type: "BEARER", authentication_config: { token: "token-value" }, headers: [{ key: "Accept", value: "application/json", enabled: true }], query_parameters: [{ key: "expand", value: "profile", enabled: true }], assertions: [{ assertion_type: "STATUS_CODE", expected_value: "200" }] });
  });

  it("executes a saved request and renders response details", async () => {
    mocks.execute.mockResolvedValue({ data: run }); const user = userEvent.setup();
    render(<ToastProvider><ApiRequestBuilder request={request} draftCollectionId={null} environmentId="env-1" canManage canExecute onSaved={() => undefined} onDeleted={() => undefined} /></ToastProvider>);
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("500")).toBeInTheDocument();
    expect(mocks.execute).toHaveBeenCalledWith("request-1", "env-1");
    await user.click(screen.getByRole("button", { name: "Test Results" }));
    expect(screen.getByText(/Status code equals 200/)).toBeInTheDocument();
  });

  it("navigates a collection tree and displays safe JSON response text", async () => {
    const choose = vi.fn(); const user = userEvent.setup();
    render(<><CollectionTree collections={[{ id: "collection-1", project_id: "project-1", name: "Users", description: null, created_by: "qa", created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z", request_count: 1, requests: [request] }]} selectedRequestId="request-1" onRequest={choose} onNewCollection={() => undefined} onNewRequest={() => undefined} onRun={() => undefined} /><ResponseViewer result={result} /></>);
    await user.click(screen.getByRole("button", { name: /List users/ }));
    expect(choose).toHaveBeenCalledWith("collection-1", "request-1");
    expect(screen.getByText(/"error": "failed"/)).toBeInTheDocument();
  });

  it("validates JSON bodies and changes the selected environment", async () => {
    const bodyChange = vi.fn(); const environmentChange = vi.fn(); const user = userEvent.setup();
    render(<ToastProvider><BodyEditor type="JSON" body="{invalid" onType={() => undefined} onBody={bodyChange} /><EnvironmentSelector environments={[{ id: "env-1", project_id: "project-1", name: "QA", classification: "QA", variables: [], created_by: "qa", created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z" }]} value="" onChange={environmentChange} onManage={() => undefined} /></ToastProvider>);
    await user.click(screen.getByRole("button", { name: "Format & validate" }));
    expect(screen.getByText("Invalid JSON.")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Environment"), "env-1");
    expect(environmentChange).toHaveBeenCalledWith("env-1");
  });
});
