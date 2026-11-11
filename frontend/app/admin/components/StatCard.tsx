"use client";

import React from "react";

interface StatCardProps {
    title: string;
    value: number | string;
    subtext: string;
    icon: React.ReactNode;
    badge?: string;
    badgeColor?: "green" | "amber" | "blue" | "gray";
}

export function StatCard({
    title,
    value,
    subtext,
    icon,
    badge,
    badgeColor = "green",
}: StatCardProps) {
    const badgeColors = {
        green: "bg-emerald-50 text-emerald-700 border-emerald-200",
        amber: "bg-amber-50 text-amber-700 border-amber-200",
        blue: "bg-blue-50 text-blue-700 border-blue-200",
        gray: "bg-gray-50 text-gray-600 border-gray-200",
    };

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
                <span className="text-xs font-semibold tracking-wider text-gray-500 uppercase">
                    {title}
                </span>
                <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center">
                    {icon}
                </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-gray-900">
                    {typeof value === "number" ? value.toLocaleString() : value}
                </span>
                {badge && (
                    <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium border ${badgeColors[badgeColor]}`}
                    >
                        {badge}
                    </span>
                )}
            </div>

            <p className="mt-1 text-xs text-gray-500 truncate">{subtext}</p>
        </div>
    );
}
