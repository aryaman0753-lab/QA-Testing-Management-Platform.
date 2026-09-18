import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getAdminSystem } from "../api/operations";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useAuth } from "../context/AuthContext";

export function AdminSystem() {
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (user?.role === "ADMIN") getAdminSystem().then((response) => setData(response.data)).catch(() => setError("System status is unavailable.")); }, [user]);
  if (user?.role !== "ADMIN") return <Navigate to="/dashboard" replace />;

  return <AppLayout>
    <div className="page-header"><div><h1>System Operations</h1><p className="muted">Runtime health, queues, workers, failures, and release state.</p></div>{data && <span className={`status-badge status-${data.status === "healthy" ? "active" : "archived"}`}>{data.status}</span>}</div>
    {error && <div className="alert alert-error">{error}</div>}
    {!data ? !error && <LoadingSpinner /> : <>
      <div className="card-grid"><div className="stat-card"><span className="stat-value">{data.database}</span><span className="stat-label">Database</span></div><div className="stat-card"><span className="stat-value">{data.redis}</span><span className="stat-label">Redis</span></div><div className="stat-card"><span className="stat-value">{data.active_jobs.automation + data.active_jobs.load_tests}</span><span className="stat-label">Active jobs</span></div><div className="stat-card"><span className="stat-value">{data.version}</span><span className="stat-label">Version / migration {data.database_migration}</span></div></div>
      <section className="panel"><h2>Workers</h2>{data.workers.length === 0 ? <p className="muted">No workers have reported a heartbeat.</p> : <table className="table"><thead><tr><th>Type</th><th>Worker</th><th>Status</th><th>Current job</th><th>Completed</th><th>Failed</th><th>Last heartbeat</th></tr></thead><tbody>{data.workers.map((row: any) => <tr key={row.worker_id}><td>{row.worker_type}</td><td><code>{row.worker_id}</code></td><td>{row.status}</td><td>{row.current_job || "-"}</td><td>{row.completed_jobs}</td><td>{row.failed_jobs}</td><td>{new Date(row.last_heartbeat).toLocaleString()}</td></tr>)}</tbody></table>}</section>
      <section className="panel"><h2>Queues and failures</h2><table className="table"><thead><tr><th>Queue</th><th>Waiting</th><th>Failures</th></tr></thead><tbody><tr><td>Automation</td><td>{data.queues.automation ?? "Unavailable"}</td><td>{data.failed_jobs.automation}</td></tr><tr><td>Load testing</td><td>{data.queues.load_testing ?? "Unavailable"}</td><td>{data.failed_jobs.load_tests}</td></tr><tr><td>Webhook delivery</td><td>{data.queues.webhooks ?? "Unavailable"}</td><td>{data.failed_jobs.webhook_deliveries}</td></tr></tbody></table></section>
      <section className="panel"><h2>Recent failures</h2>{data.recent_failures.length === 0 ? <p className="muted">No recent failures.</p> : <table className="table"><thead><tr><th>Type</th><th>Project</th><th>Message</th><th>Created</th></tr></thead><tbody>{data.recent_failures.map((row: any) => <tr key={`${row.type}-${row.id}`}><td>{row.type}</td><td><code>{row.project_id.slice(0, 8)}</code></td><td>{row.message}</td><td>{new Date(row.created_at).toLocaleString()}</td></tr>)}</tbody></table>}</section>
    </>}
  </AppLayout>;
}
