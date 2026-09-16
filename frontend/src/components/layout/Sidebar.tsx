import { NavLink, useParams } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Dashboard", to: "/dashboard", disabled: false },
  { label: "Projects", to: "/projects", disabled: false },
  { label: "Bugs", to: "/projects", disabled: false },
  { label: "Load Tests", to: "#", disabled: true },
  { label: "Reports", to: "#", disabled: true },
  { label: "Settings", to: "#", disabled: true },
];

export function Sidebar() {
  const { projectId, id } = useParams();
  const activeProjectId = projectId ?? id;
  const items = [...NAV_ITEMS.slice(0, 3), { label: "API Tests", to: activeProjectId ? `/projects/${activeProjectId}/api-testing` : "/projects", disabled: false }, ...NAV_ITEMS.slice(3)];
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">QAHub</div>
      <nav className="sidebar-nav">
        {items.map((item) =>
          item.disabled ? (
            <span key={item.label} className="nav-item nav-item-disabled" title="Coming soon">
              {item.label}
              <span className="badge-soon">Coming Soon</span>
            </span>
          ) : (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
            >
              {item.label}
            </NavLink>
          )
        )}
      </nav>
    </aside>
  );
}
