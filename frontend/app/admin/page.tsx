"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAdminToken, clearAdminSession } from "./auth";
import { AdminAnalyticsData, AdminUser } from "./types";
import { AdminSidebar } from "./components/AdminSidebar";
import { AdminHeader } from "./components/AdminHeader";
import { StatCard } from "./components/StatCard";
import { UsageChart } from "./components/UsageChart";
import { LanguageChart } from "./components/LanguageChart";
import { IntentChart } from "./components/IntentChart";
import { RecentActivity } from "./components/RecentActivity";

export default function AdminDashboardPage() {
    const router = useRouter();
    const [user, setUser] = useState<AdminUser | null>(null);
    const [days, setDays] = useState<number>(7);
    const [refreshKey, setRefreshKey] = useState<number>(0);
    const [data, setData] = useState<AdminAnalyticsData | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let isMounted = true;

        async function loadDashboard() {
            const token = getAdminToken();
            if (!token) {
                router.push("/admin/login");
                return;
            }

            try {
                // Verify admin session validity with backend
                const meRes = await fetch("/api/auth/me", {
                    headers: { Authorization: `Bearer ${token}` },
                });

                if (!meRes.ok) {
                    clearAdminSession();
                    router.push("/admin/login");
                    return;
                }

                const meData = await meRes.json();
                if (meData.role !== "admin") {
                    clearAdminSession();
                    router.push("/admin/login");
                    return;
                }

                if (isMounted) {
                    setUser(meData);
                }

                // Fetch real analytics from proxy endpoint
                const res = await fetch(`/api/admin/analytics?days=${days}`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                if (res.status === 401 || res.status === 403) {
                    clearAdminSession();
                    router.push("/admin/login");
                    return;
                }

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.detail || `Server returned status ${res.status}`);
                }

                const json = (await res.json()) as AdminAnalyticsData;
                if (isMounted) {
                    setData(json);
                    setError(null);
                    setIsLoading(false);
                }
            } catch (err: unknown) {
                if (isMounted) {
                    const msg = err instanceof Error ? err.message : "Failed to load analytics.";
                    setError(msg);
                    setIsLoading(false);
                }
            }
        }

        loadDashboard();

        return () => {
            isMounted = false;
        };
    }, [days, refreshKey, router]);

    const handleRefresh = () => {
        setIsLoading(true);
        setRefreshKey((k) => k + 1);
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col lg:flex-row">
            {/* Sidebar Navigation */}
            <AdminSidebar user={user} />

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                <AdminHeader
                    days={days}
                    onDaysChange={(d) => {
                        setIsLoading(true);
                        setDays(d);
                    }}
                    onRefresh={handleRefresh}
                    isLoading={isLoading}
                />

                <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl w-full mx-auto">
                    {/* Error Banner */}
                    {error && (
                        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                                <svg className="w-5 h-5 text-rose-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <span>{error}</span>
                            </div>
                            <button
                                onClick={handleRefresh}
                                className="px-3 py-1 rounded bg-rose-100 hover:bg-rose-200 font-semibold text-rose-900 transition-colors"
                            >
                                Retry
                            </button>
                        </div>
                    )}

                    {/* Loading Skeleton */}
                    {isLoading && !data && (
                        <div className="space-y-6 animate-pulse">
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
                                {[...Array(6)].map((_, i) => (
                                    <div key={i} className="h-28 bg-white rounded-xl border border-gray-200 p-4" />
                                ))}
                            </div>
                            <div className="h-72 bg-white rounded-xl border border-gray-200" />
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div className="h-64 bg-white rounded-xl border border-gray-200" />
                                <div className="h-64 bg-white rounded-xl border border-gray-200" />
                            </div>
                        </div>
                    )}

                    {/* Loaded Analytics */}
                    {data && (
                        <>
                            {/* Summary Metrics Row */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
                                <StatCard
                                    title="Registered Farmers"
                                    value={data.summary.total_farmers}
                                    subtext="Unique farmer profiles"
                                    icon={
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                                        </svg>
                                    }
                                    badge="Accounts"
                                    badgeColor="green"
                                />

                                <StatCard
                                    title="Total Sessions"
                                    value={data.summary.total_sessions}
                                    subtext={`${data.summary.active_sessions} currently active`}
                                    icon={
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                        </svg>
                                    }
                                    badge="SQLite"
                                    badgeColor="blue"
                                />

                                <StatCard
                                    title="Total Queries"
                                    value={data.summary.total_queries}
                                    subtext="Processed farmer questions"
                                    icon={
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    }
                                    badge="LCEL RAG"
                                    badgeColor="green"
                                />

                                <StatCard
                                    title="Today's Queries"
                                    value={data.summary.today_queries}
                                    subtext="Incoming today (UTC)"
                                    icon={
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    }
                                    badge="Today"
                                    badgeColor="green"
                                />

                                <StatCard
                                    title="Unanswered / Flagged"
                                    value={data.summary.unanswered_queries}
                                    subtext="Pending human expert review"
                                    icon={
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                        </svg>
                                    }
                                    badge={data.summary.unanswered_queries > 0 ? "Review Needed" : "All Clear"}
                                    badgeColor={data.summary.unanswered_queries > 0 ? "amber" : "green"}
                                />

                                <StatCard
                                    title="Feedback Ratio"
                                    value={
                                        data.summary.feedback.has_feedback_data
                                            ? `${data.summary.feedback.positive} 👍 / ${data.summary.feedback.negative} 👎`
                                            : "0 Ratings"
                                    }
                                    subtext={
                                        data.summary.feedback.has_feedback_data
                                            ? `${data.summary.feedback.satisfaction_rate ?? 0}% farmer satisfaction`
                                            : "No farmer feedback recorded"
                                    }
                                    icon={
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                                        </svg>
                                    }
                                    badge={data.summary.feedback.has_feedback_data ? "Verified" : "Empty State"}
                                    badgeColor={data.summary.feedback.has_feedback_data ? "green" : "gray"}
                                />
                            </div>

                            {/* Activity Trend Line/Bar Chart */}
                            <UsageChart data={data.daily_usage} days={days} />

                            {/* Dual Distribution Row */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <LanguageChart data={data.language_distribution} />
                                <IntentChart data={data.intent_distribution} />
                            </div>

                            {/* Recent Activity Table */}
                            <RecentActivity data={data.recent_activity} />
                        </>
                    )}
                </main>
            </div>
        </div>
    );
}
