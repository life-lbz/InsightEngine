import { useRealtimeStream } from "./useRealtimeStream";
import { useChatStore } from "../stores/chatStore";
import type { WSEvent } from "../types";

const CHAT_WS_ENDPOINT = "/api/v1/stream";

/**
 * 通用聊天 WebSocket（薄封装）：
 * 连接生命周期由 useRealtimeStream 统一管理，此处仅注入
 * Chat 事件处理与 store 读写。
 */
export function useWebSocket() {
  return useRealtimeStream({
    endpoint: CHAT_WS_ENDPOINT,

    onEvent: (raw) => {
      const data = raw as unknown as WSEvent;
      const s = useChatStore.getState();
      switch (data.type) {
        case "start": {
          const msgId = crypto.randomUUID();
          s.addMessage({
            id: msgId,
            role: "assistant",
            content: "",
            timestamp: Date.now(),
            trace_id: data.trace_id,
          });
          s.setStreaming(true);
          s.resetStreamingContent();
          break;
        }

        case "status": {
          s.setStreamingStage(data.stage || data.message || "");
          break;
        }

        case "token": {
          if (data.token) {
            s.appendStreamingContent(data.token);
          }
          break;
        }

        case "end": {
          const msgs = s.messages;
          const lastMsg = msgs[msgs.length - 1];
          if (lastMsg && lastMsg.role === "assistant") {
            s.finalizeStreamingMessage(lastMsg.id, {
              answer: data.answer || s.streamingContent,
              sources: data.sources,
              confidence: data.confidence,
              confidence_level: data.confidence_level,
              cache_hit: data.cache_hit,
              degraded: data.degraded,
              trace_id: data.trace_id,
            });
          }
          break;
        }

        case "error": {
          s.setStreaming(false);
          s.resetStreamingContent();
          break;
        }
      }
    },

    buildQueryPayload: () => {
      const s = useChatStore.getState();
      return {
        session_id: s.sessionId,
        course_id: s.currentCourseId,
      };
    },

    onMessageSent: (question: string) => {
      const s = useChatStore.getState();
      s.addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: question,
        timestamp: Date.now(),
      });
    },
  });
}
