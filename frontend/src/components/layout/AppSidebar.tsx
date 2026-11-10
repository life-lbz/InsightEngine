import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";
import { authApi } from "../../api/auth";

export interface NavItem {
  to: string;
  label: string;
  icon: string;
}

export interface NavGroup {
  label: string;
  icon: string;
  items: NavItem[];
}

export type SidebarAccent = "indigo" | "amber" | "cyan";

interface AccentConfig {
  active: string;
  bar: string;
  user: string;
  text: string;
}

const ACCENTS: Record<SidebarAccent, AccentConfig> = {
  indigo: {
    active: "bg-indigo-50 text-indigo-600",
    bar: "bg-indigo-600",
    user: "bg-indigo-100",
    text: "text-indigo-600",
  },
  amber: {
    active: "bg-amber-50 text-amber-700",
    bar: "bg-amber-500",
    user: "bg-amber-100",
    text: "text-amber-600",
  },
  cyan: {
    active: "bg-cyan-50 text-cyan-700",
    bar: "bg-cyan-500",
    user: "bg-cyan-100",
    text: "text-cyan-600",
  },
};

const chevronIcon = "M19 9l-7 7-7-7";
const logoIcon =
  "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253";
const logoutIcon =
  "M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1";

interface AppSidebarProps {
  items: (NavItem | NavGroup)[];
  title: string;
  accent?: SidebarAccent;
  collapsible?: boolean;
}

function isNavGroup(item: NavItem | NavGroup): item is NavGroup {
  return "items" in item;
}

/** SVG path 以字母开头（M/L/C…），emoji 以非 ASCII 开头 */
const isSvgIcon = (icon: string) => /^[A-Za-z]/.test(icon);

/**
 * 统一侧边栏：Admin / Teacher / Student 三端共用。
 * 通过 props 注入导航项、标题与主题色；可选折叠（collapsible）。
 */
export function AppSidebar({
  items,
  title,
  accent = "indigo",
  collapsible = false,
}: AppSidebarProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [manualGroup, setManualGroup] = useState<string | null>(null);
  const cfg = ACCENTS[accent];

  useEffect(() => {
    setManualGroup(null);
  }, [location.pathname]);

  const activeGroup = (() => {
    for (const item of items) {
      if (
        isNavGroup(item) &&
        item.items.some((sub) => location.pathname.startsWith(sub.to))
      ) {
        return item.label;
      }
    }
    return null;
  })();

  const toggleGroup = (label: string) => {
    if (label === activeGroup) return;
    setManualGroup((prev) => (prev === label ? null : label));
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    logout();
    navigate("/login");
  };

  const renderIcon = (icon: string, size = "w-5 h-5") => {
    if (isSvgIcon(icon)) {
      return (
        <svg
          className={`${size} flex-shrink-0`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
        </svg>
      );
    }
    return <span className="text-base flex-shrink-0">{icon}</span>;
  };

  const renderItem = (item: NavItem) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.to === "/admin" || item.to === "/teacher" || item.to === "/student"}
      title={item.label}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
          collapsed ? "justify-center px-2" : ""
        } ${
          isActive
            ? `${cfg.active} font-medium`
            : "text-gray-600 hover:bg-gray-50"
        }`
      }
    >
      {renderIcon(item.icon)}
      {!collapsed && <span>{item.label}</span>}
    </NavLink>
  );

  const renderGroup = (group: NavGroup) => {
    const isExpanded = group.label === activeGroup || group.label === manualGroup;
    const hasActiveChild = group.items.some((sub) =>
      location.pathname === sub.to || location.pathname.startsWith(sub.to + "/")
    );

    return (
      <div key={group.label}>
        <button
          onClick={() => toggleGroup(group.label)}
          title={group.label}
          className={`flex items-center w-full gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
            collapsed ? "justify-center px-2" : ""
          } ${
            hasActiveChild
              ? `${cfg.active} font-medium`
              : "text-gray-600 hover:bg-gray-50"
          }`}
        >
          {renderIcon(group.icon)}
          {!collapsed && <span className="flex-1 text-left">{group.label}</span>}
          {!collapsed && (
            <svg
              className={`w-4 h-4 transition-transform ${isExpanded ? "rotate-90" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={chevronIcon} />
            </svg>
          )}
        </button>
        {isExpanded && !collapsed && (
          <div className="mt-0.5 ml-3 pl-4 border-l border-gray-100 space-y-0.5">
            {group.items.map((sub) => renderItem(sub))}
          </div>
        )}
      </div>
    );
  };

  const roleLabel =
    user?.role === "admin" ? "管理员" : user?.role === "teacher" ? "教师" : "学员";

  return (
    <aside
      className={`${
        collapsed ? "w-16" : "w-64"
      } bg-white border-r border-gray-200 flex flex-col transition-all duration-200 shrink-0`}
    >
      {/* Logo */}
      <div className="p-4 border-b border-gray-100 flex items-center gap-2">
        <div className={`w-8 h-8 ${cfg.bar} rounded-lg flex items-center justify-center`}>
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={logoIcon} />
          </svg>
        </div>
        {!collapsed && <span className="text-lg font-bold text-gray-900">{title}</span>}
        {collapsible && (
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto text-gray-400 hover:text-gray-600 text-sm"
            title={collapsed ? "展开" : "折叠"}
          >
            {collapsed ? "▶" : "◀"}
          </button>
        )}
      </div>

      {/* 导航 */}
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {items.map((item) => (isNavGroup(item) ? renderGroup(item) : renderItem(item)))}
      </nav>

      {/* 用户信息 */}
      <div className="p-4 border-t border-gray-100">
        <div className="flex items-center gap-3">
          <div
            className={`w-8 h-8 ${cfg.user} rounded-full flex items-center justify-center shrink-0`}
          >
            <span className={`text-sm font-medium ${cfg.text}`}>
              {user?.user_id?.[0]?.toUpperCase() || "U"}
            </span>
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-700 truncate">
                {user?.user_id || "用户"}
              </p>
              <p className="text-xs text-gray-400">{roleLabel}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
            title="退出登录"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={logoutIcon} />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
