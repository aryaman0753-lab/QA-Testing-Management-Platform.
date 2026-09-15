import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useAuth } from "../context/AuthContext";
import { listProjects } from "../api/projects";
import type { Project } from "../types";

export function Dashboard() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    listProjects()
      .then((response) => setProjects(response.data))
      .catch(() => setProjects([]));
  }, []);

  const totalProjects = projects?.length ?? 0;
  const activeProjects = projects?.filter((p) => p.status === "ACTIVE").length ?? 0;
  const recentProjects = [...(projects ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return (
    <AppLayout>
      <h1>Welcome, {user?.full_name}</h1>

      {projects === null ? (
        <LoadingSpinner />
      ) : (
        <>
          <div className="card-grid">
            <div className="stat-card">
              <span className="stat-value">{totalProjects}</span>
              <span className="stat-label">Total Projects</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">{activeProjects}</span>
              <span className="stat-label">Active Projects</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">{user?.role.replace("_", " ")}</span>
              <span className="stat-label">Your Role</span>
            </div>
          </div>

          <section className="panel">
            <h2>Recent Projects</h2>
            {recentProjects.length === 0 ? (
              <p className="muted">
                No projects yet. <Link to="/projects">Create your first project</Link>.
              </p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Key</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {recentProjects.map((project) => (
                    <tr key={project.id}>
                      <td>
                        <Link to={`/projects/${project.id}`}>{project.name}</Link>
                      </td>
                      <td>
                        <code>{project.key}</code>
                      </td>
                      <td>
                        <span className={`status-badge status-${project.status.toLowerCase()}`}>
                          {project.status}
                        </span>
                      </td>
                      <td>{new Date(project.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </AppLayout>
  );
}
