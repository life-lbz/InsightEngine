import { Outlet } from "react-router-dom";
import { AppSidebar, type NavItem } from "../../components/layout/AppSidebar";

const teacherNavItems: NavItem[] = [
  { label: "学情概览", to: "/teacher", icon: "📊" },
  { label: "AI 学情分析", to: "/teacher/insights", icon: "🤖" },
  { label: "学员进度", to: "/teacher/students", icon: "📈" },
  { label: "对话回放", to: "/teacher/sessions", icon: "🔄" },
  { label: "反馈查看", to: "/teacher/feedbacks", icon: "👎" },
  { label: "检索统计", to: "/teacher/retrieval-stats", icon: "🔍" },
];

export default function TeacherLayout() {
  return (
    <div className="flex h-screen bg-gray-50">
      <AppSidebar items={teacherNavItems} title="教师工作台" accent="amber" collapsible />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
