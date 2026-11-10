import { useCallback, useEffect, useMemo, useState } from "react";
import { adminApi } from "../../api/admin";
import type {
  Course,
  Document,
  IngestionProgressItem,
  IngestionProgressResponse,
  IngestionTask,
  KbVersion,
  KnowledgeBaseStats,
  UploadResult,
} from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { StatCard } from "../../components/admin/StatCard";
import { UploadZone } from "../../components/admin/UploadZone";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { StatusBadge } from "../../components/admin/StatusBadge";
import { Pagination } from "../../components/admin/Pagination";
import { KbVersionCreateModal } from "../../components/admin/KbVersionCreateModal";
import { useToast } from "../../components/common/Toast";
import { useConfirm } from "../../components/common/ConfirmDialog";
import { usePolling } from "../../hooks/usePolling";
import { AppSelect } from "../../components/common/AppSelect";

export default function KnowledgeBasePage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [stats, setStats] = useState<KnowledgeBaseStats[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docPage, setDocPage] = useState(1);
  const [progress, setProgress] = useState<IngestionProgressResponse | null>(null);
  const [tasks, setTasks] = useState<IngestionTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadResults, setUploadResults] = useState<UploadResult[]>([]);
  const [triggerMsg, setTriggerMsg] = useState("");
  const [pendingFiles, setPendingFiles] = useState(0);
  const [ingestMode, setIngestMode] = useState<"full" | "incremental">("full");
  const [kbVersion, setKbVersion] = useState("kb_manual_v1");
  const [kbVersions, setKbVersions] = useState<KbVersion[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [showCreateVersion, setShowCreateVersion] = useState(false);

  const fetchKbVersions = useCallback(async () => {
    try {
      const data = await adminApi.getKbVersions();
      setKbVersions(data.versions);
    } catch {
      setKbVersions([]);
    }
  }, []);

  const fetchCourses = useCallback(async () => {
    try {
      const data = await adminApi.getCourses();
      setCourses(data.courses);
    } catch {
      setCourses([]);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const data = await adminApi.getKnowledgeBaseStats();
      setStats(data);
    } catch {
      setStats([]);
    }
  }, []);

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await adminApi.getDocuments(docPage, 20, kbVersion);
      setDocuments(data.documents);
      setDocTotal(data.total);
    } catch {
      setDocuments([]);
      setDocTotal(0);
    }
  }, [docPage, kbVersion]);

  const fetchProgress = useCallback(async () => {
    try {
      const data = await adminApi.getIngestionProgress(kbVersion);
      setProgress(data);
    } catch {
      setProgress(null);
    }
  }, [kbVersion]);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await adminApi.getIngestionTasks();
      setTasks(data.tasks);
    } catch {
      setTasks([]);
    }
  }, []);

  const fetchPendingFiles = useCallback(async () => {
    try {
      const data = await adminApi.getPendingIngestionFiles();
      setPendingFiles(data.total);
    } catch {
      setPendingFiles(0);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      fetchKbVersions(),
      fetchCourses(),
      fetchStats(),
      fetchDocuments(),
      fetchProgress(),
      fetchTasks(),
      fetchPendingFiles(),
    ]);
    setLoading(false);
  }, [fetchKbVersions, fetchCourses, fetchStats, fetchDocuments, fetchProgress, fetchTasks, fetchPendingFiles]);

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 入库进度与任务 5s 轮询（失败退避 + 页面隐藏暂停 + 卸载清理）
  usePolling(
    async () => {
      const [p, t] = await Promise.all([
        adminApi.getIngestionProgress(kbVersion),
        adminApi.getIngestionTasks(),
      ]);
      setProgress(p);
      setTasks(t.tasks);
    },
    [kbVersion],
    { intervalMs: 5000, onError: () => {} }
  );

  const handleUpload = async (files: File[]) => {
    const result = await adminApi.uploadDocuments(files, kbVersion);
    setUploadResults(result.results);
    const dupCount = result.results.filter((r) => r.duplicate).length;
    const realFailed = result.failed - dupCount;
    if (result.success > 0 || dupCount > 0) {
      setUploadMsg(
        `上传完成：成功 ${result.success} 个${dupCount > 0 ? `，已存在 ${dupCount} 个` : ""}${realFailed > 0 ? `，失败 ${realFailed} 个` : ""}，可在「入库控制」选择模式后开始入库`
      );
      fetchPendingFiles();
    } else {
      setUploadMsg(`上传失败：${result.failed} 个文件均未通过校验`);
    }
    setTimeout(() => setUploadMsg(""), 6000);
    fetchDocuments();
  };

  const handleDelete = async (fileHash: string) => {
    const ok = await confirm.confirm({
      message: "确认删除该文档？此操作将移除向量索引和文件记录。",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const result = await adminApi.deleteDocument(fileHash, kbVersion);
    if (result.error) {
      toast.toast(`删除失败：${result.error}`, "error");
    } else {
      toast.toast("文档已删除", "success");
    }
    fetchDocuments();
    fetchStats();
  };

  const handleStartIngestion = async () => {
    setTriggering(true);
    try {
      // 入库前校验：待入库目录是否有文档
      const pending = await adminApi.getPendingIngestionFiles();
      if (pending.total === 0) {
        setTriggerMsg("暂无待入库文档，请先将文档放入 data/raw 目录");
        setTimeout(() => setTriggerMsg(""), 5000);
        return;
      }
      const result = await adminApi.triggerIngestion(ingestMode, kbVersion);
      setTriggerMsg(
        `已触发${ingestMode === "full" ? "全量" : "增量"}入库任务 ${result.task_id}（待入库文件 ${pending.total} 个）`
      );
      setTimeout(() => {
        fetchProgress();
        fetchTasks();
        fetchPendingFiles();
      }, 1000);
      setTimeout(() => setTriggerMsg(""), 5000);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "触发入库失败，请稍后重试";
      setTriggerMsg(msg.includes("409") ? "已有入库任务正在进行，请等待完成后再试" : msg);
      setTimeout(() => setTriggerMsg(""), 6000);
    } finally {
      setTriggering(false);
    }
  };

  // 版本选择项：按 kb_version 去重，始终包含当前选中版本
  const versionOptions = useMemo(() => {
    const map = new Map<string, KbVersion>();
    kbVersions.forEach((v) => {
      if (!map.has(v.kb_version)) map.set(v.kb_version, v);
    });
    if (!map.has(kbVersion)) {
      map.set(kbVersion, {
        course_id: "",
        kb_version: kbVersion,
        version_seq: 0,
        status: "",
        description: "",
        doc_collection: "",
        faq_collection: "",
        question_collection: "",
        created_at: "",
        updated_at: "",
      });
    }
    return Array.from(map.values());
  }, [kbVersion, kbVersions]);

  const handleKbVersionChange = (value: string) => {
    setKbVersion(value);
    setDocPage(1);
  };

  const totalRows = stats.reduce((sum, s) => sum + s.row_count, 0);
  const healthyCount = stats.filter((s) => s.healthy).length;

  const docColumns: Column<Document>[] = [
    {
      key: "file_path",
      label: "文件路径",
      render: (row) => (
        <span className="font-mono text-xs text-gray-600 truncate max-w-xs block">
          {row.file_path.split(/[/\\]/).pop() || row.file_path}
        </span>
      ),
    },
    {
      key: "chunk_count",
      label: "Chunk 数",
      render: (row) => (
        <span className="font-medium text-gray-700">{row.chunk_count}</span>
      ),
    },
    {
      key: "file_hash",
      label: "文件哈希",
      render: (row) => (
        <span className="font-mono text-xs text-gray-400">
          {row.file_hash.slice(0, 12)}...
        </span>
      ),
    },
    {
      key: "ingested_at",
      label: "入库时间",
      render: (row) => (
        <span className="text-xs text-gray-500">
          {row.ingested_at || "-"}
        </span>
      ),
    },
    {
      key: "actions",
      label: "操作",
      render: (row) => (
        <button
          onClick={() => handleDelete(row.file_hash)}
          className="text-xs text-red-500 hover:text-red-700 hover:underline"
        >
          删除
        </button>
      ),
    },
  ];

  const summary = progress?.summary;

  return (
    <div>
      <PageHeader
        title="知识库管理"
        subtitle="管理文档入库、查看集合统计与入库进度"
        actions={
          <button
            onClick={refreshAll}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
          >
            {loading ? "刷新中..." : "刷新"}
          </button>
        }
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Collection 数" value={stats.length} hint={`健康 ${healthyCount}/${stats.length}`} />
        <StatCard label="总向量行数" value={totalRows.toLocaleString()} accent="green" />
        <StatCard
          label="已入库文档"
          value={docTotal}
          accent="indigo"
          hint={`版本: ${kbVersion}`}
        />
        <StatCard
          label="入库任务"
          value={tasks.filter((t) => t.status === "running").length}
          accent={tasks.some((t) => t.status === "running") ? "amber" : "gray"}
          hint={`共 ${tasks.length} 个任务`}
        />
      </div>

      {/* 文档上传 + 入库控制 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-700">上传文档</h3>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">入库版本</label>
              <AppSelect
                value={kbVersion}
                onChange={(v) => handleKbVersionChange(v)}
                className="px-2 py-1 text-xs"
              >
                {versionOptions.map((v) => (
                  <option key={v.kb_version} value={v.kb_version}>
                    {v.kb_version}
                    {v.course_id ? `（${v.course_id}）` : ""}
                  </option>
                ))}
              </AppSelect>
              <button
                onClick={() => {
                  fetchCourses();
                  setShowCreateVersion(true);
                }}
                className="px-2 py-1 text-xs text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition"
              >
                + 新建
              </button>
            </div>
          </div>
          <UploadZone
            onUpload={handleUpload}
            accept=".md,.txt,.pdf,.docx,.pptx,.csv,.xlsx"
            hint="支持 MD / TXT / PDF / DOCX / PPTX / CSV / XLSX，可多选；上传后进入待入库目录，在「入库控制」开始入库"
          />
          {uploadMsg && (
            <p className="mt-2 text-sm text-indigo-600">{uploadMsg}</p>
          )}

          {uploadResults.length > 0 && (
            <div className="mt-3 space-y-1.5 max-h-56 overflow-y-auto pr-1">
              {uploadResults.map((r, idx) => {
                const isDuplicate = r.duplicate && !r.already_ingested;
                const isAlreadyIngested = Boolean(r.already_ingested);
                const badgeClass = isAlreadyIngested
                  ? "bg-blue-50 text-blue-700"
                  : isDuplicate
                    ? "bg-amber-50 text-amber-700"
                    : r.error
                      ? "bg-red-50 text-red-700"
                      : "bg-emerald-50 text-emerald-700";
                const badgeText = isAlreadyIngested
                  ? "已入库"
                  : isDuplicate
                    ? "已存在"
                    : r.error
                      ? "失败"
                      : "成功";
                return (
                  <div
                    key={`${r.file_name}-${r.file_hash || idx}`}
                    className="flex items-start gap-2 text-xs"
                  >
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium shrink-0 mt-px ${badgeClass}`}
                    >
                      {badgeText}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-700 break-all">
                        {r.file_name}
                      </p>
                      {r.error && (
                        <p className="text-gray-400 break-all">{r.error}</p>
                      )}
                      {!r.error && (
                        <p className="text-gray-400">
                          {(r.size / 1024).toFixed(1)} KB，已进入待入库目录
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">入库控制</h3>

          {/* 入库模式选择 */}
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setIngestMode("full")}
              disabled={triggering}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition disabled:opacity-50 ${
                ingestMode === "full"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-gray-50 text-gray-600 border border-gray-200 hover:border-indigo-300"
              }`}
            >
              全量入库
            </button>
            <button
              onClick={() => setIngestMode("incremental")}
              disabled={triggering}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition disabled:opacity-50 ${
                ingestMode === "incremental"
                  ? "bg-amber-500 text-white shadow-sm"
                  : "bg-gray-50 text-gray-600 border border-gray-200 hover:border-amber-300"
              }`}
            >
              增量入库
            </button>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            当前模式：
            <span
              className={`font-medium ${
                ingestMode === "full" ? "text-indigo-600" : "text-amber-600"
              }`}
            >
              {ingestMode === "full"
                ? "全量（处理全部文档）"
                : "增量（仅处理新增/变更文档）"}
            </span>
            {pendingFiles > 0 && (
              <span className="ml-2 text-gray-500">
                · 待入库文档 {pendingFiles} 个
              </span>
            )}
          </p>

          {/* 开始入库 */}
          <button
            onClick={handleStartIngestion}
            disabled={triggering}
            className="w-full px-4 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-cyan-600 rounded-lg hover:from-indigo-700 hover:to-cyan-700 transition disabled:opacity-50 shadow-sm"
          >
            {triggering ? "正在触发..." : "开始入库"}
          </button>

          {triggerMsg && (
            <p
              className={`mt-3 text-sm ${
                triggerMsg.includes("暂无")
                  ? "text-amber-600"
                  : "text-indigo-600"
              }`}
            >
              {triggerMsg}
            </p>
          )}

          {summary && (
            <div className="grid grid-cols-4 gap-2">
              <div className="text-center p-2 bg-gray-50 rounded-lg">
                <p className="text-lg font-bold text-gray-700">{summary.total}</p>
                <p className="text-xs text-gray-400">总计</p>
              </div>
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <p className="text-lg font-bold text-green-600">{summary.completed}</p>
                <p className="text-xs text-gray-400">完成</p>
              </div>
              <div className="text-center p-2 bg-amber-50 rounded-lg">
                <p className="text-lg font-bold text-amber-600">{summary.pending}</p>
                <p className="text-xs text-gray-400">待处理</p>
              </div>
              <div className="text-center p-2 bg-red-50 rounded-lg">
                <p className="text-lg font-bold text-red-600">{summary.failed}</p>
                <p className="text-xs text-gray-400">失败</p>
              </div>
            </div>
          )}

          {tasks.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                最近任务
              </p>
              {tasks.slice(0, 3).map((task) => (
                <div
                  key={task.task_id}
                  className="flex items-center justify-between text-xs gap-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium shrink-0 border ${
                        task.mode === "incremental"
                          ? "bg-amber-50 text-amber-700 border-amber-200"
                          : "bg-indigo-50 text-indigo-700 border-indigo-200"
                      }`}
                    >
                      {task.mode === "incremental" ? "增量" : "全量"}
                    </span>
                    <span className="font-mono text-gray-500 truncate">
                      {task.task_id}
                    </span>
                  </div>
                  <StatusBadge status={task.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 集合统计表 */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Milvus 集合统计</h3>
        <DataTable
          columns={[
            { key: "collection_name", label: "Collection", render: (r: KnowledgeBaseStats) => <span className="font-mono text-xs text-gray-700">{r.collection_name}</span> },
            { key: "row_count", label: "行数", render: (r: KnowledgeBaseStats) => <span className="text-gray-600">{r.row_count.toLocaleString()}</span> },
            { key: "index_status", label: "索引状态", render: (r: KnowledgeBaseStats) => <StatusBadge status={r.index_status} /> },
            { key: "healthy", label: "健康", render: (r: KnowledgeBaseStats) => <StatusBadge status={r.healthy ? "healthy" : "degraded"} /> },
          ]}
          data={stats}
          rowKey={(r) => r.collection_name}
          loading={loading}
          emptyTitle="暂无集合"
          emptyDescription="触发入库后将自动创建 Collection"
        />
      </div>

      {/* 文档列表 */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">已入库文档</h3>
        <DataTable
          columns={docColumns}
          data={documents}
          rowKey={(r) => r.file_hash}
          loading={loading}
          emptyTitle="暂无文档"
          emptyDescription="上传文档并触发入库后，将在此显示"
        />
        <Pagination
          page={docPage}
          total={docTotal}
          pageSize={20}
          onChange={setDocPage}
        />
      </div>

      {/* 入库进度详情 */}
      {progress && progress.items.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">入库进度详情</h3>
          <DataTable
            columns={[
              { key: "file_path", label: "文件", render: (r: IngestionProgressItem) => <span className="font-mono text-xs text-gray-600 truncate max-w-xs block">{r.file_path.split(/[/\\]/).pop() || r.file_path}</span> },
              { key: "status", label: "状态", render: (r: IngestionProgressItem) => <StatusBadge status={r.status} /> },
              { key: "chunk_count", label: "Chunk 数", render: (r: IngestionProgressItem) => <span className="text-gray-600">{r.chunk_count}</span> },
              { key: "error_msg", label: "错误信息", render: (r: IngestionProgressItem) => <span className="text-xs text-red-500 truncate max-w-xs block">{r.error_msg || "-"}</span> },
              { key: "processed_at", label: "处理时间", render: (r: IngestionProgressItem) => <span className="text-xs text-gray-500">{r.processed_at || "-"}</span> },
            ]}
            data={progress.items}
            rowKey={(r) => r.file_hash}
            emptyTitle="暂无进度记录"
          />
        </div>
      )}

      {showCreateVersion && (
        <KbVersionCreateModal
          courses={courses}
          onClose={() => setShowCreateVersion(false)}
          onSuccess={({ kb_version: newKb }) => {
            setShowCreateVersion(false);
            handleKbVersionChange(newKb);
            fetchKbVersions();
            fetchDocuments();
            fetchProgress();
            fetchStats();
          }}
        />
      )}
    </div>
  );
}
