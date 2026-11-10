import { create } from "zustand";
import type { ChatMessage, Source } from "../types";

interface ChatState {
  // 消息列表
  messages: ChatMessage[];
  // 流式生成中
  isStreaming: boolean;
  // 当前流式消息的临时内容
  streamingContent: string;
  // 流式阶段状态
  streamingStage: string;
  // 当前选中的课程 ID
  currentCourseId: string;
  // 会话 ID
  sessionId: string;

  // 操作
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  setStreaming: (streaming: boolean) => void;
  appendStreamingContent: (token: string) => void;
  setStreamingStage: (stage: string) => void;
  resetStreamingContent: () => void;
  finalizeStreamingMessage: (id: string, data: {
    answer: string;
    sources?: Source[];
    confidence?: number;
    confidence_level?: "high" | "medium" | "low";
    cache_hit?: boolean;
    degraded?: boolean;
    trace_id?: string;
  }) => void;
  setCourseId: (courseId: string) => void;
  setSessionId: (sessionId: string) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  streamingContent: "",
  streamingStage: "",
  currentCourseId: "",
  sessionId: crypto.randomUUID(),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    })),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  appendStreamingContent: (token) =>
    set((state) => ({
      streamingContent: state.streamingContent + token,
    })),

  setStreamingStage: (stage) => set({ streamingStage: stage }),

  resetStreamingContent: () =>
    set({ streamingContent: "", streamingStage: "" }),

  finalizeStreamingMessage: (id, data) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id
          ? {
              ...msg,
              content: data.answer,
              sources: data.sources,
              confidence: data.confidence,
              confidence_level: data.confidence_level,
              cache_hit: data.cache_hit,
              degraded: data.degraded,
              trace_id: data.trace_id,
            }
          : msg
      ),
      isStreaming: false,
      streamingContent: "",
      streamingStage: "",
    })),

  setCourseId: (courseId) => set({ currentCourseId: courseId }),
  setSessionId: (sessionId) => set({ sessionId }),
  clearMessages: () => set({ messages: [] }),
}));