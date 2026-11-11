import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "../_lib/proxy";

export async function GET() {
    try {
        const result = await forwardToBackend("/health", "GET");

        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            {
                status: "unreachable",
                detail: `Cannot connect to FastAPI at ${getBackendBaseUrl()}`,
            },
            { status: 502 }
        );
    }
}
