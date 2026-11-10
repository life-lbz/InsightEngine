import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Modal } from "./Modal";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions | string) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

/**
 * Promise 化确认框：`const ok = await confirm({ message: "确定删除？" })`，
 * 替代各页面散落的原生 window.confirm / window.alert。
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{
    open: boolean;
    options: ConfirmOptions;
  } | null>(null);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback((options: ConfirmOptions | string) => {
    const opts: ConfirmOptions =
      typeof options === "string" ? { message: options } : options;
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
      setState({ open: true, options: opts });
    });
  }, []);

  const settle = useCallback((value: boolean) => {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setState(null);
  }, []);

  const opts = state?.options;

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      <Modal
        open={Boolean(state?.open)}
        onClose={() => settle(false)}
        title={opts?.title || "确认操作"}
        maxWidth="sm"
        footer={
          <>
            <button
              onClick={() => settle(false)}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              {opts?.cancelText || "取消"}
            </button>
            <button
              onClick={() => settle(true)}
              autoFocus
              className={`px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90 ${
                opts?.danger
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-indigo-600 hover:bg-indigo-700"
              }`}
            >
              {opts?.confirmText || "确认"}
            </button>
          </>
        }
      >
        <p className="text-sm text-gray-600 whitespace-pre-wrap">{opts?.message}</p>
      </Modal>
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmContextValue {
  const ctx = useContext(ConfirmContext);
  if (!ctx) {
    throw new Error("useConfirm 必须在 ConfirmProvider 内使用");
  }
  return ctx;
}
