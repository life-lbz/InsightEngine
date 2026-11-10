export function Header() {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">
          智能答疑
        </h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            基于 RAG 检索增强生成
          </span>
        </div>
      </div>
    </header>
  );
}