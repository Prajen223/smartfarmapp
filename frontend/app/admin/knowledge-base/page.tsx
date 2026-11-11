"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getAdminToken, clearAdminSession } from "../auth";
import {
    AdminUser,
    KnowledgeRecordItem,
    KnowledgeBaseStats,
    KnowledgeBaseResponse,
    KnowledgeSyncStatus,
} from "../types";
import { AdminSidebar } from "../components/AdminSidebar";
import { RecordDetailModal } from "./components/RecordDetailModal";
import { RecordFormModal } from "./components/RecordFormModal";
import { UploadDocumentModal } from "./components/UploadDocumentModal";
import { DeleteConfirmModal } from "./components/DeleteConfirmModal";
import { ReindexModal } from "./components/ReindexModal";

export default function KnowledgeBasePage() {
    const router = useRouter();
    const [user, setUser] = useState<AdminUser | null>(null);

    // Records & Stats state
    const [records, setRecords] = useState<KnowledgeRecordItem[]>([]);
    const [stats, setStats] = useState<KnowledgeBaseStats | null>(null);
    const [syncStatus, setSyncStatus] = useState<KnowledgeSyncStatus | null>(null);
    const [total, setTotal] = useState<number>(0);
    const [offset, setOffset] = useState<number>(0);
    const limit = 15;

    // Filters state
    const [categoryFilter, setCategoryFilter] = useState<string>("all");
    const [cropFilter, setCropFilter] = useState<string>("all");
    const [languageFilter, setLanguageFilter] = useState<string>("all");
    const [searchTerm, setSearchTerm] = useState<string>("" );
    const [searchInput, setSearchInput] = useState<string>("");

    // Modal state
    const [detailRecord, setDetailRecord] = useState<KnowledgeRecordItem | null>(null);
    const [formRecord, setFormRecord] = useState<KnowledgeRecordItem | null>(null);
    const [isFormOpen, setIsFormOpen] = useState<boolean>(false);
    const [deleteTarget, setDeleteTarget] = useState<KnowledgeRecordItem | null>(null);
    const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
    const [isReindexOpen, setIsReindexOpen] = useState<boolean>(false);

    // UI state
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [successBanner, setSuccessBanner] = useState<string | null>(null);

    // User-initiated refresh trigger
    const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
    const refetchData = useCallback(() => {
        setIsLoading(true);
        setRefreshTrigger((c) => c + 1);
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
                // Offline fallback
            }
        }

        verifyAuth();
        return () => {
            isMounted = false;
        };
    }, [router]);

    // Fetch records and status
    useEffect(() => {
        let isMounted = true;

        async function fetchKnowledgeData() {
            const token = getAdminToken();
            if (!token) return;

            try {
                const params = new URLSearchParams();
                params.set("limit", limit.toString());
                params.set("offset", offset.toString());
                if (categoryFilter !== "all") params.set("category", categoryFilter);
                if (cropFilter !== "all") params.set("crop", cropFilter);
                if (languageFilter !== "all") params.set("language", languageFilter);
                if (searchTerm.trim()) params.set("search", searchTerm.trim());

                // Parallel fetch of records & sync status
                const [recordsRes, statusRes] = await Promise.all([
                    fetch(`/api/admin/knowledge-base?${params.toString()}`, {
                        headers: { Authorization: `Bearer ${token}` },
                    }),
                    fetch("/api/admin/knowledge-base/status", {
                        headers: { Authorization: `Bearer ${token}` },
                    }),
                ]);

                if (recordsRes.status === 401 || recordsRes.status === 403) {
                    clearAdminSession();
                    router.push("/admin/login");
                    return;
                }

                if (!recordsRes.ok) {
                    const errData = await recordsRes.json().catch(() => ({}));
                    throw new Error(errData.detail || `Server returned status ${recordsRes.status}`);
                }

                const recordsData = (await recordsRes.json()) as KnowledgeBaseResponse;
                const statusData = statusRes.ok ? ((await statusRes.json()) as KnowledgeSyncStatus) : null;

                if (isMounted) {
                    setRecords(recordsData.records || []);
                    setStats(recordsData.stats || null);
                    setTotal(recordsData.total || 0);
                    if (statusData) setSyncStatus(statusData);
                    setError(null);
                    setIsLoading(false);
                }
            } catch (err: unknown) {
                if (isMounted) {
                    const msg = err instanceof Error ? err.message : "Failed to load knowledge records.";
                    setError(msg);
                    setIsLoading(false);
                }
            }
        }

        fetchKnowledgeData();
        return () => {
            isMounted = false;
        };
    }, [limit, offset, categoryFilter, cropFilter, languageFilter, searchTerm, refreshTrigger, router]);

    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setOffset(0);
        setSearchTerm(searchInput);
    };

    const handleClearFilters = () => {
        setCategoryFilter("all");
        setCropFilter("all");
        setLanguageFilter("all");
        setSearchTerm("");
        setSearchInput("");
        setOffset(0);
    };

    const showSuccess = (msg: string) => {
        setSuccessBanner(msg);
        setTimeout(() => setSuccessBanner(null), 4000);
    };

    const categoryBadges: Record<string, string> = {
        crops: "bg-emerald-50 text-emerald-800 border-emerald-200",
        pests: "bg-rose-50 text-rose-800 border-rose-200",
        diseases: "bg-purple-50 text-purple-800 border-purple-200",
        soil: "bg-amber-50 text-amber-800 border-amber-200",
        farming_practices: "bg-blue-50 text-blue-800 border-blue-200",
        government_schemes: "bg-indigo-50 text-indigo-800 border-indigo-200",
        market_prices: "bg-teal-50 text-teal-800 border-teal-200",
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col lg:flex-row">
            <AdminSidebar user={user} />

            <div className="flex-1 flex flex-col min-w-0">
                {/* Header */}
                <header className="bg-white border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2.5">
                            <h1 className="text-xl font-bold tracking-tight text-gray-900">
                                Agricultural Knowledge Base
                            </h1>
                            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                                Vector RAG Synced
                            </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                            Manage official ICAR, KCC, and Government agricultural records with real-time vector synchronization
                        </p>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                        <button
                            onClick={refetchData}
                            disabled={isLoading}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors shadow-xs"
                            title="Refresh records from database"
                        >
                            <svg
                                className={`w-4 h-4 ${isLoading ? "animate-spin text-emerald-600" : ""}`}
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
                        </button>

                        <button
                            onClick={() => setIsReindexOpen(true)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-50 transition-colors shadow-xs"
                        >
                            <span>🔄</span>
                            <span>Re-index Vector Store</span>
                        </button>

                        <button
                            onClick={() => setIsUploadOpen(true)}
                            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-emerald-300 bg-emerald-50 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 transition-colors shadow-xs"
                        >
                            <span>📄</span>
                            <span>Upload Document</span>
                        </button>

                        <button
                            onClick={() => {
                                setFormRecord(null);
                                setIsFormOpen(true);
                            }}
                            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800 shadow-xs transition-colors"
                        >
                            <span>+</span>
                            <span>Add Record</span>
                        </button>
                    </div>
                </header>

                <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl w-full mx-auto">
                    {/* Success Toast */}
                    {successBanner && (
                        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between animate-in fade-in">
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
                                onClick={refetchData}
                                className="px-3 py-1 rounded bg-rose-100 hover:bg-rose-200 font-semibold text-rose-900 transition-colors"
                            >
                                Retry
                            </button>
                        </div>
                    )}

                    {/* Health & Sync Status Strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="p-4 rounded-xl bg-white border border-gray-200 shadow-xs">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block">
                                Authoritative Records
                            </span>
                            <div className="text-2xl font-bold text-gray-900 mt-1">
                                {stats?.total_records ?? 0}
                            </div>
                            <span className="text-[11px] text-gray-500 mt-0.5 block">
                                Official ICAR / KCC docs
                            </span>
                        </div>

                        <div className="p-4 rounded-xl bg-white border border-gray-200 shadow-xs">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block">
                                Vector Chunks Indexed
                            </span>
                            <div className="text-2xl font-bold text-emerald-700 mt-1">
                                {stats?.vector_chunks ?? 0}
                            </div>
                            <span className="text-[11px] text-gray-500 mt-0.5 block font-mono">
                                {syncStatus?.backend || stats?.vector_backend || "local_vector_store"}
                            </span>
                        </div>

                        <div className="p-4 rounded-xl bg-white border border-gray-200 shadow-xs">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block">
                                Vector Synchronization
                            </span>
                            <div className="mt-2 flex items-center gap-1.5">
                                <span
                                    className={`inline-block w-2.5 h-2.5 rounded-full ${
                                        stats?.in_sync ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                                    }`}
                                />
                                <span className={`text-xs font-bold ${stats?.in_sync ? "text-emerald-700" : "text-amber-700"}`}>
                                    {stats?.in_sync ? "Active & Synchronized" : "Pending Sync"}
                                </span>
                            </div>
                            <span className="text-[11px] text-gray-400 mt-1 block">
                                RAG hybrid retriever ready
                            </span>
                        </div>

                        <div className="p-4 rounded-xl bg-white border border-gray-200 shadow-xs">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block">
                                Top Cultivated Crops
                            </span>
                            <div className="flex flex-wrap gap-1 mt-2">
                                {stats?.top_crops && stats.top_crops.length > 0 ? (
                                    stats.top_crops.slice(0, 4).map((c) => (
                                        <span key={c} className="text-[10px] font-medium px-1.5 py-0.5 bg-gray-100 rounded text-gray-700">
                                            {c}
                                        </span>
                                    ))
                                ) : (
                                    <span className="text-xs text-gray-400">Paddy, Wheat, Cotton</span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Search and Filters Bar */}
                    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs space-y-3">
                        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-2">
                            <div className="relative flex-1">
                                <input
                                    type="text"
                                    value={searchInput}
                                    onChange={(e) => setSearchInput(e.target.value)}
                                    placeholder="Search by title, crop, pest, practice, ID, or keyword..."
                                    className="w-full rounded-lg border border-gray-300 pl-9 pr-4 py-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
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
                                className="px-4 py-2 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800 transition-colors shadow-xs"
                            >
                                Search
                            </button>

                            {(searchTerm || categoryFilter !== "all" || cropFilter !== "all" || languageFilter !== "all") && (
                                <button
                                    type="button"
                                    onClick={handleClearFilters}
                                    className="px-3 py-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 text-xs font-medium transition-colors"
                                >
                                    Clear Filters
                                </button>
                            )}
                        </form>

                        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-gray-100 text-xs text-gray-600">
                            {/* Category Filter */}
                            <div className="flex items-center gap-1.5">
                                <span className="text-[11px] font-bold text-gray-400 uppercase">Category:</span>
                                <select
                                    value={categoryFilter}
                                    onChange={(e) => {
                                        setCategoryFilter(e.target.value);
                                        setOffset(0);
                                    }}
                                    className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:border-emerald-600"
                                >
                                    <option value="all">All Categories ({stats?.total_records || 0})</option>
                                    <option value="crops">Crops</option>
                                    <option value="pests">Pests</option>
                                    <option value="diseases">Diseases</option>
                                    <option value="soil">Soil & Nutrition</option>
                                    <option value="farming_practices">Farming Practices</option>
                                    <option value="government_schemes">Government Schemes</option>
                                    <option value="market_prices">Market Prices</option>
                                </select>
                            </div>

                            {/* Crop Filter */}
                            <div className="flex items-center gap-1.5">
                                <span className="text-[11px] font-bold text-gray-400 uppercase">Crop:</span>
                                <select
                                    value={cropFilter}
                                    onChange={(e) => {
                                        setCropFilter(e.target.value);
                                        setOffset(0);
                                    }}
                                    className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:border-emerald-600"
                                >
                                    <option value="all">All Crops</option>
                                    {syncStatus?.crops?.map((c) => (
                                        <option key={c} value={c}>
                                            {c.charAt(0).toUpperCase() + c.slice(1)}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Language Filter */}
                            <div className="flex items-center gap-1.5">
                                <span className="text-[11px] font-bold text-gray-400 uppercase">Language:</span>
                                <select
                                    value={languageFilter}
                                    onChange={(e) => {
                                        setLanguageFilter(e.target.value);
                                        setOffset(0);
                                    }}
                                    className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:border-emerald-600"
                                >
                                    <option value="all">Any Language</option>
                                    <option value="en">English (Canonical)</option>
                                    <option value="hi">हिन्दी (Hindi)</option>
                                    <option value="kn">ಕನ್ನಡ (Kannada)</option>
                                    <option value="ta">தமிழ் (Tamil)</option>
                                </select>
                            </div>

                            <span className="text-gray-400 ml-auto">
                                Showing {records.length} of {total} records
                            </span>
                        </div>
                    </div>

                    {/* Records Table */}
                    <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
                        {isLoading ? (
                            <div className="p-12 text-center space-y-3">
                                <div className="w-8 h-8 border-3 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto" />
                                <p className="text-xs text-gray-500">Loading knowledge records...</p>
                            </div>
                        ) : records.length === 0 ? (
                            <div className="p-12 text-center space-y-2">
                                <p className="text-sm font-semibold text-gray-700">No knowledge records found.</p>
                                <p className="text-xs text-gray-400">
                                    Try adjusting your search criteria or add a new verified record.
                                </p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse text-xs">
                                    <thead>
                                        <tr className="border-b border-gray-200 bg-gray-50/80 text-[11px] uppercase tracking-wider text-gray-500 font-bold">
                                            <th className="py-3 px-4">Document / Title</th>
                                            <th className="py-3 px-3">Category</th>
                                            <th className="py-3 px-3">Crops</th>
                                            <th className="py-3 px-3">Source & Org</th>
                                            <th className="py-3 px-3">Languages</th>
                                            <th className="py-3 px-4 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {records.map((rec) => {
                                            const catClass = categoryBadges[rec.category] || "bg-gray-100 text-gray-700 border-gray-200";
                                            return (
                                                <tr key={rec.doc_id} className="hover:bg-emerald-50/30 transition-colors">
                                                    <td className="py-3 px-4">
                                                        <div className="space-y-0.5">
                                                            <div className="font-semibold text-gray-900 hover:text-emerald-700 cursor-pointer" onClick={() => setDetailRecord(rec)}>
                                                                {rec.title}
                                                            </div>
                                                            <div className="text-[11px] font-mono text-gray-400">
                                                                {rec.doc_id}
                                                            </div>
                                                        </div>
                                                    </td>

                                                    <td className="py-3 px-3">
                                                        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${catClass}`}>
                                                            {rec.category.replace("_", " ")}
                                                        </span>
                                                    </td>

                                                    <td className="py-3 px-3">
                                                        <div className="flex flex-wrap gap-1 max-w-[150px]">
                                                            {rec.crops_applicable && rec.crops_applicable.length > 0 ? (
                                                                rec.crops_applicable.slice(0, 2).map((c) => (
                                                                    <span key={c} className="px-1.5 py-0.5 bg-amber-50 text-amber-900 border border-amber-200 rounded text-[10px]">
                                                                        {c}
                                                                    </span>
                                                                ))
                                                            ) : (
                                                                <span className="text-gray-400 text-[11px] italic">General</span>
                                                            )}
                                                            {rec.crops_applicable && rec.crops_applicable.length > 2 && (
                                                                <span className="text-[10px] text-gray-400">
                                                                    +{rec.crops_applicable.length - 2}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </td>

                                                    <td className="py-3 px-3">
                                                        <div className="text-gray-800 font-medium text-[11px] truncate max-w-[160px]">
                                                            {rec.source_name || "Official"}
                                                        </div>
                                                        <div className="text-gray-400 text-[10px] truncate max-w-[160px]">
                                                            {rec.organization || "ICAR"}
                                                        </div>
                                                    </td>

                                                    <td className="py-3 px-3">
                                                        <div className="flex items-center gap-1">
                                                            {rec.content_en && (
                                                                <span className="px-1 rounded bg-blue-50 text-blue-700 font-bold text-[10px]" title="English">
                                                                    EN
                                                                </span>
                                                            )}
                                                            {rec.content_hi && (
                                                                <span className="px-1 rounded bg-emerald-50 text-emerald-700 font-bold text-[10px]" title="Hindi">
                                                                    HI
                                                                </span>
                                                            )}
                                                            {rec.content_kn && (
                                                                <span className="px-1 rounded bg-purple-50 text-purple-700 font-bold text-[10px]" title="Kannada">
                                                                    KN
                                                                </span>
                                                            )}
                                                            {rec.content_ta && (
                                                                <span className="px-1 rounded bg-amber-50 text-amber-700 font-bold text-[10px]" title="Tamil">
                                                                    TA
                                                                </span>
                                                            )}
                                                        </div>
                                                    </td>

                                                    <td className="py-3 px-4 text-right">
                                                        <div className="flex items-center justify-end gap-1.5">
                                                            <button
                                                                onClick={() => setDetailRecord(rec)}
                                                                className="px-2.5 py-1 rounded border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 text-xs font-semibold transition-colors"
                                                            >
                                                                View
                                                            </button>
                                                            <button
                                                                onClick={() => {
                                                                    setFormRecord(rec);
                                                                    setIsFormOpen(true);
                                                                }}
                                                                className="px-2.5 py-1 rounded border border-emerald-300 text-emerald-800 hover:bg-emerald-50 text-xs font-semibold transition-colors"
                                                            >
                                                                Edit
                                                            </button>
                                                            <button
                                                                onClick={() => setDeleteTarget(rec)}
                                                                className="px-2 py-1 rounded text-rose-600 hover:bg-rose-50 text-xs font-semibold transition-colors"
                                                            >
                                                                Delete
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Pagination Bar */}
                        {!isLoading && total > limit && (
                            <div className="p-4 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600 bg-gray-50/50">
                                <span>
                                    Showing {offset + 1} to {Math.min(offset + limit, total)} of {total} records
                                </span>
                                <div className="flex items-center gap-1.5">
                                    <button
                                        disabled={offset === 0}
                                        onClick={() => setOffset(Math.max(0, offset - limit))}
                                        className="px-3 py-1.5 rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 transition-colors font-medium"
                                    >
                                        Previous
                                    </button>
                                    <button
                                        disabled={offset + limit >= total}
                                        onClick={() => setOffset(offset + limit)}
                                        className="px-3 py-1.5 rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 transition-colors font-medium"
                                    >
                                        Next
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </main>
            </div>

            {/* Modals */}
            <RecordDetailModal
                record={detailRecord}
                onClose={() => setDetailRecord(null)}
                onEdit={(rec) => {
                    setDetailRecord(null);
                    setFormRecord(rec);
                    setIsFormOpen(true);
                }}
                onDelete={(rec) => {
                    setDetailRecord(null);
                    setDeleteTarget(rec);
                }}
            />

            <RecordFormModal
                key={formRecord ? formRecord.doc_id : "new-record"}
                record={formRecord}
                isOpen={isFormOpen}
                onClose={() => {
                    setIsFormOpen(false);
                    setFormRecord(null);
                }}
                onSaved={() => {
                    showSuccess(formRecord ? `Record ${formRecord.doc_id} updated and vector re-indexed!` : "New agricultural record created and synchronized!");
                    refetchData();
                }}
            />

            <UploadDocumentModal
                isOpen={isUploadOpen}
                onClose={() => setIsUploadOpen(false)}
                onIngested={() => {
                    showSuccess("Uploaded document ingested and synchronized into vector store!");
                    refetchData();
                }}
            />

            <DeleteConfirmModal
                record={deleteTarget}
                isOpen={!!deleteTarget}
                onClose={() => setDeleteTarget(null)}
                onDeleted={() => {
                    showSuccess(`Record ${deleteTarget?.doc_id} and associated vector chunks deleted.`);
                    refetchData();
                }}
            />

            <ReindexModal
                isOpen={isReindexOpen}
                onClose={() => setIsReindexOpen(false)}
                onCompleted={() => {
                    showSuccess("Vector store full re-indexing complete!");
                    refetchData();
                }}
            />
        </div>
    );
}
