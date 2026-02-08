import React from "react";
import htm from "htm";

import { TaskQueuePanel } from "../components/task-queue-panel.js";

const html = htm.bind(React.createElement);

/**
 * 任务队列页面
 * 显示全局任务队列的状态
 */
export function TasksPage({
    tasks,
    stats,
    connected,
    queuedTasks,
    runningTasks,
    completedTasks,
    onRefresh,
}) {
    return html`
        <div className="h-full flex flex-col gap-4 p-4">
            <${TaskQueuePanel}
                tasks=${tasks}
                stats=${stats}
                connected=${connected}
                queuedTasks=${queuedTasks}
                runningTasks=${runningTasks}
                completedTasks=${completedTasks}
                onRefresh=${onRefresh}
                className="flex-1"
            />
        </div>
    `;
}
