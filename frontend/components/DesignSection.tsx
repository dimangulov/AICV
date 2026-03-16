"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

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
      .then((text) => { setMarkdown(text); setLoading(false); })
      .catch((err: unknown) => { setError(String(err)); setLoading(false); });
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 py-12 px-6 md:px-12 lg:px-24">
      <div className="max-w-5xl mx-auto">

        {loading && (
          <div className="flex items-center gap-3 text-gray-400 py-20 justify-center">
            <span className="inline-block w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Loading design document…
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-900/30 border border-red-700 text-red-300 px-5 py-4 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && (
          <article className="
            prose prose-invert max-w-none
            prose-headings:scroll-mt-20
            prose-h1:text-3xl prose-h1:font-bold prose-h1:text-white prose-h1:border-b prose-h1:border-gray-700 prose-h1:pb-3 prose-h1:mb-6
            prose-h2:text-xl prose-h2:font-semibold prose-h2:text-blue-300 prose-h2:mt-10 prose-h2:mb-4 prose-h2:border-b prose-h2:border-gray-800 prose-h2:pb-2
            prose-h3:text-base prose-h3:font-semibold prose-h3:text-gray-100 prose-h3:mt-7 prose-h3:mb-3
            prose-h4:text-sm prose-h4:font-semibold prose-h4:text-gray-300 prose-h4:uppercase prose-h4:tracking-wide
            prose-p:text-gray-300 prose-p:leading-7
            prose-a:text-blue-400 prose-a:no-underline hover:prose-a:text-blue-300 hover:prose-a:underline
            prose-strong:text-white prose-strong:font-semibold
            prose-code:text-blue-300 prose-code:bg-blue-950/40 prose-code:border prose-code:border-blue-900/40 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-mono prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700/60 prose-pre:rounded-xl prose-pre:text-xs prose-pre:overflow-x-auto prose-pre:p-0 prose-pre:shadow-lg
            prose-blockquote:border-l-2 prose-blockquote:border-blue-500 prose-blockquote:bg-blue-950/20 prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:text-gray-400 prose-blockquote:not-italic
            prose-ul:text-gray-300 prose-ol:text-gray-300
            prose-li:text-gray-300 prose-li:marker:text-blue-500
            prose-hr:border-gray-800 prose-hr:my-8
            prose-table:text-sm prose-table:w-full
            prose-thead:bg-gray-800/60
            prose-th:text-gray-200 prose-th:font-semibold prose-th:px-4 prose-th:py-2 prose-th:border prose-th:border-gray-700
            prose-td:text-gray-300 prose-td:px-4 prose-td:py-2 prose-td:border prose-td:border-gray-700/60
            prose-tr:even:bg-gray-800/20
            prose-img:rounded-xl
          ">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
            >
              {markdown}
            </ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
