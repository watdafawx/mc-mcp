package dev.mtop.mcmcp.metrics;

import java.util.Arrays;
import java.util.Map;

import dev.mtop.mcmcp.mcp.J;

/**
 * Frame-time ring buffer, fed once per frame from the render thread. Frame time is the gap between
 * consecutive frame starts, so it includes everything the frame waited on (vsync, frame limiter).
 */
public final class FrameStats {
    private static final int CAP = 1 << 17; // ~131k frames: 7 min at 300 fps
    private static final long[] END = new long[CAP];
    private static final int[] DUR_US = new int[CAP];
    private static volatile long count; // written only by the render thread
    private static long last;

    private FrameStats() {}

    /** Called at the start of every frame on the render thread. */
    public static void onFrame() {
        long now = System.nanoTime();
        if (last != 0) {
            long dt = now - last;
            int i = (int) (count & (CAP - 1));
            END[i] = now;
            DUR_US[i] = (int) Math.min(Integer.MAX_VALUE, dt / 1000);
            count = count + 1;
        }
        last = now;
    }

    public static long totalFrames() {
        return count;
    }

    /** Stats over frames that ended in (fromNanos, toNanos]. */
    public static Map<String, Object> window(long fromNanos, long toNanos) {
        long n = count;
        int max = (int) Math.min(n, CAP);
        int[] buf = new int[max];
        int k = 0;
        long firstStart = Long.MAX_VALUE, lastEnd = 0;
        for (int j = 0; j < max; j++) {
            int i = (int) ((n - 1 - j) & (CAP - 1));
            long e = END[i];
            if (e > toNanos) continue;
            if (e <= fromNanos) break;
            buf[k++] = DUR_US[i];
            firstStart = Math.min(firstStart, e - DUR_US[i] * 1000L);
            lastEnd = Math.max(lastEnd, e);
        }
        if (k == 0) return J.obj("frames", 0, "note", "no frames in window (game minimized, frozen, or just started)");
        int[] d = Arrays.copyOf(buf, k);
        Arrays.sort(d);
        double sumUs = 0;
        for (int v : d) sumUs += v;
        double seconds = (lastEnd - firstStart) / 1e9;
        int over50 = 0, over100 = 0;
        for (int v : d) {
            if (v >= 50_000) over50++;
            if (v >= 100_000) over100++;
        }
        return J.obj(
                "frames", k,
                "seconds", J.r2(seconds),
                "fps_avg", J.r1(k / Math.max(seconds, 1e-9)),
                "fps_1pct_low", J.r1(1e6 / meanTop(d, 0.01)),
                "fps_0_1pct_low", J.r1(1e6 / meanTop(d, 0.001)),
                "frame_ms_avg", J.r2(sumUs / k / 1000.0),
                "frame_ms_p50", J.r2(pct(d, 0.50) / 1000.0),
                "frame_ms_p95", J.r2(pct(d, 0.95) / 1000.0),
                "frame_ms_p99", J.r2(pct(d, 0.99) / 1000.0),
                "frame_ms_worst", J.r2(d[k - 1] / 1000.0),
                "frames_over_50ms", over50,
                "frames_over_100ms", over100);
    }

    private static double pct(int[] sorted, double p) {
        int idx = (int) Math.ceil(p * sorted.length) - 1;
        return sorted[Math.max(0, Math.min(sorted.length - 1, idx))];
    }

    /** Mean of the slowest {@code frac} of frames ("1% low" style). */
    private static double meanTop(int[] sorted, double frac) {
        int m = Math.max(1, (int) Math.round(sorted.length * frac));
        double s = 0;
        for (int i = sorted.length - m; i < sorted.length; i++) s += sorted[i];
        return s / m;
    }
}
