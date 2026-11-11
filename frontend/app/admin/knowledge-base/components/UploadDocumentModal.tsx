"use client";

import React, { useState } from "react";
import { UploadPreviewData } from "../../types";

interface UploadDocumentModalProps {
    isOpen: boolean;
    onClose: () => void;
    onIngested: () => void;
}

export function UploadDocumentModal({
    isOpen,
    onClose,
    onIngested,
}: UploadDocumentModalProps) {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isParsing, setIsParsing] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Preview state after parser extracts text
    const [preview, setPreview] = useState<UploadPreviewData | null>(null);
    const [curatedTitle, setCuratedTitle] = useState("");
    const [curatedCategory, setCuratedCategory] = useState("crops");
    const [curatedSubCat, setCuratedSubCat] = useState("general");
    const [curatedSourceName, setCuratedSourceName] = useState("ICAR");
    const [curatedOrg, setCuratedOrg] = useState("Indian Council of Agricultural Research");
    const [curatedUrl, setCuratedUrl] = useState("https://icar.gov.in");
    const [curatedCrops, setCuratedCrops] = useState("");
    const [curatedText, setCuratedText] = useState("");

    if (!isOpen) return null;

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setSelectedFile(e.target.files[0]);
            setPreview(null);
            setError(null);
        }
    };

    const handlePreviewUpload = async () => {
        if (!selectedFile) {
            setError("Please select an agricultural document first.");
            return;
        }

        setIsParsing(true);
        setError(null);

        try {
            const formData = new FormData();
            formData.append("file", selectedFile);

            const token = localStorage.getItem("farmsaathi_admin_token");
            const res = await fetch("/api/admin/knowledge-base/upload", {
                method: "POST",
                headers: {
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: formData,
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to extract document content.");
            }

            const data = await res.json();
            const p: UploadPreviewData = data.preview;
            setPreview(p);
            setCuratedTitle(p.suggested_title || "");
            setCuratedCategory(p.suggested_category || "crops");
            setCuratedSourceName("ICAR");
            setCuratedOrg("Indian Council of Agricultural Research");
            setCuratedUrl("https://icar.gov.in");
            setCuratedCrops((p.suggested_crops || []).join(", "));
            setCuratedText(p.extracted_text || "");
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Error parsing document.");
        } finally {
            setIsParsing(false);
        }
    };

    const handleConfirmIngestion = async () => {
        if (!curatedTitle.trim() || !curatedText.trim()) {
            setError("Title and content are required.");
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            const token = localStorage.getItem("farmsaathi_admin_token");
            const payload = {
                category: curatedCategory,
                title: curatedTitle.trim(),
                sub_category: curatedSubCat.trim() || "general",
                source_name: curatedSourceName.trim() || "ICAR",
                organization: curatedOrg.trim() || "Agricultural Department",
                official_url: curatedUrl.trim() || "https://icar.gov.in",
                verification_status: "offline_import",
                content_en: curatedText.trim(),
                crops_applicable: curatedCrops.split(",").map((c) => c.trim().toLowerCase()).filter(Boolean),
                tags: [curatedCategory, "document_upload"],
            };

            const res = await fetch("/api/admin/knowledge-base", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to ingest record.");
            }

            onIngested();
            handleClose();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Error ingesting record.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        setSelectedFile(null);
        setPreview(null);
        setError(null);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
            <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-gray-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                {/* Header */}
                <div className="p-5 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-emerald-50/60 to-white">
                    <div>
                        <h2 className="text-base font-bold text-gray-900">
                            Upload & Ingest Agricultural Document
                        </h2>
                        <p className="text-xs text-gray-500 mt-0.5">
                            Extract text from PDF, TXT, MD, or JSON, preview, verify provenance, and index into vector store
                        </p>
                    </div>
                    <button
                        onClick={handleClose}
                        className="text-gray-400 hover:text-gray-700 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                        aria-label="Close"
                    >
                        ✕
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto space-y-4 flex-1 text-xs">
                    {error && (
                        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
                            <span>{error}</span>
                            <button onClick={() => setError(null)} className="font-bold">
                                ✕
                            </button>
                        </div>
                    )}

                    {!preview ? (
                        /* Step 1: File Selection & Preview Trigger */
                        <div className="space-y-4">
                            <div className="p-6 border-2 border-dashed border-gray-300 rounded-xl text-center space-y-3 hover:border-emerald-500 transition-colors bg-gray-50/50">
                                <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-700 mx-auto flex items-center justify-center text-xl font-bold">
                                    📄
                                </div>
                                <div>
                                    <label
                                        htmlFor="docFileInput"
                                        className="cursor-pointer text-xs font-semibold text-emerald-700 hover:text-emerald-800 underline"
                                    >
                                        Choose an agricultural document
                                    </label>
                                    <span className="text-gray-500"> or drag and drop</span>
                                    <input
                                        id="docFileInput"
                                        type="file"
                                        accept=".pdf,.txt,.md,.json"
                                        onChange={handleFileChange}
                                        className="hidden"
                                    />
                                </div>
                                <p className="text-[11px] text-gray-400">
                                    Supported formats: PDF, Text (.txt), Markdown (.md), JSON (.json) up to 5 MB
                                </p>
                            </div>

                            {selectedFile && (
                                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-emerald-800">Selected:</span>
                                        <span className="font-mono text-emerald-900">{selectedFile.name}</span>
                                        <span className="text-[11px] text-emerald-600">
                                            ({Math.round(selectedFile.size / 1024)} KB)
                                        </span>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={handlePreviewUpload}
                                        disabled={isParsing}
                                        className="px-3.5 py-1.5 rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 font-semibold shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
                                    >
                                        {isParsing && (
                                            <svg className="w-3.5 h-3.5 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                            </svg>
                                        )}
                                        <span>{isParsing ? "Extracting..." : "Extract & Preview"}</span>
                                    </button>
                                </div>
                            )}

                            <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200 text-amber-900 text-[11px] space-y-1">
                                <span className="font-bold block">🛡️ Provenance & Safety Safeguard:</span>
                                <p>
                                    Uploaded documents are never executed. Text is parsed securely in an isolated environment.
                                    You will be able to review, adjust metadata, and verify source attribution before any content is indexed.
                                </p>
                            </div>
                        </div>
                    ) : (
                        /* Step 2: Extracted Text Preview & Verification */
                        <div className="space-y-4">
                            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] flex items-center justify-between">
                                <div>
                                    <span className="font-bold">✓ Successfully Extracted:</span> {preview.filename} (
                                    {preview.word_count} words, {preview.character_count} chars)
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setPreview(null)}
                                    className="text-xs font-semibold text-emerald-700 hover:underline"
                                >
                                    Change File
                                </button>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                <div className="sm:col-span-2">
                                    <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                        Curated Title *
                                    </label>
                                    <input
                                        type="text"
                                        value={curatedTitle}
                                        onChange={(e) => setCuratedTitle(e.target.value)}
                                        className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 font-medium focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                    />
                                </div>

                                <div>
                                    <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                        Category *
                                    </label>
                                    <select
                                        value={curatedCategory}
                                        onChange={(e) => setCuratedCategory(e.target.value)}
                                        className="w-full rounded-lg border border-gray-300 p-2 text-xs bg-white text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                    >
                                        <option value="crops">Crops</option>
                                        <option value="pests">Pests</option>
                                        <option value="diseases">Diseases</option>
                                        <option value="soil">Soil & Fertilizer</option>
                                        <option value="farming_practices">Farming Practices</option>
                                        <option value="government_schemes">Government Schemes</option>
                                        <option value="market_prices">Market Prices</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                    Sub-Category
                                </label>
                                <input
                                    type="text"
                                    value={curatedSubCat}
                                    onChange={(e) => setCuratedSubCat(e.target.value)}
                                    placeholder="e.g. cereals, pulse, IPM, fertilizer"
                                    className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                />
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                <div>
                                    <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                        Source Name
                                    </label>
                                    <input
                                        type="text"
                                        value={curatedSourceName}
                                        onChange={(e) => setCuratedSourceName(e.target.value)}
                                        className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                        Organization
                                    </label>
                                    <input
                                        type="text"
                                        value={curatedOrg}
                                        onChange={(e) => setCuratedOrg(e.target.value)}
                                        className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                        Official URL
                                    </label>
                                    <input
                                        type="text"
                                        value={curatedUrl}
                                        onChange={(e) => setCuratedUrl(e.target.value)}
                                        className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                    Applicable Crops (Comma separated)
                                </label>
                                <input
                                    type="text"
                                    value={curatedCrops}
                                    onChange={(e) => setCuratedCrops(e.target.value)}
                                    placeholder="e.g. paddy, wheat, cotton"
                                    className="w-full rounded-lg border border-gray-300 p-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                />
                            </div>

                            <div>
                                <label className="block text-[11px] font-bold uppercase text-gray-700 mb-1">
                                    Extracted Text Content (Review & Edit before Ingesting)
                                </label>
                                <textarea
                                    rows={8}
                                    value={curatedText}
                                    onChange={(e) => setCuratedText(e.target.value)}
                                    className="w-full rounded-lg border border-gray-300 p-3 text-xs text-gray-900 font-sans leading-relaxed focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end gap-2">
                    <button
                        type="button"
                        onClick={handleClose}
                        disabled={isSubmitting || isParsing}
                        className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 text-xs font-semibold transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    {preview && (
                        <button
                            type="button"
                            onClick={handleConfirmIngestion}
                            disabled={isSubmitting}
                            className="px-5 py-2 rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
                        >
                            {isSubmitting && (
                                <svg className="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                            )}
                            <span>{isSubmitting ? "Ingesting & Indexing..." : "Confirm & Ingest Record"}</span>
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
