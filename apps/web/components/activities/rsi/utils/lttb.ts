/**
 * LTTB (Largest Triangle Three Buckets) downsampling.
 *
 * Reduces a time-series to `target` points while preserving visual shape.
 * Always retains first and last points.
 *
 * Reference: Sveinn Steinarsson, "Downsampling Time Series for Visual
 * Representation", University of Iceland, 2013.
 */

export interface LTTBPoint {
  time: number;
  [key: string]: number | null;
}

export function lttbDownsample<T extends LTTBPoint>(
  data: T[],
  target: number,
  yKey: string = 'hr',
): T[] {
  const n = data.length;
  if (n <= target || target < 3) return data.slice();

  const sampled: T[] = [data[0]]; // always keep first
  const bucketSize = (n - 2) / (target - 2);

  let prevIndex = 0;

  for (let i = 1; i < target - 1; i++) {
    const bucketStart = Math.floor((i - 1) * bucketSize) + 1;
    const bucketEnd = Math.min(Math.floor(i * bucketSize) + 1, n - 1);

    // Average of next bucket (for triangle area calc)
    const nextBucketStart = Math.floor(i * bucketSize) + 1;
    const nextBucketEnd = Math.min(Math.floor((i + 1) * bucketSize) + 1, n - 1);
    let avgX = 0;
    let avgY = 0;
    const nextLen = nextBucketEnd - nextBucketStart;
    for (let j = nextBucketStart; j < nextBucketEnd; j++) {
      avgX += data[j].time;
      avgY += (data[j] as Record<string, number>)[yKey] ?? 0;
    }
    if (nextLen > 0) {
      avgX /= nextLen;
      avgY /= nextLen;
    }

    // Point A (previously selected)
    const ax = data[prevIndex].time;
    const ay = (data[prevIndex] as Record<string, number>)[yKey] ?? 0;

    // Find point in current bucket with largest triangle area
    let maxArea = -1;
    let maxIdx = bucketStart;
    for (let j = bucketStart; j < bucketEnd; j++) {
      const bx = data[j].time;
      const by = (data[j] as Record<string, number>)[yKey] ?? 0;
      const area = Math.abs((ax - avgX) * (by - ay) - (ax - bx) * (avgY - ay));
      if (area > maxArea) {
        maxArea = area;
        maxIdx = j;
      }
    }

    sampled.push(data[maxIdx]);
    prevIndex = maxIdx;
  }

  sampled.push(data[n - 1]); // always keep last
  return sampled;
}
