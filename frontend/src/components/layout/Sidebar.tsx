import { NavLink, useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export function Sidebar() {
  const { user } = useAuth();
  const { projectId, id } = useParams(); const activeProjectId = projectId ?? id;
  const items = [
    { label: "Dashboard", to: "/dashboard" }, { label: "Projects", to: "/projects" },
    { label: "QA Overview", to: activeProjectId ? `/projects/${activeProjectId}/qa-dashboard` : "/projects" },
    { label: "Bugs", to: activeProjectId ? `/projects/${activeProjectId}/bugs` : "/projects" },
    { label: "API Tests", to: activeProjectId ? `/projects/${activeProjectId}/api-testing` : "/projects" },
    { label: "Load Tests", to: activeProjectId ? `/projects/${activeProjectId}/load-testing` : "/projects" },
    { label: "Automation", to: activeProjectId ? `/projects/${activeProjectId}/automation` : "/projects" },
    { label: "Reports", to: activeProjectId ? `/projects/${activeProjectId}/reports` : "/projects" },
    { label: "CI & Webhooks", to: activeProjectId ? `/projects/${activeProjectId}/integrations` : "/projects" },
  ];
  return <aside className="sidebar"><div className="sidebar-brand">QAHub</div><nav className="sidebar-nav">{items.map((item) => <NavLink key={item.label} to={item.to} className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}>{item.label}</NavLink>)}{user?.role === "ADMIN" && <NavLink to="/admin/system" className={({isActive})=>`nav-item${isActive?" nav-item-active":""}`}>System</NavLink>}</nav></aside>;
}
