import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ProjectTasks, ProjectClues } from "../src/react/pages/workspace-page.js";

globalThis.window = {
    API: {
        getFileUrl: (_projectName, path) => `/files/${path}`,
    },
};

test("ProjectTasks should use compact scene-like grid cards", () => {
    const markup = renderToStaticMarkup(
        React.createElement(ProjectTasks, {
            currentProjectData: {
                characters: {
                    "张三": {
                        description: "主角",
                        voice_style: "沉稳",
                        character_sheet: "characters/zhangsan.png",
                        reference_image: "characters/zhangsan_ref.png",
                    },
                },
            },
            currentProjectName: "demo",
            characterDrafts: {
                "张三": {
                    description: "主角",
                    voiceStyle: "沉稳",
                },
            },
            newCharacter: { name: "", description: "", voiceStyle: "" },
            onNewCharacterChange: () => {},
            onCreateCharacter: () => {},
            onCharacterDraftChange: () => {},
            onSaveCharacter: () => {},
            onDeleteCharacter: () => {},
            onUploadCharacterImage: () => {},
            onUploadCharacterReference: () => {},
            onGenerateCharacter: () => {},
            onOpenPreview: () => {},
            busy: false,
        })
    );

    assert.ok(markup.includes("grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2"));
    assert.ok(markup.includes("展开编辑"));
    assert.ok(markup.includes("看参考"));
});

test("ProjectClues should use compact scene-like grid cards", () => {
    const markup = renderToStaticMarkup(
        React.createElement(ProjectClues, {
            currentProjectData: {
                clues: {
                    "旧楼": {
                        description: "关键场景",
                        type: "location",
                        importance: "major",
                        clue_sheet: "clues/old-building.png",
                    },
                },
            },
            currentProjectName: "demo",
            clueDrafts: {
                "旧楼": {
                    clueType: "location",
                    importance: "major",
                    description: "关键场景",
                },
            },
            newClue: { name: "", clueType: "prop", importance: "major", description: "" },
            onNewClueChange: () => {},
            onCreateClue: () => {},
            onClueDraftChange: () => {},
            onSaveClue: () => {},
            onDeleteClue: () => {},
            onUploadClueImage: () => {},
            onGenerateClue: () => {},
            onOpenPreview: () => {},
            busy: false,
        })
    );

    assert.ok(markup.includes("grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2"));
    assert.ok(markup.includes("展开编辑"));
});
