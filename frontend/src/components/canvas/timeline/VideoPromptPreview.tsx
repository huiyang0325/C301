import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, Eye, EyeOff, MessageSquare, Music, Video } from "lucide-react";
import type { Dialogue, VideoPrompt } from "@/types";
import { CAMERA_MOTION_I18N_KEYS } from "@/types";

interface VideoPromptPreviewProps {
  prompt: VideoPrompt;
  /** 是否可折叠，默认 true */
  collapsible?: boolean;
}

/**
 * 视频提示词预览组件 — 可视化展示视频生成所用的完整提示词。
 *
 * 显示模式：
 * 1. 结构化视图 — 各字段独立展示，便于检查细节
 * 2. 编译后文本 — 将各字段合并为实际发送给模型的字符串
 */
export function VideoPromptPreview({ prompt, collapsible = true }: VideoPromptPreviewProps) {
  const { t } = useTranslation("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [showCompiled, setShowCompiled] = useState(false);

  const dialogue: Dialogue[] = prompt.dialogue ?? [];

  // 编译后的提示词文本（与后端 video_prompt_to_yaml 逻辑保持一致）
  const compiledText = buildCompiledVideoPrompt(prompt);

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900/40 p-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Video className="h-3.5 w-3.5 text-indigo-400" />
          <span className="text-[11px] font-semibold text-gray-300">
            {t("video_prompt_preview") ?? "Video Prompt Preview"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* 编译文本切换 */}
          <button
            type="button"
            onClick={() => setShowCompiled((v) => !v)}
            className="inline-flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-400"
            title={showCompiled ? t("show_structured_view") : t("show_compiled_view")}
          >
            {showCompiled ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            <span>{showCompiled ? t("structured_view") : t("compiled_view")}</span>
          </button>

          {collapsible && (
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              className="inline-flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-400"
            >
              <ChevronDown className={`h-3 w-3 transition-transform ${collapsed ? "-rotate-90" : ""}`} />
              <span>{collapsed ? t("expand") : t("collapse")}</span>
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="flex flex-col gap-2">
          {showCompiled ? (
            /* 编译后文本视图 */
            <div className="rounded-md border border-gray-700 bg-gray-950/60 p-2">
              <pre className="whitespace-pre-wrap text-[11px] text-gray-300 font-mono leading-relaxed">
                {compiledText || <span className="text-gray-600 italic">{t("no_video_prompt")}</span>}
              </pre>
            </div>
          ) : (
            /* 结构化视图 */
            <div className="flex flex-col gap-2 pl-1">
              {/* Action */}
              <FieldBlock icon={<Video className="h-3 w-3 text-blue-400" />} label={t("action_label") ?? "动作"}>
                <span className="text-[12px] text-gray-200 leading-relaxed">
                  {prompt.action || <span className="text-gray-600 italic">{t("not_set")}</span>}
                </span>
              </FieldBlock>

              {/* Camera Motion */}
              {prompt.camera_motion && (
                <FieldBlock
                  icon={<span className="text-[10px] text-orange-400">CAM</span>}
                  label={t("camera_motion_label") ?? "镜头运动"}
                >
                  <span className="text-[12px] text-gray-300">
                    {t(CAMERA_MOTION_I18N_KEYS[prompt.camera_motion] ?? prompt.camera_motion)}
                  </span>
                </FieldBlock>
              )}

              {/* Ambiance Audio */}
              {prompt.ambiance_audio && (
                <FieldBlock icon={<Music className="h-3 w-3 text-green-400" />} label={t("ambiance_audio_label") ?? "环境音效"}>
                  <span className="text-[12px] text-gray-300 leading-relaxed">{prompt.ambiance_audio}</span>
                </FieldBlock>
              )}

              {/* Dialogue */}
              {dialogue.length > 0 && (
                <FieldBlock
                  icon={<MessageSquare className="h-3 w-3 text-purple-400" />}
                  label={t("dialogue_label") ?? "对话"}
                >
                  <div className="flex flex-col gap-1">
                    {dialogue.map((d, i) => (
                      <div key={i} className="flex flex-col">
                        <span className="text-[10px] font-medium text-purple-300">{d.speaker}</span>
                        <span className="text-[11px] text-gray-300 leading-relaxed">&quot;{d.line}&quot;</span>
                      </div>
                    ))}
                  </div>
                </FieldBlock>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub components
// ---------------------------------------------------------------------------

function FieldBlock({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-1">
        {icon}
        <span className="text-[10px] font-medium uppercase tracking-wider text-gray-500">{label}</span>
      </div>
      <div className="pl-4">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compiled prompt builder (mirrors backend logic)
// ---------------------------------------------------------------------------

export function buildCompiledVideoPrompt(prompt: VideoPrompt): string {
  const lines: string[] = [];

  if (prompt.action) {
    lines.push(`Action: ${prompt.action}`);
  }

  if (prompt.camera_motion) {
    lines.push(`Camera Motion: ${prompt.camera_motion}`);
  }

  if (prompt.ambiance_audio) {
    lines.push(`Ambiance Audio: ${prompt.ambiance_audio}`);
  }

  const dialogue: Dialogue[] = prompt.dialogue ?? [];
  if (dialogue.length > 0) {
    lines.push("Dialogue:");
    for (const d of dialogue) {
      lines.push(`  - Speaker: ${d.speaker}`);
      lines.push(`    Line: ${d.line}`);
    }
  }

  return lines.join("\n");
}