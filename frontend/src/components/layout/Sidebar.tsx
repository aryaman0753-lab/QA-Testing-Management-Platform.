import { NavLink, useParams } from "react-router-dom";

export function Sidebar() {
  const { projectId, id } = useParams(); const activeProjectId = projectId ?? id;
  const items = [
    { label: "Dashboard", to: "/dashboard" }, { label: "Projects", to: "/projects" },
    { label: "Bugs", to: activeProjectId ? `/projects/${activeProjectId}/bugs` : "/projects" },
    { label: "API Tests", to: activeProjectId ? `/projects/${activeProjectId}/api-testing` : "/projects" },
    { label: "Load Tests", to: activeProjectId ? `/projects/${activeProjectId}/load-testing` : "/projects" },
  ];
  return <aside className="sidebar"><div className="sidebar-brand">QAHub</div><nav className="sidebar-nav">{items.map((item) => <NavLink key={item.label} to={item.to} className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}>{item.label}</NavLink>)}<span className="nav-item nav-item-disabled" title="Coming soon">Reports<span className="badge-soon">Coming Soon</span></span><span className="nav-item nav-item-disabled" title="Coming soon">Settings<span className="badge-soon">Coming Soon</span></span></nav></aside>;
}
