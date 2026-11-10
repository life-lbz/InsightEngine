import apiClient from "./client";
import type { AgentChatResponse } from "../types";

export const agentApi = {
  async chat(
    question: string,
    courseId: string,
    sessionId: string
  ): Promise<AgentChatResponse> {
    const response = await apiClient.post("/agent/chat", {
      question,
      course_id: courseId || undefined,
      session_id: sessionId,
    });
    return response.data;
  },
};
