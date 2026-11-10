import apiClient from "./client";
import type { FeedbackRequest, PracticeRequest, Question } from "../types";

export const chatApi = {
  /** 提交答疑反馈 */
  async submitFeedback(data: FeedbackRequest): Promise<{ success: boolean }> {
    const response = await apiClient.post("/feedback", data, {
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    return response.data;
  },

  /** 获取练习题 */
  async getPracticeQuestions(
    data: PracticeRequest
  ): Promise<{ questions: Question[] }> {
    const response = await apiClient.post("/practice", data);
    return response.data;
  },

  /** 获取聊天历史 */
  async getHistory(
    sessionId: string,
    limit: number = 50
  ): Promise<{ messages: import("../types").ChatMessage[] }> {
    const response = await apiClient.get("/history", {
      params: { session_id: sessionId, limit },
    });
    return response.data;
  },

  /** 获取我的会话列表（聊天历史页） */
  async getSessions(): Promise<{
    sessions: { session_id: string; message_count: number; preview: string; role: string }[];
    total: number;
  }> {
    const response = await apiClient.get("/student/sessions");
    return response.data;
  },
};