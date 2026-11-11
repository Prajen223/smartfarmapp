"use client";

import React, { useState } from "react";
import { KnowledgeRecordItem } from "../../types";

interface RecordDetailModalProps {
    record: KnowledgeRecordItem | null;
    onClose: () => void;
    onEdit: (record: KnowledgeRecordItem) => void;
    onDelete: (record: KnowledgeRecordItem) => void;
}

export function RecordDetailModal({
    record,
    onClose,
    onEdit,
    onDelete,
}: RecordDetailModalProps) {
    const [activeLangTab, setActiveLangTab] = useState<"en" | "hi" | "kn" | "ta">("en");

    if (!record) return null;

    const languagesAvailable = [
        { code: "en", label: "English", available: !!record.content_en },
        { code: "hi", label: "हिन्दी (Hindi)", available: !!record.content_hi },
        { code: "kn", label: "ಕನ್ನಡ (Kannada)", available: !!record.content_kn },
        { code: "ta", label: "தமிழ் (Tamil)", available: !!record.content_ta },
    ] as const;

    const currentContent = {
        en: record.content_en || "No English content provided.",
        hi: record.content_hi || "कोई हिन्दी सामग्री उपलब्ध नहीं है।",
        kn: record.content_kn || "ಯಾವುದೇ ಕನ್ನಡ ವಿಷಯ ಲಭ್ಯವಿಲ್ಲ.",
        ta: record.content_ta || "தமிழ் உள்ளடக்கம் இல்லை.",
    }[activeLangTab];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
            <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-gray-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                {/* Header */}
                <div className="p-5 border-b border-gray-100 flex items-start justify-between bg-gradient-to-r from-emerald-50/50 to-white">
                    <div className="space-y-1 pr-6">
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                                {record.category.replace("_", " ")}
                            </span>
                            <span className="text-xs font-mono text-gray-400">
                                {record.doc_id}
                            </span>
                        </div>
                        <h2 className="text-base font-bold text-gray-900 line-clamp-2">
                            {record.title}
                        </h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-700 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                        aria-label="Close"
                    >
                        ✕
                    </button>
                </div>

                {/* Body Content */}
                <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
                    {/* Provenance & Source Strip */}
                    <div className="p-3.5 rounded-xl bg-gray-50 border border-gray-200/80 grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-400 block">Organization</span>
                            <span className="text-xs font-semibold text-gray-800">{record.organization || "ICAR"}</span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-400 block">Source Name</span>
                            <span className="text-xs font-semibold text-gray-800">{record.source_name || "Official Source"}</span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-400 block">Official URL</span>
                            {record.official_url ? (
                                <a
                                    href={record.official_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-xs text-emerald-600 hover:underline truncate block"
                                >
                                    {record.official_url}
                                </a>
                            ) : (
                                <span className="text-gray-400">None</span>
                            )}
                        </div>
                    </div>

                    {/* Applicable Metadata Badges */}
                    <div className="space-y-2">
                        <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">
                            Applicable Crops & Entities
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                            {record.crops_applicable && record.crops_applicable.length > 0 ? (
                                record.crops_applicable.map((c) => (
                                    <span key={c} className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 text-[11px] font-medium">
                                        🌱 {c}
                                    </span>
                                ))
                            ) : (
                                <span className="text-gray-400 italic text-[11px]">General agricultural guidance (All crops)</span>
                            )}

                            {record.soil_types_applicable?.map((s) => (
                                <span key={s} className="px-2 py-0.5 rounded-md bg-stone-100 text-stone-700 border border-stone-200 text-[11px]">
                                    🧱 {s}
                                </span>
                            ))}

                            {record.tags?.map((t) => (
                                <span key={t} className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 text-[11px]">
                                    #{t}
                                </span>
                            ))}
                        </div>
                    </div>

                    {/* Multilingual Content Tabs */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between border-b border-gray-200">
                            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">
                                Verified Content
                            </span>
                            <div className="flex space-x-1">
                                {languagesAvailable.map((tab) => (
                                    <button
                                        key={tab.code}
                                        onClick={() => setActiveLangTab(tab.code)}
                                        className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
                                            activeLangTab === tab.code
                                                ? "border-emerald-600 text-emerald-800 font-bold"
                                                : "border-transparent text-gray-500 hover:text-gray-800"
                                        } ${!tab.available ? "opacity-40" : ""}`}
                                    >
                                        {tab.label} {!tab.available && "(None)"}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="p-4 rounded-xl bg-gray-50/70 border border-gray-200 min-h-[140px] whitespace-pre-wrap font-sans text-xs leading-relaxed text-gray-800">
                            {currentContent}
                        </div>
                    </div>

                    {/* Guardrail Notice */}
                    {record.guardrail_notice && (
                        <div className="p-3 rounded-lg bg-amber-50/80 border border-amber-200 text-amber-900 text-[11px] flex gap-2">
                            <span className="font-bold">⚠️ Guardrail:</span>
                            <span>{record.guardrail_notice}</span>
                        </div>
                    )}
                </div>

                {/* Footer Controls */}
                <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
                    <button
                        onClick={() => onDelete(record)}
                        className="px-3.5 py-1.5 rounded-lg border border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-semibold transition-colors"
                    >
                        Delete Record
                    </button>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={onClose}
                            className="px-3.5 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 text-xs font-semibold transition-colors"
                        >
                            Close
                        </button>
                        <button
                            onClick={() => onEdit(record)}
                            className="px-4 py-1.5 rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 text-xs font-semibold shadow-xs transition-colors"
                        >
                            Edit Record
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
