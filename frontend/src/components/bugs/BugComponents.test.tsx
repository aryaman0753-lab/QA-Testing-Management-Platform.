import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { BugListItem, ProjectMember } from "../../types";
import { BugFilters } from "./BugFilters";
import { BugForm } from "./BugForm";
import { BugTable } from "./BugTable";
import { Pagination } from "./Pagination";
import { BugStatusControl } from "./BugStatusControl";

const member: ProjectMember = { id: "membership", project_id: "project", user_id: "user", project_role: "MEMBER", created_at: "2026-09-15T00:00:00Z", user: { id: "user", full_name: "Dev User", email: "dev@example.com", role: "DEVELOPER", is_active: true, created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z" } };
const bug: BugListItem = { id: "bug", project_id: "project", bug_number: 1, bug_key: "ECOM-001", title: "Checkout fails", severity: "HIGH", priority: "URGENT", status: "NEW", environment: "QA", reported_by: "reporter", assigned_to: "user", reporter: { id: "reporter", full_name: "QA User", email: "qa@example.com" }, assignee: { id: "user", full_name: "Dev User", email: "dev@example.com" }, created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z" };

describe("bug components", () => {
  it("renders the bug table with badges and route", () => {
    render(<MemoryRouter><BugTable bugs={[bug]} projectId="project" /></MemoryRouter>);
    expect(screen.getByText("ECOM-001")).toBeInTheDocument();
    expect(screen.getByText("Checkout fails").closest("a")).toHaveAttribute("href", "/projects/project/bugs/bug");
    expect(screen.getByText("URGENT")).toBeInTheDocument();
  });

  it("applies combined bug filters", async () => {
    const apply = vi.fn(); const user = userEvent.setup();
    render(<BugFilters members={[member]} value={{ page: 2 }} onApply={apply} />);
    await user.type(screen.getByLabelText("Search bugs"), "checkout");
    await user.selectOptions(screen.getByLabelText("Status"), "REOPENED");
    await user.selectOptions(screen.getByLabelText("Assignee"), "user");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(apply).toHaveBeenCalledWith(expect.objectContaining({ page: 1, search: "checkout", status: ["REOPENED"], assigned_to: "user" }));
  });

  it("validates required bug form fields", async () => {
    const submit = vi.fn();
    render(<BugForm members={[]} onSubmit={submit} onCancel={() => undefined} />);
    fireEvent.submit(screen.getByRole("button", { name: "Create Bug" }).closest("form")!);
    expect(await screen.findByText("Title and description are required.")).toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
  });

  it("navigates server-side pagination", async () => {
    const change = vi.fn(); const user = userEvent.setup();
    render(<Pagination page={2} totalPages={4} total={61} onChange={change} />);
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(change).toHaveBeenCalledWith(3);
  });

  it("submits an allowed status update", async () => {
    const change = vi.fn(); const user = userEvent.setup();
    render(<BugStatusControl allowed={["IN_PROGRESS", "WONT_FIX"]} onChange={change} />);
    await user.selectOptions(screen.getByLabelText("Change status"), "IN_PROGRESS");
    expect(change).toHaveBeenCalledWith("IN_PROGRESS");
  });
});
