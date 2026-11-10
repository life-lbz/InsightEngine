import { useRealtimeStream } from "./useRealtimeStream";
import { useAgentStore } from "../stores/agentStore";
import type { AgentWSEvent } from "../types";

const AGENT_WS_ENDPOINT = "/api/v1/agent/stream";

/**
 * Agent 协作 WebSocket（薄封装）：
 * 连接生命周期由 useRealtimeStream 统一管理，此处仅注入
 * Agent 事件处理与 store 读写。
 */
export function useAgentWebSocket() {
  return useRealtimeStream({
    endpoint: AGENT_WS_ENDPOINT,

    onEvent: (raw) => {
      const data = raw as unknown as AgentWSEvent;
      const s = useAgentStore.getState();
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
          const stage = data.stage || data.message || "";
          s.setStreamingStage(stage);
          if (stage === "ready" || stage === "thinking") {
            s.setAgentName("supervisor");
          }
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
              intent: data.intent,
              agent_name: data.agent_name,
              degraded: data.degraded,
              trace_id: data.trace_id,
            });
          }
          if (data.intent) {
            s.setIntent(data.intent);
          }
          s.setDegraded(Boolean(data.degraded));
          break;
        }

        case "fallback": {
          s.setDegraded(true);
          s.setStreamingStage("fallback");
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
      const s = useAgentStore.getState();
      return {
        session_id: s.sessionId,
        course_id: s.currentCourseId,
      };
    },

    onMessageSent: (question: string) => {
      const s = useAgentStore.getState();
      s.addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: question,
        timestamp: Date.now(),
      });
    },

    onStop: () => {
      const s = useAgentStore.getState();
      const msgs = s.messages;
      const lastMsg = msgs[msgs.length - 1];
      const currentContent = s.streamingContent;

      if (lastMsg && lastMsg.role === "assistant" && !lastMsg.content) {
        s.finalizeStreamingMessage(lastMsg.id, {
          answer: currentContent ? currentContent + "\n\n[已停止]" : "[已停止]",
          sources: [],
          intent: s.currentIntent,
        });
      }

      s.setStreaming(false);
      s.resetStreamingContent();
    },
  });
}
