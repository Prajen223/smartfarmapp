"use client";

import React, { useState } from "react";
import { KnowledgeRecordItem } from "../../types";

interface RecordFormModalProps {
    record: KnowledgeRecordItem | null; // null for Create mode, record for Edit mode
    isOpen: boolean;
    onClose: () => void;
    onSaved: () => void;
}

export function RecordFormModal({
    record,
    isOpen,
    onClose,
    onSaved,
}: RecordFormModalProps) {
    const isEdit = !!record;

    const [category, setCategory] = useState(record?.category || "crops");
    const [title, setTitle] = useState(record?.title || "");
    const [subCategory, setSubCategory] = useState(record?.sub_category || "cereals");
    const [sourceName, setSourceName] = useState(record?.source_name || "ICAR");
    const [organization, setOrganization] = useState(record?.organization || "Indian Council of Agricultural Research");
    const [officialUrl, setOfficialUrl] = useState(record?.official_url || "https://icar.gov.in");
    const [cropsStr, setCropsStr] = useState((record?.crops_applicable || []).join(", "));
    const [tagsStr, setTagsStr] = useState((record?.tags || []).join(", "));
    const [guardrailNotice, setGuardrailNotice] = useState(record?.guardrail_notice || "");

    // Multilingual contents
    const [contentEn, setContentEn] = useState(record?.content_en || "");
    const [contentHi, setContentHi] = useState(record?.content_hi || "");
    const [contentKn, setContentKn] = useState(record?.content_kn || "");
    const [contentTa, setContentTa] = useState(record?.content_ta || "");
    const [activeLangTab, setActiveLangTab] = useState<"en" | "hi" | "kn" | "ta">("en");

    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMessage(null);

        if (!title.trim()) {
            setErrorMessage("Document Title is required.");
            return;
        }

        if (!contentEn.trim()) {
            setErrorMessage("English content is required as the canonical base.");
            return;
        }

        const cropsList = cropsStr
            .split(",")
            .map((c) => c.trim().toLowerCase())
            .filter(Boolean);

        const tagsList = tagsStr
            .split(",")
            .map((t) => t.trim().toLowerCase())
            .filter(Boolean);

        const payload = {
            category,
            title: title.trim(),
            sub_category: subCategory.trim() || "general",
            source_name: sourceName.trim() || "ICAR",
            organization: organization.trim() || "Agricultural Department",
            official_url: officialUrl.trim() || "https://icar.gov.in",
            verification_status: "verified_curated",
            content_en: contentEn.trim(),
            content_hi: contentHi.trim(),
            content_kn: contentKn.trim(),
            content_ta: contentTa.trim(),
            crops_applicable: cropsList,
            tags: tagsList,
            guardrail_notice: guardrailNotice.trim(),
        };

        setIsSaving(true);
        try {
            const token = localStorage.getItem("farmsaathi_admin_token");
            const url = isEdit
                ? `/api/admin/knowledge-base/${record.doc_id}`
                : "/api/admin/knowledge-base";
            const method = isEdit ? "PUT" : "POST";

            const res = await fetch(url, {
                method,
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Server responded with ${res.status}`);
            }

            onSaved();
            onClose();
        } catch (err: unknown) {
            setErrorMessage(err instanceof Error ? err.message : "Failed to save record.");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
            <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-gray-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                {/* Header */}
                <div className="p-5 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-emerald-50/60 to-white">
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            {isEdit ? `Edit Knowledge Record (${record.doc_id})` : "Add New Agricultural Knowledge Record"}
                        </h2>
                        <p className="text-xs text-gray-500 mt-0.5">
                            Synchronizes automatically with persistent vector index and agricultural RAG pipeline
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-700 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                        aria-label="Close"
                    >
                        ✕
                    </button>
                </div>

                {/* Form Body */}
                <form id="recordForm" onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-4 flex-1 text-xs">
                    {errorMessage && (
                        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
                            <span>{errorMessage}</span>
                            <button type="button" onClick={() => setErrorMessage(null)} className="font-bold">
                                ✕
                            </button>
                        </div>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Category *
                            </label>
                            <select
                                value={category}
                                onChange={(e) => setCategory(e.target.value)}
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs bg-white text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            >
                                <option value="crops">Crops (Package of Practices)</option>
                                <option value="pests">Pests (Identification & IPM)</option>
                                <option value="diseases">Diseases (Fungal, Viral, Bacterial)</option>
                                <option value="soil">Soil & Nutrition (NPK, Micronutrients)</option>
                                <option value="farming_practices">Farming Practices (Irrigation, Sowing)</option>
                                <option value="government_schemes">Government Schemes (PM-Kisan, PMFBY)</option>
                                <option value="market_prices">Market Prices & Mandis</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Sub-Category
                            </label>
                            <input
                                type="text"
                                value={subCategory}
                                onChange={(e) => setSubCategory(e.target.value)}
                                placeholder="e.g. cereals, pulse, IPM, fertilizer"
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                            Document Title *
                        </label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="e.g. Mustard Aphid Management & Neem Oil Spray Schedule"
                            className="w-full rounded-lg border border-gray-300 p-2.5 text-xs text-gray-900 font-medium focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Source Name
                            </label>
                            <input
                                type="text"
                                value={sourceName}
                                onChange={(e) => setSourceName(e.target.value)}
                                placeholder="e.g. ICAR-DRMR / KCC"
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Organization
                            </label>
                            <input
                                type="text"
                                value={organization}
                                onChange={(e) => setOrganization(e.target.value)}
                                placeholder="e.g. ICAR / Ministry of Agriculture"
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Official URL
                            </label>
                            <input
                                type="text"
                                value={officialUrl}
                                onChange={(e) => setOfficialUrl(e.target.value)}
                                placeholder="https://icar.gov.in"
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Applicable Crops (Comma separated)
                            </label>
                            <input
                                type="text"
                                value={cropsStr}
                                onChange={(e) => setCropsStr(e.target.value)}
                                placeholder="e.g. wheat, mustard, chickpea"
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                Search Tags (Comma separated)
                            </label>
                            <input
                                type="text"
                                value={tagsStr}
                                onChange={(e) => setTagsStr(e.target.value)}
                                placeholder="e.g. aphid, spray, dosage, rabi"
                                className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                            />
                        </div>
                    </div>

                    {/* Multilingual Content Tabs */}
                    <div className="space-y-2 pt-2 border-t border-gray-100">
                        <div className="flex items-center justify-between">
                            <span className="text-[11px] font-bold uppercase text-gray-700">
                                Verified Agricultural Content *
                            </span>
                            <div className="flex space-x-1">
                                {(
                                    [
                                        { code: "en", label: "English *" },
                                        { code: "hi", label: "हिन्दी" },
                                        { code: "kn", label: "ಕನ್ನಡ" },
                                        { code: "ta", label: "தமிழ்" },
                                    ] as const
                                ).map((t) => (
                                    <button
                                        type="button"
                                        key={t.code}
                                        onClick={() => setActiveLangTab(t.code)}
                                        className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
                                            activeLangTab === t.code
                                                ? "bg-emerald-600 text-white"
                                                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                        }`}
                                    >
                                        {t.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {activeLangTab === "en" && (
                            <textarea
                                rows={6}
                                value={contentEn}
                                onChange={(e) => setContentEn(e.target.value)}
                                placeholder="Enter canonical English package of practices, IPM dosage, sowing recommendations..."
                                className="w-full rounded-lg border border-gray-300 p-3 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 placeholder:text-gray-400 font-sans leading-relaxed"
                            />
                        )}

                        {activeLangTab === "hi" && (
                            <textarea
                                rows={6}
                                value={contentHi}
                                onChange={(e) => setContentHi(e.target.value)}
                                placeholder="हिन्दी में वैज्ञानिक सलाह, कीटनाशक की मात्रा, या बुवाई की सिफारिशें दर्ज करें..."
                                className="w-full rounded-lg border border-gray-300 p-3 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 placeholder:text-gray-400 font-sans leading-relaxed"
                            />
                        )}

                        {activeLangTab === "kn" && (
                            <textarea
                                rows={6}
                                value={contentKn}
                                onChange={(e) => setContentKn(e.target.value)}
                                placeholder="ಕನ್ನಡದಲ್ಲಿ ಕೃಷಿ ಮಾಹಿತಿ ಮತ್ತು ಶಿಫಾರಸುಗಳನ್ನು ನಮೂದಿಸಿ..."
                                className="w-full rounded-lg border border-gray-300 p-3 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 placeholder:text-gray-400 font-sans leading-relaxed"
                            />
                        )}

                        {activeLangTab === "ta" && (
                            <textarea
                                rows={6}
                                value={contentTa}
                                onChange={(e) => setContentTa(e.target.value)}
                                placeholder="தமிழில் வேளாண்மை வழிகாட்டுதலை உள்ளிடவும்..."
                                className="w-full rounded-lg border border-gray-300 p-3 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 placeholder:text-gray-400 font-sans leading-relaxed"
                            />
                        )}
                    </div>

                    <div>
                        <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                            Guardrail Notice (Optional Safety Warning)
                        </label>
                        <input
                            type="text"
                            value={guardrailNotice}
                            onChange={(e) => setGuardrailNotice(e.target.value)}
                            placeholder="e.g. Chemical pesticide spray is hazardous; wear protective gloves and do not spray near water sources."
                            className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                        />
                    </div>
                </form>

                {/* Footer */}
                <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end gap-2">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isSaving}
                        className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 text-xs font-semibold transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        form="recordForm"
                        disabled={isSaving}
                        className="px-5 py-2 rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
                    >
                        {isSaving && (
                            <svg className="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                            </svg>
                        )}
                        <span>{isSaving ? "Synchronizing..." : isEdit ? "Update & Re-index" : "Create & Synchronize"}</span>
                    </button>
                </div>
            </div>
        </div>
    );
}
