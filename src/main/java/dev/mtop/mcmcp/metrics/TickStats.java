package dev.mtop.mcmcp.metrics;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;

import dev.mtop.mcmcp.mcp.J;

/** TPS/MSPT from the server's own last-100-ticks buffers (whole server and per dimension). */
public final class TickStats {
    private TickStats() {}

    /** Call on the server thread. */
    public static Map<String, Object> of(MinecraftServer server) {
        long[] t = server.getTickTimesNanos().clone();
        float rate = server.tickRateManager().tickrate();
        List<Map<String, Object>> dims = new ArrayList<>();
        for (ServerLevel level : server.getAllLevels()) {
            long[] d = server.getTickTime(level.dimension());
            if (d == null) continue;
            Map<String, Object> s = summary(d.clone(), rate);
            s.remove("tps");
            s.put("dimension", level.dimension().location().toString());
            dims.add(s);
        }
        dims.sort((a, b) -> Double.compare(((Number) b.get("mspt_avg")).doubleValue(), ((Number) a.get("mspt_avg")).doubleValue()));
        Map<String, Object> out = summary(t, rate);
        out.put("target_tps", rate);
        out.put("paused", server.isPaused());
        out.put("players", server.getPlayerCount());
        out.put("per_dimension", dims);
        out.put("note", "last 100 ticks; mspt over 50 means the server cannot hold 20 TPS. Paused singleplayer reports stale values.");
        return out;
    }

    private static Map<String, Object> summary(long[] nanos, float rate) {
        long[] v = Arrays.stream(nanos).filter(x -> x > 0).sorted().toArray();
        if (v.length == 0) return J.obj("ticks", 0, "mspt_avg", 0.0);
        double sum = 0;
        for (long x : v) sum += x;
        double avgMs = sum / v.length / 1e6;
        double interval = 1000.0 / rate;
        return J.obj(
                "ticks", v.length,
                "tps", J.r2(Math.min(rate, 1000.0 / Math.max(avgMs, interval))),
                "mspt_avg", J.r2(avgMs),
                "mspt_p95", J.r2(v[Math.max(0, Math.min(v.length - 1, (int) Math.ceil(v.length * 0.95) - 1))] / 1e6),
                "mspt_max", J.r2(v[v.length - 1] / 1e6));
    }
}
