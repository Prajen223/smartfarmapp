import { NextResponse } from "next/server";
import { forwardToBackend } from "../_lib/proxy";

export async function GET() {
    try {
        const result = await forwardToBackend("/health", "GET");

        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            {
                status: "unreachable",
                detail: "Cannot connect to FastAPI on port 6000",
            },
            { status: 502 }
        );
    }
}
