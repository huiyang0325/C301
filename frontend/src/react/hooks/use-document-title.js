import { useEffect } from "react";
import { ROUTE_KIND } from "../constants.js";

export function useDocumentTitle(routeKind, currentProjectName) {
    useEffect(() => {
        if (routeKind === ROUTE_KIND.LANDING) {
            document.title = "ArcReel · 把小说批量做成漫剧视频";
            return;
        }

        if (routeKind === ROUTE_KIND.WORKSPACE && currentProjectName) {
            document.title = `${currentProjectName} · ArcReel`;
            return;
        }

        if (routeKind === ROUTE_KIND.ASSISTANT) {
            document.title = "对话管理 · ArcReel";
            return;
        }

        if (routeKind === ROUTE_KIND.USAGE) {
            document.title = "费用统计 · ArcReel";
            return;
        }

        document.title = "漫剧项目 · ArcReel";
    }, [routeKind, currentProjectName]);
}
