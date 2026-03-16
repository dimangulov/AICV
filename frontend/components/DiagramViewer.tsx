"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { ZoomIn, ZoomOut, Maximize2, Loader2, Terminal } from "lucide-react";

interface DiagramViewerProps {
  /** Public path to the SVG, e.g. /diagrams/L1_SystemContext.svg */
  src: string;
  alt: string;
  /** Viewer height in px (default 540) */
  height?: number;
}

const MIN_SCALE  = 0.15;
const MAX_SCALE  = 6;
const ZOOM_STEP  = 0.12;

export default function DiagramViewer({ src, alt, height = 540 }: DiagramViewerProps) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const [svgHtml,    setSvgHtml]    = useState<string | null>(null);
  const [loadError,  setLoadError]  = useState(false);
  const [scale,      setScale]      = useState(1);
  const [pan,        setPan]        = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  // Refs give wheel/pointer handlers access to the latest state without
  // registering them as effect dependencies.
  const scaleRef     = useRef(1);
  const panRef       = useRef({ x: 0, y: 0 });
  const dragOrigin   = useRef<{ mx: number; my: number; ox: number; oy: number } | null>(null);
  scaleRef.current   = scale;
  panRef.current     = pan;

  // ── Fetch and inline SVG ────────────────────────────────────────────────────
  useEffect(() => {
    setSvgHtml(null);
    setLoadError(false);
    setScale(1);
    setPan({ x: 0, y: 0 });

    fetch(src)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then((html) => {
        // Strip XML / DOCTYPE declarations — not valid inside HTML
        const clean = html
          .replace(/<\?xml[^?]*\?>/g, "")
          .replace(/<!DOCTYPE[^>]*>/gi, "")
          .trim();
        setSvgHtml(clean);
      })
      .catch(() => setLoadError(true));
  }, [src]);

  // ── Non-passive wheel listener for zoom-to-cursor ───────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect   = el.getBoundingClientRect();
      const cx     = e.clientX - rect.left;
      const cy     = e.clientY - rect.top;
      const prev   = scaleRef.current;
      const factor = e.deltaY < 0 ? 1 + ZOOM_STEP : 1 - ZOOM_STEP;
      const next   = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev * factor));
      const ratio  = next / prev;
      setPan((p) => ({ x: cx - ratio * (cx - p.x), y: cy - ratio * (cy - p.y) }));
      setScale(next);
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [svgHtml]); // re-attach after SVG loads so containerRef.current is ready

  // ── Pointer drag handlers ────────────────────────────────────────────────────
  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragOrigin.current = {
      mx: e.clientX, my: e.clientY,
      ox: panRef.current.x, oy: panRef.current.y,
    };
    setIsDragging(true);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragOrigin.current) return;
    setPan({
      x: dragOrigin.current.ox + e.clientX - dragOrigin.current.mx,
      y: dragOrigin.current.oy + e.clientY - dragOrigin.current.my,
    });
  }, []);

  const onPointerUp = useCallback(() => {
    dragOrigin.current = null;
    setIsDragging(false);
  }, []);

  // ── Button zoom — centered on the container midpoint ────────────────────────
  const zoomBy = (factor: number) => {
    const el = containerRef.current;
    const cx = el ? el.clientWidth  / 2 : 0;
    const cy = el ? el.clientHeight / 2 : 0;
    setScale((s) => {
      const next  = Math.min(MAX_SCALE, Math.max(MIN_SCALE, s * factor));
      const ratio = next / s;
      setPan((p) => ({ x: cx - ratio * (cx - p.x), y: cy - ratio * (cy - p.y) }));
      return next;
    });
  };

  const reset = () => { setScale(1); setPan({ x: 0, y: 0 }); };

  // ── Error state — SVGs not yet exported ─────────────────────────────────────
  if (loadError) {
    return (
      <div className="flex flex-col items-center gap-5 py-10 px-6 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center">
          <Terminal className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <p className="text-white font-medium mb-1">Diagrams not yet exported</p>
          <p className="text-gray-400 text-sm max-w-sm">
            Run the export script once to generate SVGs from{" "}
            <code className="text-blue-300 bg-blue-950/40 px-1 rounded text-xs">c4/workspace.dsl</code>:
          </p>
        </div>
        <div className="bg-gray-950 border border-gray-700 rounded-lg px-5 py-3 text-left w-full max-w-md">
          <p className="text-gray-500 text-xs mb-1 font-mono"># Requires Docker Desktop</p>
          <p className="text-green-400 font-mono text-xs">pwsh c4/export-diagrams.ps1</p>
        </div>
      </div>
    );
  }

  // ── Loading skeleton ─────────────────────────────────────────────────────────
  if (!svgHtml) {
    return (
      <div
        className="flex items-center justify-center text-gray-500 text-sm gap-2"
        style={{ height }}
      >
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading diagram…
      </div>
    );
  }

  // ── Viewer ───────────────────────────────────────────────────────────────────
  return (
    <div className="relative select-none" style={{ touchAction: "none" }}>
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-0.5 bg-gray-900/95 border border-gray-700 rounded-lg px-1 py-1 backdrop-blur-sm shadow-lg">
        <button
          onClick={() => zoomBy(1 + ZOOM_STEP * 2)}
          title="Zoom in (scroll up)"
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <span className="text-gray-500 text-xs px-1.5 tabular-nums min-w-[2.8rem] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={() => zoomBy(1 - ZOOM_STEP * 2)}
          title="Zoom out (scroll down)"
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-4 bg-gray-700 mx-0.5" />
        <button
          onClick={reset}
          title="Reset to 100%"
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ── Canvas ──────────────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="c4-diagram overflow-hidden rounded-lg bg-gray-950/60 w-full"
        style={{ height, cursor: isDragging ? "grabbing" : "grab" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        aria-label={alt}
        role="img"
      >
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
            transformOrigin: "0 0",
            willChange: "transform",
          }}
          // SVG is generated by our own CLI export pipeline — not user input.
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: svgHtml }}
        />
      </div>

      {/* ── Hint ────────────────────────────────────────────────────────── */}
      <p className="absolute bottom-2 left-3 text-xs text-gray-600 pointer-events-none select-none">
        Scroll to zoom · Drag to pan
      </p>
    </div>
  );
}
