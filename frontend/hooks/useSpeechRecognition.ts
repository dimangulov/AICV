"use client";

import { useState, useCallback, useRef, useEffect } from "react";

// ── Browser API type declarations ────────────────────────────────────────────
// webkitSpeechRecognition is not in the standard TypeScript DOM lib.

interface SpeechRecognitionResultItem {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionResult {
  readonly [index: number]: SpeechRecognitionResultItem;
  readonly length: number;
  readonly isFinal: boolean;
}

interface SpeechRecognitionResultList {
  readonly [index: number]: SpeechRecognitionResult;
  readonly length: number;
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  onresult: ((ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((ev: SpeechRecognitionErrorEvent) => void) | null;
  onend: ((ev: Event) => void) | null;
  onstart: ((ev: Event) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

// ── Hook interface ────────────────────────────────────────────────────────────

interface UseSpeechRecognitionOptions {
  /** Called once with the final transcript when the user stops speaking. */
  onResult: (transcript: string) => void;
  /** Called when the browser reports a recognition error. */
  onError?: (error: string) => void;
  /** BCP-47 language tag. Defaults to "en-US". */
  lang?: string;
}

interface UseSpeechRecognitionReturn {
  /** Whether the microphone is currently active. */
  isListening: boolean;
  /** Last captured transcript (cleared when a new session starts). */
  transcript: string;
  /** False on Firefox or when running on the server. */
  isSupported: boolean;
  /** Start a new recognition session. */
  startListening: () => void;
  /** Stop the current session (triggers onResult if anything was captured). */
  stopListening: () => void;
}

// ── Hook implementation ───────────────────────────────────────────────────────

export function useSpeechRecognition({
  onResult,
  onError,
  lang = "en-US",
}: UseSpeechRecognitionOptions): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  const startListening = useCallback(() => {
    if (!isSupported) return;

    // Abort any in-progress session before starting a new one
    recognitionRef.current?.abort();

    const Ctor = (
      (window as unknown as Record<string, unknown>).SpeechRecognition ??
      (window as unknown as Record<string, unknown>).webkitSpeechRecognition
    ) as new () => SpeechRecognitionInstance;

    const recognition = new Ctor();
    recognition.lang = lang;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onstart = () => {
      setIsListening(true);
      setTranscript("");
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const text = event.results[0]?.[0]?.transcript ?? "";
      setTranscript(text);
      if (text.trim()) {
        onResult(text.trim());
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // "no-speech" is normal — don't surface it as an error to the user
      if (event.error !== "no-speech") {
        onError?.(event.error);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [isSupported, lang, onResult, onError]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  // Abort on unmount to avoid dangling microphone permissions
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return { isListening, transcript, isSupported, startListening, stopListening };
}
