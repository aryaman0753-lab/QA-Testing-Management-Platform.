import { useEffect, useState } from "react";
import type { BugAttachment, User } from "../../types";
import { deleteAttachment, downloadAttachment, uploadBugAttachment } from "../../api/bugs";
import { extractErrorMessage } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { Modal } from "../ui/Modal";

export function AttachmentList({ bugId, attachments, currentUser, canUpload, onChanged }: {
  bugId: string; attachments: BugAttachment[]; currentUser: User; canUpload: boolean; onChanged: () => void;
}) {
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const { showToast } = useToast();
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  async function open(item: BugAttachment) {
    try {
      const response = await downloadAttachment(item.id); const url = URL.createObjectURL(response.data);
      if (item.mime_type.startsWith("image/")) setPreview({ url, name: item.file_name }); else { const link = document.createElement("a"); link.href = url; link.download = item.file_name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    } catch (error) { showToast(extractErrorMessage(error), "error"); }
  }
  async function upload(files: FileList | null) {
    if (!files?.length) return; setUploading(true);
    try { for (const file of Array.from(files)) await uploadBugAttachment(bugId, file); showToast("Attachment uploaded.", "success"); onChanged(); }
    catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setUploading(false); }
  }
  async function remove(item: BugAttachment) {
    if (!window.confirm(`Delete ${item.file_name}?`)) return;
    try { await deleteAttachment(item.id); showToast("Attachment deleted.", "success"); onChanged(); }
    catch (error) { showToast(extractErrorMessage(error), "error"); }
  }
  return <section className="panel"><div className="panel-header"><h2>Attachments</h2>{canUpload && <label className="btn btn-secondary file-button">{uploading ? "Uploading..." : "+ Add evidence"}<input disabled={uploading} type="file" multiple onChange={(e) => upload(e.target.files)} /></label>}</div>
    {attachments.length === 0 ? <p className="muted">No evidence attached.</p> : <div className="attachment-list">{attachments.map((item) => <div className="attachment-row" key={item.id}><button onClick={() => open(item)}>{item.mime_type.startsWith("image/") ? "▧" : "▤"} {item.file_name}</button><span className="muted">{Math.ceil(item.file_size / 1024)} KB · {item.uploader.full_name}</span>{(item.uploaded_by === currentUser.id || currentUser.role === "ADMIN") && <button className="link-danger" onClick={() => remove(item)}>Delete</button>}</div>)}</div>}
    {preview && <Modal wide title={preview.name} onClose={() => setPreview(null)}><img className="attachment-preview" src={preview.url} alt={preview.name} /></Modal>}
  </section>;
}
