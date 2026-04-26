/**
 * Client-side PNG card for shareable Manual findings (1080×1350).
 * No PII: headline + optional subline are caller-sanitized.
 */

export const FINDING_SHARE_CARD_WIDTH = 1080;
export const FINDING_SHARE_CARD_HEIGHT = 1350;

export const FINDING_SHARE_LANDING_URL =
  'https://strideiq.run/tools?utm_source=share_card&utm_medium=social&utm_campaign=finding';

export interface FindingShareCardInput {
  headline: string;
  /** Short supporting line (e.g. narrative excerpt). Omit for headline-only cards. */
  subline?: string;
  /** Shown as "Confirmed N times" when > 0 */
  confirmedTimes?: number;
}

function wrapTextLines(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  maxLines: number,
): string[] {
  const words = text.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = '';
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
      if (lines.length >= maxLines) break;
    } else {
      line = test;
    }
  }
  if (line && lines.length < maxLines) lines.push(line);
  if (words.length && lines.length === 0) lines.push(words.slice(0, 12).join(' '));
  return lines.slice(0, maxLines);
}

/**
 * Renders the share card to a PNG blob (for Web Share / download).
 */
export async function renderFindingShareCardPng(input: FindingShareCardInput): Promise<Blob> {
  const w = FINDING_SHARE_CARD_WIDTH;
  const h = FINDING_SHARE_CARD_HEIGHT;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get canvas context');

  const padX = 80;
  const contentW = w - padX * 2;

  const bg = ctx.createLinearGradient(0, 0, w, h);
  bg.addColorStop(0, '#0f172a');
  bg.addColorStop(0.45, '#172554');
  bg.addColorStop(1, '#1e1b4b');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  ctx.fillStyle = '#f97316';
  ctx.fillRect(padX, 140, 6, 220);

  let y = 200;
  ctx.fillStyle = '#f8fafc';
  ctx.font =
    '600 52px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  const headlineLines = wrapTextLines(ctx, input.headline, contentW, 7);
  for (const hl of headlineLines) {
    ctx.fillText(hl, padX + 24, y);
    y += 68;
  }

  y += 24;
  if (input.subline?.trim()) {
    ctx.fillStyle = '#94a3b8';
    ctx.font =
      '400 34px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    const subLines = wrapTextLines(ctx, input.subline, contentW, 8);
    for (const sl of subLines) {
      ctx.fillText(sl, padX + 24, y);
      y += 48;
    }
  }

  if (input.confirmedTimes != null && input.confirmedTimes > 0) {
    y += 32;
    ctx.fillStyle = '#64748b';
    ctx.font =
      '500 30px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(`Confirmed ${input.confirmedTimes} times`, padX + 24, y);
  }

  const footerY = h - 160;
  ctx.fillStyle = '#64748b';
  ctx.font =
    '500 28px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.fillText('Discovered by StrideIQ', padX + 24, footerY);

  ctx.fillStyle = '#f97316';
  ctx.font =
    '400 26px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  const urlLines = wrapTextLines(ctx, FINDING_SHARE_LANDING_URL, contentW, 2);
  let uy = footerY + 44;
  for (const ul of urlLines) {
    ctx.fillText(ul, padX + 24, uy);
    uy += 34;
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error('PNG export failed'));
      },
      'image/png',
      1,
    );
  });
}

export function findingShareCaption(): string {
  return `Training intelligence worth sharing — ${FINDING_SHARE_LANDING_URL}`;
}
