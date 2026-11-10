import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "../stores/authStore";

// 心跳间隔 25s
const HEARTBEAT_INTERVAL = 25000;
// PONG 超时 45s：超时未收到任何消息判定死连接
const PONG_TIMEOUT = 45000;
// 连接超时 8s：未 open 则关闭并重试
const CONNECT_TIMEOUT = 8000;
// 最大重连次数（指数退避）
const MAX_RECONNECT_ATTEMPTS = 8;
// 最大重连延迟 30s
const MAX_RECONNECT_DELAY = 30000;

export interface RealtimeStreamOptions {
  /** WS 端点路径，如 "/api/v1/agent/stream"，DEV 下自动拼接 127.0.0.1:8000 */
  endpoint: string;
  /** 后端事件处理（由调用方写入对应 store） */
  onEvent: (data: Record<string, unknown>) => void;
  /** 构造发送 payload（含 session_id / course_id 等） */
  buildQueryPayload: (question: string) => Record<string, unknown>;
  /** 发送前将用户消息写入 store（可选） */
  onMessageSent?: (question: string) => void;
  /** 停止生成时对 store 的处理（可选） */
  onStop?: () => void;
  heartbeatInterval?: number;
  pongTimeout?: number;
  connectTimeout?: number;
  maxReconnectAttempts?: number;
  maxReconnectDelay?: number;
}

/**
 * 泛化 WebSocket 流式连接管理（生命周期完备版）：
 * - 幂等连接 + 连接超时保护 + 指数退避重连
 * - 心跳保活 + PONG 超时判死
 * - 连接未就绪时缓存提问，建立后自动补发
 * - 卸载/disconnect 时清理全部定时器，杜绝泄漏
 */
export function useRealtimeStream(options: RealtimeStreamOptions) {
  const {
    heartbeatInterval = HEARTBEAT_INTERVAL,
    pongTimeout = PONG_TIMEOUT,
    connectTimeout = CONNECT_TIMEOUT,
    maxReconnectAttempts = MAX_RECONNECT_ATTEMPTS,
    maxReconnectDelay = MAX_RECONNECT_DELAY,
  } = options;

  // 通过 ref 引用 options，避免回调依赖数组随每次渲染变化
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);
  const pongTimerRef = useRef<number | null>(null);
  const connectTimerRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const connectingRef = useRef(false);
  const disposedRef = useRef(false);
  const pendingQuestionRef = useRef<string | null>(null);
  // 间接引用，避免 useCallback 间的循环依赖
  const sendQuestionRef = useRef<(q: string) => boolean>(() => false);
  const connectRef = useRef<() => void>(() => {});
  const scheduleReconnectRef = useRef<() => void>(() => {});

  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearTimers = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    if (pongTimerRef.current) {
      clearTimeout(pongTimerRef.current);
      pongTimerRef.current = null;
    }
    if (connectTimerRef.current) {
      clearTimeout(connectTimerRef.current);
      connectTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const clearPongTimer = useCallback(() => {
    if (pongTimerRef.current) {
      clearTimeout(pongTimerRef.current);
      pongTimerRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = window.setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ type: "ping" }));
        } catch {
          return;
        }
        clearPongTimer();
        pongTimerRef.current = window.setTimeout(() => {
          // 超时未收到任何消息（含 pong），判定死连接
          wsRef.current?.close(4000, "pong timeout");
        }, pongTimeout);
      }
    }, heartbeatInterval);
  }, [clearPongTimer, heartbeatInterval, pongTimeout]);

  const handleEvent = useCallback(
    (raw: string) => {
      try {
        const data = JSON.parse(raw) as Record<string, unknown>;
        if (data.type === "ping" || data.type === "pong") {
          return;
        }
        // 连接层错误统一由基座设置，调用方 onEvent 只需处理 store 清理
        if (data.type === "error") {
          setError((data.error as string) || "服务异常");
        }
        optionsRef.current.onEvent(data);
      } catch {
        // ignore parse errors
      }
    },
    []
  );

  const connect = useCallback(() => {
    // 幂等：已有连接或正在连接则跳过
    if (connectingRef.current) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    if (disposedRef.current) return;

    const token = useAuthStore.getState().accessToken;
    if (!token) {
      setError("未登录，无法建立连接");
      return;
    }

    connectingRef.current = true;
    setError(null);

    const { endpoint } = optionsRef.current;
    const base =
      import.meta.env.VITE_WS_BASE_URL ||
      (import.meta.env.DEV
        ? "ws://127.0.0.1:8000"
        : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`);
    const url = `${base}${endpoint}?token=${encodeURIComponent(token)}`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      connectingRef.current = false;
      scheduleReconnectRef.current();
      return;
    }
    wsRef.current = ws;

    // 连接超时保护：N s 未 open 则关闭并重试
    connectTimerRef.current = window.setTimeout(() => {
      if (ws.readyState === WebSocket.CONNECTING) {
        ws.close(4001, "connect timeout");
      }
    }, connectTimeout);

    ws.onopen = () => {
      connectingRef.current = false;
      if (connectTimerRef.current) {
        clearTimeout(connectTimerRef.current);
        connectTimerRef.current = null;
      }
      reconnectAttemptsRef.current = 0;
      setConnected(true);
      setError(null);
      startHeartbeat();

      // 补发连接期间积压的提问
      const pending = pendingQuestionRef.current;
      if (pending) {
        pendingQuestionRef.current = null;
        sendQuestionRef.current(pending);
      }
    };

    ws.onmessage = (event) => {
      // 任意消息到达都视为连接活跃，重置 PONG 超时
      clearPongTimer();
      handleEvent(event.data as string);
    };

    ws.onerror = () => {
      setError("连接异常");
    };

    ws.onclose = (event) => {
      const wasConnecting = connectingRef.current;
      connectingRef.current = false;
      if (connectTimerRef.current) {
        clearTimeout(connectTimerRef.current);
        connectTimerRef.current = null;
      }
      clearPongTimer();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      setConnected(false);

      if (disposedRef.current) return;

      if (event.code === 4401) {
        setError("认证失败，请重新登录");
        return;
      }
      if (event.code === 4403) {
        setError("服务未启用");
        return;
      }

      // 用户主动断开（停止/卸载/登出）不重连
      if (event.code === 1000) return;

      // 连接超时/异常/网络抖动 → 指数退避重连
      if (wasConnecting || event.code !== 4000) {
        scheduleReconnectRef.current();
      }
    };
  }, [startHeartbeat, clearPongTimer, handleEvent, connectTimeout]);

  connectRef.current = connect;

  // 指数退避重连调度（单一入口，避免并发）
  scheduleReconnectRef.current = () => {
    if (disposedRef.current) return;
    if (reconnectTimerRef.current) return;

    const attempt = reconnectAttemptsRef.current;
    if (attempt >= maxReconnectAttempts) {
      setError("连接失败，请刷新页面重试");
      return;
    }

    const delay = Math.min(
      1000 * Math.pow(2, attempt) + Math.random() * 300,
      maxReconnectDelay
    );
    reconnectAttemptsRef.current = attempt + 1;

    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      connectRef.current();
    }, delay);
  };

  const sendQuestion = useCallback(
    (question: string) => {
      const { buildQueryPayload, onMessageSent } = optionsRef.current;

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        // 连接未就绪：缓存消息，待连接建立后自动补发
        pendingQuestionRef.current = question;
        setError(null);
        connect();
        return false;
      }

      onMessageSent?.(question);

      wsRef.current.send(
        JSON.stringify({
          type: "query",
          question,
          ...buildQueryPayload(question),
        })
      );

      return true;
    },
    [connect]
  );

  sendQuestionRef.current = sendQuestion;

  const disconnect = useCallback(() => {
    disposedRef.current = true;
    clearTimers();
    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null;
      ws.close(1000, "user disconnect");
    }
    connectingRef.current = false;
    setConnected(false);
  }, [clearTimers]);

  const stopGeneration = useCallback(() => {
    optionsRef.current.onStop?.();

    // 关闭当前连接但不标记 disposed，让 onclose 走 1000 主动断开逻辑
    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null;
      ws.close(1000, "user stopped");
    }
    setConnected(false);

    // 稍后重新建立连接
    setTimeout(() => {
      if (!disposedRef.current) {
        reconnectAttemptsRef.current = 0;
        connect();
      }
    }, 300);
  }, [connect]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connected,
    error,
    connect,
    disconnect,
    sendQuestion,
    stopGeneration,
  };
}
