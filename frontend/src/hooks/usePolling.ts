import { useEffect, useRef } from "react";

export interface UsePollingOptions {
  /** 成功时的轮询间隔（ms） */
  intervalMs: number;
  /** 失败退避的最大间隔（ms），默认 30s */
  maxRetryDelayMs?: number;
  /** 失败退避倍数基数，默认 2（2^0, 2^1, ...） */
  retryBase?: number;
  /** 置 true 时暂停轮询 */
  paused?: boolean;
  /** 单轮失败回调 */
  onError?: (err: unknown) => void;
}

/**
 * 轮询抽象：内置失败指数退避、页面不可见暂停、卸载必清理。
 * 替代页面裸 `setInterval(fetch, N)`（无退避、无清理隐患）。
 */
export function usePolling(
  task: () => Promise<void>,
  deps: unknown[],
  options: UsePollingOptions
) {
  const {
    intervalMs,
    maxRetryDelayMs = 30000,
    retryBase = 2,
    paused = false,
    onError,
  } = options;

  const taskRef = useRef(task);
  taskRef.current = task;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    if (paused) return;

    let timer: number | null = null;
    let disposed = false;
    let retryCount = 0;
    let running = false;

    const schedule = (delay: number) => {
      if (disposed) return;
      timer = window.setTimeout(run, delay);
    };

    const run = async () => {
      if (disposed || running) return;
      running = true;
      try {
        await taskRef.current();
        retryCount = 0;
      } catch (err) {
        retryCount += 1;
        onErrorRef.current?.(err);
      } finally {
        running = false;
      }
      if (disposed) return;
      // 失败指数退避；成功恢复固定间隔
      const delay = Math.min(
        intervalMs * Math.pow(retryBase, Math.min(retryCount, 6)),
        maxRetryDelayMs
      );
      schedule(delay);
    };

    // 立即执行首轮
    run();

    // 页面不可见时暂停，恢复后立即续跑（避免后台空转）
    const onVisibility = () => {
      if (document.hidden) {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
      } else if (!timer && !running) {
        run();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      disposed = true;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, intervalMs, maxRetryDelayMs, retryBase, paused]);
}
