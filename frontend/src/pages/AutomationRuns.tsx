import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { allAutomationSuites, listAutomationRuns } from "../api/automation";
import { listApiEnvironments } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { AutomationError, AutomationNav, AutomationPagination, AutomationRunTable } from "../components/automation/AutomationShared";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import type { ApiEnvironment } from "../types/apiTesting";
import type { AutomationPage, AutomationRun, AutomationSuite, RunFilters } from "../types/automation";

export function AutomationRuns() {
  const { projectId = "" } = useParams(); const [search, setSearch] = useSearchParams();
  const [data, setData] = useState<AutomationPage<AutomationRun> | null>(null); const [suites, setSuites] = useState<AutomationSuite[]>([]); const [environments, setEnvironments] = useState<ApiEnvironment[]>([]); const [page, setPage] = useState(1); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const filters: RunFilters = Object.fromEntries(["suite_id", "environment_id", "status", "created_from", "created_to"].map((key) => [key, search.get(key) ?? ""]));
  const filterKey = search.toString();
  const load = useCallback(async () => { setError(""); setLoading(true); try { const { data: response } = await listAutomationRuns(projectId, page, Object.fromEntries(new URLSearchParams(filterKey))); setData(response); } catch (reason) { setError(extractErrorMessage(reason)); } finally { setLoading(false); } }, [projectId, page, filterKey]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { let active = true; Promise.all([allAutomationSuites(projectId), listApiEnvironments(projectId)]).then(([suiteResponse, envResponse]) => { if (active) { setSuites(suiteResponse); setEnvironments(envResponse.data); } }).catch((reason) => { if (active) setError(extractErrorMessage(reason)); }); return () => { active = false; }; }, [projectId]);
  function change(key: keyof RunFilters, value: string) { const next = new URLSearchParams(search); if (value) next.set(key, value); else next.delete(key); setPage(1); setSearch(next); }
  return <AppLayout><div className="page-header"><div><h1>Automation run history</h1><p className="muted">Inspect manual and scheduled executions across your project.</p></div><Button variant="secondary" disabled={loading} onClick={load}>Refresh</Button></div><AutomationNav projectId={projectId} /><section className="panel"><div className="automation-run-filters"><label className="field">Suite<select value={filters.suite_id} onChange={(e) => change("suite_id", e.target.value)}><option value="">All suites</option>{suites.map((suite) => <option key={suite.id} value={suite.id}>{suite.name}</option>)}</select></label><label className="field">Environment<select value={filters.environment_id} onChange={(e) => change("environment_id", e.target.value)}><option value="">All environments</option>{environments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field">Status<select value={filters.status} onChange={(e) => change("status", e.target.value)}><option value="">All statuses</option>{["QUEUED", "RUNNING", "PASSED", "FAILED", "CANCELLED"].map((status) => <option key={status}>{status}</option>)}</select></label><label className="field">From date<input type="date" value={filters.created_from} onChange={(e) => change("created_from", e.target.value)} /></label><label className="field">To date<input type="date" value={filters.created_to} min={filters.created_from} onChange={(e) => change("created_to", e.target.value)} /></label></div>{error && <AutomationError message={error} retry={load} />}{loading ? <LoadingSpinner /> : data && <><AutomationRunTable projectId={projectId} runs={data.items} suites={suites} /><AutomationPagination data={data} onChange={setPage} /></>}</section></AppLayout>;
}
