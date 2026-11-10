import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_STYLES: Record<ToastType, { icon: string; className: string }> = {
  success: { icon: "✓", className: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  error: { icon: "✕", className: "border-red-200 bg-red-50 text-red-700" },
  info: { icon: "ℹ", className: "border-indigo-200 bg-indigo-50 text-indigo-700" },
};

const TOAST_DURATION = 3500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);
  const timersRef = useRef<Map<string, number>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = String(++idRef.current);
      setToasts((prev) => [...prev, { id, type, message }]);
      const timer = window.setTimeout(() => dismiss(id), TOAST_DURATION);
      timersRef.current.set(id, timer);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="fixed top-4 right-4 z-[100] space-y-2 w-80 max-w-[90vw]"
      >
        {toasts.map((t) => {
          const style = TOAST_STYLES[t.type];
          return (
            <div
              key={t.id}
              className={`flex items-start gap-2 px-4 py-3 rounded-lg border shadow-sm text-sm ${style.className}`}
            >
              <span className="shrink-0 font-bold leading-5">{style.icon}</span>
              <span className="flex-1 break-all leading-5">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="关闭提示"
                className="shrink-0 text-xs opacity-60 hover:opacity-100 leading-5"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast 必须在 ToastProvider 内使用");
  }
  return ctx;
}
