"use client";

import React from "react";
import { RecentActivityItem } from "../types";

interface RecentActivityProps {
    data: RecentActivityItem[];
}

export function RecentActivity({ data }: RecentActivityProps) {
    const hasData = data && data.length > 0;

    const intentBadges: Record<string, string> = {
        irrigation: "bg-blue-50 text-blue-700 border-blue-200",
        crop_advisory: "bg-emerald-50 text-emerald-700 border-emerald-200",
        pest_control: "bg-rose-50 text-rose-700 border-rose-200",
        market_prices: "bg-amber-50 text-amber-700 border-amber-200",
        government_schemes: "bg-purple-50 text-purple-700 border-purple-200",
        weather: "bg-sky-50 text-sky-700 border-sky-200",
        general: "bg-gray-50 text-gray-700 border-gray-200",
    };

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
            <div className="p-6 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                    <h2 className="text-base font-bold text-gray-900">Recent Farmer Activity</h2>
                    <p className="text-xs text-gray-500 mt-0.5">
                        Live stream of sanitized queries entering the agricultural assistant
                    </p>
                </div>
                <span className="text-xs text-gray-500 bg-gray-50 px-2.5 py-1 rounded-md border border-gray-200 self-start sm:self-auto font-medium">
                    PII Masked • Real Database Records
                </span>
            </div>

            {!hasData ? (
                <div className="p-12 text-center">
                    <p className="text-xs text-gray-400">No recent activity recorded.</p>
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                        <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] font-semibold tracking-wider border-b border-gray-100">
                            <tr>
                                <th scope="col" className="px-6 py-3">Farmer</th>
                                <th scope="col" className="px-6 py-3">Session</th>
                                <th scope="col" className="px-6 py-3">Query Preview</th>
                                <th scope="col" className="px-6 py-3">Language</th>
                                <th scope="col" className="px-6 py-3">Intent</th>
                                <th scope="col" className="px-6 py-3 text-right">Timestamp</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 text-gray-700">
                            {data.map((item) => {
                                const badge = intentBadges[item.intent] || intentBadges.general;
                                const dateObj = new Date(item.created_at);
                                const timeStr = isNaN(dateObj.getTime())
                                    ? item.created_at
                                    : dateObj.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
                                      " " +
                                      dateObj.toLocaleDateString([], { month: "short", day: "numeric" });

                                return (
                                    <tr key={item.message_id} className="hover:bg-gray-50/80 transition-colors">
                                        <td className="px-6 py-3.5 font-medium text-gray-900 whitespace-nowrap">
                                            {item.farmer_id_masked}
                                        </td>
                                        <td className="px-6 py-3.5 font-mono text-gray-500 whitespace-nowrap">
                                            {item.session_id_masked}
                                        </td>
                                        <td className="px-6 py-3.5 max-w-md truncate font-normal text-gray-800" title={item.query_preview}>
                                            &ldquo;{item.query_preview}&rdquo;
                                        </td>
                                        <td className="px-6 py-3.5 whitespace-nowrap">
                                            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gray-100 text-gray-700">
                                                {item.language}
                                            </span>
                                        </td>
                                        <td className="px-6 py-3.5 whitespace-nowrap">
                                            <span
                                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${badge}`}
                                            >
                                                {item.intent.replace("_", " ")}
                                            </span>
                                        </td>
                                        <td className="px-6 py-3.5 text-right text-gray-400 whitespace-nowrap font-mono text-[11px]">
                                            {timeStr}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
