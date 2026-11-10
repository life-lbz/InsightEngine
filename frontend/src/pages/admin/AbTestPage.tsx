import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { AbTest, AbTestResult } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";

export default function AbTestPage() {
  const [tests, setTests] = useState<AbTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [selectedTestId, setSelectedTestId] = useState<string>("");
  const [results, setResults] = useState<AbTestResult[]>([]);

  const [form, setForm] = useState({
    name: "",
    course_id: "global",
    strategy_a: "hybrid",
    strategy_b: "dense_only",
    traffic_split: 50,
    description: "",
  });

  const fetchTests = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getAbTests();
      setTests(data.ab_tests);
    } catch {
      setTests([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchResults = useCallback(async (testId: string) => {
    try {
      const data = await adminApi.getAbTestResults(testId);
      setResults(data.results);
    } catch {
      setResults([]);
    }
  }, []);

  useEffect(() => {
    fetchTests();
  }, [fetchTests]);

  useEffect(() => {
    if (selectedTestId) {
      fetchResults(selectedTestId);
    } else {
      setResults([]);
    }
  }, [selectedTestId, fetchResults]);

  const handleCreate = async () => {
    const result = await adminApi.createAbTest(form);
    if (result.test_id) {
      setActionMsg(`已创建测试 ${result.test_id}`);
      setShowCreate(false);
      setForm({ name: "", course_id: "global", strategy_a: "hybrid", strategy_b: "dense_only", traffic_split: 50, description: "" });
      fetchTests();
    } else {
      setActionMsg(`创建失败: ${result.error || "未知错误"}`);
    }
    setTimeout(() => setActionMsg(""), 3000);
  };

  const handleStatusChange = async (testId: string, status: string) => {
    await adminApi.updateAbTest(testId, { status });
    setActionMsg(`状态已更新为 ${status}`);
    fetchTests();
    setTimeout(() => setActionMsg(""), 3000);
  };

  const handleDelete = async (testId: string) => {
    await adminApi.deleteAbTest(testId);
    setActionMsg("测试已删除");
    fetchTests();
    setTimeout(() => setActionMsg(""), 3000);
  };

  const columns: Column<AbTest>[] = [
    {
      key: "name",
      label: "测试名称",
      render: (row) => (
        <span className="text-sm font-medium text-gray-700">{row.name}</span>
      ),
    },
    {
      key: "strategies",
      label: "策略对比",
      render: (row) => (
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded">{row.strategy_a}</span>
          <span className="text-gray-400">vs</span>
          <span className="px-2 py-0.5 bg-purple-50 text-purple-600 rounded">{row.strategy_b}</span>
        </div>
      ),
    },
    {
      key: "traffic_split",
      label: "流量分配",
      render: (row) => (
        <div className="flex items-center gap-2">
          <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden flex">
            <div className="bg-blue-500" style={{ width: `${row.traffic_split}%` }} />
            <div className="bg-purple-500" style={{ width: `${100 - row.traffic_split}%` }} />
          </div>
          <span className="text-xs text-gray-500">{row.traffic_split}:{100 - row.traffic_split}</span>
        </div>
      ),
    },
    {
      key: "status",
      label: "状态",
      render: (row) => {
        const colors: Record<string, string> = {
          draft: "bg-gray-100 text-gray-500",
          running: "bg-green-100 text-green-700",
          paused: "bg-amber-100 text-amber-700",
          completed: "bg-blue-100 text-blue-700",
        };
        return (
          <span className={`text-xs px-2 py-0.5 rounded ${colors[row.status] || "bg-gray-100"}`}>
            {row.status}
          </span>
        );
      },
    },
    {
      key: "actions",
      label: "操作",
      render: (row) => (
        <div className="flex gap-2">
          <button
            onClick={() => setSelectedTestId(row.test_id === selectedTestId ? "" : row.test_id)}
            className="text-xs px-2 py-1 text-indigo-600 border border-indigo-200 rounded hover:bg-indigo-50"
          >
            {row.test_id === selectedTestId ? "收起结果" : "查看结果"}
          </button>
          {row.status === "draft" && (
            <button
              onClick={() => handleStatusChange(row.test_id, "running")}
              className="text-xs px-2 py-1 text-green-600 border border-green-200 rounded hover:bg-green-50"
            >
              启动
            </button>
          )}
          {row.status === "running" && (
            <button
              onClick={() => handleStatusChange(row.test_id, "paused")}
              className="text-xs px-2 py-1 text-amber-600 border border-amber-200 rounded hover:bg-amber-50"
            >
              暂停
            </button>
          )}
          {row.status === "paused" && (
            <button
              onClick={() => handleStatusChange(row.test_id, "running")}
              className="text-xs px-2 py-1 text-green-600 border border-green-200 rounded hover:bg-green-50"
            >
              继续
            </button>
          )}
          <button
            onClick={() => handleDelete(row.test_id)}
            className="text-xs px-2 py-1 text-red-600 border border-red-200 rounded hover:bg-red-50"
          >
            删除
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="A/B 测试"
        subtitle="检索策略对比实验：不同策略的效果评估"
        actions={
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-3 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
          >
            {showCreate ? "取消" : "新建测试"}
          </button>
        }
      />

      {actionMsg && (
        <div className="mb-4 p-3 bg-indigo-50 text-indigo-600 text-sm rounded-lg">
          {actionMsg}
        </div>
      )}

      {showCreate && (
        <div className="mb-6 p-5 bg-white rounded-xl border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">创建 A/B 测试</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500">测试名称</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg mt-1"
                placeholder="如: hybrid vs dense_only"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">课程范围</label>
              <input
                value={form.course_id}
                onChange={(e) => setForm({ ...form, course_id: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg mt-1"
                placeholder="global 或具体课程ID"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">策略 A</label>
              <input
                value={form.strategy_a}
                onChange={(e) => setForm({ ...form, strategy_a: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">策略 B</label>
              <input
                value={form.strategy_b}
                onChange={(e) => setForm({ ...form, strategy_b: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">流量分配 (A%)</label>
              <input
                type="number"
                min="0"
                max="100"
                value={form.traffic_split}
                onChange={(e) => setForm({ ...form, traffic_split: parseInt(e.target.value) || 50 })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500">描述</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg mt-1"
                placeholder="测试目的..."
              />
            </div>
          </div>
          <button
            onClick={handleCreate}
            className="mt-4 px-4 py-2 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
          >
            确认创建
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : (
        <DataTable columns={columns} data={tests} />
      )}

      {selectedTestId && results.length > 0 && (
        <div className="mt-6 p-5 bg-white rounded-xl border border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            测试结果统计 ({selectedTestId})
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {results.map((r) => (
              <div key={r.strategy} className="p-4 rounded-lg border border-gray-100 bg-gray-50/50">
                <h4 className="text-sm font-medium text-indigo-600 mb-3">{r.strategy}</h4>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">总请求数</span>
                    <span className="font-mono text-gray-700">{r.total_requests}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">正向反馈</span>
                    <span className="font-mono text-green-600">{r.positive_feedback}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">负向反馈</span>
                    <span className="font-mono text-red-600">{r.negative_feedback}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">平均检索分</span>
                    <span className="font-mono text-gray-700">{r.avg_retrieval_score}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">平均响应时间</span>
                    <span className="font-mono text-gray-700">{r.avg_response_time_ms}ms</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
