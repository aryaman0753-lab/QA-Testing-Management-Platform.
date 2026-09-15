import { useState, type FormEvent } from "react";
import type { BugComment, User } from "../../types";
import { addBugComment, deleteBugComment, updateBugComment } from "../../api/bugs";
import { extractErrorMessage } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { Button } from "../ui/Button";

export function BugComments({ bugId, comments, currentUser, onChanged }: {
  bugId: string; comments: BugComment[]; currentUser: User; onChanged: () => void;
}) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const { showToast } = useToast();
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!text.trim()) return; setSaving(true);
    try { await addBugComment(bugId, text); setText(""); showToast("Comment added.", "success"); onChanged(); }
    catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setSaving(false); }
  }
  async function edit(comment: BugComment) {
    const next = window.prompt("Edit comment", comment.comment); if (!next?.trim()) return;
    try { await updateBugComment(bugId, comment.id, next); showToast("Comment updated.", "success"); onChanged(); }
    catch (error) { showToast(extractErrorMessage(error), "error"); }
  }
  async function remove(comment: BugComment) {
    if (!window.confirm("Delete this comment?")) return;
    try { await deleteBugComment(bugId, comment.id); showToast("Comment deleted.", "success"); onChanged(); }
    catch (error) { showToast(extractErrorMessage(error), "error"); }
  }
  return (
    <section className="panel"><h2>Comments</h2>
      <div className="comment-list">{comments.length === 0 ? <p className="muted">No comments yet.</p> : comments.map((comment) => (
        <article className="comment" key={comment.id}><div><strong>{comment.user.full_name}</strong><span className="muted"> · {new Date(comment.created_at).toLocaleString()}</span></div><p>{comment.comment}</p>
          {(comment.user_id === currentUser.id || currentUser.role === "ADMIN") && <div className="comment-actions"><button onClick={() => edit(comment)}>Edit</button><button onClick={() => remove(comment)}>Delete</button></div>}
        </article>
      ))}</div>
      <form className="comment-form" onSubmit={submit}><textarea aria-label="Write a comment" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a comment..." /><Button type="submit" isLoading={saving}>Comment</Button></form>
    </section>
  );
}
