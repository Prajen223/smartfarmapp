import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "../_lib/proxy";

export async function POST(request: Request) {
    try {
        const body = await request.json();
        const authHeader = request.headers.get("authorization");
        const headers: Record<string, string> = {};
        if (authHeader) {
            headers["Authorization"] = authHeader;
        }

        const result = await forwardToBackend("/feedback", "POST", body, headers);
        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            { detail: `Unable to connect to backend at ${getBackendBaseUrl()}.` },
            { status: 502 }
        );
    }
}
