import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { type ReactNode } from "react";
import ErrorBoundary from "../components/common/ErrorBoundary";

function ThrowOnRender({ error }: { error: Error }): ReactNode {
  throw error;
}

function SafeChild(): ReactNode {
  return <div>正常内容</div>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("正常渲染子组件", () => {
    render(
      <ErrorBoundary>
        <SafeChild />
      </ErrorBoundary>
    );
    expect(screen.getByText("正常内容")).toBeInTheDocument();
  });

  it("捕获渲染异常并显示降级 UI", () => {
    const error = new Error("测试崩溃");
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowOnRender error={error} />
      </ErrorBoundary>
    );

    expect(screen.getByText("页面出现异常")).toBeInTheDocument();
    expect(screen.getByText("刷新页面")).toBeInTheDocument();
    spy.mockRestore();
  });

  it("点击刷新按钮调用 location.reload", () => {
    const error = new Error("测试崩溃");
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload: reloadSpy },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowOnRender error={error} />
      </ErrorBoundary>
    );

    const button = screen.getByText("刷新页面");
    button.click();
    expect(reloadSpy).toHaveBeenCalledOnce();
    spy.mockRestore();
  });
});
