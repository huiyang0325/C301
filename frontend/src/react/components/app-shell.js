import React from "react";
import htm from "htm";

import { PROJECT_TABS, ROUTE_KIND, VIEW_META } from "../constants.js";
import { cn } from "../utils.js";
import { IconAssistant, IconProject, IconSpark, IconTasks, IconUsage } from "./icons.js";

const html = htm.bind(React.createElement);

export function AppShell({
    route,
    dashboardKind,
    selectedProjectItem,
    projectsCount,
    totalCalls,
    onNavigate,
    onToggleAssistantPanel,
    headerActions = null,
    children,
}) {
    const fixedViewportLayout =
        route.kind === ROUTE_KIND.ASSISTANT || route.kind === ROUTE_KIND.WORKSPACE || route.kind === ROUTE_KIND.TASKS;
    const showAssistantTrigger = route.kind !== ROUTE_KIND.ASSISTANT;
    const currentWorkspaceTabLabel =
        PROJECT_TABS.find((item) => item.key === route.tab)?.label || PROJECT_TABS[0].label;
    const workspaceTitle = selectedProjectItem?.title || route.projectName || "未选择项目";

    return html`
        <div className="app-frame flex">
            <aside className="app-sidebar hidden md:flex md:w-64 h-screen overflow-y-auto p-5 flex-col gap-6">
                <div>
                    <button
                        onClick=${() => onNavigate({ kind: ROUTE_KIND.LANDING })}
                        className="inline-flex items-center gap-3"
                    >
                        <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-neon-400 to-amberx-400"></span>
                        <div>
                            <p className="app-title text-lg font-semibold tracking-wide">ArcReel</p>
                            <p className="text-xs text-slate-400">AI 剧集生产后台</p>
                        </div>
                    </button>
                </div>

                <nav className="space-y-2">
                    <button
                        onClick=${() => onNavigate({ kind: ROUTE_KIND.PROJECTS })}
                        className=${cn(
                            "app-menu-item w-full rounded-xl px-3 py-2.5 flex items-center gap-3 text-sm border",
                            route.kind === ROUTE_KIND.PROJECTS || route.kind === ROUTE_KIND.WORKSPACE
                                ? "border-neon-400/40 bg-neon-500/10 text-neon-300"
                                : "border-white/10 bg-white/5 text-slate-300 hover:border-white/25"
                        )}
                    >
                        <${IconProject} />
                        <span>漫剧项目</span>
                    </button>
                    <button
                        onClick=${() => onNavigate({ kind: ROUTE_KIND.ASSISTANT })}
                        className=${cn(
                            "app-menu-item w-full rounded-xl px-3 py-2.5 flex items-center gap-3 text-sm border",
                            route.kind === ROUTE_KIND.ASSISTANT
                                ? "border-neon-400/40 bg-neon-500/10 text-neon-300"
                                : "border-white/10 bg-white/5 text-slate-300 hover:border-white/25"
                        )}
                    >
                        <${IconAssistant} />
                        <span>对话管理</span>
                    </button>
                    <button
                        onClick=${() => onNavigate({ kind: ROUTE_KIND.TASKS })}
                        className=${cn(
                            "app-menu-item w-full rounded-xl px-3 py-2.5 flex items-center gap-3 text-sm border",
                            route.kind === ROUTE_KIND.TASKS
                                ? "border-neon-400/40 bg-neon-500/10 text-neon-300"
                                : "border-white/10 bg-white/5 text-slate-300 hover:border-white/25"
                        )}
                    >
                        <${IconTasks} />
                        <span>任务队列</span>
                    </button>
                    <button
                        onClick=${() => onNavigate({ kind: ROUTE_KIND.USAGE })}
                        className=${cn(
                            "app-menu-item w-full rounded-xl px-3 py-2.5 flex items-center gap-3 text-sm border",
                            route.kind === ROUTE_KIND.USAGE
                                ? "border-neon-400/40 bg-neon-500/10 text-neon-300"
                                : "border-white/10 bg-white/5 text-slate-300 hover:border-white/25"
                        )}
                    >
                        <${IconUsage} />
                        <span>费用统计</span>
                    </button>
                </nav>

                <div className="mt-auto space-y-3">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <p className="text-xs text-slate-400">当前项目数</p>
                        <p className="mt-2 text-2xl font-semibold">${projectsCount}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <p className="text-xs text-slate-400">总调用次数</p>
                        <p className="mt-2 text-2xl font-semibold text-neon-300">${totalCalls}</p>
                    </div>
                </div>
            </aside>

            <main className="flex-1 h-screen min-h-0 p-3 md:p-4 overflow-hidden">
                <div className="mx-auto w-full max-w-[1560px] h-full min-h-0 flex flex-col gap-2">
                    <header className="app-panel rounded-xl px-3 py-2 md:px-4 md:py-2 flex flex-col md:flex-row md:items-center md:justify-between gap-2 shrink-0">
                        <div className="min-w-0">
                            ${route.kind === ROUTE_KIND.WORKSPACE
                                ? html`
                                      <nav className="flex items-center gap-1.5 text-[11px] text-slate-400 overflow-hidden whitespace-nowrap">
                                          <span className="shrink-0">漫剧项目</span>
                                          <span className="text-slate-600">/</span>
                                          <span className="truncate text-slate-200">${workspaceTitle}</span>
                                          <span className="text-slate-600">/</span>
                                          <span className="shrink-0 text-neon-300">${currentWorkspaceTabLabel}</span>
                                      </nav>
                                  `
                                : html`
                                      <p className="text-sm font-semibold app-title text-slate-100">${VIEW_META[dashboardKind].label}</p>
                                  `}
                        </div>

                        <div className="md:hidden grid grid-cols-4 gap-1.5">
                            <button onClick=${() => onNavigate({ kind: ROUTE_KIND.PROJECTS })} className=${cn("h-8 rounded-lg text-[11px]", route.kind === ROUTE_KIND.PROJECTS || route.kind === ROUTE_KIND.WORKSPACE ? "bg-neon-500/20 text-neon-300" : "bg-white/5 text-slate-300")}>项目</button>
                            <button onClick=${() => onNavigate({ kind: ROUTE_KIND.ASSISTANT })} className=${cn("h-8 rounded-lg text-[11px]", route.kind === ROUTE_KIND.ASSISTANT ? "bg-neon-500/20 text-neon-300" : "bg-white/5 text-slate-300")}>对话</button>
                            <button onClick=${() => onNavigate({ kind: ROUTE_KIND.TASKS })} className=${cn("h-8 rounded-lg text-[11px]", route.kind === ROUTE_KIND.TASKS ? "bg-neon-500/20 text-neon-300" : "bg-white/5 text-slate-300")}>队列</button>
                            <button onClick=${() => onNavigate({ kind: ROUTE_KIND.USAGE })} className=${cn("h-8 rounded-lg text-[11px]", route.kind === ROUTE_KIND.USAGE ? "bg-neon-500/20 text-neon-300" : "bg-white/5 text-slate-300")}>费用</button>
                        </div>

                        <div className="hidden md:flex items-center gap-2">
                            ${headerActions}
                            <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] text-slate-400">${selectedProjectItem ? `当前：${selectedProjectItem.title || selectedProjectItem.name}` : "未选择项目"}</span>
                        </div>
                    </header>

                    <section
                        className=${cn(
                            "flex-1 min-h-0",
                            fixedViewportLayout ? "overflow-hidden" : "overflow-y-auto"
                        )}
                    >
                        ${children}
                    </section>
                </div>
            </main>

            ${showAssistantTrigger
                ? html`
                      <button
                          onClick=${onToggleAssistantPanel}
                          className="fixed right-5 bottom-5 z-50 w-14 h-14 rounded-full bg-neon-500 text-ink-950 shadow-glow hover:bg-neon-400 transition-colors flex items-center justify-center"
                          title="助手工作台"
                      >
                          <${IconSpark} />
                      </button>
                  `
                : null}
        </div>
    `;
}
