import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "../_lib/proxy";

export async function POST(request: Request) {
    try {
        const body = await request.json();
        // Allow 60 seconds to accommodate Render Free cold-start wake-up latency
        const result = await forwardToBackend("/ask", "POST", body, undefined, 60000);

        if (result.status >= 500) {
            const dataObj = typeof result.data === "object" && result.data !== null ? (result.data as Record<string, unknown>) : null;
            const detail = typeof dataObj?.detail === "string" && dataObj.detail
                ? dataObj.detail
                : "The farming assistant backend is temporarily unavailable or restarting. Please try again in a few moments.";
            return NextResponse.json({ detail }, {
                status: result.status,
                headers: { "Cache-Control": "no-store, no-cache, must-revalidate" },
            });
        }

        return NextResponse.json(result.data, {
            status: result.status,
            headers: { "Cache-Control": "no-store, no-cache, must-revalidate" },
        });
    } catch {
        return NextResponse.json(
            {
                detail: `Unable to connect to the backend at ${getBackendBaseUrl()}. Please ensure FastAPI is running.`,
            },
            {
                status: 502,
                headers: { "Cache-Control": "no-store, no-cache, must-revalidate" },
            }
        );
    }
}
