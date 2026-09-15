import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { createProject, listProjects } from "../api/projects";
import { extractErrorMessage } from "../api/client";
import type { Project } from "../types";

const CAN_CREATE_ROLES = new Set(["ADMIN", "QA_ENGINEER"]);

export function Projects() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  function refresh() {
    listProjects()
      .then((response) => setProjects(response.data))
      .catch(() => setProjects([]));
  }

  useEffect(refresh, []);

  const canCreate = user ? CAN_CREATE_ROLES.has(user.role) : false;

  return (
    <AppLayout>
      <div className="page-header">
        <h1>Projects</h1>
        {canCreate && <Button onClick={() => setIsModalOpen(true)}>+ Create Project</Button>}
      </div>

      {projects === null ? (
        <LoadingSpinner />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description={
            canCreate
              ? "Create your first project to get started."
              : "You are not a member of any project yet. Ask a project owner to add you."
          }
          action={canCreate ? <Button onClick={() => setIsModalOpen(true)}>+ Create Project</Button> : undefined}
        />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Project Name</th>
              <th>Project Key</th>
              <th>Status</th>
              <th>Created Date</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => (
              <tr key={project.id}>
                <td>
                  <Link to={`/projects/${project.id}`}>{project.name}</Link>
                </td>
                <td>
                  <code>{project.key}</code>
                </td>
                <td>
                  <span className={`status-badge status-${project.status.toLowerCase()}`}>{project.status}</span>
                </td>
                <td>{new Date(project.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {isModalOpen && (
        <CreateProjectModal
          onClose={() => setIsModalOpen(false)}
          onCreated={() => {
            setIsModalOpen(false);
            refresh();
            showToast("Project created.", "success");
          }}
        />
      )}
    </AppLayout>
  );
}

function CreateProjectModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createProject({ name, key, description: description || undefined });
      onCreated();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal title="Create Project" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}

        <label className="field">
          <span>Project Name</span>
          <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="E-Commerce Application" />
        </label>

        <label className="field">
          <span>Project Key</span>
          <input
            required
            value={key}
            onChange={(e) => setKey(e.target.value.toUpperCase())}
            placeholder="ECOM"
            maxLength={10}
          />
          <small>Uppercase letters and digits, e.g. "ECOM". Used as a prefix for future bug IDs.</small>
        </label>

        <label className="field">
          <span>Description</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        </label>

        <div className="modal-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting}>
            Create Project
          </Button>
        </div>
      </form>
    </Modal>
  );
}
