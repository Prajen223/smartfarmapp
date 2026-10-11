import http from "node:http";

export interface ProxyResponse<T = unknown> {
    status: number;
    data: T;
}

export function forwardToBackend<T = unknown>(
    path: string,
    method: string,
    body?: unknown
): Promise<ProxyResponse<T>> {
    return new Promise((resolve, reject) => {
        const rawBody = body ? JSON.stringify(body) : undefined;
        const req = http.request(
            {
                hostname: "127.0.0.1",
                port: 6000,
                path: path.startsWith("/") ? path : `/${path}`,
                method,
                headers: {
                    "Content-Type": "application/json",
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
