import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "@/app/api/_lib/proxy";

export async function GET(request: Request) {
    try {
        const authHeader = request.headers.get("authorization");
        const headers: Record<string, string> = {};
        if (authHeader) {
            headers["Authorization"] = authHeader;
        }

        const { search } = new URL(request.url);
        const result = await forwardToBackend(`/admin/knowledge-base${search}`, "GET", undefined, headers);
        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            { detail: `Unable to connect to backend at ${getBackendBaseUrl()}.` },
            { status: 502 }
        );
    }
}

export async function POST(request: Request) {
    try {
        const authHeader = request.headers.get("authorization");
        const headers: Record<string, string> = {};
        if (authHeader) {
            headers["Authorization"] = authHeader;
        }

        const body = await request.json();
        const result = await forwardToBackend("/admin/knowledge-base", "POST", body, headers);
        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            { detail: `Unable to connect to backend at ${getBackendBaseUrl()}.` },
            { status: 502 }
        );
    }
}
