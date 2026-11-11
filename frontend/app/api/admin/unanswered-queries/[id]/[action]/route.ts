import { NextResponse } from "next/server";
import { forwardToBackend, getBackendBaseUrl } from "@/app/api/_lib/proxy";

export async function POST(
    request: Request,
    { params }: { params: Promise<{ id: string; action: string }> }
) {
    try {
        const { id, action } = await params;
        const authHeader = request.headers.get("authorization");
        const headers: Record<string, string> = {};
        if (authHeader) {
            headers["Authorization"] = authHeader;
        }

        let body: unknown = undefined;
        try {
            body = await request.json();
        } catch {
            body = undefined;
        }

        const result = await forwardToBackend(
            `/admin/unanswered-queries/${id}/${action}`,
            "POST",
            body,
            headers
        );
        return NextResponse.json(result.data, { status: result.status });
    } catch {
        return NextResponse.json(
            { detail: `Unable to connect to backend at ${getBackendBaseUrl()}.` },
            { status: 502 }
        );
    }
}
