import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ProjectsPage } from "../src/react/pages/projects-page.js";

function renderProjectsPage() {
    const projects = [
        {
            name: "project-alpha",
            title: "Alpha",
            style: "Photographic",
            current_phase: "storyboard",
            thumbnail: "https://example.com/alpha.jpg",
            progress: {
                characters: { completed: 1, total: 2 },
                storyboards: { completed: 3, total: 6 },
                videos: { completed: 1, total: 4 },
            },
        },
    ];

    return renderToStaticMarkup(
        React.createElement(ProjectsPage, {
            projects,
            projectsLoading: false,
            selectedProject: "project-alpha",
            onSelectProject: () => {},
            onRefreshProjects: () => {},
            onShowCreate: () => {},
        })
    );
}

test("projects page should use denser multi-column card wall", () => {
    const html = renderProjectsPage();
    assert.ok(html.includes("grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"));
});

test("projects page card should render compact progress bars for each stage", () => {
    const html = renderProjectsPage();
    assert.ok(html.includes("h-1.5 rounded-full bg-white/10 overflow-hidden"));
    assert.ok(html.includes("人物"));
    assert.ok(html.includes("分镜"));
    assert.ok(html.includes("视频"));
});
