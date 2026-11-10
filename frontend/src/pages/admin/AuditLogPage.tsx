import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { AuditLog } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { AppSelect } from "../../components/common/AppSelect";
import { Pagination } from "../../components/admin/Pagination";

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    operator_id: "",
    action: "",
    start_date: "",
    end_date: "",
  });

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    const cleanFilters: Record<string, string> = {};
    if (filters.operator_id) cleanFilters.operator_id = filters.operator_id;
    if (filters.action) cleanFilters.action = filters.action;
    if (filters.start_date) cleanFilters.start_date = filters.start_date;
    if (filters.end_date) cleanFilters.end_date = filters.end_date;

    try {
      const result = await adminApi.getAuditLogsFiltered(
        page,
        20,
        Object.keys(cleanFilters).length > 0 ? cleanFilters : undefined
      );
      setLogs(result.logs);
      setTotal(result.total);
    } catch {
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleExport = () => {
    const headers = ["时间", "操作人", "操作", "资源", "状态", "IP", "Trace ID"];
    const rows = logs.map((log) => [
      log.created_at,
      log.operator_id,
      log.action,
      log.resource || "",
      String(log.response_status),
      log.ip || "",
      log.trace_id || "",
    ]);
    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => `"${cell}"`).join(","))
      .join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: Column<AuditLog>[] = [
    {
      key: "created_at",
      label: "时间",
      render: (row) => (
        <span className="text-xs text-gray-500">
          {new Date(row.created_at).toLocaleString("zh-CN")}
        </span>
      ),
    },
    {
      key: "operator_id",
      label: "操作人",
      render: (row) => (
        <span className="text-sm text-gray-700">{row.operator_id}</span>
      ),
    },
    {
      key: "action",
      label: "操作",
      render: (row) => (
        <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded">
          {row.action}
        </span>
      ),
    },
    {
      key: "resource",
      label: "资源",
      render: (row) => (
        <span className="text-sm text-gray-600 truncate max-w-xs block">
          {row.resource || "-"}
        </span>
      ),
    },
    {
      key: "response_status",
      label: "状态",
      render: (row) => (
        <span
          className={`text-xs font-medium ${
            row.response_status < 400
              ? "text-green-600"
              : "text-red-600"
          }`}
        >
          {row.response_status}
        </span>
      ),
    },
    {
      key: "ip",
      label: "IP",
      render: (row) => (
        <span className="text-xs font-mono text-gray-400">{row.ip || "-"}</span>
      ),
    },
    {
      key: "trace_id",
      label: "Trace ID",
      render: (row) => (
        <span className="text-xs font-mono text-gray-400">
          {row.trace_id ? row.trace_id.slice(0, 8) + "..." : "-"}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="审计日志"
        subtitle="追踪所有管理操作的执行记录"
        actions={
          <button
            onClick={handleExport}
            disabled={logs.length === 0}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
          >
            导出 CSV
          </button>
        }
      />

      {/* 筛选器 */}
      <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-white border border-gray-200 rounded-xl">
        <input
          type="text"
          placeholder="操作人"
          value={filters.operator_id}
          onChange={(e) =>
            setFilters({ ...filters, operator_id: e.target.value })
          }
          className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg w-32"
        />
        <AppSelect
          value={filters.action}
          onChange={(v) => setFilters({ ...filters, action: v })}
          options={[
            { value: "", label: "全部操作" },
            { value: "create", label: "创建" },
            { value: "update", label: "更新" },
            { value: "delete", label: "删除" },
            { value: "ingest", label: "入库" },
          ]}
        />
        <input
          type="date"
          value={filters.start_date}
          onChange={(e) =>
            setFilters({ ...filters, start_date: e.target.value })
          }
          className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg"
        />
        <span className="text-xs text-gray-400">至</span>
        <input
          type="date"
          value={filters.end_date}
          onChange={(e) =>
            setFilters({ ...filters, end_date: e.target.value })
          }
          className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg"
        />
        <button
          onClick={() => {
            setPage(1);
            fetchLogs();
          }}
          disabled={loading}
          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "查询中..." : "查询"}
        </button>
        <button
          onClick={() => {
            setFilters({
              operator_id: "",
              action: "",
              start_date: "",
              end_date: "",
            });
            setPage(1);
          }}
          className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          重置
        </button>
      </div>

      <DataTable
        columns={columns}
        data={logs}
        rowKey={(r) => String(r.id)}
        loading={loading}
        emptyTitle="暂无审计日志"
        emptyDescription="筛选条件下无匹配记录"
      />
      <Pagination page={page} total={total} pageSize={20} onChange={setPage} />
    </div>
  );
}
