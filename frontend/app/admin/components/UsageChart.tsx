"use client";

import React, { useState } from "react";
import { DailyUsagePoint } from "../types";

interface UsageChartProps {
    data: DailyUsagePoint[];
    days: number;
}

export function UsageChart({ data, days }: UsageChartProps) {
    const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

    const hasData = data && data.length > 0;
    const maxVal = Math.max(...(hasData ? data.map((d) => Math.max(d.queries, d.sessions)) : [0]), 1);

    const totalQueries = data.reduce((acc, d) => acc + d.queries, 0);
    const totalSessions = data.reduce((acc, d) => acc + d.sessions, 0);

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-gray-100">
                <div>
                    <h2 className="text-base font-bold text-gray-900">
                        Query & Session Activity Trend
                    </h2>
                    <p className="text-xs text-gray-500 mt-0.5">
                        Daily incoming farmer questions vs. active dialogue sessions over {days} days
                    </p>
                </div>
                <div className="flex items-center gap-4 text-xs">
                    <div className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-xs bg-emerald-600 inline-block" />
                        <span className="text-gray-600 font-medium">
                            Queries ({totalQueries})
                        </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-xs bg-teal-300 inline-block" />
                        <span className="text-gray-600 font-medium">
                            Sessions ({totalSessions})
                        </span>
                    </div>
                </div>
            </div>

            {!hasData || totalQueries + totalSessions === 0 ? (
                <div className="h-64 flex flex-col items-center justify-center text-center p-6">
                    <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center text-gray-400 mb-2">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                    </div>
                    <p className="text-sm font-medium text-gray-700">No Query Activity in Selected Window</p>
                    <p className="text-xs text-gray-400 mt-1 max-w-sm">
                        Incoming farmer questions and session starts will appear here in real-time.
                    </p>
                </div>
            ) : (
                <div className="mt-6">
                    <div className="h-56 flex items-end gap-2 sm:gap-4 relative pt-6 pb-2">
                        {data.map((point, idx) => {
                            const qHeight = Math.max((point.queries / maxVal) * 100, point.queries > 0 ? 6 : 2);
                            const sHeight = Math.max((point.sessions / maxVal) * 100, point.sessions > 0 ? 6 : 2);
                            const isHovered = hoveredIdx === idx;
                            const dateLabel = point.date.slice(5); // e.g. "11-08"

                            return (
                                <div
                                    key={point.date}
                                    className="flex-1 flex flex-col items-center h-full justify-end group relative cursor-pointer"
                                    onMouseEnter={() => setHoveredIdx(idx)}
                                    onMouseLeave={() => setHoveredIdx(null)}
                                >
                                    {/* Hover Tooltip */}
                                    {isHovered && (
                                        <div className="absolute -top-14 z-20 bg-gray-900 text-white text-xs rounded-md py-1.5 px-2.5 shadow-lg whitespace-nowrap pointer-events-none transform -translate-x-1/2 left-1/2">
                                            <div className="font-semibold">{point.date}</div>
                                            <div className="text-emerald-300">Queries: {point.queries}</div>
                                            <div className="text-teal-200">Sessions: {point.sessions}</div>
                                        </div>
                                    )}

                                    {/* Dual Bars */}
                                    <div className="w-full flex items-end justify-center gap-1 sm:gap-1.5 h-full">
                                        <div
                                            style={{ height: `${qHeight}%` }}
                                            className={`w-full max-w-[16px] rounded-t-xs transition-all ${
                                                point.queries > 0
                                                    ? "bg-emerald-600 group-hover:bg-emerald-700"
                                                    : "bg-gray-100"
                                            }`}
                                        />
                                        <div
                                            style={{ height: `${sHeight}%` }}
                                            className={`w-full max-w-[16px] rounded-t-xs transition-all ${
                                                point.sessions > 0
                                                    ? "bg-teal-300 group-hover:bg-teal-400"
                                                    : "bg-gray-100"
                                            }`}
                                        />
                                    </div>

                                    {/* X-axis date */}
                                    <span className="text-[10px] sm:text-xs text-gray-400 mt-2 truncate w-full text-center">
                                        {dateLabel}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
