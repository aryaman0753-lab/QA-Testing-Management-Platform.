import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BugAttachment, BugComment, User } from "../../types";
import { ToastProvider } from "../../context/ToastContext";
import { AttachmentList } from "./AttachmentList";
import { BugComments } from "./BugComments";

const mocks = vi.hoisted(() => ({ addComment: vi.fn(), upload: vi.fn(), download: vi.fn(), removeAttachment: vi.fn() }));
vi.mock("../../api/bugs", async () => {
  const actual = await vi.importActual<typeof import("../../api/bugs")>("../../api/bugs");
  return { ...actual, addBugComment: mocks.addComment, uploadBugAttachment: mocks.upload, downloadAttachment: mocks.download, deleteAttachment: mocks.removeAttachment };
});

const currentUser: User = { id: "me", full_name: "QA User", email: "qa@example.com", role: "QA_ENGINEER", is_active: true, created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z" };
const comment: BugComment = { id: "comment", bug_id: "bug", user_id: "me", comment: "Working on it", created_at: "2026-09-15T00:00:00Z", updated_at: "2026-09-15T00:00:00Z", user: currentUser };
const attachment: BugAttachment = { id: "attachment", bug_id: "bug", uploaded_by: "me", file_name: "evidence.png", file_size: 100, mime_type: "image/png", created_at: "2026-09-15T00:00:00Z", uploader: currentUser, download_url: "/download" };

describe("bug interactions", () => {
  beforeEach(() => vi.clearAllMocks());
  it("submits a plain-text comment", async () => {
    mocks.addComment.mockResolvedValue({}); const changed = vi.fn(); const user = userEvent.setup();
    render(<ToastProvider><BugComments bugId="bug" comments={[comment]} currentUser={currentUser} onChanged={changed} /></ToastProvider>);
    await user.type(screen.getByLabelText("Write a comment"), "Fixed in build 12");
    await user.click(screen.getByRole("button", { name: "Comment" }));
    await waitFor(() => expect(mocks.addComment).toHaveBeenCalledWith("bug", "Fixed in build 12"));
    expect(changed).toHaveBeenCalled();
  });

  it("renders attachment evidence and uploads selected files", async () => {
    mocks.upload.mockResolvedValue({}); const changed = vi.fn();
    const { container } = render(<ToastProvider><AttachmentList bugId="bug" attachments={[attachment]} currentUser={currentUser} canUpload onChanged={changed} /></ToastProvider>);
    expect(screen.getByText(/evidence.png/)).toBeInTheDocument();
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    fireEvent.change(container.querySelector("input[type=file]")!, { target: { files: [file] } });
    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith("bug", file));
    expect(changed).toHaveBeenCalled();
  });
});
