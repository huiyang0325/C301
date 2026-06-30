/**
 * 长视频编排页面 - 按 Segment Break 分组展示所有分镜
 * 支持组内上下移动顺序和删除分镜
 * 独立于原始剧本，数据存储在 arrangements/ 目录
 */

import { useMemo, useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ArrowUp, ArrowDown, Trash2, ImageIcon, AlertCircle, RefreshCw, Video, Film } from "lucide-react";
import { API } from "@/api";
import { useProjectsStore } from "@/stores/projects-store";
import { useAppStore } from "@/stores/app-store";
import { PreviewableImageFrame } from "@/components/ui/PreviewableImageFrame";
import { AspectFrame } from "@/components/ui/AspectFrame";
import { ImageFlipReveal } from "@/components/ui/ImageFlipReveal";
import type {
  EpisodeScript,
  NarrationEpisodeScript,
  DramaEpisodeScript,
  NarrationSegment,
  DramaScene,
  ProjectData,
} from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Segment = NarrationSegment | DramaScene;

function getSegmentId(segment: Segment, mode: "narration" | "drama"): string {
  return mode === "narration"
    ? (segment as NarrationSegment).segment_id
    : (segment as DramaScene).scene_id;
}

/** Group segments by segment_break into contiguous groups. */
function groupBySegmentBreak(segments: Segment[]): Segment[][] {
  const groups: Segment[][] = [];
  let current: Segment[] = [];
  for (const seg of segments) {
    if (seg.segment_break && current.length > 0) {
      groups.push(current);
      current = [];
    }
    current.push(seg);
  }
  if (current.length > 0) groups.push(current);
  return groups;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildSegmentDescription(segment: Segment, contentMode: "narration" | "drama"): string {
  const parts: string[] = [];

  if (contentMode === "narration") {
    const s = segment as NarrationSegment;
    if (s.novel_text) {
      parts.push(`[原文] ${s.novel_text}`);
    }
  }

  const vp = segment.video_prompt;
  if (typeof vp === "string" && vp) {
    parts.push(vp);
  } else if (typeof vp === "object" && vp !== null) {
    const v = vp as { action?: string; camera_motion?: string; ambiance_audio?: string; dialogue?: { speaker: string; line: string }[] };
    if (v.action) parts.push(`Action: ${v.action}`);
    if (v.camera_motion) parts.push(`Camera: ${v.camera_motion}`);
    if (v.ambiance_audio) parts.push(`Ambiance: ${v.ambiance_audio}`);
    if (v.dialogue && v.dialogue.length > 0) {
      for (const d of v.dialogue) {
        parts.push(`Dialogue: ${d.speaker} - "${d.line}"`);
      }
    }
  }

  const chars = contentMode === "drama"
    ? ((segment as DramaScene).characters_in_scene ?? [])
    : ((segment as NarrationSegment).characters_in_segment ?? []);
  if (chars.length > 0) parts.push(`Characters: ${chars.join(", ")}`);

  if (segment.scenes && segment.scenes.length > 0) parts.push(`Scenes: ${segment.scenes.join(", ")}`);
  if (segment.props && segment.props.length > 0) parts.push(`Props: ${segment.props.join(", ")}`);

  parts.push(`Transition: ${segment.transition_to_next}`);

  if (segment.note) parts.push(`Note: ${segment.note}`);

  return parts.join("\n");
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LongVideoArrangeProps {
  projectName: string;
  episode: number;
  episodeScript: EpisodeScript;
  scriptFile?: string;
  projectData: ProjectData | null;
  contentMode: "narration" | "drama";
}

// ---------------------------------------------------------------------------
// Segment Row Component
// ---------------------------------------------------------------------------

interface SegmentRowProps {
  segment: Segment;
  contentMode: "narration" | "drama";
  projectName: string;
  index: number;
  totalInGroup: number;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onDelete?: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
}

function SegmentRow({
  segment,
  contentMode,
  projectName,
  index,
  totalInGroup,
  onMoveUp,
  onMoveDown,
  onDelete,
  canMoveUp,
  canMoveDown,
}: SegmentRowProps) {
  const { t } = useTranslation("dashboard");
  const segmentId = getSegmentId(segment, contentMode);
  const assets = segment.generated_assets;
  const storyboardFp = useProjectsStore(
    (s) => assets?.storyboard_image ? s.getAssetFingerprint(assets.storyboard_image) : null,
  );
  const storyboardUrl = assets?.storyboard_image
    ? API.getFileUrl(projectName, assets.storyboard_image, storyboardFp)
    : null;

  const [promptText, setPromptText] = useState(() => buildSegmentDescription(segment, contentMode));

  return (
    <div className="flex gap-3 py-2 px-3 bg-gray-900/50 border border-gray-800 rounded-lg hover:bg-gray-900 transition-colors">
      {/* 缩略图 */}
      <div className="w-20 h-14 flex-shrink-0 rounded overflow-hidden bg-gray-800">
        <PreviewableImageFrame src={storyboardUrl} alt={segmentId}>
          <AspectFrame ratio="16:9">
            <ImageFlipReveal
              src={storyboardUrl}
              alt={segmentId}
              loading="lazy"
              className="h-full w-full object-cover"
              fallback={
                <div className="flex h-full w-full items-center justify-center text-gray-600">
                  <ImageIcon className="h-5 w-5" />
                </div>
              }
            />
          </AspectFrame>
        </PreviewableImageFrame>
      </div>

      {/* ID + 时长 */}
      <div className="flex-shrink-0 text-xs font-mono text-gray-500 pt-0.5">{segmentId} · {segment.duration_seconds}s</div>

      {/* 提示词框 */}
      <div className="flex-1 min-w-0">
        <textarea
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          rows={4}
          className="w-full max-h-28 overflow-y-auto resize-none rounded border border-gray-700 bg-gray-800/40 px-2.5 py-2 text-xs text-gray-300 leading-relaxed placeholder-gray-500 focus:border-indigo-500 focus-outline-none"
        />
      </div>

      {/* 操作按钮 */}
      <div className="flex flex-col items-center gap-1 flex-shrink-0">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={!canMoveUp}
          title={t("move_up")}
          className={`p-1.5 rounded transition-colors focus-ring ${
            canMoveUp
              ? "text-gray-500 hover:text-indigo-400 hover:bg-indigo-600/20"
              : "text-gray-700 cursor-not-allowed"
          }`}
        >
          <ArrowUp className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={!canMoveDown}
          title={t("move_down")}
          className={`p-1.5 rounded transition-colors focus-ring ${
            canMoveDown
              ? "text-gray-500 hover:text-indigo-400 hover:bg-indigo-600/20"
              : "text-gray-700 cursor-not-allowed"
          }`}
        >
          <ArrowDown className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          title={t("delete_segment")}
          className="p-1.5 rounded text-gray-500 hover:text-red-400 hover:bg-red-600/20 transition-colors focus-ring"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Segment Group Component
// ---------------------------------------------------------------------------

interface SegmentGroupProps {
  group: Segment[];
  groupIndex: number;
  contentMode: "narration" | "drama";
  projectName: string;
  episode: number;
  onMoveSegment?: (groupIndex: number, fromIndex: number, toIndex: number) => void;
  onDeleteSegment?: (groupIndex: number, index: number) => void;
  onGenerateLongVideo?: (groupIndex: number, segmentIds: string[], totalDuration: number) => void;
  generatedVideo?: string | null;
  aspectRatio?: "9:16" | "16:9" | "3:4" | "1:1";
}

function SegmentGroup({
  group,
  groupIndex,
  contentMode,
  projectName,
  episode,
  onMoveSegment,
  onDeleteSegment,
  onGenerateLongVideo,
  generatedVideo,
  aspectRatio = "16:9",
}: SegmentGroupProps) {
  const { t } = useTranslation("dashboard");

  // 计算该组有 storyboard_image 的分镜的 IDs 和总时长
  const validSegments = group.filter((s) => {
    const assets = s.generated_assets;
    return assets?.storyboard_image;
  });
  const segmentIds = validSegments.map((s) => getSegmentId(s, contentMode));
  const totalDuration = validSegments.reduce((sum, s) => sum + s.duration_seconds, 0);
  // 每个分镜使用自己的 duration_seconds（而不是总和），避免 3x4s=12s 传成每个视频12s
  const segmentDuration = validSegments.length > 0 ? validSegments[0].duration_seconds : 0;

  // 视频预览 URL
  const videoUrl = generatedVideo ? API.getFileUrl(projectName, generatedVideo) : null;

  return (
    <div className="mb-4">
      {/* 组标题 */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 border-t border-dashed border-amber-600/40" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-500/70">
          Segment Break {groupIndex + 1}
        </span>
        <div className="flex-1 border-t border-dashed border-amber-600/40" />
      </div>

      {/* 分镜列表 */}
      <div className="flex flex-col gap-2">
        {group.map((segment, index) => (
          <SegmentRow
            key={getSegmentId(segment, contentMode)}
            segment={segment}
            contentMode={contentMode}
            projectName={projectName}
            index={index}
            totalInGroup={group.length}
            canMoveUp={index > 0}
            canMoveDown={index < group.length - 1}
            onMoveUp={() => onMoveSegment?.(groupIndex, index, index - 1)}
            onMoveDown={() => onMoveSegment?.(groupIndex, index, index + 1)}
            onDelete={() => onDeleteSegment?.(groupIndex, index)}
          />
        ))}
      </div>

      {/* 视频预览 */}
      <div className="mt-3">
        <div className="mb-1.5 flex items-center gap-1.5">
          <Film className="h-3 w-3 text-gray-500" />
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            {t("long_video_preview") ?? "Long Video"}
          </span>
        </div>
        {videoUrl ? (
          <AspectFrame ratio={aspectRatio}>
            <video
              src={videoUrl}
              className="h-full w-full object-contain"
              controls
              playsInline
            />
          </AspectFrame>
        ) : (
          <AspectFrame ratio={aspectRatio}>
            <div className="flex h-full w-full items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-800/30">
              <span className="text-xs text-gray-600">{t("no_long_video_yet")}</span>
            </div>
          </AspectFrame>
        )}
      </div>

      {/* 生成长视频按钮 */}
      <div className="mt-3 flex justify-center">
        <button
          type="button"
          onClick={() => onGenerateLongVideo?.(groupIndex, segmentIds, segmentDuration)}
          disabled={segmentIds.length === 0}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition-colors ${
            segmentIds.length === 0
              ? "bg-gray-700 text-gray-500 cursor-not-allowed"
              : "bg-indigo-600 text-white hover:bg-indigo-500"
          }`}
        >
          <Video className="h-4 w-4" />
          {t("generate_long_video", { count: segmentIds.length, duration: totalDuration })}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function LongVideoArrange({
  projectName,
  episode,
  episodeScript: _episodeScript,
  scriptFile: _scriptFile,
  projectData,
  contentMode,
}: LongVideoArrangeProps) {
  const { t } = useTranslation("dashboard");
  const [arrangement, setArrangement] = useState<EpisodeScript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConfirmDelete, setShowConfirmDelete] = useState<{ groupIndex: number; index: number } | null>(null);
  const [generatedVideos, setGeneratedVideos] = useState<Record<number, string>>({});

  // 视频宽高比（与剧本时间线一致）
  const aspectRatio = (
    typeof projectData?.aspect_ratio === "string"
      ? projectData.aspect_ratio
      : projectData?.aspect_ratio?.storyboard ??
        (contentMode === "narration" ? "9:16" : "16:9")
  ) as "9:16" | "16:9" | "3:4" | "1:1";

  // 加载编排数据
  const loadArrangement = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await API.getArrangement(projectName, episode);
      setArrangement(data as EpisodeScript);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [projectName, episode]);

  // 初始加载
  useEffect(() => {
    loadArrangement();
  }, [loadArrangement]);

  // 获取 segments 数组
  const segments = useMemo<Segment[]>(() => {
    if (!arrangement) return [];
    return contentMode === "narration"
      ? ((arrangement as NarrationEpisodeScript).segments ?? [])
      : ((arrangement as DramaEpisodeScript).scenes ?? []);
  }, [arrangement, contentMode]);

  // 按 segment_break 分组
  const segmentGroups = useMemo(() => groupBySegmentBreak(segments), [segments]);

  // 当编排数据加载后，从 long_video_groups 恢复已生成的视频
  useEffect(() => {
    if (!arrangement) return;
    const longVideoGroups = (arrangement as Record<string, unknown>).long_video_groups as Record<string, string> | undefined;
    if (longVideoGroups && Object.keys(longVideoGroups).length > 0) {
      const videosMap: Record<number, string> = {};
      // 重新计算 segmentGroups（因为 arrangement 变了）
      const groups = groupBySegmentBreak(segments);
      groups.forEach((group, groupIndex) => {
        // 只用有 storyboard_image 的分镜来计算 key（与后端一致）
        const validIds = group
          .filter((s) => s.generated_assets?.storyboard_image)
          .map((s) => getSegmentId(s, contentMode))
          .sort()
          .join(",");
        if (longVideoGroups[validIds]) {
          videosMap[groupIndex] = longVideoGroups[validIds];
        }
      });
      setGeneratedVideos(videosMap);
    }
  }, [arrangement, segments, contentMode]);

  // 计算总时长
  const totalDuration = useMemo(
    () => segments.reduce((sum, s) => sum + s.duration_seconds, 0),
    [segments],
  );

  // 处理移动 - 组内上下移动分镜
  const handleMoveSegment = useCallback(
    async (groupIndex: number, fromIndex: number, toIndex: number) => {
      if (!arrangement) return;

      const contentModeVal = arrangement.content_mode ?? contentMode;
      const idKey = contentModeVal === "narration" ? "segment_id" : "scene_id";

      // 计算在 flat segments 数组中的实际索引
      let offsetBeforeGroup = 0;
      for (let g = 0; g < groupIndex; g++) {
        offsetBeforeGroup += segmentGroups[g].length;
      }
      const actualFromIndex = offsetBeforeGroup + fromIndex;
      const actualToIndex = offsetBeforeGroup + toIndex;

      // 构建新的 segment_ids 顺序
      const allIds = segments.map((s) => getSegmentId(s, contentMode));
      // 交换两个位置
      const newIds = [...allIds];
      newIds[actualFromIndex] = allIds[actualToIndex];
      newIds[actualToIndex] = allIds[actualFromIndex];

      try {
        await API.reorderArrangement(projectName, episode, newIds);
        await loadArrangement();
      } catch (e) {
        setError(String(e));
      }
    },
    [arrangement, contentMode, segmentGroups, segments, projectName, episode, loadArrangement],
  );

  // 处理删除
  const handleDeleteConfirm = useCallback(async () => {
    if (!showConfirmDelete || !arrangement) return;
    const { groupIndex, index } = showConfirmDelete;
    const group = segmentGroups[groupIndex];
    const segment = group[index];
    const segmentId = getSegmentId(segment, arrangement.content_mode ?? contentMode);

    try {
      await API.deleteArrangementSegment(projectName, episode, segmentId);
      setShowConfirmDelete(null);
      await loadArrangement();
    } catch (e) {
      setError(String(e));
    }
  }, [showConfirmDelete, arrangement, segmentGroups, contentMode, projectName, episode, loadArrangement]);

  // 重置编排
  const handleReset = useCallback(async () => {
    try {
      await API.deleteArrangement(projectName, episode);
      await loadArrangement();
    } catch (e) {
      setError(String(e));
    }
  }, [projectName, episode, loadArrangement]);

  // 处理生成长视频
  const [generatingLongVideo, setGeneratingLongVideo] = useState(false);
  const handleGenerateLongVideo = useCallback(
    async (groupIndex: number, segmentIds: string[], totalDuration: number) => {
      if (!arrangement) return;
      // 构建合并的 prompt（从该组所有分镜收集）
      const group = segmentGroups[groupIndex];
      const promptText = group
        .map((s) => {
          const vp = s.video_prompt;
          if (typeof vp === "string") return vp;
          if (typeof vp === "object" && vp !== null) {
            return (vp as { action?: string }).action || "";
          }
          return "";
        })
        .filter(Boolean)
        .join(" ");

      setGeneratingLongVideo(true);
      try {
        const result = await API.generateLongVideo(
          projectName,
          episode,
          segmentIds,
          promptText || "continuous video",
          totalDuration,
          "16:9",
        );
        useAppStore.getState().pushToast(
          result.message || t("long_video_task_submitted", { count: segmentIds.length }),
          "success",
        );

        // 轮询 arrangement，直到 long_video_groups 出现该组的新视频
        const group = segmentGroups[groupIndex];
        const keyIds = group
          .filter((s) => s.generated_assets?.storyboard_image)
          .map((s) => getSegmentId(s, contentMode))
          .sort()
          .join(",");

        const maxAttempts = 40; // 40 * 3s = 120s
        let attempts = 0;
        const poll = async () => {
          attempts++;
          const freshData = await API.getArrangement(projectName, episode) as Record<string, unknown>;
          const lvg = freshData?.long_video_groups as Record<string, string> | undefined;
          if (lvg && lvg[keyIds]) {
            setArrangement(freshData as EpisodeScript);
            setGeneratedVideos((prev) => ({ ...prev, [groupIndex]: lvg[keyIds] }));
            useAppStore.getState().pushToast(t("long_video_ready"), "success");
          } else if (attempts < maxAttempts) {
            setTimeout(poll, 3000);
          } else {
            useAppStore.getState().pushToast(t("long_video_timeout"), "warning");
          }
        };
        setTimeout(poll, 3000);
      } catch (e) {
        setError(String(e));
      } finally {
        setGeneratingLongVideo(false);
      }
    },
    [projectName, episode, segmentGroups, contentMode, t],
  );

  // 加载状态
  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-500">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="h-8 w-8 animate-spin text-gray-600" />
          <p>{t("loading_projects")}</p>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error) {
    return (
      <div className="flex h-64 items-center justify-center text-red-500">
        <div className="flex flex-col items-center gap-3">
          <AlertCircle className="h-10 w-10" />
          <p>{error}</p>
          <button onClick={loadArrangement} className="text-sm text-indigo-400 hover:text-indigo-300">
            {t("retry")}
          </button>
        </div>
      </div>
    );
  }

  // 空状态
  if (!arrangement || segments.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-500">
        <div className="flex flex-col items-center gap-3">
          <AlertCircle className="h-10 w-10 text-gray-600" />
          <p>{t("no_episodes_yet")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* 头部信息 */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-gray-300">
            {arrangement.title} · {segments.length} {contentMode === "narration" ? t("segment_count", { count: segments.length }) : t("scene_count_label", { count: segments.length })} · ~{totalDuration}s
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            title={t("reset_arrangement")}
            className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-2.5 py-1 text-xs text-gray-400 hover:bg-gray-800 transition-colors"
          >
            <RefreshCw className="h-3 w-3" />
            {t("reset_arrangement")}
          </button>
          <span className="text-xs text-amber-500/70 flex items-center gap-1.5">
            <AlertCircle className="h-3 w-3" />
            {t("longvideo_arrange_hint")}
          </span>
        </div>
      </div>

      {/* 分组列表 */}
      <div>
        {segmentGroups.map((group, groupIndex) => (
          <SegmentGroup
            key={groupIndex}
            group={group}
            groupIndex={groupIndex}
            contentMode={contentMode}
            projectName={projectName}
            episode={episode}
            aspectRatio={aspectRatio}
            onMoveSegment={handleMoveSegment}
            onDeleteSegment={(groupIndex, index) => setShowConfirmDelete({ groupIndex, index })}
            onGenerateLongVideo={handleGenerateLongVideo}
            generatedVideo={generatedVideos[groupIndex]}
          />
        ))}
      </div>

      {/* 删除确认弹窗 */}
      {showConfirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-80 rounded-xl border border-gray-700 bg-gray-900 p-4 shadow-xl">
            <h4 className="mb-3 text-sm font-medium text-gray-200">{t("confirm_delete_segment")}</h4>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowConfirmDelete(null)}
                className="rounded-lg px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-800 transition-colors"
              >
                {t("cancel")}
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-500 transition-colors"
              >
                {t("confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}