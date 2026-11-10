import { useState } from "react";
import { useAuthStore } from "../../stores/authStore";
import { agentApi } from "../../api/agent";
import { AgentBadge } from "../../components/agent/AgentBadge";
import { CourseSelector } from "../../components/common/CourseSelector";
import type { InsightReport } from "../../types";

const REPORT_TEMPLATES = [
  {
    key: "overview",
    label: "学情总览",
    prompt: "请生成当前课程的整体学情分析报告，包括学习进度、高频问题和知识薄弱点",
  },
  {
    key: "at_risk",
    label: "学困生预警",
    prompt: "请分析当前课程中学困生情况，列出需要重点关注的学生及原因",
  },
  {
    key: "knowledge_gap",
    label: "知识盲区",
    prompt: "请分析当前课程的知识点掌握情况，找出学生普遍薄弱的知识点",
  },
  {
    key: "recommendation",
    label: "教学建议",
    prompt: "基于当前学情数据，请给出具体的教学改进建议和下一步教学重点",
  },
];

export default function TeacherInsightPage() {
  const user = useAuthStore((s) => s.user);
  const [courseId, setCourseId] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<InsightReport | null>(null);
  const [rawAnswer, setRawAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeTemplate, setActiveTemplate] = useState<string | null>(null);

  const handleGenerate = async (prompt: string, templateKey: string) => {
    setLoading(true);
    setError(null);
    setActiveTemplate(templateKey);
    setRawAnswer("");

    try {
      const sessionId = `teacher-insight-${Date.now()}`;
      const result = await agentApi.chat(prompt, courseId, sessionId);
      setRawAnswer(result.answer);

      const parsed = parseInsightReport(result.answer, courseId);
      setReport(parsed);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Agent 请求失败，请稍后重试"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-800">AI 学情分析</h1>
            <AgentBadge agentName="teacher_insight_agent" size="md" />
          </div>
          <p className="text-gray-500 mt-1">
            由 AI Agent 自动聚合学情数据并生成分析报告
          </p>
        </div>
      </div>

      {/* 课程选择 */}
      <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium text-gray-700">课程</label>
          <CourseSelector
            courseIds={user?.course_ids || []}
            value={courseId}
            onChange={setCourseId}
            accent="amber"
          />
        </div>
      </div>

      {/* 报告模板 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {REPORT_TEMPLATES.map((tpl) => (
          <button
            key={tpl.key}
            onClick={() => handleGenerate(tpl.prompt, tpl.key)}
            disabled={loading}
            className={`p-4 rounded-xl border text-left transition ${
              activeTemplate === tpl.key
                ? "border-amber-300 bg-amber-50/50 shadow-sm"
                : "border-gray-100 bg-white hover:border-amber-200 hover:shadow-sm"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
                <svg
                  className="w-4 h-4 text-amber-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
              </div>
            </div>
            <p className="text-sm font-medium text-gray-700">{tpl.label}</p>
            <p className="text-xs text-gray-400 mt-1 line-clamp-2">
              {tpl.prompt}
            </p>
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-8">
          <div className="flex items-center gap-3 mb-4">
            <AgentBadge agentName="teacher_insight_agent" size="md" />
            <span className="text-sm text-gray-500">Agent 正在分析学情数据...</span>
          </div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-100 rounded animate-pulse" />
            <div className="h-4 bg-gray-100 rounded animate-pulse w-5/6" />
            <div className="h-4 bg-gray-100 rounded animate-pulse w-4/6" />
            <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4" />
          </div>
        </div>
      )}

      {/* Report */}
      {!loading && report && <InsightReportView report={report} rawAnswer={rawAnswer} />}
    </div>
  );
}

function InsightReportView({
  report,
  rawAnswer,
}: {
  report: InsightReport;
  rawAnswer: string;
}) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-gradient-to-br from-amber-50 to-white rounded-xl p-5 border border-amber-100">
        <div className="flex items-center gap-2 mb-3">
          <AgentBadge agentName="teacher_insight_agent" size="md" />
          <span className="text-xs text-gray-400">
            生成于 {report.generated_at}
          </span>
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">{report.summary}</p>
      </div>

      {/* Key Findings */}
      {report.key_findings.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="font-semibold text-gray-700 mb-3">关键发现</h3>
          <div className="space-y-2">
            {report.key_findings.map((finding, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-xs flex items-center justify-center font-bold shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <p className="text-sm text-gray-600">{finding}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="font-semibold text-gray-700 mb-3">教学建议</h3>
          <div className="space-y-2">
            {report.recommendations.map((rec, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <svg
                  className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <p className="text-sm text-gray-600">{rec}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* At-risk Students */}
      {report.at_risk_students.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="font-semibold text-gray-700 mb-3">学困生预警</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-3 text-xs font-medium text-gray-500">
                    学员
                  </th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-gray-500">
                    预警原因
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.at_risk_students.map((s, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-50 hover:bg-gray-50/50"
                  >
                    <td className="py-2 px-3 font-medium text-gray-700">
                      {s.user_id}
                    </td>
                    <td className="py-2 px-3 text-gray-600">{s.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Knowledge Gaps */}
      {report.knowledge_gaps.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="font-semibold text-gray-700 mb-3">知识盲区</h3>
          <div className="space-y-3">
            {report.knowledge_gaps.map((gap, idx) => (
              <div key={idx}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-gray-700">
                    {gap.knowledge_point}
                  </span>
                  <span className="text-xs text-gray-400">
                    掌握率 {(gap.mastery_rate * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      gap.mastery_rate < 0.4
                        ? "bg-red-400"
                        : gap.mastery_rate < 0.7
                          ? "bg-amber-400"
                          : "bg-emerald-400"
                    }`}
                    style={{ width: `${gap.mastery_rate * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw Answer */}
      <details className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <summary className="cursor-pointer text-sm text-gray-500 font-medium">
          查看 Agent 原始回复
        </summary>
        <div className="mt-3 text-sm text-gray-600 whitespace-pre-wrap leading-relaxed">
          {rawAnswer}
        </div>
      </details>
    </div>
  );
}

function parseInsightReport(answer: string, courseId: string): InsightReport {
  const reportId = `report-${Date.now()}`;
  const generatedAt = new Date().toLocaleString("zh-CN");

  const lines = answer.split("\n").filter((l) => l.trim());

  const summary = lines.slice(0, 3).join(" ");

  const keyFindings: string[] = [];
  const recommendations: string[] = [];
  const atRiskStudents: { user_id: string; reason: string }[] = [];
  const knowledgeGaps: { knowledge_point: string; mastery_rate: number }[] = [];

  let currentSection = "";
  for (const line of lines) {
    const trimmed = line.trim();
    if (/关键发现|问题|发现/.test(trimmed) && trimmed.length < 20) {
      currentSection = "findings";
      continue;
    }
    if (/建议|推荐|改进/.test(trimmed) && trimmed.length < 20) {
      currentSection = "recommendations";
      continue;
    }
    if (/学困|预警|风险学生/.test(trimmed) && trimmed.length < 20) {
      currentSection = "at_risk";
      continue;
    }
    if (/知识|盲区|薄弱/.test(trimmed) && trimmed.length < 20) {
      currentSection = "gaps";
      continue;
    }

    if (currentSection === "findings" && trimmed.match(/^[-\d.]/)) {
      keyFindings.push(trimmed.replace(/^[-\d.\s]+/, ""));
    }
    if (currentSection === "recommendations" && trimmed.match(/^[-\d.]/)) {
      recommendations.push(trimmed.replace(/^[-\d.\s]+/, ""));
    }
  }

  return {
    report_id: reportId,
    course_id: courseId,
    generated_at: generatedAt,
    summary,
    key_findings: keyFindings,
    recommendations,
    at_risk_students: atRiskStudents,
    knowledge_gaps: knowledgeGaps,
  };
}
