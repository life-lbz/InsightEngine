// ===================== 认证相关 =====================

export interface UserInfo {
  user_id: string;
  role: "student" | "teacher" | "admin";
  course_ids: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: UserInfo;
}

// ===================== WebSocket 事件 =====================

/** 后端 -> 前端的事件类型 */
export type WSEventType = "start" | "status" | "token" | "end" | "error" | "ping" | "pong";

export interface WSEvent {
  type: WSEventType;
  // start 事件
  trace_id?: string;
  // status 事件
  stage?: string;          // "retrieving" | "reranking" | "generating"
  message?: string;
  // token 事件
  token?: string;
  // end 事件
  answer?: string;
  sources?: Source[];
  confidence?: number;
  confidence_level?: "high" | "medium" | "low";
  cache_hit?: boolean;
  hallucination_risk?: boolean;
  degraded?: boolean;
  // error 事件
  error?: string;
}

// ===================== 聊天消息 =====================

export interface Source {
  content: string;
  score: number;
  metadata: {
    source?: string;
    course_id?: string;
    doc_type?: string;
    chunk_id?: string;
    page?: number;
  };
}

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  // 仅 assistant 消息有
  sources?: Source[];
  confidence?: number;
  confidence_level?: "high" | "medium" | "low";
  cache_hit?: boolean;
  degraded?: boolean;
  trace_id?: string;
  feedback?: "useful" | "not_useful" | null;
}

// ===================== 练习题 =====================

export interface Question {
  id: string;
  question: string;
  options?: string[];
  answer: string;
  explanation?: string;
  difficulty: "easy" | "medium" | "hard";
  knowledge_point: string;
}

export interface PracticeRequest {
  course_id: string;
  knowledge_point?: string;
  difficulty?: string;
  count?: number;
}

// ===================== 反馈 =====================

export interface FeedbackRequest {
  session_id: string;
  course_id: string;
  question: string;
  answer: string;
  rating: "useful" | "not_useful";
  comment?: string;
  sources?: Source[];
}

// ===================== 管理后台 =====================

export interface KnowledgeBaseStats {
  collection_name: string;
  row_count: number;
  index_status: string;
  healthy: boolean;
}

export interface AuditLog {
  id: number;
  operator_id: string;
  action: string;
  resource: string;
  response_status: number;
  ip: string;
  trace_id: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  components?: Record<string, { healthy: boolean; latency_ms: number }>;
}

// ===================== 文档管理 =====================

export interface Document {
  file_path: string;
  file_hash: string;
  kb_version: string;
  chunk_count: number;
  ingested_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface UploadResult {
  file_path: string;
  file_name: string;
  file_hash: string;
  size: number;
  suffix: string;
  kb_version: string;
  error?: string;
  pending?: boolean;
  duplicate?: boolean;
  already_ingested?: boolean;
  message?: string;
}

export interface UploadBatchResult {
  total: number;
  success: number;
  failed: number;
  results: UploadResult[];
}

// ===================== 入库管理 =====================

export interface IngestionProgressItem {
  file_path: string;
  file_hash: string;
  kb_version: string;
  status: string;
  chunk_count: number;
  error_msg: string;
  created_at: string;
  processed_at: string;
}

export interface IngestionSummary {
  total: number;
  completed: number;
  failed: number;
  pending: number;
}

export interface IngestionProgressResponse {
  summary: IngestionSummary;
  items: IngestionProgressItem[];
}

export interface IngestionTask {
  task_id: string;
  kb_version: string;
  mode: string;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: number;
  started_at?: number;
  finished_at?: number | null;
}

export interface TriggerIngestionResponse {
  task_id: string;
  mode: string;
  kb_version: string;
}

// ===================== 检索质量监控 =====================

export interface RetrievalLog {
  id: number;
  session_id: string;
  query: string;
  intent: string | null;
  channel: string;
  hit_count: number;
  top_score: number | null;
  elapsed_ms: number | null;
  trace_id: string;
  created_at: string;
}

export interface RetrievalStats {
  total: number;
  avg_hit_count: number;
  avg_elapsed_ms: number;
  zero_hit_count: number;
  zero_hit_rate: number;
  channels: { channel: string; count: number; avg_hit: number }[];
}

// ===================== 用户反馈 =====================

export interface Feedback {
  id: number;
  session_id: string;
  course_id: string;
  question: string;
  answer: string;
  rating: string;
  comment: string | null;
  created_at: string;
}

export interface FeedbackStats {
  total: number;
  useful: number;
  not_useful: number;
  useful_rate: number;
}

// ===================== P1: 用户管理 =====================

export interface User {
  id: number;
  user_id: string;
  username: string;
  role: string;
  course_ids: string[];
  display_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreateRequest {
  username: string;
  password: string;
  role: string;
  course_ids: string;
  display_name?: string;
}

export interface UserUpdateRequest {
  role?: string;
  course_ids?: string;
  display_name?: string;
  is_active?: boolean;
  password?: string;
}

// ===================== P1: 课程管理 =====================

export interface Course {
  course_id: string;
  title: string;
  description: string;
  active_kb_version: string;
  created_at: string;
}

export interface CourseCreateRequest {
  course_id: string;
  title: string;
  description: string;
  active_kb_version: string;
  create_kb_version?: string;
  kb_description?: string;
}

// ===================== P1: FAQ 管理 =====================

export interface Faq {
  faq_id: string;
  course_id: string;
  question: string;
  answer: string;
  source: string;
  created_at: string;
}

// ===================== P1: 仪表盘统计 =====================

export interface DashboardStats {
  total_queries: number;
  total_feedback: number;
  total_users: number;
  total_docs: number;
  avg_hit_count: number;
  zero_hit_rate: number;
  feedback_rate: number;
  useful_rate: number;
  query_trend: { date: string; count: number; avg_hit: number }[];
}

// ===================== P1: 系统配置 =====================

export interface SystemConfig {
  llm_model: string;
  llm_fallback_model: string;
  embedding_model_path: string;
  reranker_model_path: string;
  milvus_uri: string;
  redis_url: string;
  mysql_host: string;
  mysql_database: string;
  doc_top_k: number;
  faq_top_k: number;
  rerank_top_n: number;
  embedding_batch_size: number;
  min_chunk_chars: number;
  chunk_dedup_jaccard_threshold: number;
  rag_min_score_threshold: number;
}

// ===================== P2: KB 版本管理 =====================

export interface KbVersion {
  course_id: string;
  kb_version: string;
  version_seq: number;
  status: string;
  description: string;
  doc_collection: string;
  faq_collection: string;
  question_collection: string;
  created_at: string;
  updated_at: string;
}

// ===================== P2: 章节管理 =====================

export interface Chapter {
  chapter_id: string;
  course_id: string;
  chapter_no: number;
  title: string;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface ChapterCreateRequest {
  chapter_no: number;
  title: string;
  summary: string;
}

// ===================== P2: 题库管理 =====================

export interface QuestionBankItem {
  question_id: string;
  course_id: string;
  chapter_id: string | null;
  point_id: string | null;
  question_type: string;
  difficulty: string;
  question_text: string;
  answer: string;
  explanation: string;
  source: string;
  created_at: string;
}

export interface QuestionBankCreateRequest {
  course_id: string;
  chapter_id?: string;
  point_id?: string;
  question_type: string;
  difficulty: string;
  question_text: string;
  answer: string;
  explanation: string;
  source: string;
}

// ===================== P2: 学员进度 =====================

export interface StudentProgress {
  user_id: string;
  course_id: string;
  current_chapter_id: string;
  mastered_points: string;
  updated_at: string;
  username: string;
  display_name: string;
}

// ===================== P2: 对话回放 =====================

export interface SessionItem {
  session_id: string;
  message_count: number;
}

export interface ReplayMessage {
  id: number;
  session_id: string;
  message: string;
}

export interface SessionReplay {
  session_id: string;
  messages: ReplayMessage[];
  retrieval_logs: RetrievalLog[];
  feedbacks: {
    id: number;
    question: string;
    answer: string;
    rating: string;
    comment: string | null;
    created_at: string;
  }[];
}

// ===================== P2: 负反馈惩罚 =====================

export interface FeedbackPenalty {
  chunk_id: string;
  penalty_score: number;
  ttl_seconds: number;
}

// ===================== P3: 限流监控 =====================

export interface RateLimit {
  endpoint: string;
  current_count: number;
  limit: number;
  window_seconds: number;
  blocked_count_today: number;
}

// ===================== P3: 插件健康检查 =====================

export interface PluginStatus {
  name: string;
  healthy: boolean;
  latency_ms: number;
  error: string;
}

export interface PluginHealthResponse {
  overall: boolean;
  plugins: PluginStatus[];
  total: number;
  error?: string;
}

// ===================== P3: Prometheus 指标 =====================

export interface MetricSample {
  name: string;
  labels: Record<string, string>;
  value: number;
}

export interface MetricsSummary {
  rag_request_duration?: MetricSample[];
  rag_first_token_latency?: MetricSample[];
  milvus_search_duration?: MetricSample[];
  milvus_search_total?: MetricSample[];
  llm_request_duration?: MetricSample[];
  llm_token_usage?: MetricSample[];
  llm_request_total?: MetricSample[];
  cache_hit_rate?: MetricSample[];
  degraded_request_total?: MetricSample[];
  websocket_active_connections?: MetricSample[];
  hallucination_risk_total?: MetricSample[];
  plugin_health_status?: MetricSample[];
  feedback_rating_ratio?: MetricSample[];
  metric_count: number;
  error?: string;
}

// ===================== P3: A/B 测试 =====================

export interface AbTest {
  test_id: string;
  name: string;
  course_id: string;
  strategy_a: string;
  strategy_b: string;
  traffic_split: number;
  status: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface AbTestCreateRequest {
  name: string;
  course_id: string;
  strategy_a: string;
  strategy_b: string;
  traffic_split: number;
  description: string;
}

export interface AbTestResult {
  strategy: string;
  total_requests: number;
  positive_feedback: number;
  negative_feedback: number;
  avg_retrieval_score: number;
  avg_response_time_ms: number;
}

// ===================== 二期：Agent 协作 =====================

/** Agent 类型 */
export type AgentType =
  | "qa_agent"
  | "quiz_agent"
  | "planner_agent"
  | "explain_agent"
  | "teacher_insight_agent"
  | "kb_ops_agent";

/** Agent 意图分类 */
export type AgentIntent =
  | "qa"
  | "quiz"
  | "planner"
  | "explain"
  | "insight"
  | "kb_ops"
  | "unknown";

/** Agent WebSocket 事件类型（兼容原有 WSEvent 并扩展） */
export type AgentWSEventType =
  | "start"
  | "status"
  | "token"
  | "end"
  | "error"
  | "fallback"
  | "ping"
  | "pong";

export interface AgentWSEvent {
  type: AgentWSEventType;
  trace_id?: string;
  stage?: string;
  message?: string;
  token?: string;
  answer?: string;
  sources?: Source[];
  intent?: string;
  agent_name?: string;
  degraded?: boolean;
  reason?: string;
  error?: string;
}

/** Agent 协作消息（在 ChatMessage 基础上扩展） */
export interface AgentMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  sources?: Source[];
  intent?: string;
  agent_name?: string;
  degraded?: boolean;
  trace_id?: string;
  feedback?: "useful" | "not_useful" | null;
}

/** Agent HTTP 响应 */
export interface AgentChatResponse {
  answer: string;
  sources: Source[];
  intent: string;
  degraded?: boolean;
}

/** 学习路径节点 */
export interface LearningPathNode {
  chapter_id: string;
  title: string;
  mastery_level: "unstarted" | "learning" | "mastered";
  recommended_action: string;
  knowledge_points: string[];
}

/** 学习路径 */
export interface LearningPath {
  course_id: string;
  nodes: LearningPathNode[];
  summary: string;
}

/** 练习记录 */
export interface PracticeRecord {
  id: number;
  user_id: string;
  course_id: string;
  question_id: string;
  question_text: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  knowledge_point: string;
  difficulty: string;
  created_at: string;
}

/** 学情分析报告 */
export interface InsightReport {
  report_id: string;
  course_id: string;
  generated_at: string;
  summary: string;
  key_findings: string[];
  recommendations: string[];
  at_risk_students: { user_id: string; reason: string }[];
  knowledge_gaps: { knowledge_point: string; mastery_rate: number }[];
}

/** FAQ 候选项 */
export interface FaqCandidate {
  id: number;
  course_id: string;
  question: string;
  suggested_answer: string;
  frequency: number;
  confidence: number;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

/** Agent 任务 */
export interface AgentTask {
  task_id: string;
  agent_name: string;
  status: "pending" | "running" | "completed" | "failed";
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

/** KB 运维状态 */
export interface KbOpsStatus {
  total_documents: number;
  total_chunks: number;
  pending_faqs: number;
  last_ingestion: string | null;
  collections: { name: string; row_count: number; healthy: boolean }[];
}