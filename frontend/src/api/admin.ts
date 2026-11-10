import apiClient from "./client";
import type {
  AbTest,
  AbTestCreateRequest,
  AbTestResult,
  AuditLog,
  Chapter,
  ChapterCreateRequest,
  Course,
  CourseCreateRequest,
  DashboardStats,
  DocumentListResponse,
  Faq,
  Feedback,
  FeedbackPenalty,
  FeedbackStats,
  HealthStatus,
  IngestionProgressResponse,
  IngestionTask,
  KbVersion,
  KnowledgeBaseStats,
  MetricsSummary,
  PluginHealthResponse,
  QuestionBankCreateRequest,
  QuestionBankItem,
  RateLimit,
  RetrievalLog,
  RetrievalStats,
  SessionItem,
  SessionReplay,
  StudentProgress,
  SystemConfig,
  TriggerIngestionResponse,
  UploadBatchResult,
  UploadResult,
  User,
  UserCreateRequest,
  UserUpdateRequest,
} from "../types";

export const adminApi = {
  /** 获取系统健康状态 */
  async getHealth(): Promise<HealthStatus> {
    const response = await apiClient.get("/admin/health");
    return response.data;
  },

  /** 获取知识库统计 */
  async getKnowledgeBaseStats(): Promise<KnowledgeBaseStats[]> {
    const response = await apiClient.get("/admin/knowledge-base/stats");
    return response.data;
  },

  /** 获取审计日志 */
  async getAuditLogs(
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ logs: AuditLog[]; total: number }> {
    const response = await apiClient.get("/admin/audit-logs", {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  // ── 文档管理 ──

  /** 上传文档（单个） */
  async uploadDocument(
    file: File,
    kbVersion: string = ""
  ): Promise<UploadResult> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/admin/documents/upload", formData, {
      params: { kb_version: kbVersion },
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  /** 批量上传文档（一次请求处理多个文件，避免逐文件触发限流） */
  async uploadDocuments(
    files: File[],
    kbVersion: string = ""
  ): Promise<UploadBatchResult> {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    const response = await apiClient.post(
      "/admin/documents/upload-batch",
      formData,
      {
        params: { kb_version: kbVersion },
        headers: { "Content-Type": "multipart/form-data" },
      }
    );
    return response.data;
  },

  /** 获取文档列表 */
  async getDocuments(
    page: number = 1,
    pageSize: number = 20,
    kbVersion?: string
  ): Promise<DocumentListResponse> {
    const response = await apiClient.get("/admin/documents", {
      params: { page, page_size: pageSize, kb_version: kbVersion },
    });
    return response.data;
  },

  /** 删除文档 */
  async deleteDocument(
    fileHash: string,
    kbVersion: string = ""
  ): Promise<{ deleted: boolean; file_hash: string; error?: string }> {
    const response = await apiClient.delete(`/admin/documents/${fileHash}`, {
      params: { kb_version: kbVersion },
    });
    return response.data;
  },

  // ── 入库管理 ──

  /** 获取待入库文件列表（用于入库前校验） */
  async getPendingIngestionFiles(): Promise<{
    total: number;
    files: { name: string; path: string; size: number }[];
  }> {
    const response = await apiClient.get("/admin/ingestion/pending-files");
    return response.data;
  },

  /** 触发入库 */
  async triggerIngestion(
    mode: string = "full",
    kbVersion: string = "",
    courseId: string = "",
    inputDir?: string
  ): Promise<TriggerIngestionResponse> {
    const response = await apiClient.post("/admin/ingestion", null, {
      params: { mode, kb_version: kbVersion, course_id: courseId, input_dir: inputDir },
    });
    return response.data;
  },

  /** 获取入库进度 */
  async getIngestionProgress(
    kbVersion: string = ""
  ): Promise<IngestionProgressResponse> {
    const response = await apiClient.get("/admin/ingestion/progress", {
      params: { kb_version: kbVersion },
    });
    return response.data;
  },

  /** 获取入库任务列表 */
  async getIngestionTasks(): Promise<{ tasks: IngestionTask[] }> {
    const response = await apiClient.get("/admin/ingestion/tasks");
    return response.data;
  },

  /** 获取入库任务详情 */
  async getIngestionTaskDetail(taskId: string): Promise<IngestionTask> {
    const response = await apiClient.get(`/admin/ingestion/tasks/${taskId}`);
    return response.data;
  },

  // ── 检索质量监控 ──

  /** 获取检索日志 */
  async getRetrievalLogs(
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ logs: RetrievalLog[]; total: number }> {
    const response = await apiClient.get("/admin/retrieval-logs", {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /** 获取检索统计 */
  async getRetrievalStats(): Promise<RetrievalStats> {
    const response = await apiClient.get("/admin/retrieval-stats");
    return response.data;
  },

  // ── 用户反馈分析 ──

  /** 获取反馈列表 */
  async getFeedbacks(
    page: number = 1,
    pageSize: number = 20,
    rating?: string
  ): Promise<{ feedbacks: Feedback[]; total: number }> {
    const response = await apiClient.get("/admin/feedbacks", {
      params: { page, page_size: pageSize, rating },
    });
    return response.data;
  },

  /** 获取反馈统计 */
  async getFeedbackStats(): Promise<FeedbackStats> {
    const response = await apiClient.get("/admin/feedbacks/stats");
    return response.data;
  },

  // ── P1: 仪表盘统计 ──

  async getDashboardStats(): Promise<DashboardStats> {
    const response = await apiClient.get("/admin/dashboard/stats");
    return response.data;
  },

  // ── P1: 用户管理 ──

  async getUsers(
    page: number = 1,
    pageSize: number = 20,
    role?: string
  ): Promise<{ users: User[]; total: number }> {
    const response = await apiClient.get("/admin/users", {
      params: { page, page_size: pageSize, role },
    });
    return response.data;
  },

  async createUser(req: UserCreateRequest): Promise<{ user_id: string; error?: string }> {
    const response = await apiClient.post("/admin/users", req);
    return response.data;
  },

  async updateUser(
    userId: string,
    req: UserUpdateRequest
  ): Promise<{ updated: boolean; error?: string }> {
    const response = await apiClient.put(`/admin/users/${userId}`, req);
    return response.data;
  },

  async disableUser(userId: string): Promise<{ disabled: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/users/${userId}`);
    return response.data;
  },

  // ── P1: 课程管理 ──

  async getCourses(): Promise<{ courses: Course[] }> {
    const response = await apiClient.get("/admin/courses");
    return response.data;
  },

  async createCourse(req: CourseCreateRequest): Promise<{ course_id: string; error?: string }> {
    const response = await apiClient.post("/admin/courses", req);
    return response.data;
  },

  async updateCourse(
    courseId: string,
    data: Partial<CourseCreateRequest>
  ): Promise<{ updated: boolean; error?: string }> {
    const response = await apiClient.put(`/admin/courses/${courseId}`, data);
    return response.data;
  },

  async deleteCourse(courseId: string): Promise<{ deleted: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/courses/${courseId}`);
    return response.data;
  },

  // ── P1: FAQ 管理 ──

  async getFaqs(
    page: number = 1,
    pageSize: number = 20,
    courseId?: string
  ): Promise<{ faqs: Faq[]; total: number }> {
    const response = await apiClient.get("/admin/faqs", {
      params: { page, page_size: pageSize, course_id: courseId },
    });
    return response.data;
  },

  async createFaq(req: {
    course_id: string;
    question: string;
    answer: string;
    source?: string;
  }): Promise<{ faq_id: string; error?: string }> {
    const response = await apiClient.post("/admin/faqs", req);
    return response.data;
  },

  async deleteFaq(faqId: string): Promise<{ deleted: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/faqs/${faqId}`);
    return response.data;
  },

  // ── P1: 审计日志增强 ──

  async getAuditLogsFiltered(
    page: number = 1,
    pageSize: number = 20,
    filters?: {
      operator_id?: string;
      action?: string;
      start_date?: string;
      end_date?: string;
    }
  ): Promise<{ logs: AuditLog[]; total: number }> {
    const response = await apiClient.get("/admin/audit-logs/filtered", {
      params: { page, page_size: pageSize, ...filters },
    });
    return response.data;
  },

  // ── P1: 配置管理 ──

  async getConfig(): Promise<SystemConfig> {
    const response = await apiClient.get("/admin/config");
    return response.data;
  },

  async updateConfig(req: {
    doc_top_k?: number;
    faq_top_k?: number;
    rerank_top_n?: number;
    rag_min_score_threshold?: number;
  }): Promise<{ updated: string[] }> {
    const response = await apiClient.put("/admin/config", req);
    return response.data;
  },

  // ── P2: KB 版本管理 ──

  async getKbVersions(courseId?: string): Promise<{ versions: KbVersion[]; total: number }> {
    const response = await apiClient.get("/admin/kb-versions", {
      params: { course_id: courseId },
    });
    return response.data;
  },

  async createKbVersion(req: {
    course_id: string;
    kb_version: string;
    description?: string;
    activate?: boolean;
  }): Promise<{
    created?: boolean;
    activated?: boolean;
    error?: string;
    detail?: string;
    kb_version?: string;
  }> {
    const response = await apiClient.post("/admin/kb-versions", req);
    return response.data;
  },

  async activateKbVersion(kbVersion: string, courseId: string): Promise<{ activated?: boolean; error?: string }> {
    const response = await apiClient.put(`/admin/kb-versions/${kbVersion}/activate`, null, {
      params: { course_id: courseId },
    });
    return response.data;
  },

  // ── P2: 索引重建 ──

  async rebuildIndex(
    collection: string,
    dryRun: boolean = false
  ): Promise<{
    rebuilt?: boolean;
    dry_run?: boolean;
    error?: string;
    collection?: string;
    row_count?: number;
  }> {
    const response = await apiClient.post("/admin/indexes/rebuild", null, {
      params: { collection, dry_run: dryRun },
    });
    return response.data;
  },

  // ── P2: 章节管理 ──

  async getChapters(courseId: string): Promise<{ chapters: Chapter[]; total: number }> {
    const response = await apiClient.get(`/admin/courses/${courseId}/chapters`);
    return response.data;
  },

  async createChapter(courseId: string, req: ChapterCreateRequest): Promise<{ chapter_id?: string; error?: string }> {
    const response = await apiClient.post(`/admin/courses/${courseId}/chapters`, req);
    return response.data;
  },

  async updateChapter(chapterId: string, req: Partial<ChapterCreateRequest>): Promise<{ updated?: boolean; error?: string }> {
    const response = await apiClient.put(`/admin/chapters/${chapterId}`, req);
    return response.data;
  },

  async deleteChapter(chapterId: string): Promise<{ deleted?: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/chapters/${chapterId}`);
    return response.data;
  },

  // ── P2: 题库管理 ──

  async getQuestions(courseId?: string, page: number = 1, pageSize: number = 20): Promise<{ questions: QuestionBankItem[]; total: number }> {
    const response = await apiClient.get("/admin/questions", {
      params: { course_id: courseId, page, page_size: pageSize },
    });
    return response.data;
  },

  async createQuestion(req: QuestionBankCreateRequest): Promise<{ question_id?: string; error?: string }> {
    const response = await apiClient.post("/admin/questions", req);
    return response.data;
  },

  async updateQuestion(questionId: string, req: Partial<QuestionBankCreateRequest>): Promise<{ updated?: boolean; error?: string }> {
    const response = await apiClient.put(`/admin/questions/${questionId}`, req);
    return response.data;
  },

  async deleteQuestion(questionId: string): Promise<{ deleted?: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/questions/${questionId}`);
    return response.data;
  },

  // ── P2: 学员进度 ──

  async getStudentProgress(courseId?: string): Promise<{ progress: StudentProgress[]; total: number }> {
    const response = await apiClient.get("/admin/students/progress", {
      params: { course_id: courseId },
    });
    return response.data;
  },

  async getStudentDetail(userId: string, courseId?: string): Promise<{ progress: StudentProgress[] }> {
    const response = await apiClient.get(`/admin/students/${userId}/progress`, {
      params: { course_id: courseId },
    });
    return response.data;
  },

  // ── P2: 对话回放 ──

  async getSessions(page: number = 1, pageSize: number = 20): Promise<{ sessions: SessionItem[]; total: number }> {
    const response = await apiClient.get("/admin/sessions", {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  async getSessionReplay(sessionId: string): Promise<SessionReplay> {
    const response = await apiClient.get(`/admin/sessions/${sessionId}/replay`);
    return response.data;
  },

  // ── P2: 负反馈惩罚 ──

  async getFeedbackPenalties(): Promise<{ penalties: FeedbackPenalty[]; total: number }> {
    const response = await apiClient.get("/admin/feedback-penalties");
    return response.data;
  },

  async resetFeedbackPenalty(chunkId: string): Promise<{ reset?: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/feedback-penalties/${chunkId}`);
    return response.data;
  },

  // ── P3: 限流监控 ──

  async getRateLimits(): Promise<{ rate_limits: RateLimit[]; total: number }> {
    const response = await apiClient.get("/admin/rate-limits");
    return response.data;
  },

  // ── P3: 插件健康检查 ──

  async getPluginsHealth(): Promise<PluginHealthResponse> {
    const response = await apiClient.get("/admin/plugins/health");
    return response.data;
  },

  // ── P3: Prometheus 指标聚合 ──

  async getMetricsSummary(): Promise<MetricsSummary> {
    const response = await apiClient.get("/admin/metrics/summary");
    return response.data;
  },

  // ── P3: A/B 测试 ──

  async getAbTests(status?: string): Promise<{ ab_tests: AbTest[]; total: number }> {
    const response = await apiClient.get("/admin/ab-tests", {
      params: { status },
    });
    return response.data;
  },

  async createAbTest(req: AbTestCreateRequest): Promise<{ test_id?: string; error?: string }> {
    const response = await apiClient.post("/admin/ab-tests", req);
    return response.data;
  },

  async updateAbTest(testId: string, req: Partial<AbTestCreateRequest> & { status?: string }): Promise<{ updated?: boolean; error?: string }> {
    const response = await apiClient.put(`/admin/ab-tests/${testId}`, req);
    return response.data;
  },

  async deleteAbTest(testId: string): Promise<{ deleted?: boolean; error?: string }> {
    const response = await apiClient.delete(`/admin/ab-tests/${testId}`);
    return response.data;
  },

  async getAbTestResults(testId: string): Promise<{ test_id: string; results: AbTestResult[] }> {
    const response = await apiClient.get(`/admin/ab-tests/${testId}/results`);
    return response.data;
  },
};
