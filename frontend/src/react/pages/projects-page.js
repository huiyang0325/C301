import React from "react";
import htm from "htm";

import { PHASE_BADGE_CLASS, PHASE_LABELS } from "../constants.js";
import { Badge, Button, Card, EmptyState } from "../components/primitives.js";
import { cn, progressPercent } from "../utils.js";

const html = htm.bind(React.createElement);

function ProjectsGrid({
    projects,
    projectsLoading,
    onShowCreate,
    onNavigateWorkspace,
}) {
    if (projectsLoading && projects.length === 0) {
        return html`<div className="py-12 text-center text-slate-400">项目列表加载中...</div>`;
    }

    if (projects.length === 0) {
        return html`
            <${EmptyState}
                title="还没有漫剧项目"
                description="先创建一个项目，再进入概览/任务/线索/剧集场景管理。"
                action=${html`<${Button} onClick=${onShowCreate}>创建首个项目<//>`}
            />
        `;
    }

    return html`
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            ${projects.map((project) => {
                const progress = project.progress || {};
                const chars = progress.characters || { total: 0, completed: 0 };
                const storyboards = progress.storyboards || { total: 0, completed: 0 };
                const videos = progress.videos || { total: 0, completed: 0 };
                const stages = [
                    { label: "人物", data: chars, barClass: "bg-fuchsia-400/90" },
                    { label: "分镜", data: storyboards, barClass: "bg-sky-400/90" },
                    { label: "视频", data: videos, barClass: "bg-emerald-400/90" },
                ];

                return html`
                    <article key=${project.name} className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
                        <div className="aspect-video bg-ink-900/60">
                            ${project.thumbnail
                                ? html`<img src=${project.thumbnail} alt=${project.title || project.name} className="w-full h-full object-cover" />`
                                : html`<div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">暂无封面</div>`}
                        </div>
                        <div className="p-3.5 space-y-2.5">
                            <div className="flex items-start justify-between gap-2.5">
                                <div>
                                    <h3 className="font-semibold text-base truncate">${project.title || project.name}</h3>
                                    <p className="text-xs text-slate-400 mt-0.5">${project.style || project.name}</p>
                                </div>
                                <${Badge}
                                    className=${cn(
                                        PHASE_BADGE_CLASS[project.current_phase || "unknown"] || PHASE_BADGE_CLASS.unknown,
                                        "text-[11px] px-2 py-0.5"
                                    )}
                                >
                                    ${PHASE_LABELS[project.current_phase || "unknown"] || "未知"}
                                <//>
                            </div>

                            <div className="space-y-1.5">
                                ${stages.map((stage) => {
                                    const completed = Number(stage.data.completed || 0);
                                    const total = Number(stage.data.total || 0);
                                    const percent = progressPercent(completed, total);
                                    return html`
                                        <div key=${`${project.name}-${stage.label}`} className="text-xs">
                                            <div className="flex items-center justify-between text-slate-300">
                                                <span>${stage.label}</span>
                                                <span>${completed}/${total}</span>
                                            </div>
                                            <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                                                <div
                                                    className=${cn("h-full rounded-full transition-[width]", stage.barClass)}
                                                    style=${{ width: `${percent}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                    `;
                                })}
                            </div>

                            <${Button}
                                size="sm"
                                onClick=${() => onNavigateWorkspace(project.name)}
                                className="w-full"
                            >
                                进入项目工作台
                            <//>
                        </div>
                    </article>
                `;
            })}
        </div>
    `;
}

export function ProjectsPage({
    projects,
    projectsLoading,
    selectedProject,
    onSelectProject,
    onRefreshProjects,
    onShowCreate,
}) {
    return html`
        <div className="space-y-3">
            <${Card} className="app-grid-bg overflow-hidden p-3">
                <div className="relative z-10 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                        <${Button} variant="outline" onClick=${onRefreshProjects}>刷新<//>
                        <${Button} onClick=${onShowCreate}>新建漫剧项目<//>
                    </div>
                    ${projects.length > 0
                        ? html`
                              <select
                                  value=${selectedProject || projects[0].name}
                                  onChange=${(event) => onSelectProject(event.target.value)}
                                  className="h-8 rounded-lg border border-white/15 bg-ink-900/70 px-2 text-xs"
                              >
                                  ${projects.map(
                                      (project) => html`<option key=${project.name} value=${project.name}>${project.title || project.name}</option>`
                                  )}
                              </select>
                          `
                        : null}
                </div>
            <//>

            <${ProjectsGrid}
                projects=${projects}
                projectsLoading=${projectsLoading}
                onShowCreate=${onShowCreate}
                onNavigateWorkspace=${onSelectProject}
            />
        </div>
    `;
}
