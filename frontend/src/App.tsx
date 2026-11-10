import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { BrowserRouter } from "react-router-dom";
import { useAuthStore } from "./stores/authStore";
import { LoadingSpinner } from "./components/common/LoadingSpinner";
import { ToastProvider } from "./components/common/Toast";
import { ConfirmProvider } from "./components/common/ConfirmDialog";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { initSentry } from "./utils/sentry";

// 布局组件：首屏必需，保持同步加载
import AdminLayout from "./pages/admin/AdminLayout";
import TeacherLayout from "./pages/teacher/TeacherLayout";
import StudentLayout from "./pages/student/StudentLayout";

// 页面级代码分割（按需懒加载，首屏只加载当前路由对应的 chunk）
const LoginPage = lazy(() => import("./pages/LoginPage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const PracticePage = lazy(() => import("./pages/PracticePage"));
const DashboardPage = lazy(() => import("./pages/admin/DashboardPage"));
const KnowledgeBasePage = lazy(() => import("./pages/admin/KnowledgeBasePage"));
const CourseManagementPage = lazy(() => import("./pages/admin/CourseManagementPage"));
const FaqManagementPage = lazy(() => import("./pages/admin/FaqManagementPage"));
const UserManagementPage = lazy(() => import("./pages/admin/UserManagementPage"));
const RetrievalLogPage = lazy(() => import("./pages/admin/RetrievalLogPage"));
const FeedbackAnalysisPage = lazy(() => import("./pages/admin/FeedbackAnalysisPage"));
const AuditLogPage = lazy(() => import("./pages/admin/AuditLogPage"));
const ConfigPage = lazy(() => import("./pages/admin/ConfigPage"));
const KbVersionPage = lazy(() => import("./pages/admin/KbVersionPage"));
const ChapterManagementPage = lazy(() => import("./pages/admin/ChapterManagementPage"));
const QuestionBankPage = lazy(() => import("./pages/admin/QuestionBankPage"));
const StudentProgressPage = lazy(() => import("./pages/admin/StudentProgressPage"));
const ConversationReplayPage = lazy(() => import("./pages/admin/ConversationReplayPage"));
const RateLimitPage = lazy(() => import("./pages/admin/RateLimitPage"));
const PluginStatusPage = lazy(() => import("./pages/admin/PluginStatusPage"));
const SystemMetricsPage = lazy(() => import("./pages/admin/SystemMetricsPage"));
const AbTestPage = lazy(() => import("./pages/admin/AbTestPage"));
const TeacherDashboard = lazy(() => import("./pages/teacher/TeacherDashboard"));
const TeacherInsightPage = lazy(() => import("./pages/teacher/TeacherInsightPage"));
const TeacherRetrievalStatsPage = lazy(() => import("./pages/teacher/TeacherRetrievalStatsPage"));
const StudentDashboard = lazy(() => import("./pages/student/StudentDashboard"));
const MyProgressPage = lazy(() => import("./pages/student/StudentProgressPage"));
const StudentMaterialsPage = lazy(() => import("./pages/student/StudentMaterialsPage"));
const StudentHistoryPage = lazy(() => import("./pages/student/StudentHistoryPage"));
const AgentChatPage = lazy(() => import("./pages/student/AgentChatPage"));

initSentry();

/** 路由切换时的全局加载态 */
function PageLoading() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  );
}

/** JWT 路由守卫 */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** 管理员路由守卫 */
function AdminGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (!user || user.role !== "admin") {
    return <Navigate to="/student" replace />;
  }
  return <>{children}</>;
}

/** 教师路由守卫（teacher + admin 可访问） */
function TeacherGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (!user || (user.role !== "teacher" && user.role !== "admin")) {
    return <Navigate to="/student" replace />;
  }
  return <>{children}</>;
}

/** 学员路由守卫（student + teacher + admin 均可访问） */
function StudentGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** 角色感知默认重定向 */
function RoleRedirect() {
  const user = useAuthStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  const target = user.role === "admin" ? "/admin" : user.role === "teacher" ? "/teacher" : "/student";
  return <Navigate to={target} replace />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ConfirmProvider>
          <BrowserRouter>
            <Suspense fallback={<PageLoading />}>
              <Routes>
                {/* 公开路由 */}
                <Route path="/login" element={<LoginPage />} />

                {/* 学员端（StudentGuard：所有角色可访问） */}
                <Route
                  path="/student"
                  element={
                    <AuthGuard>
                      <StudentGuard>
                        <StudentLayout />
                      </StudentGuard>
                    </AuthGuard>
                  }
                >
                  <Route index element={<StudentDashboard />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="practice" element={<PracticePage />} />
              <Route path="progress" element={<MyProgressPage />} />
              <Route path="materials" element={<StudentMaterialsPage />} />
              <Route path="history" element={<StudentHistoryPage />} />
              <Route path="agent" element={<AgentChatPage />} />
            </Route>

                {/* 向后兼容：旧路径重定向 */}
                <Route path="/chat" element={<Navigate to="/student/chat" replace />} />
                <Route path="/practice" element={<Navigate to="/student/practice" replace />} />

                {/* 教师端（需教师权限） */}
                <Route
                  path="/teacher"
                  element={
                    <AuthGuard>
                      <TeacherGuard>
                        <TeacherLayout />
                      </TeacherGuard>
                    </AuthGuard>
                  }
                >
                  <Route index element={<TeacherDashboard />} />
              <Route path="students" element={<StudentProgressPage />} />
              <Route path="sessions" element={<ConversationReplayPage />} />
              <Route path="feedbacks" element={<FeedbackAnalysisPage />} />
              <Route path="insights" element={<TeacherInsightPage />} />
              <Route path="retrieval-stats" element={<TeacherRetrievalStatsPage />} />
            </Route>

                {/* 管理后台（需管理员权限） */}
                <Route
                  path="/admin"
                  element={
                    <AuthGuard>
                      <AdminGuard>
                        <AdminLayout />
                      </AdminGuard>
                    </AuthGuard>
                  }
                >
                  <Route index element={<DashboardPage />} />
                  <Route path="knowledge-base" element={<KnowledgeBasePage />} />
                  <Route path="courses" element={<CourseManagementPage />} />
                  <Route path="faqs" element={<FaqManagementPage />} />
                  <Route path="users" element={<UserManagementPage />} />
                  <Route path="retrieval-logs" element={<RetrievalLogPage />} />
                  <Route path="feedbacks" element={<FeedbackAnalysisPage />} />
                  <Route path="audit-logs" element={<AuditLogPage />} />
                  <Route path="config" element={<ConfigPage />} />
                  {/* P2: 高级管理 */}
                  <Route path="kb-versions" element={<KbVersionPage />} />
                  <Route path="chapters" element={<ChapterManagementPage />} />
                  <Route path="questions" element={<QuestionBankPage />} />
                  <Route path="student-progress" element={<StudentProgressPage />} />
                  <Route path="sessions" element={<ConversationReplayPage />} />
                  {/* P3: 高级分析 */}
                  <Route path="rate-limits" element={<RateLimitPage />} />
                  <Route path="plugins" element={<PluginStatusPage />} />
                  <Route path="metrics" element={<SystemMetricsPage />} />
                  <Route path="ab-tests" element={<AbTestPage />} />
            </Route>

                {/* 默认重定向（角色感知） */}
                <Route path="/" element={<RoleRedirect />} />
                <Route path="*" element={<RoleRedirect />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ConfirmProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
