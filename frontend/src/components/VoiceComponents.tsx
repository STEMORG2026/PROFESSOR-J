"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface UseVoiceInputOptions {
  onResult: (transcript: string) => void;
  onError?: (error: string) => void;
  language?: string;
}

export function useVoiceInput({
  onResult,
  onError,
  language = "en",
}: UseVoiceInputOptions) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // Check browser support for MediaRecorder
  useEffect(() => {
    const supported = !!(navigator.mediaDevices && window.MediaRecorder);
    setIsSupported(supported);
  }, []);

  const startListening = useCallback(async () => {
    if (isListening || isProcessing) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        try {
          const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
          const formData = new FormData();
          formData.append("audio", audioBlob, "recording.webm");
          if (language) {
            formData.append("language", language);
          }

          const response = await fetch("/api/voice/stt", {
            method: "POST",
            body: formData,
          });

          if (!response.ok) {
            throw new Error(`STT failed: ${response.status}`);
          }

          const result = await response.json();
          if (result.text) {
            onResult(result.text);
          }
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : "Transcription failed";
          onError?.(errorMsg);
        } finally {
          setIsProcessing(false);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100); // Collect data every 100ms
      setIsListening(true);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to start recording";
      onError?.(errorMsg);
      setIsListening(false);
    }
  }, [isListening, isProcessing, onResult, onError, language]);

  const stopListening = useCallback(() => {
    if (mediaRecorderRef.current && isListening) {
      mediaRecorderRef.current.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsListening(false);
  }, [isListening]);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && isListening) {
        mediaRecorderRef.current.stop();
        streamRef.current?.getTracks().forEach((track) => track.stop());
      }
    };
  }, [isListening]);

  return {
    isSupported,
    isListening,
    isProcessing,
    startListening,
    stopListening,
    toggleListening,
  };
}

interface UseTTSOptions {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error: string) => void;
}

export function useTTS({ onStart, onEnd, onError }: UseTTSOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const speak = useCallback(
    async (text: string, options?: { voice_id?: string; length_scale?: number }) => {
      if (!text.trim()) return;

      // Cancel any ongoing speech
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      try {
        setIsSpeaking(true);
        onStart?.();

        const formData = new FormData();
        formData.append("text", text);
        if (options?.voice_id) {
          formData.append("voice_id", options.voice_id);
        }
        if (options?.length_scale) {
          formData.append("length_scale", String(options.length_scale));
        }

        const response = await fetch("/api/voice/tts", {
          method: "POST",
          body: formData,
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`TTS failed: ${response.status}`);
        }

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        audioRef.current = new Audio(audioUrl);
        audioRef.current.onended = () => {
          setIsSpeaking(false);
          onEnd?.();
          URL.revokeObjectURL(audioUrl);
        };
        audioRef.current.onerror = () => {
          setIsSpeaking(false);
          const err = "Audio playback failed";
          onError?.(err);
          URL.revokeObjectURL(audioUrl);
        };

        await audioRef.current.play();
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return; // Ignore aborted requests
        }
        setIsSpeaking(false);
        const errorMsg = err instanceof Error ? err.message : "Speech synthesis failed";
        onError?.(errorMsg);
      }
    },
    [onStart, onEnd, onError]
  );

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
  }, []);

  const resume = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.play().catch(() => {});
    }
  }, []);

  return {
    isSupported: true,
    isSpeaking,
    speak,
    stop,
    pause,
    resume,
  };
}

export function VoiceInputButton({
  onTranscript,
  disabled = false,
  className = "",
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const { isSupported, isListening, isProcessing, toggleListening } = useVoiceInput({
    onResult: onTranscript,
    onError: (err) => console.error("Voice input error:", err),
  });

  if (!isSupported) {
    return (
      <span className="text-xs text-slate-500" title="Voice input not supported in this browser">
        🎤✕
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleListening}
      disabled={disabled || isProcessing}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border transition ${
        isListening
          ? "border-rose-500/50 bg-rose-500/10 text-rose-400 animate-pulse"
          : isProcessing
          ? "border-amber-500/50 bg-amber-500/10 text-amber-400"
          : "border-white/10 bg-white/5 text-slate-300 hover:border-cyan-500/50 hover:text-cyan-300"
      } ${className}`}
      title={isListening ? "Click to stop listening" : isProcessing ? "Processing..." : "Click to start voice input"}
    >
      {isListening ? (
        <>
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="text-sm">Listening...</span>
        </>
      ) : isProcessing ? (
        <>
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="text-sm">Processing...</span>
        </>
      ) : (
        <>
          <span className="text-cyan-400">🎤</span>
          <span className="text-sm">Voice</span>
        </>
      )}
    </button>
  );
}

export function TTSButton({
  text,
  disabled = false,
  className = "",
  voice_id,
  length_scale = 1.0,
}: {
  text: string;
  disabled?: boolean;
  className?: string;
  voice_id?: string;
  length_scale?: number;
}) {
  const { isSupported, isSpeaking, speak, stop } = useTTS();

  if (!isSupported) {
    return (
      <span className="text-xs text-slate-500" title="Text-to-speech not supported">
        🔊✕
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={isSpeaking ? stop : () => speak(text, { voice_id, length_scale })}
      disabled={disabled || !text.trim()}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border transition ${
        isSpeaking
          ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-400"
          : "border-white/10 bg-white/5 text-slate-300 hover:border-cyan-500/50 hover:text-cyan-300"
      } ${className}`}
      title={isSpeaking ? "Click to stop" : "Click to speak"}
    >
      {isSpeaking ? (
        <>
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span className="text-sm">Speaking...</span>
        </>
      ) : (
        <>
          <span className="text-fuchsia-400">🔊</span>
          <span className="text-sm">Speak</span>
        </>
      )}
    </button>
  );
}

export function MessageTTSButton({
  text,
  disabled = false,
  voice_id,
}: {
  text: string;
  disabled?: boolean;
  voice_id?: string;
}) {
  const { isSupported, isSpeaking, speak, stop } = useTTS();

  if (!isSupported) {
    return null;
  }

  const speaking = isSpeaking;

  return (
    <button
      type="button"
      onClick={speaking ? stop : () => speak(text, { voice_id })}
      disabled={disabled || !text.trim()}
      className={`p-1.5 rounded transition ${
        speaking
          ? "bg-cyan-500/20 text-cyan-400"
          : "text-slate-400 hover:text-fuchsia-400 hover:bg-white/5"
      }`}
      title={speaking ? "Stop speaking" : "Read aloud"}
      aria-label={speaking ? "Stop reading" : "Read message aloud"}
    >
      {speaking ? (
        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" stroke="currentColor" strokeWidth="4" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        </svg>
      )}
    </button>
  );
}
