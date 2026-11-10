import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { Course, User, UserCreateRequest } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { StatCard } from "../../components/admin/StatCard";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { Pagination } from "../../components/admin/Pagination";
import { useToast } from "../../components/common/Toast";
import { useConfirm } from "../../components/common/ConfirmDialog";
import { AppSelect } from "../../components/common/AppSelect";

export default function UserManagementPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [users, setUsers] = useState<User[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState<string | undefined>(undefined);
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<User | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const [userData, courseData] = await Promise.all([
        adminApi.getUsers(page, 20, roleFilter),
        adminApi.getCourses(),
      ]);
      setUsers(userData.users);
      setTotal(userData.total);
      setCourses(courseData.courses);
    } catch {
      setUsers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, roleFilter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const courseTitle = useCallback(
    (courseId: string) =>
      courses.find((c) => c.course_id === courseId)?.title || courseId,
    [courses]
  );

  const handleDisable = async (userId: string) => {
    const ok = await confirm.confirm({
      message: "确认禁用该用户？禁用后该用户将无法登录。",
      confirmText: "禁用",
      danger: true,
    });
    if (!ok) return;
    const result = await adminApi.disableUser(userId);
    if (result.error) {
      toast.toast(`操作失败：${result.error}`, "error");
    } else {
      toast.toast("用户已禁用", "success");
    }
    fetchUsers();
  };

  const columns: Column<User>[] = [
    {
      key: "username",
      label: "用户名",
      render: (row) => (
        <span className="font-medium text-gray-700">{row.username}</span>
      ),
    },
    {
      key: "display_name",
      label: "显示名",
      render: (row) => (
        <span className="text-sm text-gray-500">{row.display_name || "-"}</span>
      ),
    },
    {
      key: "role",
      label: "角色",
      render: (row) => (
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
            row.role === "admin"
              ? "bg-indigo-50 text-indigo-700"
              : row.role === "teacher"
              ? "bg-amber-50 text-amber-700"
              : "bg-gray-100 text-gray-600"
          }`}
        >
          {row.role === "admin" ? "管理员" : row.role === "teacher" ? "教师" : "学员"}
        </span>
      ),
    },
    {
      key: "course_ids",
      label: "已分配课程",
      render: (row) => (
        <span className="text-xs text-gray-500">
          {row.course_ids.length > 0
            ? row.course_ids.map((id) => courseTitle(id)).join("、")
            : "-"}
        </span>
      ),
    },
    {
      key: "is_active",
      label: "状态",
      render: (row) => (
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
            row.is_active
              ? "bg-green-50 text-green-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              row.is_active ? "bg-green-500" : "bg-red-500"
            }`}
          />
          {row.is_active ? "启用" : "禁用"}
        </span>
      ),
    },
    {
      key: "created_at",
      label: "创建时间",
      render: (row) => (
        <span className="text-xs text-gray-400">{row.created_at}</span>
      ),
    },
    {
      key: "actions",
      label: "操作",
      render: (row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditUser(row)}
            className="text-xs text-indigo-500 hover:text-indigo-700 hover:underline"
          >
            编辑
          </button>
          {row.is_active && (
            <button
              onClick={() => handleDisable(row.user_id)}
              className="text-xs text-red-500 hover:text-red-700 hover:underline"
            >
              禁用
            </button>
          )}
        </div>
      ),
    },
  ];

  const activeCount = users.filter((u) => u.is_active).length;
  const adminCount = users.filter((u) => u.role === "admin").length;
  const teacherCount = users.filter((u) => u.role === "teacher").length;

  return (
    <div>
      <PageHeader
        title="用户管理"
        subtitle="管理系统用户账号、角色和权限"
        actions={
          <div className="flex items-center gap-2">
            <AppSelect
              value={roleFilter || ""}
              onChange={(v) => {
                setRoleFilter(v || undefined);
                setPage(1);
              }}
              options={[
                { value: "", label: "全部角色" },
                { value: "admin", label: "管理员" },
                { value: "teacher", label: "教师" },
                { value: "student", label: "学员" },
              ]}
            />
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition"
            >
              新建用户
            </button>
            <button
              onClick={fetchUsers}
              disabled={loading}
              className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
            >
              {loading ? "刷新中..." : "刷新"}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="总用户数" value={total} accent="indigo" />
        <StatCard label="活跃用户" value={activeCount} accent="green" />
        <StatCard label="管理员" value={adminCount} accent="amber" />
        <StatCard label="教师" value={teacherCount} accent="cyan" />
        <StatCard label="学员" value={total - adminCount - teacherCount} accent="gray" />
      </div>

      <DataTable
        columns={columns}
        data={users}
        rowKey={(r) => r.user_id}
        loading={loading}
        emptyTitle="暂无用户"
        emptyDescription="点击「新建用户」创建第一个用户"
      />
      <Pagination page={page} total={total} pageSize={20} onChange={setPage} />

      {(showCreate || editUser) && (
        <UserModal
          user={editUser}
          courses={courses}
          onClose={() => {
            setShowCreate(false);
            setEditUser(null);
          }}
          onSuccess={() => {
            setShowCreate(false);
            setEditUser(null);
            fetchUsers();
          }}
        />
      )}
    </div>
  );
}

function UserModal({
  user,
  courses,
  onClose,
  onSuccess,
}: {
  user: User | null;
  courses: Course[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form, setForm] = useState<UserCreateRequest>({
    username: user?.username || "",
    password: "",
    role: user?.role || "student",
    course_ids: user?.course_ids.join(",") || "",
    display_name: user?.display_name || "",
  });
  const [selectedCourseIds, setSelectedCourseIds] = useState<string[]>(
    user?.course_ids || []
  );
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const toggleCourse = (courseId: string) => {
    setSelectedCourseIds((prev) =>
      prev.includes(courseId)
        ? prev.filter((id) => id !== courseId)
        : [...prev, courseId]
    );
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    const payload: UserCreateRequest = {
      ...form,
      course_ids: selectedCourseIds.join(","),
    };
    try {
      if (user) {
        const result = await adminApi.updateUser(user.user_id, {
          role: payload.role,
          course_ids: payload.course_ids,
          display_name: payload.display_name || undefined,
          ...(payload.password ? { password: payload.password } : {}),
        });
        if (result.error) {
          setError(result.error);
          return;
        }
      } else {
        const result = await adminApi.createUser(payload);
        if (result.error) {
          setError(result.error);
          return;
        }
      }
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl p-6 w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {user ? "编辑用户" : "新建用户"}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              用户名
            </label>
            <input
              type="text"
              value={form.username}
              disabled={!!user}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              密码 {user && "(留空则不修改)"}
            </label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              角色
            </label>
            <AppSelect
              value={form.role}
              onChange={(v) => setForm({ ...form, role: v })}
              className="w-full"
            >
              <option value="admin">管理员</option>
              <option value="teacher">教师</option>
              <option value="student">学员</option>
            </AppSelect>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              分配课程
            </label>
            {courses.length === 0 ? (
              <p className="text-xs text-amber-600">
                暂无课程，请先在课程管理页创建课程
              </p>
            ) : (
              <div className="border border-gray-200 rounded-lg p-2 max-h-44 overflow-y-auto space-y-1">
                {courses.map((c) => {
                  const checked = selectedCourseIds.includes(c.course_id);
                  return (
                    <label
                      key={c.course_id}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition ${
                        checked
                          ? "bg-indigo-50 text-indigo-700"
                          : "hover:bg-gray-50 text-gray-700"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCourse(c.course_id)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
                      />
                      <span className="flex-1 truncate">{c.title || c.course_id}</span>
                      <span className="text-xs text-gray-400 font-mono">{c.course_id}</span>
                    </label>
                  );
                })}
              </div>
            )}
            {selectedCourseIds.length > 0 && (
              <p className="text-xs text-gray-400 mt-1">
                已分配 {selectedCourseIds.length} 门课程
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              显示名
            </label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) =>
                setForm({ ...form, display_name: e.target.value })
              }
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "提交中..." : "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}
