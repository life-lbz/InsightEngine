import { useCallback, useEffect, useRef, useState } from "react";

export interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** 手动重新拉取（loading 置位） */
  reload: () => void;
  /** 静默写入数据（供轮询等场景使用，不触发 loading） */
  setData: (data: T | null) => void;
}

/**
 * 轻量数据请求抽象：收敛 loading / data / error 三态 + reload / setData。
 * 替代页面手写的 `useState(loading) + useCallback(fetch) + catch 静默` 三件套。
 *
 * 注意：fetcher 用 ref 引用，每次渲染不必 useCallback 包裹；
 * deps 变化或调用 reload() 时重新执行。
 */
export function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): UseFetchResult<T> {
  const [data, setDataState] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcherRef
      .current()
      .then((d) => {
        if (!cancelled) setDataState(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "加载失败，请稍后重试"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((d: T | null) => setDataState(d), []);

  return { data, loading, error, reload, setData };
}
