import { Outlet } from "react-router-dom";
import { AppSidebar, type NavItem } from "../../components/layout/AppSidebar";

const studentNavItems: NavItem[] = [
  { label: "学习概览", to: "/student", icon: "📊" },
  { label: "AI 答疑", to: "/student/chat", icon: "💬" },
  { label: "AI 协作", to: "/student/agent", icon: "🤖" },
  { label: "练习题库", to: "/student/practice", icon: "✏️" },
  { label: "学习进度", to: "/student/progress", icon: "📈" },
  { label: "课程资料", to: "/student/materials", icon: "📚" },
  { label: "聊天历史", to: "/student/history", icon: "🕘" },
];

export default function StudentLayout() {
  return (
    <div className="flex h-screen bg-gray-50">
      <AppSidebar items={studentNavItems} title="学员中心" accent="cyan" collapsible />

      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
}
