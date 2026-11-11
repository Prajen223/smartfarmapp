"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getAdminToken, setAdminToken, setAdminUser } from "../auth";

export default function AdminLoginPage() {
    const router = useRouter();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        // If already authenticated as admin, redirect to /admin directly
        const token = getAdminToken();
        if (token) {
            router.push("/admin");
        }
    }, [router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (!username.trim() || !password.trim()) {
            setError("Please enter both username and password.");
            return;
        }

        setIsLoading(true);
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: username.trim(),
                    password: password.trim(),
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || "Authentication failed. Please verify credentials.");
                setIsLoading(false);
                return;
            }

            // Verify admin role requirement
            if (data.role !== "admin") {
                setError(
                    "Access denied: Administrator privileges required. Farmer accounts cannot access the admin console."
                );
                setIsLoading(false);
                return;
            }

            // Save admin session securely in sessionStorage
            setAdminToken(data.access_token);
            setAdminUser({ username: data.username, role: data.role });

            // Navigate to admin dashboard
            router.push("/admin");
        } catch {
            setError("Unable to connect to authentication service. Please ensure the backend is running.");
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-emerald-950 via-emerald-900 to-gray-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
            <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-3xl shadow-lg mb-4">
                    🌾
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-white">
                    FarmSaathi Admin Console
                </h1>
                <p className="mt-1.5 text-xs text-emerald-300 font-medium">
                    Secure Administrative Access & Operations Dashboard
                </p>
            </div>

            <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
                <div className="bg-white py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-emerald-900/40">
                    <form className="space-y-5" onSubmit={handleSubmit}>
                        {error && (
                            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium leading-relaxed">
                                {error}
                            </div>
                        )}

                        <div>
                            <label
                                htmlFor="username"
                                className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
                            >
                                Administrator Username
                            </label>
                            <div className="mt-1.5">
                                <input
                                    id="username"
                                    name="username"
                                    type="text"
                                    autoComplete="username"
                                    required
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    placeholder="e.g. admin"
                                    className="block w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                                />
                            </div>
                        </div>

                        <div>
                            <label
                                htmlFor="password"
                                className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
                            >
                                Password
                            </label>
                            <div className="mt-1.5">
                                <input
                                    id="password"
                                    name="password"
                                    type="password"
                                    autoComplete="current-password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••••••"
                                    className="block w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                                />
                            </div>
                        </div>

                        <div>
                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-emerald-700 hover:bg-emerald-800 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-50 transition-colors"
                            >
                                {isLoading ? "Authenticating..." : "Sign In to Admin Console"}
                            </button>
                        </div>
                    </form>

                    <div className="mt-6 pt-5 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                        <Link
                            href="/"
                            className="font-medium text-emerald-700 hover:text-emerald-800 flex items-center gap-1.5"
                        >
                            <span>← Back to Farmer Assistant</span>
                        </Link>
                        <span className="font-mono text-[11px] text-gray-400">
                            RBAC Enforced
                        </span>
                    </div>
                </div>

                <p className="mt-6 text-center text-xs text-emerald-400/80">
                    Protected by Scrypt Key Derivation & RFC 7519 JWT Validation
                </p>
            </div>
        </div>
    );
}
