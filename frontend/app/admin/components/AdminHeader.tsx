"use client";

import React from "react";

interface AdminHeaderProps {
    days: number;
    onDaysChange: (days: number) => void;
    onRefresh: () => void;
    isLoading: boolean;
}

export function AdminHeader({
    days,
    onDaysChange,
    onRefresh,
    isLoading,
}: AdminHeaderProps) {
    return (
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
                <div className="flex items-center gap-2.5">
                    <h1 className="text-xl font-bold tracking-tight text-gray-900">
                        Admin Overview & Analytics
                    </h1>
                    <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                        Production Live
                    </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                    Real-time dialogue metrics, farmer usage volume, and domain distributions
                </p>
            </div>

            <div className="flex items-center gap-3 self-start sm:self-auto">
                {/* Time Range Selector */}
                <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1 text-xs">
                    {[7, 14, 30].map((d) => (
                        <button
                            key={d}
                            onClick={() => onDaysChange(d)}
                            className={`px-3 py-1 rounded-md font-medium transition-colors ${
                                days === d
                                    ? "bg-white text-emerald-800 shadow-xs font-semibold"
                                    : "text-gray-600 hover:text-gray-900"
                            }`}
                        >
                            {d} Days
                        </button>
                    ))}
                </div>

                {/* Refresh Button */}
                <button
                    onClick={onRefresh}
                    disabled={isLoading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 hover:text-emerald-700 disabled:opacity-50 transition-colors shadow-xs"
                    title="Refresh analytics data"
                >
                    <svg
                        className={`w-4 h-4 ${isLoading ? "animate-spin text-emerald-600" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                        />
                    </svg>
                    <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
                </button>
            </div>
        </header>
    );
}
