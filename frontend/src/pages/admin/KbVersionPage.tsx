import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { KbVersion, Course } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { AppSelect } from "../../components/common/AppSelect";
import { KbVersionCreateModal } from "../../components/admin/KbVersionCreateModal";

export default function KbVersionPage() {
  const [versions, setVersions] = useState<KbVersion[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [courseData, versionData] = await Promise.all([
        adminApi.getCourses(),
        adminApi.getKbVersions(selectedCourse || undefined),
      ]);
      setCourses(courseData.courses);
      setVersions(versionData.versions);
    } catch {
      setVersions([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCourse]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleActivate = async (kbVersion: string, courseId: string) => {
    const result = await adminApi.activateKbVersion(kbVersion, courseId);
    if (result.activated) {
      setActionMsg(`已激活版本 ${kbVersion}`);
      fetchData();
    } else {
      setActionMsg(`激活失败: ${result.error || "未知错误"}`);
    }
    setTimeout(() => setActionMsg(""), 3000);
  };

  const handleRebuild = async (collection: string) => {
    setActionMsg(`正在重建索引 ${collection}...`);
    const result = await adminApi.rebuildIndex(collection);
    if (result.rebuilt) {
      setActionMsg(`索引重建完成: ${collection} (${result.row_count} 行)`);
    } else if (result.dry_run) {
      setActionMsg(`预检: ${collection} 有 ${result.row_count} 行`);
    } else {
      setActionMsg(`重建失败: ${result.error || "未知错误"}`);
    }
    setTimeout(() => setActionMsg(""), 5000);
  };

  const columns: Column<KbVersion>[] = [
    {
      key: "kb_version",
      label: "版本号",
      render: (row) => (
        <span className="text-sm font-mono text-gray-700">{row.kb_version}</span>
      ),
    },
    {
      key: "course_id",
      label: "课程",
      render: (row) => (
        <span className="text-sm text-gray-600">{row.course_id}</span>
      ),
    },
    {
      key: "status",
      label: "状态",
      render: (row) => (
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            row.status === "active"
              ? "bg-green-50 text-green-600"
              : "bg-gray-50 text-gray-500"
          }`}
        >
          {row.status}
        </span>
      ),
    },
    {
      key: "version_seq",
      label: "序号",
      render: (row) => (
        <span className="text-sm text-gray-500">{row.version_seq}</span>
      ),
    },
    {
      key: "description",
      label: "描述",
      render: (row) => (
        <span className="text-sm text-gray-500 truncate max-w-xs block">
          {row.description || "-"}
        </span>
      ),
    },
    {
      key: "created_at",
      label: "创建时间",
      render: (row) => (
        <span className="text-xs text-gray-400">
          {row.created_at ? new Date(row.created_at).toLocaleString("zh-CN") : "-"}
        </span>
      ),
    },
    {
      key: "actions",
      label: "操作",
      render: (row) => (
        <div className="flex gap-2">
          {row.status !== "active" && (
            <button
              onClick={() => handleActivate(row.kb_version, row.course_id)}
              className="text-xs px-2 py-1 text-indigo-600 border border-indigo-200 rounded hover:bg-indigo-50"
            >
              激活
            </button>
          )}
          <button
            onClick={() => handleRebuild(row.doc_collection)}
            className="text-xs px-2 py-1 text-amber-600 border border-amber-200 rounded hover:bg-amber-50"
          >
            重建文档索引
          </button>
          <button
            onClick={() => handleRebuild(row.faq_collection)}
            className="text-xs px-2 py-1 text-amber-600 border border-amber-200 rounded hover:bg-amber-50"
          >
            重建FAQ索引
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="KB 版本管理"
        subtitle="管理知识库版本、激活切换、索引重建"
        actions={
          <div className="flex items-center gap-2">
            <AppSelect
              value={selectedCourse}
              onChange={(v) => setSelectedCourse(v)}
              options={[
                { value: "", label: "全部课程" },
                ...courses.map((c) => ({ value: c.course_id, label: c.title })),
              ]}
            />
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition"
            >
              新建版本
            </button>
            <button
              onClick={fetchData}
              disabled={loading}
              className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
            >
              {loading ? "刷新中..." : "刷新"}
            </button>
          </div>
        }
      />

      {actionMsg && (
        <div className="mb-4 p-3 bg-indigo-50 text-indigo-600 text-sm rounded-lg">
          {actionMsg}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : (
        <DataTable columns={columns} data={versions} />
      )}

      {showCreate && (
        <KbVersionCreateModal
          courses={courses}
          defaultCourseId={selectedCourse || undefined}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            setActionMsg("版本创建成功");
            setTimeout(() => setActionMsg(""), 3000);
            fetchData();
          }}
        />
      )}
    </div>
  );
}
