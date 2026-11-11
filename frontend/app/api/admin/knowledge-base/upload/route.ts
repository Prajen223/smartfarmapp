import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_lib/proxy";

export async function POST(request: Request) {
    try {
        const authHeader = request.headers.get("authorization");
        const headers: Record<string, string> = {};
        if (authHeader) {
            headers["Authorization"] = authHeader;
        }

        const formData = await request.formData();
        const backendUrl = `${getBackendBaseUrl()}/admin/knowledge-base/upload`;

        const res = await fetch(backendUrl, {
            method: "POST",
            headers,
            body: formData,
        });

        const data = await res.json();
        return NextResponse.json(data, { status: res.status });
    } catch {
        return NextResponse.json(
            { detail: `Unable to connect to backend at ${getBackendBaseUrl()}.` },
            { status: 502 }
        );
    }
}
