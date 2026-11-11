"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getAdminToken, clearAdminSession } from "../auth";
import { ReviewRecordItem, ReviewStats, AdminUser, UnansweredQueriesResponse } from "../types";
import { AdminSidebar } from "../components/AdminSidebar";
import { QueryDetailModal } from "./components/QueryDetailModal";

export default function UnansweredQueriesPage() {
    const router = useRouter();
    const [user, setUser] = useState<AdminUser | null>(null);

    // Queries & Stats state
    const [queries, setQueries] = useState<ReviewRecordItem[]>([]);
    const [stats, setStats] = useState<ReviewStats>({
        total: 0,
        pending: 0,
        approved: 0,
        corrected: 0,
        rejected: 0,
    });
    const [total, setTotal] = useState<number>(0);
    const [offset, setOffset] = useState<number>(0);
    const limit = 15;

    // Filters state
    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [languageFilter, setLanguageFilter] = useState<string>("all");
    const [intentFilter, setIntentFilter] = useState<string>("all");
    const [searchTerm, setSearchTerm] = useState<string>("");
    const [searchInput, setSearchInput] = useState<string>("");

    // Modal & Action state
    const [selectedQuery, setSelectedQuery] = useState<ReviewRecordItem | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [isUpdating, setIsUpdating] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successBanner, setSuccessBanner] = useState<string | null>(null);

    // Refresh trigger for user-initiated reloads
    const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
    const refetchQueries = useCallback(() => {
        setIsLoading(true);
        setRefreshTrigger((prev) => prev + 1);
    }, []);

    // Initial auth verification
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
                // If offline proceed
            }
        }

        verifyAuth();
        return () => {
            isMounted = false;
        };
    }, [router]);

    // Fetch queries whenever pagination, filters, or refreshTrigger change
    useEffect(() => {
        let isMounted = true;

        async function fetchQueries() {
            const token = getAdminToken();
            if (!token) {
                return;
            }

            try {
                const params = new URLSearchParams();
                params.set("limit", limit.toString());
                params.set("offset", offset.toString());
                if (statusFilter !== "all") params.set("status", statusFilter);
                if (languageFilter !== "all") params.set("language", languageFilter);
                if (intentFilter !== "all") params.set("intent", intentFilter);
                if (searchTerm.trim()) params.set("search", searchTerm.trim());

                const res = await fetch(`/api/admin/unanswered-queries?${params.toString()}`, {
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

                const data = (await res.json()) as UnansweredQueriesResponse;
                if (isMounted) {
                    setQueries(data.queries || []);
                    setStats(data.stats || { total: 0, pending: 0, approved: 0, corrected: 0, rejected: 0 });
                    setTotal(data.total || 0);
                    setError(null);
                    setIsLoading(false);
                }
            } catch (err: unknown) {
                if (isMounted) {
                    const msg = err instanceof Error ? err.message : "Failed to load queries.";
                    setError(msg);
                    setIsLoading(false);
                }
            }
        }

        fetchQueries();
        return () => {
            isMounted = false;
        };
    }, [limit, offset, statusFilter, languageFilter, intentFilter, searchTerm, refreshTrigger, router]);

    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setOffset(0);
        setSearchTerm(searchInput);
    };

    const handleClearFilters = () => {
        setStatusFilter("all");
        setLanguageFilter("all");
        setIntentFilter("all");
        setSearchTerm("");
        setSearchInput("");
        setOffset(0);
    };

    const handleStatusUpdate = async (
        queryId: string,
        status: "approved" | "rejected" | "corrected",
        notes: string,
        correctedAnswer?: string
    ) => {
        const token = getAdminToken();
        if (!token) {
            router.push("/admin/login");
            return;
        }

        setIsUpdating(true);
        try {
            const res = await fetch(`/api/admin/unanswered-queries/${queryId}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    status,
                    reviewer_notes: notes,
                    corrected_answer: correctedAnswer,
                }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to update review.");
            }

            setSuccessBanner(`Query ${queryId} successfully marked as ${status}.`);
            setTimeout(() => setSuccessBanner(null), 4000);

            // Reload queries
            refetchQueries();
        } finally {
            setIsUpdating(false);
        }
    };

    const statusPillColors: Record<string, string> = {
        pending: "bg-amber-50 text-amber-700 border-amber-200",
        approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
        corrected: "bg-blue-50 text-blue-700 border-blue-200",
        rejected: "bg-rose-50 text-rose-700 border-rose-200",
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col lg:flex-row">
            <AdminSidebar user={user} />

            <div className="flex-1 flex flex-col min-w-0">
                {/* Header Strip */}
                <header className="bg-white border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2.5">
                            <h1 className="text-xl font-bold tracking-tight text-gray-900">
                                Unanswered & Flagged Queries
                            </h1>
                            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                                Expert Review Queue
                            </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                            Review, verify, and correct farmer questions flagged for low confidence or safety
                        </p>
                    </div>

                    <button
                        onClick={refetchQueries}
                        disabled={isLoading}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors shadow-xs self-start sm:self-auto"
                    >
                        <svg
                            className={`w-4 h-4 ${isLoading ? "animate-spin text-emerald-600" : ""}`}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        <span>{isLoading ? "Refreshing..." : "Refresh Queue"}</span>
                    </button>
                </header>

                <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl w-full mx-auto">
                    {/* Success Toast */}
                    {successBanner && (
                        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between">
                            <span>✓ {successBanner}</span>
                            <button onClick={() => setSuccessBanner(null)} className="text-emerald-600 hover:text-emerald-900 font-bold">
                                ✕
                            </button>
                        </div>
                    )}

                    {/* Error Banner */}
                    {error && (
                        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between">
                            <span>{error}</span>
                            <button
                                onClick={refetchQueries}
                                className="px-3 py-1 rounded bg-rose-100 hover:bg-rose-200 font-semibold text-rose-900 transition-colors"
                            >
                                Retry
                            </button>
                        </div>
                    )}

                    {/* Review Queue Status Counter Pills */}
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                        <button
                            onClick={() => { setStatusFilter("all"); setOffset(0); }}
                            className={`p-3 rounded-xl border text-left transition-all ${
                                statusFilter === "all" ? "bg-emerald-50 border-emerald-400 shadow-xs" : "bg-white border-gray-200 hover:border-gray-300"
                            }`}
                        >
                            <span className="text-[10px] uppercase font-bold text-gray-500 block">Total Flagged</span>
                            <span className="text-lg font-bold text-gray-900 mt-0.5 block">{stats.total}</span>
                        </button>

                        <button
                            onClick={() => { setStatusFilter("pending"); setOffset(0); }}
                            className={`p-3 rounded-xl border text-left transition-all ${
                                statusFilter === "pending" ? "bg-amber-50 border-amber-400 shadow-xs" : "bg-white border-gray-200 hover:border-gray-300"
                            }`}
                        >
                            <span className="text-[10px] uppercase font-bold text-amber-700 block">Pending Review</span>
                            <span className="text-lg font-bold text-amber-900 mt-0.5 block">{stats.pending}</span>
                        </button>

                        <button
                            onClick={() => { setStatusFilter("approved"); setOffset(0); }}
                            className={`p-3 rounded-xl border text-left transition-all ${
                                statusFilter === "approved" ? "bg-emerald-50 border-emerald-400 shadow-xs" : "bg-white border-gray-200 hover:border-gray-300"
                            }`}
                        >
                            <span className="text-[10px] uppercase font-bold text-emerald-700 block">Verified / Approved</span>
                            <span className="text-lg font-bold text-emerald-900 mt-0.5 block">{stats.approved}</span>
                        </button>

                        <button
                            onClick={() => { setStatusFilter("corrected"); setOffset(0); }}
                            className={`p-3 rounded-xl border text-left transition-all ${
                                statusFilter === "corrected" ? "bg-blue-50 border-blue-400 shadow-xs" : "bg-white border-gray-200 hover:border-gray-300"
                            }`}
                        >
                            <span className="text-[10px] uppercase font-bold text-blue-700 block">Expert Corrected</span>
                            <span className="text-lg font-bold text-blue-900 mt-0.5 block">{stats.corrected}</span>
                        </button>

                        <button
                            onClick={() => { setStatusFilter("rejected"); setOffset(0); }}
                            className={`p-3 rounded-xl border text-left transition-all ${
                                statusFilter === "rejected" ? "bg-rose-50 border-rose-400 shadow-xs" : "bg-white border-gray-200 hover:border-gray-300"
                            }`}
                        >
                            <span className="text-[10px] uppercase font-bold text-rose-700 block">Rejected</span>
                            <span className="text-lg font-bold text-rose-900 mt-0.5 block">{stats.rejected}</span>
                        </button>
                    </div>

                    {/* Filter and Search Bar */}
                    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
                            <div className="relative flex-1">
                                <input
                                    type="text"
                                    value={searchInput}
                                    onChange={(e) => setSearchInput(e.target.value)}
                                    placeholder="Search query, canonical text or review ID..."
                                    className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                />
                                <svg
                                    className="w-4 h-4 text-gray-400 absolute left-3 top-2.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                            </div>
                            <button
                                type="submit"
                                className="px-3.5 py-2 bg-emerald-700 text-white rounded-lg font-semibold hover:bg-emerald-800 transition-colors"
                            >
                                Search
                            </button>
                        </form>

                        <div className="flex flex-wrap items-center gap-2">
                            {/* Language Filter */}
                            <select
                                value={languageFilter}
                                onChange={(e) => { setLanguageFilter(e.target.value); setOffset(0); }}
                                className="px-3 py-2 border border-gray-300 rounded-lg text-xs text-gray-700 bg-white focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            >
                                <option value="all">All Languages</option>
                                <option value="en">English (en)</option>
                                <option value="hi">हिंदी (hi)</option>
                                <option value="kn">ಕನ್ನಡ (kn)</option>
                                <option value="ta">தமிழ் (ta)</option>
                            </select>

                            {/* Intent Filter */}
                            <select
                                value={intentFilter}
                                onChange={(e) => { setIntentFilter(e.target.value); setOffset(0); }}
                                className="px-3 py-2 border border-gray-300 rounded-lg text-xs text-gray-700 bg-white focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            >
                                <option value="all">All Intents</option>
                                <option value="crop_advisory">Crop Advisory</option>
                                <option value="irrigation">Irrigation</option>
                                <option value="pest_control">Pest Control</option>
                                <option value="market_prices">Market Prices</option>
                                <option value="weather">Weather</option>
                                <option value="government_schemes">Government Schemes</option>
                            </select>

                            {(statusFilter !== "all" || languageFilter !== "all" || intentFilter !== "all" || searchTerm) && (
                                <button
                                    onClick={handleClearFilters}
                                    className="px-3 py-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 font-medium transition-colors"
                                >
                                    Reset
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Query Table */}
                    <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
                        {isLoading && queries.length === 0 ? (
                            <div className="p-12 text-center text-xs text-gray-500 animate-pulse">
                                Loading review queue...
                            </div>
                        ) : queries.length === 0 ? (
                            <div className="p-16 text-center">
                                <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3 text-2xl">
                                    ✓
                                </div>
                                <h3 className="text-sm font-bold text-gray-900">All Caught Up!</h3>
                                <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto">
                                    No unanswered or flagged queries match your active filter criteria.
                                </p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs">
                                    <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] font-semibold tracking-wider border-b border-gray-100">
                                        <tr>
                                            <th className="px-6 py-3.5">Review ID</th>
                                            <th className="px-6 py-3.5">Original Question</th>
                                            <th className="px-6 py-3.5">Domain</th>
                                            <th className="px-6 py-3.5">Quality</th>
                                            <th className="px-6 py-3.5">Status</th>
                                            <th className="px-6 py-3.5">Flag Reason</th>
                                            <th className="px-6 py-3.5 text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100 text-gray-700">
                                        {queries.map((q) => {
                                            const statusClass = statusPillColors[q.status] || statusPillColors.pending;
                                            return (
                                                <tr
                                                    key={q.review_id}
                                                    onClick={() => setSelectedQuery(q)}
                                                    className="hover:bg-emerald-50/40 transition-colors cursor-pointer"
                                                >
                                                    <td className="px-6 py-4 font-mono font-medium text-gray-900 whitespace-nowrap">
                                                        {q.review_id}
                                                    </td>
                                                    <td className="px-6 py-4 max-w-md truncate font-medium text-gray-800" title={q.query}>
                                                        &ldquo;{q.query}&rdquo;
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className="capitalize font-semibold text-gray-700">
                                                            {q.intent.replace("_", " ")}
                                                        </span>
                                                        <span className="ml-1.5 text-[9px] uppercase px-1.5 py-0.5 rounded bg-gray-100 font-bold text-gray-600">
                                                            {q.language}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap font-semibold">
                                                        <span className={q.quality_score >= 0.6 ? "text-emerald-700" : "text-amber-700"}>
                                                            {Math.round(q.quality_score * 100)}%
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusClass}`}>
                                                            {q.status}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 text-gray-500 max-w-xs truncate" title={q.flag_reason}>
                                                        {q.flag_reason}
                                                    </td>
                                                    <td className="px-6 py-4 text-right whitespace-nowrap">
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setSelectedQuery(q);
                                                            }}
                                                            className="px-3 py-1 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 rounded-md font-semibold text-xs border border-emerald-200 transition-colors"
                                                        >
                                                            Inspect
                                                        </button>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Pagination Bar */}
                        {total > limit && (
                            <div className="p-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                                <span>
                                    Showing <span className="font-semibold text-gray-800">{offset + 1}</span> to{" "}
                                    <span className="font-semibold text-gray-800">{Math.min(offset + limit, total)}</span> of{" "}
                                    <span className="font-semibold text-gray-800">{total}</span> queries
                                </span>
                                <div className="flex items-center gap-2">
                                    <button
                                        disabled={offset === 0}
                                        onClick={() => setOffset((o) => Math.max(0, o - limit))}
                                        className="px-3 py-1.5 rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 font-medium transition-colors"
                                    >
                                        Previous
                                    </button>
                                    <button
                                        disabled={offset + limit >= total}
                                        onClick={() => setOffset((o) => o + limit)}
                                        className="px-3 py-1.5 rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 font-medium transition-colors"
                                    >
                                        Next
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </main>
            </div>

            {/* Query Detail & Action Modal */}
            <QueryDetailModal
                query={selectedQuery}
                onClose={() => setSelectedQuery(null)}
                onStatusUpdate={handleStatusUpdate}
                isUpdating={isUpdating}
            />
        </div>
    );
}
