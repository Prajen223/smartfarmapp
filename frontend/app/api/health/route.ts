import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "../_lib/proxy";

export async function GET() {
    try {
        // Fast 8-second probe for health checks to detect sleeping / waking states quickly
        const result = await forwardToBackend("/health", "GET", undefined, undefined, 8000);

        return NextResponse.json(result.data, {
            status: result.status,
            headers: {
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        });
    } catch {
        return NextResponse.json(
            {
                status: "connecting",
                detail: `FastAPI backend is starting up or waking from sleep at ${getBackendBaseUrl()}`,
            },
            {
                status: 502,
                headers: {
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                },
            }
        );
    }
}
