import { create } from "zustand";
import type { AgentMessage, Source } from "../types";

interface AgentState {
  messages: AgentMessage[];
  isStreaming: boolean;
  streamingContent: string;
  streamingStage: string;
  currentIntent: string;
  currentAgentName: string;
  degraded: boolean;
  sessionId: string;
  currentCourseId: string;

  addMessage: (message: AgentMessage) => void;
  updateMessage: (id: string, updates: Partial<AgentMessage>) => void;
  setStreaming: (streaming: boolean) => void;
  appendStreamingContent: (token: string) => void;
  setStreamingStage: (stage: string) => void;
  setIntent: (intent: string) => void;
  setAgentName: (name: string) => void;
  setDegraded: (degraded: boolean) => void;
  resetStreamingContent: () => void;
  finalizeStreamingMessage: (
    id: string,
    data: {
      answer: string;
      sources?: Source[];
      intent?: string;
      agent_name?: string;
      degraded?: boolean;
      trace_id?: string;
    }
  ) => void;
  setCourseId: (courseId: string) => void;
  setSessionId: (sessionId: string) => void;
  clearMessages: () => void;
  removeLastMessage: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  messages: [],
  isStreaming: false,
  streamingContent: "",
  streamingStage: "",
  currentIntent: "",
  currentAgentName: "",
  degraded: false,
  sessionId: crypto.randomUUID(),
  currentCourseId: "",

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

  setIntent: (intent) => set({ currentIntent: intent }),

  setAgentName: (name) => set({ currentAgentName: name }),

  setDegraded: (degraded) => set({ degraded }),

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
              intent: data.intent,
              agent_name: data.agent_name,
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
  removeLastMessage: () =>
    set((state) => ({ messages: state.messages.slice(0, -1) })),
}));
