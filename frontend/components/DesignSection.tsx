"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

export default function DesignSection() {
  const [markdown, setMarkdown] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/DESIGN.md")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load DESIGN.md (${res.status})`);
        return res.text();
      })
      .then((text) => {
        setMarkdown(text);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(String(err));
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 py-12 px-6 md:px-12 lg:px-24">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="mb-10">
          <h2 className="text-3xl font-bold text-white tracking-tight">Solution Design</h2>
          <p className="text-gray-400 mt-2">
            Architecture, C4 diagrams, and technical design decisions behind this Digital Twin CV POC.
          </p>
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-gray-400">
            <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Loading design document…
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-900/30 border border-red-700 text-red-300 px-5 py-4 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && (
          <article className="prose prose-invert prose-sm md:prose-base max-w-none
            prose-headings:text-white
            prose-h1:text-2xl prose-h1:font-bold prose-h1:border-b prose-h1:border-gray-700 prose-h1:pb-2
            prose-h2:text-xl prose-h2:font-semibold prose-h2:text-blue-300 prose-h2:mt-8
            prose-h3:text-base prose-h3:font-semibold prose-h3:text-gray-200
            prose-p:text-gray-300 prose-p:leading-relaxed
            prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
            prose-strong:text-white
            prose-code:text-blue-300 prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700 prose-pre:rounded-lg prose-pre:text-xs prose-pre:overflow-x-auto
            prose-blockquote:border-l-blue-500 prose-blockquote:text-gray-400
            prose-li:text-gray-300
            prose-hr:border-gray-700
            prose-table:text-sm
            prose-th:text-gray-200 prose-th:bg-gray-800
            prose-td:text-gray-300 prose-td:border-gray-700">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
