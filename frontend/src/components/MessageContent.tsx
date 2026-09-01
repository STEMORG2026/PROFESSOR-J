"use client";

import dynamic from "next/dynamic";
import { Fragment, useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

const PlotlyChart = dynamic(() => import("./PlotlyChart"), { ssr: false });

// A ```plotly  ``` fenced block carrying a JSON figure config.
const PLOTLY_BLOCK_RE = /```plotly\s*\n([\s\S]*?)```/g;
// Block math $$...$$ (non-greedy, multiline-safe).
const BLOCK_MATH_RE = /\$\$([\s\S]*?)\$\$/g;
// Inline math $...$ (no whitespace right after opening $).
const INLINE_MATH_RE = /\$([^$\s][^$]*?[^$\s])\$/g;

interface Segment {
  kind: "text" | "inline-math" | "block-math" | "plotly";
  content: string;
  html?: string;
  figure?: { data: unknown[]; layout?: Record<string, unknown>; config?: Record<string, unknown> };
}

/** Render a LaTeX string to HTML via KaTeX (throws → fallback to raw text). */
function katexHtml(tex: string, display: boolean): string {
  try {
    return katex.renderToString(tex, { displayMode: display, throwOnError: false });
  } catch {
    return tex;
  }
}

/** Split message text into plotly / math / text segments (plotly first). */
function parseSegments(content: string): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  const plotlyMatches = [...content.matchAll(PLOTLY_BLOCK_RE)];
  for (const m of plotlyMatches) {
    if (m.index !== undefined && m.index > cursor) {
      segments.push(...parseMath(content.slice(cursor, m.index)));
    }
    try {
      const figure = JSON.parse(m[1]) as {
        data: unknown[];
        layout?: Record<string, unknown>;
        config?: Record<string, unknown>;
      };
      segments.push({ kind: "plotly", content: m[0], figure });
    } catch {
      segments.push({ kind: "text", content: m[0] });
    }
    cursor = m.index !== undefined ? m.index + m[0].length : cursor;
  }
  if (plotlyMatches.length > 0) {
    if (cursor < content.length) segments.push(...parseMath(content.slice(cursor)));
    return segments;
  }
  return parseMath(content);
}

function parseMath(text: string): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  const blockMatches = [...text.matchAll(BLOCK_MATH_RE)];
  for (const m of blockMatches) {
    if (m.index !== undefined && m.index > cursor) {
      segments.push(...parseInlineMath(text.slice(cursor, m.index)));
    }
    segments.push({ kind: "block-math", content: m[1].trim(), html: katexHtml(m[1].trim(), true) });
    cursor = m.index !== undefined ? m.index + m[0].length : cursor;
  }
  if (blockMatches.length > 0) {
    if (cursor < text.length) segments.push(...parseInlineMath(text.slice(cursor)));
    return segments;
  }
  return parseInlineMath(text);
}

function parseInlineMath(text: string): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  const matches = [...text.matchAll(INLINE_MATH_RE)];
  for (const m of matches) {
    if (m.index !== undefined && m.index > cursor) {
      segments.push({ kind: "text", content: text.slice(cursor, m.index) });
    }
    segments.push({ kind: "inline-math", content: m[1], html: katexHtml(m[1], false) });
    cursor = m.index !== undefined ? m.index + m[0].length : cursor;
  }
  if (matches.length > 0) {
    if (cursor < text.length) segments.push({ kind: "text", content: text.slice(cursor) });
    return segments;
  }
  return [{ kind: "text", content: text }];
}

interface MessageContentProps {
  content: string;
  streaming?: boolean;
}

/**
 * Renders a message's content with KaTeX equations ($...$, $$...$$) and Plotly
 * chart blocks (```plotly {json} ```) as rich, interactive components.
 */
export default function MessageContent({ content, streaming }: MessageContentProps) {
  const segments = useMemo(() => parseSegments(content), [content]);
  return (
    <div className="whitespace-pre-wrap break-words">
      {segments.map((seg, i) => {
        if (seg.kind === "plotly" && seg.figure) {
          return <PlotlyChart key={i} figure={seg.figure} />;
        }
        if ((seg.kind === "inline-math" || seg.kind === "block-math") && seg.html) {
          return (
            <span
              key={i}
              className={seg.kind === "block-math" ? "my-2 flex justify-center overflow-x-auto" : undefined}
              dangerouslySetInnerHTML={{ __html: seg.html }}
            />
          );
        }
        return <Fragment key={i}>{seg.content}</Fragment>;
      })}
      {streaming && !content && <span className="animate-pulse">▌</span>}
    </div>
  );
}