"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getAdminToken, clearAdminSession } from "../auth";
import {
    AdminUser,
    FarmerFeedbackItem,
    FeedbackListResponse,
    FeedbackAnalyticsResponse,
    FeedbackSummaryStats,
} from "../types";
import { AdminSidebar } from "../components/AdminSidebar";
import { FeedbackDetailModal } from "./components/FeedbackDetailModal";

export default function AdminFeedbackPage() {
    const router = useRouter();
    const [user, setUser] = useState<AdminUser | null>(null);

    // List state
    const [items, setItems] = useState<FarmerFeedbackItem[]>([]);
    const [stats, setStats] = useState<FeedbackSummaryStats>({
        total_ratings: 0,
        positive: 0,
        negative: 0,
        satisfaction_rate: 0.0,
    });
    const [total, setTotal] = useState<number>(0);
    const [offset, setOffset] = useState<number>(0);
    const limit = 15;

    // Analytics state
    const [analytics, setAnalytics] = useState<FeedbackAnalyticsResponse | null>(null);
    const [analyticsDays, setAnalyticsDays] = useState<number>(30);

    // Filters
    const [ratingFilter, setRatingFilter] = useState<string>("all");
    const [languageFilter, setLanguageFilter] = useState<string>("all");
    const [intentFilter, setIntentFilter] = useState<string>("all");
    const [searchTerm, setSearchTerm] = useState<string>("");
    const [searchInput, setSearchInput] = useState<string>("");

    // Modal & status
    const [selectedFeedback, setSelectedFeedback] = useState<FarmerFeedbackItem | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [isFlagging, setIsFlagging] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successBanner, setSuccessBanner] = useState<string | null>(null);

    // Refresh trigger
    const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
    const refreshAll = useCallback(() => {
        setIsLoading(true);
        setRefreshTrigger((prev) => prev + 1);
    }, []);

    // 1. Initial auth verification
    useEffect(() => {
        let isMounted = true;
        async function verifyAuth() {
            const token = getAdminToken();
            if (!token) {
                router.push("/admin/login");
                return;
            }

            try {
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
            } catch {
                // Ignore network errors on init
            }
        }

        verifyAuth();
        return () => {
            isMounted = false;
        };
    }, [router]);

    // 2. Fetch feedback list
    useEffect(() => {
        let isMounted = true;

        async function fetchFeedbackList() {
            const token = getAdminToken();
            if (!token) return;

            try {
                const params = new URLSearchParams();
                params.set("limit", limit.toString());
                params.set("offset", offset.toString());
                if (ratingFilter !== "all") params.set("rating", ratingFilter);
                if (languageFilter !== "all") params.set("language", languageFilter);
                if (intentFilter !== "all") params.set("intent", intentFilter);
                if (searchTerm.trim()) params.set("search", searchTerm.trim());

                const res = await fetch(`/api/admin/feedback?${params.toString()}`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                if (res.status === 401 || res.status === 403) {
                    clearAdminSession();
                    router.push("/admin/login");
                    return;
                }

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.detail || `Server returned ${res.status}`);
                }

                const data = (await res.json()) as FeedbackListResponse;
                if (isMounted) {
                    setItems(data.items || []);
                    setStats(data.stats || { total_ratings: 0, positive: 0, negative: 0, satisfaction_rate: 0.0 });
                    setTotal(data.total || 0);
                    setError(null);
                    setIsLoading(false);
                }
            } catch (err: unknown) {
                if (isMounted) {
                    setError(err instanceof Error ? err.message : "Failed to load feedback.");
                    setIsLoading(false);
                }
            }
        }

        fetchFeedbackList();
        return () => {
            isMounted = false;
        };
    }, [limit, offset, ratingFilter, languageFilter, intentFilter, searchTerm, refreshTrigger, router]);

    // 3. Fetch analytics data
    useEffect(() => {
        let isMounted = true;

        async function fetchAnalytics() {
            const token = getAdminToken();
            if (!token) return;

            try {
                const res = await fetch(`/api/admin/feedback/analytics?days=${analyticsDays}`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (res.ok) {
                    const data = (await res.json()) as FeedbackAnalyticsResponse;
                    if (isMounted) {
                        setAnalytics(data);
                    }
                }
            } catch {
                // Ignore background analytics fetch failures
            }
        }

        fetchAnalytics();
        return () => {
            isMounted = false;
        };
    }, [analyticsDays, refreshTrigger]);

    // Search and filter handlers
    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setOffset(0);
        setSearchTerm(searchInput);
    };

    const handleClearFilters = () => {
        setRatingFilter("all");
        setLanguageFilter("all");
        setIntentFilter("all");
        setSearchTerm("");
        setSearchInput("");
        setOffset(0);
    };

    // Flag feedback for review action
    const handleFlagForReview = async (feedbackId: string, notes: string) => {
        setIsFlagging(true);
        setError(null);
        try {
            const token = getAdminToken();
            const res = await fetch(`/api/admin/feedback/${feedbackId}/flag`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ notes }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to flag feedback for review.");
            }

            const data = await res.json();
            setSuccessBanner(`Feedback successfully queued for review (${data.review_id})`);
            setTimeout(() => setSuccessBanner(null), 5000);

            // Update item in local state
            setItems((prev) =>
                prev.map((it) =>
                    it.feedback_id === feedbackId ? { ...it, review_id: data.review_id } : it
                )
            );
            if (selectedFeedback && selectedFeedback.feedback_id === feedbackId) {
                setSelectedFeedback((prev) => (prev ? { ...prev, review_id: data.review_id } : null));
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to flag for review.");
        } finally {
            setIsFlagging(false);
        }
    };

    const satisfactionColor =
        stats.satisfaction_rate >= 75
            ? "text-emerald-700 bg-emerald-50 border-emerald-200"
            : stats.satisfaction_rate >= 50
            ? "text-amber-700 bg-amber-50 border-amber-200"
            : "text-rose-700 bg-rose-50 border-rose-200";

    return (
        <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">
            <AdminSidebar user={user} />

            <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
                {/* Header */}
                <header className="bg-white border-b border-gray-200 sticky top-0 z-30 px-6 py-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2">
                                <h1 className="text-xl font-bold text-gray-900 tracking-tight">
                                    Farmer Feedback & Satisfaction
                                </h1>
                                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    Part 4.4
                                </span>
                            </div>
                            <p className="text-xs text-gray-500 mt-0.5">
                                Real-time farmer thumbs-up/down ratings, feedback sentiment, and satisfaction analytics
                            </p>
                        </div>

                        <div className="flex items-center gap-3">
                            {/* Days Range Selector */}
                            <select
                                value={analyticsDays}
                                onChange={(e) => setAnalyticsDays(Number(e.target.value))}
                                aria-label="Select analytics time range"
                                className="text-xs bg-gray-50 border border-gray-300 rounded-lg px-2.5 py-1.5 font-medium text-gray-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                            >
                                <option value={7}>Last 7 Days</option>
                                <option value={14}>Last 14 Days</option>
                                <option value={30}>Last 30 Days</option>
                                <option value={90}>Last 90 Days</option>
                            </select>

                            <button
                                onClick={refreshAll}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 transition shadow-2xs"
                            >
                                <svg className="w-3.5 h-3.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                </svg>
                                <span>Refresh</span>
                            </button>
                        </div>
                    </div>
                </header>

                <main className="p-6 space-y-6 max-w-7xl mx-auto w-full">
                    {/* Banners */}
                    {successBanner && (
                        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between">
                            <span>✅ {successBanner}</span>
                            <button onClick={() => setSuccessBanner(null)} className="text-emerald-600 hover:text-emerald-900">✕</button>
                        </div>
                    )}
                    {error && (
                        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between">
                            <span>⚠️ {error}</span>
                            <button onClick={() => setError(null)} className="text-rose-600 hover:text-rose-900">✕</button>
                        </div>
                    )}

                    {/* KPI Metrics Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {/* Overall Satisfaction */}
                        <div className={`p-4 rounded-2xl border shadow-xs transition ${satisfactionColor}`}>
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-xs font-bold uppercase tracking-wider">Farmer Satisfaction</span>
                                <span className="text-xl">🌟</span>
                            </div>
                            <div className="text-2xl sm:text-3xl font-black">
                                {stats.satisfaction_rate.toFixed(1)}%
                            </div>
                            <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                                <div
                                    className="bg-emerald-600 h-1.5 rounded-full transition-all duration-500"
                                    style={{ width: `${Math.min(100, Math.max(0, stats.satisfaction_rate))}%` }}
                                />
                            </div>
                            <p className="text-[11px] opacity-75 mt-1.5">
                                Based on {stats.total_ratings} verified ratings
                            </p>
                        </div>

                        {/* Total Feedback */}
                        <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
                            <div className="flex items-center justify-between text-gray-500 mb-1">
                                <span className="text-xs font-bold uppercase tracking-wider">Total Ratings</span>
                                <span className="text-xl">💬</span>
                            </div>
                            <div className="text-2xl sm:text-3xl font-black text-gray-900">
                                {stats.total_ratings}
                            </div>
                            <p className="text-[11px] text-gray-500 mt-1">
                                All farmer responses logged
                            </p>
                        </div>

                        {/* Positive Ratings */}
                        <div className="p-4 rounded-2xl bg-white border border-emerald-100 shadow-xs">
                            <div className="flex items-center justify-between text-emerald-800 mb-1">
                                <span className="text-xs font-bold uppercase tracking-wider">Helpful (👍)</span>
                                <span className="text-xl">👍</span>
                            </div>
                            <div className="text-2xl sm:text-3xl font-black text-emerald-700">
                                {stats.positive}
                            </div>
                            <p className="text-[11px] text-emerald-600 mt-1">
                                {stats.total_ratings > 0
                                    ? `${((stats.positive / stats.total_ratings) * 100).toFixed(1)}% of total`
                                    : "0% of total"}
                            </p>
                        </div>

                        {/* Negative Ratings */}
                        <div className="p-4 rounded-2xl bg-white border border-rose-100 shadow-xs">
                            <div className="flex items-center justify-between text-rose-800 mb-1">
                                <span className="text-xs font-bold uppercase tracking-wider">Needs Work (👎)</span>
                                <span className="text-xl">👎</span>
                            </div>
                            <div className="text-2xl sm:text-3xl font-black text-rose-700">
                                {stats.negative}
                            </div>
                            <p className="text-[11px] text-rose-600 mt-1">
                                {stats.total_ratings > 0
                                    ? `${((stats.negative / stats.total_ratings) * 100).toFixed(1)}% of total`
                                    : "0% of total"}
                            </p>
                        </div>
                    </div>

                    {/* Analytics Visualizations: Daily Trends & Category Breakdowns */}
                    {analytics && (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Daily Trends Chart / Bars */}
                            <div className="lg:col-span-2 p-5 bg-white rounded-2xl border border-gray-200 shadow-xs">
                                <div className="flex items-center justify-between mb-4">
                                    <div>
                                        <h3 className="text-sm font-bold text-gray-900">
                                            Daily Satisfaction & Rating Volume
                                        </h3>
                                        <p className="text-xs text-gray-500">
                                            Past {analyticsDays} days trend (👍 Positive vs 👎 Negative)
                                        </p>
                                    </div>
                                    <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200">
                                        Avg: {analytics.satisfaction_rate.toFixed(1)}%
                                    </span>
                                </div>

                                {/* Trend Visualizer */}
                                <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                                    {analytics.daily_trend.filter((d) => d.total > 0).length === 0 ? (
                                        <div className="py-8 text-center text-xs text-gray-400">
                                            No daily feedback activity recorded in this time range.
                                        </div>
                                    ) : (
                                        analytics.daily_trend
                                            .filter((d) => d.total > 0)
                                            .map((day) => (
                                                <div key={day.date} className="flex items-center gap-3 text-xs">
                                                    <span className="w-20 font-mono text-gray-500 shrink-0">
                                                        {day.date.slice(5)}
                                                    </span>
                                                    <div className="flex-1 flex h-4 bg-gray-100 rounded-full overflow-hidden">
                                                        <div
                                                            className="bg-emerald-500 h-full"
                                                            style={{
                                                                width: `${day.total > 0 ? (day.positive / day.total) * 100 : 0}%`,
                                                            }}
                                                            title={`Positive: ${day.positive}`}
                                                        />
                                                        <div
                                                            className="bg-rose-400 h-full"
                                                            style={{
                                                                width: `${day.total > 0 ? (day.negative / day.total) * 100 : 0}%`,
                                                            }}
                                                            title={`Negative: ${day.negative}`}
                                                        />
                                                    </div>
                                                    <span className="w-12 text-right font-bold text-gray-700 shrink-0">
                                                        {day.satisfaction_rate.toFixed(0)}%
                                                    </span>
                                                    <span className="w-16 text-right text-[11px] text-gray-400 shrink-0">
                                                        ({day.total} votes)
                                                    </span>
                                                </div>
                                            ))
                                    )}
                                </div>
                            </div>

                            {/* Language & Intent Breakdowns */}
                            <div className="space-y-4">
                                {/* Language Breakdown */}
                                <div className="p-5 bg-white rounded-2xl border border-gray-200 shadow-xs">
                                    <h3 className="text-sm font-bold text-gray-900 mb-2">
                                        Satisfaction by Language
                                    </h3>
                                    <div className="space-y-2 text-xs">
                                        {analytics.by_language.length === 0 ? (
                                            <p className="text-gray-400 text-xs italic">No ratings by language yet.</p>
                                        ) : (
                                            analytics.by_language.map((lang) => (
                                                <div key={lang.code} className="flex items-center justify-between">
                                                    <span className="font-medium text-gray-700">{lang.language}</span>
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-bold text-emerald-700">
                                                            {lang.satisfaction_rate.toFixed(0)}%
                                                        </span>
                                                        <span className="text-[10px] text-gray-400">({lang.count})</span>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>

                                {/* Intent Breakdown */}
                                <div className="p-5 bg-white rounded-2xl border border-gray-200 shadow-xs">
                                    <h3 className="text-sm font-bold text-gray-900 mb-2">
                                        Satisfaction by Intent
                                    </h3>
                                    <div className="space-y-2 text-xs">
                                        {analytics.by_intent.length === 0 ? (
                                            <p className="text-gray-400 text-xs italic">No ratings by intent yet.</p>
                                        ) : (
                                            analytics.by_intent.map((inItem) => (
                                                <div key={inItem.intent} className="flex items-center justify-between">
                                                    <span className="font-medium text-gray-700 truncate max-w-[140px]">
                                                        {inItem.label}
                                                    </span>
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-bold text-emerald-700">
                                                            {inItem.satisfaction_rate.toFixed(0)}%
                                                        </span>
                                                        <span className="text-[10px] text-gray-400">({inItem.count})</span>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Filter Bar */}
                    <div className="p-4 bg-white rounded-2xl border border-gray-200 shadow-xs space-y-3">
                        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
                            {/* Filter Dropdowns */}
                            <div className="flex flex-wrap items-center gap-2.5">
                                {/* Rating Filter */}
                                <select
                                    value={ratingFilter}
                                    onChange={(e) => {
                                        setRatingFilter(e.target.value);
                                        setOffset(0);
                                    }}
                                    aria-label="Filter by rating"
                                    className="text-xs bg-gray-50 border border-gray-300 rounded-lg px-2.5 py-2 font-medium text-gray-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                                >
                                    <option value="all">All Ratings (👍 & 👎)</option>
                                    <option value="positive">👍 Positive (Helpful)</option>
                                    <option value="negative">👎 Negative (Needs Review)</option>
                                </select>

                                {/* Language Filter */}
                                <select
                                    value={languageFilter}
                                    onChange={(e) => {
                                        setLanguageFilter(e.target.value);
                                        setOffset(0);
                                    }}
                                    aria-label="Filter by language"
                                    className="text-xs bg-gray-50 border border-gray-300 rounded-lg px-2.5 py-2 font-medium text-gray-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                                >
                                    <option value="all">All Languages</option>
                                    <option value="en">English (EN)</option>
                                    <option value="hi">हिंदी (Hindi)</option>
                                    <option value="kn">ಕನ್ನಡ (Kannada)</option>
                                    <option value="ta">தமிழ் (Tamil)</option>
                                    <option value="te">తెలుగు (Telugu)</option>
                                </select>

                                {/* Intent Filter */}
                                <select
                                    value={intentFilter}
                                    onChange={(e) => {
                                        setIntentFilter(e.target.value);
                                        setOffset(0);
                                    }}
                                    aria-label="Filter by intent"
                                    className="text-xs bg-gray-50 border border-gray-300 rounded-lg px-2.5 py-2 font-medium text-gray-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                                >
                                    <option value="all">All Intents</option>
                                    <option value="crop_advisory">Crop Advisory</option>
                                    <option value="pest_control">Pest & Disease</option>
                                    <option value="irrigation">Irrigation</option>
                                    <option value="market_prices">Mandi Prices</option>
                                    <option value="government_schemes">Govt Schemes</option>
                                    <option value="weather">Weather</option>
                                </select>

                                {(ratingFilter !== "all" || languageFilter !== "all" || intentFilter !== "all" || searchTerm) && (
                                    <button
                                        type="button"
                                        onClick={handleClearFilters}
                                        className="text-xs text-rose-600 hover:text-rose-800 font-semibold px-2 py-1"
                                    >
                                        Clear Filters
                                    </button>
                                )}
                            </div>

                            {/* Search Form */}
                            <form onSubmit={handleSearchSubmit} className="flex gap-2 items-center">
                                <div className="relative">
                                    <input
                                        type="text"
                                        value={searchInput}
                                        onChange={(e) => setSearchInput(e.target.value)}
                                        placeholder="Search query or comment..."
                                        className="text-xs bg-gray-50 border border-gray-300 rounded-lg pl-8 pr-3 py-2 w-48 sm:w-64 text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                                    />
                                    <svg className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                    </svg>
                                </div>
                                <button
                                    type="submit"
                                    className="px-3 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs transition"
                                >
                                    Search
                                </button>
                            </form>
                        </div>
                    </div>

                    {/* Paginated Feedback Table */}
                    <div className="bg-white rounded-2xl border border-gray-200 shadow-xs overflow-hidden">
                        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                            <h2 className="text-sm font-bold text-gray-900">
                                Feedback Log ({total} records)
                            </h2>
                            <span className="text-xs text-gray-500">
                                Page {Math.floor(offset / limit) + 1} of {Math.max(1, Math.ceil(total / limit))}
                            </span>
                        </div>

                        {isLoading ? (
                            <div className="p-12 text-center text-xs text-gray-500">
                                Loading farmer feedback...
                            </div>
                        ) : items.length === 0 ? (
                            <div className="p-12 text-center space-y-2">
                                <span className="text-3xl">🌾</span>
                                <h3 className="text-sm font-bold text-gray-700">No Feedback Records Found</h3>
                                <p className="text-xs text-gray-500 max-w-sm mx-auto">
                                    No farmer ratings match the selected filters. Try broadening your criteria or submitting a new question in the assistant.
                                </p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs text-gray-700">
                                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-semibold uppercase text-[11px] tracking-wider">
                                        <tr>
                                            <th className="py-3 px-4">Rating</th>
                                            <th className="py-3 px-4">Farmer Query</th>
                                            <th className="py-3 px-4">Farmer Comment</th>
                                            <th className="py-3 px-4">Lang / Intent</th>
                                            <th className="py-3 px-4">Review Queue</th>
                                            <th className="py-3 px-4">Date</th>
                                            <th className="py-3 px-4 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {items.map((fb) => (
                                            <tr key={fb.feedback_id} className="hover:bg-gray-50/70 transition">
                                                <td className="py-3 px-4">
                                                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-bold text-xs ${
                                                        fb.rating === "negative"
                                                            ? "bg-rose-100 text-rose-800 border border-rose-200"
                                                            : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                                    }`}>
                                                        <span>{fb.rating === "negative" ? "👎" : "👍"}</span>
                                                        <span className="capitalize">{fb.rating}</span>
                                                    </span>
                                                </td>

                                                <td className="py-3 px-4 max-w-xs">
                                                    <div className="font-medium text-gray-900 truncate">
                                                        {fb.query_text || "—"}
                                                    </div>
                                                    <div className="text-[10px] text-gray-400 font-mono truncate">
                                                        {fb.session_id.slice(0, 8)}...
                                                    </div>
                                                </td>

                                                <td className="py-3 px-4 max-w-xs">
                                                    {fb.comment ? (
                                                        <div className="text-gray-800 italic truncate" title={fb.comment}>
                                                            &ldquo;{fb.comment}&rdquo;
                                                        </div>
                                                    ) : (
                                                        <span className="text-gray-400">—</span>
                                                    )}
                                                </td>

                                                <td className="py-3 px-4">
                                                    <div className="font-semibold text-gray-800 uppercase">
                                                        {fb.language}
                                                    </div>
                                                    <div className="text-[10px] text-gray-500 capitalize">
                                                        {(fb.intent || "general").replace(/_/g, " ")}
                                                    </div>
                                                </td>

                                                <td className="py-3 px-4">
                                                    {fb.review_id ? (
                                                        <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-mono text-[10px] font-bold">
                                                            Queued
                                                        </span>
                                                    ) : fb.rating === "negative" ? (
                                                        <button
                                                            onClick={() => handleFlagForReview(fb.feedback_id, "Flagged from table")}
                                                            disabled={isFlagging}
                                                            className="text-[11px] text-amber-700 hover:text-amber-900 font-bold underline"
                                                        >
                                                            Flag to Review
                                                        </button>
                                                    ) : (
                                                        <span className="text-gray-400 text-[10px]">—</span>
                                                    )}
                                                </td>

                                                <td className="py-3 px-4 text-gray-500 text-[11px] whitespace-nowrap">
                                                    {new Date(fb.created_at).toLocaleDateString()}
                                                </td>

                                                <td className="py-3 px-4 text-right">
                                                    <button
                                                        onClick={() => setSelectedFeedback(fb)}
                                                        className="px-2.5 py-1 rounded-md border border-gray-300 bg-white hover:bg-gray-100 font-semibold text-xs text-gray-700 transition"
                                                    >
                                                        Details
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Pagination footer */}
                        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
                            <button
                                disabled={offset === 0}
                                onClick={() => setOffset(Math.max(0, offset - limit))}
                                className="px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-40 transition"
                            >
                                Previous
                            </button>
                            <span className="text-xs text-gray-500">
                                Showing {items.length > 0 ? offset + 1 : 0} - {Math.min(offset + items.length, total)} of {total}
                            </span>
                            <button
                                disabled={offset + limit >= total}
                                onClick={() => setOffset(offset + limit)}
                                className="px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-40 transition"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </main>
            </div>

            {/* Detail Modal */}
            {selectedFeedback && (
                <FeedbackDetailModal
                    feedback={selectedFeedback}
                    onClose={() => setSelectedFeedback(null)}
                    onFlagForReview={handleFlagForReview}
                    isFlagging={isFlagging}
                />
            )}
        </div>
    );
}
