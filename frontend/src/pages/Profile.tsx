import { AppLayout } from "../components/layout/AppLayout";
import { useAuth } from "../context/AuthContext";

export function Profile() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <AppLayout>
      <h1>Profile</h1>
      <section className="panel profile-card">
        <div className="avatar avatar-large">{user.full_name.charAt(0).toUpperCase()}</div>
        <dl className="profile-fields">
          <dt>Full Name</dt>
          <dd>{user.full_name}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Role</dt>
          <dd>
            <span className="status-badge">{user.role.replace("_", " ")}</span>
          </dd>
          <dt>Account Status</dt>
          <dd>{user.is_active ? "Active" : "Inactive"}</dd>
          <dt>Member Since</dt>
          <dd>{new Date(user.created_at).toLocaleDateString()}</dd>
        </dl>
      </section>
    </AppLayout>
  );
}
