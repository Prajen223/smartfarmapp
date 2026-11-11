"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { AdminUser } from "../types";
import { clearAdminSession } from "../auth";

interface AdminSidebarProps {
    user: AdminUser | null;
}

export function AdminSidebar({ user }: AdminSidebarProps) {
    const router = useRouter();
    const pathname = usePathname();
    const [mobileOpen, setMobileOpen] = useState(false);

    const handleSignOut = () => {
        clearAdminSession();
        router.push("/admin/login");
    };

    const navItems = [
        {
            name: "Analytics & Overview",
            href: "/admin",
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
            ),
        },
        {
            name: "Unanswered Queries",
            href: "/admin/unanswered-queries",
            badge: "Review Queue",
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
            ),
        },
        {
            name: "Farmer Sessions",
            href: "#",
            badge: "Part 4.3",
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
            ),
        },
        {
            name: "Knowledge Base",
            href: "/admin/knowledge-base",
            badge: "Vector Sync",
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
            ),
        },
        {
            name: "Feedback & Satisfaction",
            href: "/admin/feedback",
            badge: "Part 4.4",
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                </svg>
            ),
        },
        {
            name: "Security & Rate Limits",
            href: "#",
            badge: "Part 4.3",
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
            ),
        },
    ];

    return (
        <>
            {/* Mobile Header Bar */}
            <div className="lg:hidden bg-emerald-900 text-white px-4 py-3 flex items-center justify-between shadow-md">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-emerald-700 flex items-center justify-center font-bold text-white text-base">
                        🌾
                    </div>
                    <div>
                        <span className="font-bold text-sm tracking-tight">FarmSaathi</span>
                        <span className="text-[10px] ml-1.5 px-1.5 py-0.5 rounded bg-emerald-800 text-emerald-200 font-semibold uppercase">
                            Admin
                        </span>
                    </div>
                </div>
                <button
                    onClick={() => setMobileOpen(!mobileOpen)}
                    className="p-1.5 rounded-md hover:bg-emerald-800 text-emerald-100"
                    aria-label="Toggle navigation menu"
                >
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
                    </svg>
                </button>
            </div>

            {/* Sidebar Desktop & Mobile Drawer */}
            <aside
                className={`fixed inset-y-0 left-0 z-40 w-64 bg-emerald-950 text-white flex flex-col justify-between transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
                    mobileOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
                }`}
            >
                {/* Brand & Top */}
                <div>
                    <div className="p-6 border-b border-emerald-900/60 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-xl shadow-md">
                            🌾
                        </div>
                        <div>
                            <div className="font-bold text-base tracking-tight text-white flex items-center gap-2">
                                FarmSaathi
                            </div>
                            <div className="text-[11px] text-emerald-300 font-medium">
                                Operations & AI Console
                            </div>
                        </div>
                    </div>

                    {/* Nav Items */}
                    <div className="px-3 py-6 space-y-1">
                        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-emerald-400/80">
                            Management
                        </div>
                        {navItems.map((item) => {
                            const isCurrent =
                                item.href === "/admin"
                                    ? pathname === "/admin"
                                    : Boolean(pathname && (pathname === item.href || pathname.startsWith(item.href + "/")));
                            return (
                                <Link
                                    key={item.name}
                                    href={item.href}
                                    onClick={() => setMobileOpen(false)}
                                    className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                                        isCurrent
                                            ? "bg-emerald-700/80 text-white shadow-xs"
                                            : "text-emerald-200/70 hover:bg-emerald-900/50 hover:text-white"
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className={isCurrent ? "text-white" : "text-emerald-400"}>
                                            {item.icon}
                                        </span>
                                        <span>{item.name}</span>
                                    </div>
                                    {item.badge && (
                                        <span
                                            className={`text-[9px] px-1.5 py-0.5 rounded font-semibold border ${
                                                isCurrent
                                                    ? "bg-emerald-800 text-white border-emerald-600"
                                                    : "bg-emerald-900 text-emerald-300 border-emerald-800"
                                            }`}
                                        >
                                            {item.badge}
                                        </span>
                                    )}
                                </Link>
                            );
                        })}
                    </div>

                    {/* Quick Link to Farmer App */}
                    <div className="px-3 pt-2">
                        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-emerald-400/80">
                            Farmer Assistant
                        </div>
                        <Link
                            href="/"
                            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium text-emerald-200/70 hover:bg-emerald-900/50 hover:text-white transition-colors"
                        >
                            <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                            </svg>
                            <span>Back to Farmer Interface</span>
                        </Link>
                    </div>
                </div>

                {/* Bottom User Profile & Sign Out */}
                <div className="p-4 border-t border-emerald-900/60 bg-emerald-950/80">
                    <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-8 h-8 rounded-full bg-emerald-700 border border-emerald-500 flex items-center justify-center font-bold text-white text-xs shrink-0">
                                {user ? user.username.charAt(0).toUpperCase() : "A"}
                            </div>
                            <div className="min-w-0">
                                <p className="text-xs font-semibold text-white truncate">
                                    {user ? user.username : "Administrator"}
                                </p>
                                <p className="text-[10px] text-emerald-400 uppercase tracking-wider font-mono">
                                    Role: {user ? user.role : "admin"}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={handleSignOut}
                            className="p-1.5 rounded-md hover:bg-emerald-800 text-emerald-300 hover:text-rose-300 transition-colors"
                            title="Sign Out"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                        </button>
                    </div>
                </div>
            </aside>

            {/* Mobile Backdrop */}
            {mobileOpen && (
                <div
                    onClick={() => setMobileOpen(false)}
                    className="fixed inset-0 z-30 bg-black/50 lg:hidden"
                />
            )}
        </>
    );
}
