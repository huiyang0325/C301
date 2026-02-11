import test from "node:test";
import assert from "node:assert/strict";

import {
    bumpReviewMediaVersionForItem,
    buildReviewVideoUrl,
    buildReviewTargetFromSelection,
    getReviewMediaVersionForSelection,
    getReviewSelectionResult,
    getSafeReviewSelection,
    isReviewItemSelected,
    normalizeReviewMediaError,
} from "../src/react/pages/workspace-page.js";

const scripts = {
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
            {
                scene_id: "E1S02",
                duration_seconds: 6,
                generated_assets: {
                    storyboard_image: "storyboards/scene_E1S02.png",
                },
            },
        ],
    },
};

test("buildReviewTargetFromSelection should return media paths for valid selection", () => {
    const selectedReview = { scriptFile: "episode_1.json", itemId: "E1S01" };
    const target = buildReviewTargetFromSelection(scripts, selectedReview, {});

    assert.equal(target.itemId, "E1S01");
    assert.equal(target.videoPath, "videos/scene_E1S01.mp4");
    assert.equal(target.storyboardPath, "storyboards/scene_E1S01.png");
});

test("buildReviewTargetFromSelection should return null for missing item", () => {
    const selectedReview = { scriptFile: "episode_1.json", itemId: "E1S99" };
    const target = buildReviewTargetFromSelection(scripts, selectedReview, {});
    assert.equal(target, null);
});

test("getSafeReviewSelection should clear invalid or non-playable selection", () => {
    assert.equal(
        getSafeReviewSelection(scripts, { scriptFile: "episode_1.json", itemId: "E1S02" }, {}),
        null
    );
});

test("getReviewSelectionResult should reject items without video", () => {
    const result = getReviewSelectionResult(scripts, { scriptFile: "episode_1.json", itemId: "E1S02" }, {});
    assert.equal(result.ok, false);
    assert.equal(result.error, "该场景暂无可播放视频");
});

test("getSafeReviewSelection should clear selection when script data is removed", () => {
    const selected = { scriptFile: "episode_1.json", itemId: "E1S01" };
    assert.equal(getSafeReviewSelection({}, selected, {}), null);
});

test("normalizeReviewMediaError should allow explicit clear", () => {
    assert.equal(normalizeReviewMediaError(""), "");
    assert.equal(normalizeReviewMediaError("  "), "");
});

test("normalizeReviewMediaError should fallback when message is missing", () => {
    assert.equal(normalizeReviewMediaError(undefined), "视频加载失败");
    assert.equal(normalizeReviewMediaError(null), "视频加载失败");
});

test("buildReviewVideoUrl should keep original url when mediaVersion is empty", () => {
    assert.equal(buildReviewVideoUrl("/files/videos/e1s01.mp4", 0), "/files/videos/e1s01.mp4");
});

test("buildReviewVideoUrl should append cache bust query with mediaVersion", () => {
    assert.equal(buildReviewVideoUrl("/files/videos/e1s01.mp4", 2), "/files/videos/e1s01.mp4?rev=2");
    assert.equal(
        buildReviewVideoUrl("/files/videos/e1s01.mp4?token=abc", 3),
        "/files/videos/e1s01.mp4?token=abc&rev=3"
    );
});

test("isReviewItemSelected should only match the active review target", () => {
    const activeReview = { scriptFile: "episode_1.json", itemId: "E1S01" };
    assert.equal(isReviewItemSelected(activeReview, "episode_1.json", "E1S01"), true);
    assert.equal(isReviewItemSelected(activeReview, "episode_1.json", "E1S02"), false);
    assert.equal(isReviewItemSelected(activeReview, "episode_2.json", "E1S01"), false);
    assert.equal(isReviewItemSelected(null, "episode_1.json", "E1S01"), false);
});

test("review media version should be scoped by selected scene and survive reselection", () => {
    const selectedA = { scriptFile: "episode_1.json", itemId: "E1S01" };
    const selectedB = { scriptFile: "episode_1.json", itemId: "E1S02" };

    const afterGenerateA = bumpReviewMediaVersionForItem({}, "episode_1.json", "E1S01");
    assert.equal(getReviewMediaVersionForSelection(afterGenerateA, selectedA), 1);
    assert.equal(getReviewMediaVersionForSelection(afterGenerateA, selectedB), 0);

    const afterGenerateATwice = bumpReviewMediaVersionForItem(afterGenerateA, "episode_1.json", "E1S01");
    assert.equal(getReviewMediaVersionForSelection(afterGenerateATwice, selectedA), 2);
});
