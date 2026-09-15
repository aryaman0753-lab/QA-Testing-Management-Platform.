import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Dashboard", to: "/dashboard", disabled: false },
  { label: "Projects", to: "/projects", disabled: false },
  { label: "Bugs", to: "#", disabled: true },
  { label: "API Tests", to: "#", disabled: true },
  { label: "Load Tests", to: "#", disabled: true },
  { label: "Reports", to: "#", disabled: true },
  { label: "Settings", to: "#", disabled: true },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">QAHub</div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) =>
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
