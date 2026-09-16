import { useState } from "react";
import type { BodyType } from "../../types/apiTesting";
import { useToast } from "../../context/ToastContext";

export function BodyEditor({ type, body, onType, onBody }: { type: BodyType; body: string; onType: (type: BodyType) => void; onBody: (body: string) => void }) {
  const [error, setError] = useState<string | null>(null); const { showToast } = useToast();
  function format() { try { onBody(JSON.stringify(JSON.parse(body), null, 2)); setError(null); } catch { setError("Invalid JSON."); } }
  async function copy() { await navigator.clipboard.writeText(body); showToast("Body copied.", "success"); }
  return <div><label className="field"><span>Body type</span><select aria-label="Body type" value={type} onChange={(e) => onType(e.target.value as BodyType)}>{["NONE", "JSON", "FORM_URLENCODED", "MULTIPART_FORM_DATA", "RAW"].map((item) => <option key={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
    {type !== "NONE" && <><div className="editor-actions">{type !== "RAW" && <button onClick={format}>Format & validate</button>}<button onClick={copy}>Copy</button><button onClick={() => onBody("")}>Clear</button></div><textarea aria-label="Request body" className="code-editor" rows={12} value={body} onChange={(e) => { onBody(e.target.value); setError(null); }} placeholder={type === "RAW" ? "Raw request body" : '{\n  "key": "value"\n}'} />{error && <div className="alert alert-error">{error}</div>}</>}
  </div>;
}
