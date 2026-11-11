"use client";

import React from "react";
import { LanguageMetric } from "../types";

interface LanguageChartProps {
    data: LanguageMetric[];
}

export function LanguageChart({ data }: LanguageChartProps) {
    const hasData = data && data.length > 0;
    const totalCount = data.reduce((acc, curr) => acc + curr.count, 0);

    const colorPalette: Record<string, { bg: string; text: string; bar: string }> = {
        en: { bg: "bg-blue-50", text: "text-blue-700", bar: "bg-blue-600" },
        hi: { bg: "bg-emerald-50", text: "text-emerald-700", bar: "bg-emerald-600" },
        kn: { bg: "bg-amber-50", text: "text-amber-700", bar: "bg-amber-600" },
        ta: { bg: "bg-purple-50", text: "text-purple-700", bar: "bg-purple-600" },
    };

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs flex flex-col justify-between">
            <div>
                <div className="flex items-center justify-between pb-4 border-b border-gray-100">
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            Language Distribution
                        </h2>
                        <p className="text-xs text-gray-500 mt-0.5">
                            Farmer queries by spoken & detected dialect
                        </p>
                    </div>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {totalCount} Queries
                    </span>
                </div>

                {!hasData || totalCount === 0 ? (
                    <div className="py-12 text-center">
                        <p className="text-xs text-gray-400">No language data recorded yet.</p>
                    </div>
                ) : (
                    <div className="mt-5 space-y-4">
                        {data.map((item) => {
                            const colors = colorPalette[item.code] || {
                                bg: "bg-gray-50",
                                text: "text-gray-700",
                                bar: "bg-gray-600",
                            };

                            return (
                                <div key={item.code} className="space-y-1.5">
                                    <div className="flex items-center justify-between text-xs">
                                        <div className="flex items-center gap-2">
                                            <span
                                                className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${colors.bg} ${colors.text}`}
                                            >
                                                {item.code}
                                            </span>
                                            <span className="font-semibold text-gray-800">
                                                {item.language}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-gray-500">{item.count} queries</span>
                                            <span className="font-bold text-gray-900 w-12 text-right">
                                                {item.percentage}%
                                            </span>
                                        </div>
                                    </div>
                                    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                                        <div
                                            className={`h-2 rounded-full transition-all duration-500 ${colors.bar}`}
                                            style={{ width: `${Math.max(item.percentage, 2)}%` }}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            <div className="mt-6 pt-4 border-t border-gray-100 text-[11px] text-gray-400 flex items-center justify-between">
                <span>Native multilingual NLP pipeline</span>
                <span>ICAR Agricultural Taxonomy</span>
            </div>
        </div>
    );
}
