"use client";

import { useState } from "react";

type ApiResponse = {
  input_text: string;
  language: string;
  language_code: string;
  intent: string;
  confidence: number | null;
  classification_method: string;
  answer: string;
  mode: string;
};

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function askQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!question.trim()) {
      setError("Please enter your farming question.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: question.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to process your question.");
      }

      setResult(data as ApiResponse);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Cannot connect to the backend. Check that it is running."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 via-white to-emerald-100 px-4 py-10 text-gray-800">
      <div className="mx-auto max-w-3xl">
        <header className="mb-10 text-center">
          <div className="mb-4 text-6xl" aria-hidden="true">
            🌱
          </div>

          <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-green-700">
            AI-powered agriculture
          </p>

          <h1 className="text-4xl font-extrabold tracking-tight text-green-950 sm:text-5xl">
            Smart Farming Assistant
          </h1>

          <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-gray-600 sm:text-lg">
            Ask farming questions in your language. Get help with irrigation,
            crop pests, fertilizers and agricultural schemes.
          </p>
        </header>

        <section className="rounded-3xl border border-green-100 bg-white p-5 shadow-xl sm:p-8">
          <h2 className="mb-2 text-2xl font-bold text-gray-900">
            How can we help your farm?
          </h2>

          <p className="mb-6 text-sm text-gray-500">
            Enter your question in English, Tamil, Hindi, Kannada or another
            supported language.
          </p>

          <form onSubmit={askQuestion}>
            <label
              htmlFor="farming-question"
              className="mb-2 block font-semibold text-gray-700"
            >
              Your farming question
            </label>

            <textarea
              id="farming-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Example: How often should I water my tomato plants?"
              rows={5}
              className="w-full resize-y rounded-xl border border-gray-300 bg-white p-4 text-base outline-none transition focus:border-green-600 focus:ring-2 focus:ring-green-100"
            />

            <button
              type="submit"
              disabled={loading}
              className="mt-4 w-full rounded-xl bg-green-700 px-6 py-4 font-bold text-white transition hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Processing your question..." : "Ask Farming Assistant →"}
            </button>
          </form>

          {error && (
            <div
              role="alert"
              className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700"
            >
              <p className="font-semibold">Something went wrong</p>
              <p className="mt-1 text-sm">{error}</p>
            </div>
          )}

          {result && (
            <div className="mt-7 rounded-2xl border border-green-200 bg-green-50 p-5">
              <h3 className="mb-4 text-xl font-bold text-green-950">
                Analysis result
              </h3>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-white p-4">
                  <p className="text-sm text-gray-500">Detected language</p>
                  <p className="mt-1 font-bold">{result.language}</p>
                  <p className="text-sm text-gray-500">
                    Code: {result.language_code}
                  </p>
                </div>

                <div className="rounded-xl bg-white p-4">
                  <p className="text-sm text-gray-500">Question category</p>
                  <p className="mt-1 font-bold">
                    {result.intent.replaceAll("_", " ")}
                  </p>
                </div>

                <div className="rounded-xl bg-white p-4">
                  <p className="text-sm text-gray-500">Classification confidence</p>
                  <p className="mt-1 font-bold">
                    {result.confidence == null
                      ? "Not available"
                      : `${(result.confidence * 100).toFixed(2)}%`}
                  </p>
                </div>

                <div className="rounded-xl bg-white p-4">
                  <p className="text-sm text-gray-500">Processing mode</p>
                  <p className="mt-1 font-bold">{result.mode}</p>
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-white p-4">
                <h4 className="font-bold text-gray-800">Assistant response</h4>
                <p className="mt-2 whitespace-pre-wrap leading-7 text-gray-700">
                  {result.answer}
                </p>
              </div>

              {result.mode === "local" && (
                <p className="mt-4 text-sm text-amber-800">
                  Note: Local testing mode is active. The response is a test
                  message, not yet a personalized AI farming recommendation.
                </p>
              )}
            </div>
          )}
        </section>

        <footer className="mt-8 text-center text-sm text-gray-500">
          Smart Farming Assistant · Supporting smarter farming decisions 🌾
        </footer>
      </div>
    </main>
  );
}