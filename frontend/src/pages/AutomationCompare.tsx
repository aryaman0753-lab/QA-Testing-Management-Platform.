import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { compareAutomationRuns, listAutomationRuns } from "../api/automation";
import { extractErrorMessage } from "../api/client";
import { AutomationError, AutomationNav } from "../components/automation/AutomationShared";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import type { AutomationRun } from "../types/automation";

export function AutomationCompare() {
  const { projectId = "" } = useParams(); const [runs,setRuns]=useState<AutomationRun[]>([]); const [a,setA]=useState(""); const [b,setB]=useState(""); const [result,setResult]=useState<any>(null); const [error,setError]=useState("");
  useEffect(()=>{listAutomationRuns(projectId,1).then(r=>setRuns(r.data.items)).catch(e=>setError(extractErrorMessage(e)));},[projectId]);
  async function compare(){try{setError("");setResult((await compareAutomationRuns(projectId,a,b)).data);}catch(e){setError(extractErrorMessage(e));}}
  return <AppLayout><div className="page-header"><div><h1>Compare automation runs</h1><p className="muted">Factual case, duration, response-time, and failure changes.</p></div></div><AutomationNav projectId={projectId}/><section className="panel"><div className="comparison-picker"><select aria-label="Run A" value={a} onChange={e=>setA(e.target.value)}><option value="">Run A</option>{runs.map(r=><option key={r.id} value={r.id}>{r.suite_name} — {r.status} — {new Date(r.created_at).toLocaleString()}</option>)}</select><span>vs</span><select aria-label="Run B" value={b} onChange={e=>setB(e.target.value)}><option value="">Run B</option>{runs.map(r=><option key={r.id} value={r.id}>{r.suite_name} — {r.status} — {new Date(r.created_at).toLocaleString()}</option>)}</select><Button disabled={!a||!b||a===b} onClick={compare}>Compare</Button></div>{error&&<AutomationError message={error}/>}</section>{result&&<><div className="automation-stat-grid"><div><span>Total Δ</span><strong>{result.differences.total_tests}</strong></div><div><span>Passed Δ</span><strong>{result.differences.passed_tests}</strong></div><div><span>Failed Δ</span><strong>{result.differences.failed_tests}</strong></div><div><span>Duration Δ</span><strong>{result.differences.duration_ms} ms</strong></div><div><span>Response Δ</span><strong>{result.differences.average_response_time_ms} ms</strong></div><div><span>New failures</span><strong>{result.differences.new_failures.length}</strong></div></div><section className="panel"><h2>Changed failures</h2><h3>New</h3>{result.differences.new_failures.length?<ul>{result.differences.new_failures.map((x:string)=><li key={x}>{x}</li>)}</ul>:<p className="muted">None.</p>}<h3>Resolved</h3>{result.differences.resolved_failures.length?<ul>{result.differences.resolved_failures.map((x:string)=><li key={x}>{x}</li>)}</ul>:<p className="muted">None.</p>}</section></>}
  </AppLayout>;
}
