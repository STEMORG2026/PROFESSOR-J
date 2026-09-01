"use client";

import { useState, useRef, ChangeEvent } from "react";

type UploadedFile = {
  original_name: string;
  stored_name: string;
  path: string;
  size: number;
  content_type: string;
};

export function FileUpload({
  onFileUpload,
  acceptedTypes = ["application/pdf", "image/*"],
  maxSizeMB = 10,
}: {
  onFileUpload: (file: UploadedFile) => void;
  acceptedTypes?: string[];
  maxSizeMB?: number;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const isValidType = acceptedTypes.some((type) => {
      if (type.endsWith("/*")) {
        return file.type.startsWith(type.slice(0, -1));
      }
      return file.type === type;
    });
    if (!isValidType) {
      setError(`File type not supported. Allowed: ${acceptedTypes.join(", ")}`);
      return;
    }

    // Validate file size
    if (file.size > maxSizeMB * 1024 * 1024) {
      setError(`File too large. Maximum size: ${maxSizeMB}MB`);
      return;
    }

    setError(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(`Upload failed: ${err}`);
      }

      const data = await res.json();
      if (data.file) {
        onFileUpload(data.file);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="mb-4">
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileSelect}
        accept={acceptedTypes.join(",")}
        className="hidden"
        id="file-upload"
        disabled={uploading}
      />
      <label
        htmlFor="file-upload"
        className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border transition cursor-pointer ${
          uploading
            ? "border-slate-600 bg-white/2 opacity-60 cursor-not-allowed"
            : "border-white/10 bg-white/5 hover:border-cyan-500/50 hover:bg-white/10"
        }`}
      >
        {uploading ? (
          <>
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
            <span className="text-sm text-slate-300">Uploading...</span>
          </>
        ) : (
          <>
            <span className="text-cyan-400">📎</span>
            <span className="text-sm text-slate-300">
              Click to attach file (PDF, images up to {maxSizeMB}MB)
            </span>
          </>
        )}
      </label>
      {error && (
        <p className="mt-1 text-xs text-rose-400">{error}</p>
      )}
    </div>
  );
}

export default FileUpload;
