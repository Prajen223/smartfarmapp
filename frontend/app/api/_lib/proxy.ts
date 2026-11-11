import http from "node:http";
import https from "node:https";

export interface ProxyResponse<T = unknown> {
    status: number;
    data: T;
}

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export function getBackendBaseUrl(): string {
    return (
        process.env.FASTAPI_BASE_URL ||
        process.env.BACKEND_URL ||
        DEFAULT_BACKEND_URL
    ).replace(/\/+$/, "");
}

export function forwardToBackend<T = unknown>(
    path: string,
    method: string,
    body?: unknown,
    customHeaders?: Record<string, string>
): Promise<ProxyResponse<T>> {
    return new Promise((resolve, reject) => {
        const rawBody = body ? JSON.stringify(body) : undefined;
        const baseUrl = new URL(getBackendBaseUrl());
        const isHttps = baseUrl.protocol === "https:";
        const client = isHttps ? https : http;
        const port = baseUrl.port
            ? parseInt(baseUrl.port, 10)
            : (isHttps ? 443 : 80);
        const basePath = baseUrl.pathname === "/" ? "" : baseUrl.pathname.replace(/\/+$/, "");
        const normalizedPath = path.startsWith("/") ? path : `/${path}`;
        const targetPath = `${basePath}${normalizedPath}`;

        const req = client.request(
            {
                hostname: baseUrl.hostname,
                port,
                path: targetPath,
                method,
                headers: {
                    "Content-Type": "application/json",
                    ...(customHeaders || {}),
                    ...(rawBody
                        ? { "Content-Length": Buffer.byteLength(rawBody).toString() }
                        : {}),
                },
            },
            (res) => {
                let responseData = "";
                res.setEncoding("utf-8");
                res.on("data", (chunk) => {
                    responseData += chunk;
                });
                res.on("end", () => {
                    try {
                        const parsed = JSON.parse(responseData) as T;
                        resolve({
                            status: res.statusCode || 200,
                            data: parsed,
                        });
                    } catch {
                        resolve({
                            status: res.statusCode || 200,
                            data: responseData as unknown as T,
                        });
                    }
                });
            }
        );

        req.on("error", (error) => {
            reject(error);
        });

        if (rawBody) {
            req.write(rawBody);
        }
        req.end();
    });
}
