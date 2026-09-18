import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { extractErrorMessage } from "../api/client";
import { addMember, archiveProject, getProject, listMembers, removeMember, updateProject } from "../api/projects";
import { listUsers } from "../api/users";
import type { Project, ProjectMember, ProjectRole, User } from "../types";

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();

  const [project, setProject] = useState<Project | null>(null);
  const [members, setMembers] = useState<ProjectMember[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);

  function refresh() {
    if (!id) return;
    getProject(id)
      .then((response) => setProject(response.data))
      .catch(() => setNotFound(true));
    listMembers(id)
      .then((response) => setMembers(response.data))
      .catch(() => setMembers([]));
  }

  useEffect(refresh, [id]);

  const myMembership = members?.find((m) => m.user_id === user?.id);
  const isOwnerOrAdmin = user?.role === "ADMIN" || myMembership?.project_role === "OWNER";

  async function handleArchive() {
    if (!id || !window.confirm("Archive this project? It will no longer appear as active.")) return;
    try {
      const response = await archiveProject(id);
      setProject(response.data);
      showToast("Project archived.", "success");
    } catch (err) {
      showToast(extractErrorMessage(err), "error");
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!id || !window.confirm("Remove this member from the project?")) return;
    try {
      await removeMember(id, userId);
      showToast("Member removed.", "success");
      refresh();
    } catch (err) {
      showToast(extractErrorMessage(err), "error");
    }
  }

  if (notFound) {
    return (
      <AppLayout>
        <div className="empty-state">
          <h3>Project not found</h3>
          <p>It may have been removed, or you may not have access to it.</p>
          <Button onClick={() => navigate("/projects")}>Back to Projects</Button>
        </div>
      </AppLayout>
    );
  }

  if (!project) {
    return (
      <AppLayout>
        <LoadingSpinner />
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1>
            {project.name} <code className="project-key-badge">{project.key}</code>
          </h1>
          <span className={`status-badge status-${project.status.toLowerCase()}`}>{project.status}</span>
        </div>
        {isOwnerOrAdmin && (
          <div className="button-row">
            <Link className="btn btn-primary link-button" to={`/projects/${project.id}/qa-dashboard`}>QA Dashboard</Link>
            <Link className="btn btn-primary link-button" to={`/projects/${project.id}/bugs`}>View Bugs</Link>
            <Link className="btn btn-secondary link-button" to={`/projects/${project.id}/api-testing`}>API Testing</Link>
            <Link className="btn btn-secondary link-button" to={`/projects/${project.id}/load-testing`}>Load Testing</Link>
            <Link className="btn btn-secondary link-button" to={`/projects/${project.id}/automation`}>Automation</Link>
            <Button variant="secondary" onClick={() => setIsEditOpen(true)}>
              Edit
            </Button>
            {project.status === "ACTIVE" && (
              <Button variant="danger" onClick={handleArchive}>
                Archive
              </Button>
            )}
          </div>
        )}
      </div>

      {!isOwnerOrAdmin && (
        <div className="button-row project-bug-link">
          <Link className="btn btn-primary link-button" to={`/projects/${project.id}/qa-dashboard`}>QA Dashboard</Link>
          <Link className="btn btn-primary link-button" to={`/projects/${project.id}/bugs`}>View Bugs</Link>
          <Link className="btn btn-secondary link-button" to={`/projects/${project.id}/api-testing`}>API Testing</Link>
          <Link className="btn btn-secondary link-button" to={`/projects/${project.id}/load-testing`}>Load Testing</Link>
          <Link className="btn btn-secondary link-button" to={`/projects/${project.id}/automation`}>Automation</Link>
        </div>
      )}

      <section className="panel">
        <h2>Description</h2>
        <p>{project.description || <span className="muted">No description provided.</span>}</p>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Members</h2>
          {isOwnerOrAdmin && <Button onClick={() => setIsAddMemberOpen(true)}>+ Add Member</Button>}
        </div>

        {members === null ? (
          <LoadingSpinner />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Project Role</th>
                {isOwnerOrAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id}>
                  <td>{member.user.full_name}</td>
                  <td>{member.user.email}</td>
                  <td>{member.project_role}</td>
        {isOwnerOrAdmin && (
                    <td>
                      <button className="link-danger" onClick={() => handleRemoveMember(member.user_id)}>
                        Remove
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {isAddMemberOpen && id && (
        <AddMemberModal
          existingMemberIds={new Set(members?.map((m) => m.user_id))}
          onClose={() => setIsAddMemberOpen(false)}
          onAdded={() => {
            setIsAddMemberOpen(false);
            refresh();
            showToast("Member added.", "success");
          }}
          projectId={id}
        />
      )}

      {isEditOpen && (
        <EditProjectModal
          project={project}
          onClose={() => setIsEditOpen(false)}
          onSaved={(updated) => {
            setProject(updated);
            setIsEditOpen(false);
            showToast("Project updated.", "success");
          }}
        />
      )}
    </AppLayout>
  );
}

function AddMemberModal({
  projectId,
  existingMemberIds,
  onClose,
  onAdded,
}: {
  projectId: string;
  existingMemberIds: Set<string>;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [users, setUsers] = useState<User[] | null>(null);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [projectRole, setProjectRole] = useState<ProjectRole>("MEMBER");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listUsers()
      .then((response) => setUsers(response.data))
      .catch(() => setUsers([]));
  }, []);

  const availableUsers = (users ?? []).filter((u) => !existingMemberIds.has(u.id));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedUserId) {
      setError("Please select a user.");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await addMember(projectId, selectedUserId, projectRole);
      onAdded();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal title="Add Member" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}

        {users === null ? (
          <LoadingSpinner />
        ) : availableUsers.length === 0 ? (
          <p className="muted">All existing users are already members of this project.</p>
        ) : (
          <>
            <label className="field">
              <span>User</span>
              <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} required>
                <option value="" disabled>
                  Select a user
                </option>
                {availableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Project Role</span>
              <select value={projectRole} onChange={(e) => setProjectRole(e.target.value as ProjectRole)}>
                <option value="OWNER">Owner</option>
                <option value="MEMBER">Member</option>
                <option value="VIEWER">Viewer</option>
              </select>
            </label>
          </>
        )}

        <div className="modal-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting} disabled={availableUsers.length === 0}>
            Add Member
          </Button>
      </div>

      </form>
    </Modal>
  );
}

function EditProjectModal({
  project,
  onClose,
  onSaved,
}: {
  project: Project;
  onClose: () => void;
  onSaved: (project: Project) => void;
}) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await updateProject(project.id, { name, description });
      onSaved(response.data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal title="Edit Project" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="alert alert-error">{error}</div>}

        <label className="field">
          <span>Project Name</span>
          <input required value={name} onChange={(e) => setName(e.target.value)} />
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
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  );
}
