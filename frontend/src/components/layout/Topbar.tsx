import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="topbar">
      <div />
      <div className="topbar-user">
        <button className="topbar-profile" onClick={() => navigate("/profile")}>
          <span className="avatar">{user?.full_name?.charAt(0).toUpperCase() ?? "?"}</span>
          <span>{user?.full_name}</span>
        </button>
        <button className="btn btn-ghost" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}
