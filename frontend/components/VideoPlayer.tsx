"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { Loader2, Play, VideoOff, AlertTriangle, Wifi, WifiOff } from "lucide-react";
import { getSession } from "@/lib/api";

type ConnectionStatus =
  | "idle"
  | "fetching-session"
  | "connecting"
  | "connected"
  | "error";

interface VideoPlayerProps {
  onLog?: (message: string, level?: "info" | "success" | "error") => void;
  /** Called once the LiveKit room is live and the avatar is ready. */
  onConnected?: () => void;
}

export default function VideoPlayer({ onLog, onConnected }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const roomRef = useRef<Room | null>(null);
  const canvasCleanupRef = useRef<(() => void) | null>(null);

  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const log = useCallback(
    (msg: string, level: "info" | "success" | "error" = "info") => {
      onLog?.(msg, level);
    },
    [onLog],
  );

  const connect = useCallback(async () => {
    // Tear down any previous LiveKit room
    void roomRef.current?.disconnect();
    roomRef.current = null;
    canvasCleanupRef.current?.();
    canvasCleanupRef.current = null;

    setStatus("fetching-session");
    setErrorMsg("");
    log("[Avatar] Requesting WebRTC session from backend...");

    try {
      // ── Step 1: Fetch session credentials ────────────────────────────────
      const session = await getSession();
      log(
        `[Avatar] Session obtained: ${session.session_id.slice(0, 12)}…`,
        "success",
      );

      setStatus("connecting");

      if (session.session_id === "mock-session-id") {
        log(
          "[Avatar] Mock mode — rendering canvas placeholder (set LIVEAVATAR_API_KEY for live avatar)",
        );
        canvasCleanupRef.current = startMockStream(videoRef);
        setStatus("connected");
        log("[Avatar] Mock stream active", "success");
        return;
      }

      // Connect to LiveAvatar's hosted LiveKit room
      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Video && videoRef.current) {
          track.attach(videoRef.current);
          videoRef.current
            .play()
            .catch((e: unknown) => log(`[Avatar] Autoplay blocked: ${e}`, "error"));
          setStatus("connected");
          log("[Avatar] Live stream connected!", "success");
        }
        if (track.kind === Track.Kind.Audio && audioRef.current) {
          track.attach(audioRef.current);
          audioRef.current
            .play()
            .catch((e: unknown) => log(`[Avatar] Audio autoplay blocked: ${e}`, "error"));
          log("[Avatar] Audio track attached", "info");
        }
      });

      room.on(RoomEvent.Connected, () => {
        log("[Avatar] Room connected", "info");
        onConnected?.();
      });

      room.on(RoomEvent.Disconnected, () => {
        log("[Avatar] LiveKit room disconnected");
        setStatus("idle");
      });

      room.on(RoomEvent.ConnectionStateChanged, (state) => {
        log(`[Avatar] Connection state → ${state}`);
      });

      await room.connect(session.livekit_url, session.livekit_client_token, {
        autoSubscribe: true,
      });
      log("[Avatar] Connected to LiveKit room, waiting for video track...");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setErrorMsg(msg);
      setStatus("error");
      log(`[Avatar] Connection failed: ${msg}`, "error");
    }
  }, [log]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      void roomRef.current?.disconnect();
      canvasCleanupRef.current?.();
    };
  }, []);

  return (
    <div className="relative w-full h-full min-h-[400px] flex flex-col items-center justify-center">
      {/* Hidden audio element for avatar voice — separate from video to avoid mute restrictions */}
      <audio ref={audioRef} autoPlay playsInline />

      {/* Video element — always rendered so the ref is stable */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-cover transition-opacity duration-500 ${
          status === "connected" ? "opacity-100" : "opacity-0 absolute"
        }`}
      />

      {/* Overlay — shown when not connected */}
      {status !== "connected" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 p-8">
          {/* Avatar silhouette placeholder */}
          <div className="relative">
            <div className="w-40 h-40 rounded-full bg-gradient-to-br from-blue-500/20 to-purple-600/20 border border-blue-500/20 flex items-center justify-center">
              <div className="w-28 h-28 rounded-full bg-gradient-to-br from-blue-500/30 to-purple-600/30 border border-blue-500/30 flex items-center justify-center">
                <span className="text-4xl font-bold text-blue-400/60 select-none">
                  AM
                </span>
              </div>
            </div>
            {/* Animated ring when connecting */}
            {(status === "fetching-session" || status === "connecting") && (
              <div className="absolute inset-0 rounded-full border-2 border-blue-400/40 animate-ping" />
            )}
          </div>

          {/* Status message */}
          <div className="text-center">
            {status === "idle" && (
              <>
                <p className="text-gray-300 text-sm mb-1">
                  Digital Twin Avatar
                </p>
                <p className="text-gray-500 text-xs">
                  Click to connect the avatar stream
                </p>
              </>
            )}
            {(status === "fetching-session" || status === "connecting") && (
              <div className="flex items-center gap-2 text-blue-400 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>
                  {status === "fetching-session"
                    ? "Requesting session…"
                    : "Connecting to avatar…"}
                </span>
              </div>
            )}
            {status === "error" && (
              <div className="flex flex-col items-center gap-2">
                <div className="flex items-center gap-2 text-red-400 text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  <span>{errorMsg}</span>
                </div>
                <p className="text-gray-500 text-xs">
                  Click to retry
                </p>
              </div>
            )}
          </div>

          {/* Connect / Retry button */}
          <button
            onClick={connect}
            disabled={
              status === "fetching-session" || status === "connecting"
            }
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-full font-medium text-sm transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30"
          >
            {status === "fetching-session" || status === "connecting" ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Connecting…
              </>
            ) : status === "error" ? (
              <>
                <WifiOff className="w-4 h-4" />
                Retry Connection
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Connect Avatar
              </>
            )}
          </button>
        </div>
      )}

      {/* Connected status badge */}
      {status === "connected" && (
        <div className="absolute top-4 left-4 flex items-center gap-1.5 bg-black/60 backdrop-blur-sm rounded-full px-3 py-1.5 text-xs text-green-400">
          <Wifi className="w-3 h-3" />
          <span>Live</span>
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
        </div>
      )}

      {/* Disconnect button when connected */}
      {status === "connected" && (
        <button
          onClick={() => {
            void roomRef.current?.disconnect();
            roomRef.current = null;
            canvasCleanupRef.current?.();
            canvasCleanupRef.current = null;
            if (videoRef.current) videoRef.current.srcObject = null;
            setStatus("idle");
            log("[Avatar] Disconnected");
          }}
          className="absolute top-4 right-4 flex items-center gap-1.5 bg-black/60 backdrop-blur-sm hover:bg-black/80 rounded-full px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <VideoOff className="w-3 h-3" />
          Disconnect
        </button>
      )}
    </div>
  );
}

// ── Mock stream (development / POC) ──────────────────────────────────────────
// Creates an animated canvas stream as a placeholder for the real avatar video.
// Returns a cleanup function that stops the animation loop.

function startMockStream(
  videoRef: React.RefObject<HTMLVideoElement | null>,
): () => void {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 720;
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};

  let rafId: number;
  let active = true;

  const draw = () => {
    if (!active) return;
    const t = Date.now() / 1000;

    // Background
    ctx.fillStyle = "#0a0f1e";
    ctx.fillRect(0, 0, 640, 720);

    // Animated radial gradients simulating lighting
    const hue1 = (t * 15) % 360;
    const hue2 = (t * 15 + 120) % 360;

    const g1 = ctx.createRadialGradient(320, 300, 40, 320, 300, 280);
    g1.addColorStop(0, `hsla(${hue1}, 70%, 55%, 0.25)`);
    g1.addColorStop(1, "transparent");
    ctx.fillStyle = g1;
    ctx.fillRect(0, 0, 640, 720);

    const g2 = ctx.createRadialGradient(320, 300, 20, 320, 300, 180);
    g2.addColorStop(0, `hsla(${hue2}, 60%, 50%, 0.15)`);
    g2.addColorStop(1, "transparent");
    ctx.fillStyle = g2;
    ctx.fillRect(0, 0, 640, 720);

    // Head/shoulder silhouette shape
    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    // Shoulders
    ctx.beginPath();
    ctx.ellipse(320, 820, 220, 160, 0, 0, Math.PI * 2);
    ctx.fill();
    // Neck
    ctx.fillRect(285, 540, 70, 80);
    // Head
    ctx.beginPath();
    ctx.ellipse(320, 480, 110, 130, 0, 0, Math.PI * 2);
    ctx.fill();

    // Face glow
    const faceGlow = ctx.createRadialGradient(320, 480, 20, 320, 480, 110);
    faceGlow.addColorStop(0, `hsla(${hue1}, 60%, 60%, 0.18)`);
    faceGlow.addColorStop(1, "transparent");
    ctx.fillStyle = faceGlow;
    ctx.beginPath();
    ctx.ellipse(320, 480, 110, 130, 0, 0, Math.PI * 2);
    ctx.fill();

    // Initials
    ctx.fillStyle = "rgba(148,163,184,0.8)";
    ctx.font = "bold 42px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("AM", 320, 476);

    // POC watermark
    ctx.fillStyle = "rgba(100,116,139,0.5)";
    ctx.font = "13px monospace";
    ctx.fillText("[ POC — Connect LiveAvatar API for live stream ]", 320, 690);

    rafId = requestAnimationFrame(draw);
  };

  draw();

  if (videoRef.current) {
    const stream = canvas.captureStream(25);
    videoRef.current.srcObject = stream;
    videoRef.current.play().catch(() => {});
  }

  return () => {
    active = false;
    cancelAnimationFrame(rafId);
  };
}
