import { useState } from "react";
import type { ApiTestResult, ExecutionStatus } from "../../types/apiTesting";

export function ExecutionBadge({ status }: { status: ExecutionStatus }) { return <span className={`execution-badge execution-${status.toLowerCase()}`}>{status}</span>; }

export function ResponseViewer({ result }: { result: ApiTestResult | null }) {
  const [tab, setTab] = useState<"body" | "headers" | "timing" | "tests">("body");
  const [copied, setCopied] = useState(false);
  if (!result) return <div className="response-empty"><h3>Response</h3><p className="muted">Send a request to inspect its response and assertion results.</p></div>;
  let body = result.response_body ?? "";
  if (result.content_type?.includes("json")) { try { body = JSON.stringify(JSON.parse(body), null, 2); } catch { /* render safely as text */ } }
  async function copyBody() { await navigator.clipboard.writeText(body); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }
  return <section className="response-viewer"><div className="response-summary"><ExecutionBadge status={result.status} /><strong>{result.status_code ?? "—"}</strong><span>{result.response_time_ms.toFixed(0)} ms</span><span>{formatBytes(result.response_size)}</span>{result.response_truncated && <span>Stored body truncated</span>}<button className="inline-link" onClick={copyBody}>{copied ? "Copied" : "Copy body"}</button></div><div className="api-tabs">{(["body", "headers", "timing", "tests"] as const).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item === "tests" ? "Test Results" : item}</button>)}</div>
    {result.error_message && <div className="alert alert-error">{result.error_message}</div>}
    {tab === "body" && <pre className="response-code">{body || "No response body."}</pre>}
    {tab === "headers" && <div className="response-headers">{Object.entries(result.response_headers).map(([key, value]) => <div key={key}><strong>{key}</strong><span>{value}</span></div>)}</div>}
    {tab === "timing" && <div className="response-headers">{Object.entries(result.timing).map(([key, value]) => <div key={key}><strong>{key.replaceAll("_", " ")}</strong><span>{value.toFixed(2)} ms</span></div>)}</div>}
    {tab === "tests" && <div className="assertion-results"><p><strong>Passed: {result.assertions_passed}</strong> · Failed: {result.assertions_failed}</p>{result.assertion_results.map((item, index) => <div className={item.passed ? "assertion-pass" : "assertion-fail"} key={index}>{item.passed ? "✓" : "✕"} {item.description}{item.expected !== null && <small> Expected: {item.expected}; Actual: {item.actual ?? "missing"}</small>}</div>)}</div>}
  </section>;
}

function formatBytes(bytes: number) { return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`; }
