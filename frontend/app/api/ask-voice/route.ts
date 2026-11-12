import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "../_lib/proxy";

export async function POST(request: Request) {
    try {
        const body = await request.json();
        // Allow 45 seconds for end-to-end speech recognition, RAG retrieval, and speech synthesis
        const result = await forwardToBackend("/ask-voice-json", "POST", body, undefined, 45000);
        return NextResponse.json(result.data, {
            status: result.status,
            headers: {
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        });
    } catch {
        return NextResponse.json(
            { detail: `Unable to connect to the backend at ${getBackendBaseUrl()}.` },
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
