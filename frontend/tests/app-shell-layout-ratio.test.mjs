import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ROUTE_KIND } from "../src/react/constants.js";
import { AppShell } from "../src/react/components/app-shell.js";

function renderShell() {
    return renderToStaticMarkup(
        React.createElement(AppShell, {
            route: { kind: ROUTE_KIND.PROJECTS, tab: "overview", projectName: "" },
            dashboardKind: ROUTE_KIND.PROJECTS,
            selectedProjectItem: null,
            projectsCount: 2,
            totalCalls: 0,
            onNavigate: () => {},
            onToggleAssistantPanel: () => {},
            headerActions: null,
            children: React.createElement("div", null, "content"),
        })
    );
}

test("app shell should use narrower sidebar width for better proportion", () => {
    const markup = renderShell();
    assert.ok(markup.includes("md:w-64"));
});

test("app shell should constrain main content to centered max width", () => {
    const markup = renderShell();
    assert.ok(markup.includes("mx-auto w-full max-w-[1560px]"));
});
