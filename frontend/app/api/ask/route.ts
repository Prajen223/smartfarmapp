import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "../_lib/proxy";

export async function POST(request: Request) {
    try {
        const body = await request.json();
        const result = await forwardToBackend("/ask", "POST", body);

        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            {
                detail: `Unable to connect to the backend at ${getBackendBaseUrl()}. Please ensure FastAPI is running.`,
            },
            { status: 502 }
        );
    }
}
