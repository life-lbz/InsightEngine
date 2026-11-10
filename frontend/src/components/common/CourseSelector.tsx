import { useState } from "react";

interface CourseSelectorProps {
  courseIds: string[];
  value: string;
  onChange: (courseId: string) => void;
  accent?: "indigo" | "amber" | "rose";
}

const ACCENT_MAP: Record<
  NonNullable<CourseSelectorProps["accent"]>,
  { activeText: string; hoverBorder: string; activeBg: string }
> = {
  indigo: {
    activeText: "text-indigo-600",
    hoverBorder: "hover:border-indigo-300",
    activeBg: "hover:bg-indigo-50/50",
  },
  amber: {
    activeText: "text-amber-600",
    hoverBorder: "hover:border-amber-300",
    activeBg: "hover:bg-amber-50/50",
  },
  rose: {
    activeText: "text-rose-600",
    hoverBorder: "hover:border-rose-300",
    activeBg: "hover:bg-rose-50/50",
  },
};

export function CourseSelector({
  courseIds,
  value,
  onChange,
  accent = "indigo",
}: CourseSelectorProps) {
  const [open, setOpen] = useState(false);

  const currentLabel = value || "全部课程";
  const colors = ACCENT_MAP[accent];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg ${colors.hoverBorder} transition`}
      >
        <svg
          className="w-4 h-4 text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
          />
        </svg>
        <span className="text-sm text-gray-700">{currentLabel}</span>
        <svg
          className={`w-3.5 h-3.5 text-gray-400 transition-transform ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {open && (
        <>
          {/* 遮罩 */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />

          {/* 下拉菜单 */}
          <div className="absolute top-full left-0 mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1">
            <button
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition ${
                value === "" ? `${colors.activeText} font-medium` : "text-gray-700"
              }`}
            >
              全部课程
            </button>
            {courseIds.map((courseId) => (
              <button
                key={courseId}
                onClick={() => {
                  onChange(courseId);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition ${
                  value === courseId
                    ? `${colors.activeText} font-medium`
                    : "text-gray-700"
                }`}
              >
                {courseId}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
