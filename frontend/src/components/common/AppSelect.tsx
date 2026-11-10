import { useId } from "react";

export interface AppSelectOption {
  value: string;
  label: string;
}

interface AppSelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  label?: string;
  /** 通过 options 提供选项（与 children 二选一） */
  options?: AppSelectOption[];
  onChange?: (value: string) => void;
}

/**
 * 统一 Select：与 CourseSelector 视觉对齐（border/圆角/字号），
 * 支持 label 关联与 focus ring。替换全站散落的原生 <select>。
 */
export function AppSelect({
  label,
  options,
  onChange,
  className = "",
  id,
  children,
  ...rest
}: AppSelectProps) {
  const autoId = useId();
  const selectId = id || (label ? `app-select-${autoId}` : undefined);

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label
          htmlFor={selectId}
          className="text-xs font-medium text-gray-500"
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        onChange={(e) => onChange?.(e.target.value)}
        className={`px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white text-gray-700
          focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300
          hover:border-gray-300 transition ${className}`}
        {...rest}
      >
        {options
          ? options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))
          : children}
      </select>
    </div>
  );
}
