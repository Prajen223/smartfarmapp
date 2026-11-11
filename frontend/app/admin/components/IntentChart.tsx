"use client";

import React from "react";
import { IntentMetric } from "../types";

interface IntentChartProps {
    data: IntentMetric[];
}

export function IntentChart({ data }: IntentChartProps) {
    const hasData = data && data.length > 0;
    const totalCount = data.reduce((acc, curr) => acc + curr.count, 0);

    const intentIcons: Record<string, string> = {
        irrigation: "💧",
        crop_advisory: "🌱",
        pest_control: "🐛",
        market_prices: "🌾",
        government_schemes: "🏛️",
        weather: "☀️",
        general: "🚜",
    };

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs flex flex-col justify-between">
            <div>
                <div className="flex items-center justify-between pb-4 border-b border-gray-100">
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            Query Intent Distribution
                        </h2>
                        <p className="text-xs text-gray-500 mt-0.5">
                            Categorization across core agricultural domains
                        </p>
                    </div>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {data.length} Domains
                    </span>
                </div>

                {!hasData || totalCount === 0 ? (
                    <div className="py-12 text-center">
                        <p className="text-xs text-gray-400">No intent classifications recorded yet.</p>
                    </div>
                ) : (
                    <div className="mt-5 space-y-3.5">
                        {data.map((item) => {
                            const icon = intentIcons[item.intent] || "🌾";
                            return (
                                <div key={item.intent} className="space-y-1.5">
                                    <div className="flex items-center justify-between text-xs">
                                        <div className="flex items-center gap-2">
                                            <span className="text-base">{icon}</span>
                                            <span className="font-semibold text-gray-800">
                                                {item.label}
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
                                            className="h-2 rounded-full bg-emerald-500 transition-all duration-500"
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
                <span>Hugging Face Zero-Shot Classifier</span>
                <span>LCEL RAG Pipeline</span>
            </div>
        </div>
    );
}
