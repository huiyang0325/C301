import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ProjectEpisodes } from "../src/react/pages/workspace-page.js";

globalThis.window = {
    API: {
        getFileUrl: (_projectName, path) => `/files/${path}`,
    },
};

function renderEpisodes(extraProps = {}) {
    const baseProps = {
        currentProjectData: {
            episodes: [{ episode: 1, title: "第一集", script_file: "scripts/episode_1.json" }],
        },
        currentProjectName: "demo",
        currentScripts: {
            "episode_1.json": {
                content_mode: "drama",
                scenes: [
                    {
                        scene_id: "E1S01",
                        duration_seconds: 6,
                        generated_assets: {
                            storyboard_image: "storyboards/scene_E1S01.png",
                            video_clip: "videos/scene_E1S01.mp4",
                            status: "completed",
                        },
                    },
                ],
            },
        },
        draftsByEpisode: {},
        itemDrafts: {},
        uploadedStoryboardMap: {},
        selectedReview: null,
        reviewMediaError: "",
        reviewMediaVersion: 0,
        onSelectReview: () => {},
        onReviewMediaError: () => {},
        onItemDraftChange: () => {},
        onOpenDraftEditor: () => {},
        onSaveItem: () => {},
        onGenerateStoryboard: () => {},
        onGenerateVideo: () => {},
        onUploadStoryboard: () => {},
        onOpenPreview: () => {},
        busy: false,
    };

    return renderToStaticMarkup(React.createElement(ProjectEpisodes, { ...baseProps, ...extraProps }));
}

test("ProjectEpisodes should render review empty state when no selection", () => {
    const html = renderEpisodes();
    assert.ok(html.includes("点击任意场景的视频缩略图开始审片"));
});

test("ProjectEpisodes should use compact 5-column scene grid", () => {
    const html = renderEpisodes();
    assert.ok(html.includes("xl:grid-cols-5"));
});

test("ProjectEpisodes should disable review retry button when busy", () => {
    const html = renderEpisodes({
        selectedReview: { scriptFile: "episode_1.json", itemId: "E1S01" },
        reviewMediaError: "视频加载失败，可重试生成",
        busy: true,
    });

    assert.ok(html.includes("重试生成视频"));
    assert.match(html, /<button[^>]*disabled=""[^>]*>\s*重试生成视频\s*<\/button>/);
});

test("ProjectEpisodes should add cache-bust query when review media version changes", () => {
    const html = renderEpisodes({
        selectedReview: { scriptFile: "episode_1.json", itemId: "E1S01" },
        reviewMediaVersion: 2,
    });

    assert.ok(html.includes('src="/files/videos/scene_E1S01.mp4?rev=2"'));
});
