import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { StudentProgress, Course } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { AppSelect } from "../../components/common/AppSelect";
import { DataTable, type Column } from "../../components/admin/DataTable";

export default function StudentProgressPage() {
  const [progress, setProgress] = useState<StudentProgress[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [courseData, progressData] = await Promise.all([
        adminApi.getCourses(),
        adminApi.getStudentProgress(selectedCourse || undefined),
      ]);
      setCourses(courseData.courses);
      setProgress(progressData.progress);
    } catch {
      setProgress([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCourse]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const columns: Column<StudentProgress>[] = [
    {
      key: "username",
      label: "用户名",
      render: (row) => (
        <div>
          <span className="text-sm font-medium text-gray-700">{row.username}</span>
          {row.display_name && (
            <span className="text-xs text-gray-400 ml-2">({row.display_name})</span>
          )}
        </div>
      ),
    },
    {
      key: "user_id",
      label: "用户ID",
      render: (row) => (
        <span className="text-xs font-mono text-gray-400">{row.user_id}</span>
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
      key: "current_chapter_id",
      label: "当前章节",
      render: (row) => (
        <span className="text-xs font-mono text-gray-500">
          {row.current_chapter_id || "未开始"}
        </span>
      ),
    },
    {
      key: "mastered_points",
      label: "已掌握知识点",
      render: (row) => {
        const points = row.mastered_points ? row.mastered_points.split(",").filter(Boolean) : [];
        return (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">{points.length} 个</span>
            {points.length > 0 && (
              <div className="flex flex-wrap gap-1 max-w-xs">
                {points.slice(0, 3).map((p, i) => (
                  <span key={i} className="text-xs px-1.5 py-0.5 bg-green-50 text-green-600 rounded">
                    {p.substring(0, 12)}
                  </span>
                ))}
                {points.length > 3 && (
                  <span className="text-xs text-gray-400">+{points.length - 3}</span>
                )}
              </div>
            )}
          </div>
        );
      },
    },
    {
      key: "updated_at",
      label: "更新时间",
      render: (row) => (
        <span className="text-xs text-gray-400">
          {row.updated_at ? new Date(row.updated_at).toLocaleString("zh-CN") : "-"}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="学员进度"
        subtitle="查看学员学习进度和知识点掌握情况"
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
              onClick={fetchData}
              disabled={loading}
              className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
            >
              {loading ? "刷新中..." : "刷新"}
            </button>
          </div>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : progress.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">
          暂无学员进度数据
        </div>
      ) : (
        <DataTable columns={columns} data={progress} />
      )}
    </div>
  );
}
