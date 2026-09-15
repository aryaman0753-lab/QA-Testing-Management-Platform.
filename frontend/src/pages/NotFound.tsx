import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <h1>404</h1>
        <p>Page not found.</p>
        <Link to="/dashboard">Back to Dashboard</Link>
      </div>
    </div>
  );
}
