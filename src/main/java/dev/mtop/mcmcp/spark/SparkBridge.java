package dev.mtop.mcmcp.spark;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import java.util.stream.Stream;

import com.google.gson.JsonObject;

import net.neoforged.fml.ModList;
import net.neoforged.fml.loading.FMLPaths;

import dev.mtop.mcmcp.Config;
import dev.mtop.mcmcp.mcp.J;
import dev.mtop.mcmcp.mcp.McpServer;
import dev.mtop.mcmcp.mcp.McpServer.Tool;

/**
 * Drives spark through its own commands ({@code sparkc} on the client, {@code spark} on a server)
 * and reads back the profile it saves with {@code --save-to-file}. No spark class is linked, so the
 * tools simply report "spark not installed" without it.
 */
public final class SparkBridge {
    /** Runs a spark command line (without slash) on one side; messages it prints go to the sink. */
    public interface Runner {
        void run(String commandLine, Consumer<String> sink);
    }

    private final Map<String, Runner> sides; // "client" -> sparkc runner, "server" -> spark runner
    private final Map<String, Long> startedAt = new ConcurrentHashMap<>();
    private final Map<String, String> startArgs = new ConcurrentHashMap<>();
    private volatile SparkAnalyzer.Profile last;

    public SparkBridge(Map<String, Runner> sides) {
        this.sides = sides;
    }

    public static boolean present() {
        return ModList.get().isLoaded("spark");
    }

    public static Path dir() {
        return FMLPaths.CONFIGDIR.get().resolve("spark");
    }

    public void register(McpServer mcp) {
        if (!Config.SPARK_TOOLS.get()) return;
        String sideList = String.join("|", sides.keySet());
        String defSide = sides.containsKey("client") ? "client" : "server";
        mcp.add(new Tool("spark_start",
                "Start the spark sampling profiler. side: " + sideList + " (default " + defSide + "; in singleplayer 'client' already covers the integrated server thread when threads='*'). "
                        + "threads: '*' for all threads (default), or a thread name. Stop with spark_stop to get the results as JSON.",
                J.Schema.of().enumOf("side", "which spark instance", sides.keySet().toArray(String[]::new))
                        .str("threads", "'*' (default) or a thread name, e.g. 'Render thread'")
                        .integer("interval_ms", "sampling interval, default 4")
                        .integer("timeout_s", "auto-stop after this many seconds (spark then uploads; prefer spark_stop)")
                        .str("extra", "extra raw spark flags, e.g. '--only-ticks-over 60' or '--alloc'")
                        .build(),
                true, this::start));
        mcp.add(new Tool("spark_stop",
                "Stop the running spark profiler, save the profile locally (no upload) and return the analysis: threads, mods by self time, hot methods with callers, and optionally the call tree.",
                analysisSchema().enumOf("side", "which spark instance", sides.keySet().toArray(String[]::new)).build(),
                true, this::stop));
        mcp.add(new Tool("spark_analyze",
                "Re-analyze the last profile (or a saved .sparkprofile file from config/spark) with other options, e.g. another thread or a tree.",
                analysisSchema().str("file", "file name in config/spark; default = last profile").build(),
                true, this::analyzeTool));
        mcp.add(new Tool("spark_status",
                "Whether spark is installed, which profilers this server started, and the saved profiles.",
                J.Schema.of().build(), true, a -> status()));
    }

    private static J.Schema analysisSchema() {
        return J.Schema.of()
                .str("thread", "thread name substring, '*' for all; default Render thread + Server thread")
                .integer("top", "rows in mods / hot methods (default 25)")
                .bool("tree", "include the call tree (default false)")
                .num("min_pct", "tree: hide nodes under this % of the thread (default 1.5)")
                .integer("max_depth", "tree: max depth (default 40)")
                .bool("include_idle", "keep time threads spend parked/sleeping/waiting (default false: dropped, so % = share of real work)");
    }

    private Runner runner(JsonObject a) {
        if (!present()) throw new McpServer.ToolError("spark is not installed");
        String side = J.str(a, "side", sides.containsKey("client") ? "client" : "server");
        Runner r = sides.get(side);
        if (r == null) throw new McpServer.ToolError("no spark side '" + side + "' here; available: " + sides.keySet());
        return r;
    }

    private Object start(JsonObject a) throws Exception {
        Runner r = runner(a);
        String side = J.str(a, "side", sides.containsKey("client") ? "client" : "server");
        StringBuilder cmd = new StringBuilder("profiler start");
        String threads = J.str(a, "threads", "*");
        if (!threads.isBlank()) cmd.append(" --thread ").append(threads.contains(" ") ? "\"" + threads + "\"" : threads);
        cmd.append(" --interval ").append(J.i(a, "interval_ms", 4));
        if (a.has("timeout_s")) cmd.append(" --timeout ").append(J.i(a, "timeout_s", 60));
        String extra = J.str(a, "extra", "");
        if (!extra.isBlank()) {
            if (extra.matches(".*[;&|`\\n].*")) throw new McpServer.ToolError("bad characters in extra");
            cmd.append(' ').append(extra);
        }
        List<String> msgs = collect(r, cmd.toString(), 4000);
        startedAt.put(side, System.currentTimeMillis());
        startArgs.put(side, cmd.toString());
        return J.obj("side", side, "command", cmd.toString(), "spark_said", msgs);
    }

    private Object stop(JsonObject a) throws Exception {
        Runner r = runner(a);
        String side = J.str(a, "side", sides.containsKey("client") ? "client" : "server");
        long t0 = System.currentTimeMillis();
        List<String> before = listProfiles();
        List<String> msgs = new ArrayList<>();
        r.run("profiler stop --save-to-file", msgs::add);
        Path file = null;
        long deadline = t0 + 120_000;
        long lastSize = -1;
        while (System.currentTimeMillis() < deadline) {
            Thread.sleep(300);
            Path newest = newestProfile(before);
            if (newest != null) {
                long size = Files.size(newest);
                if (size > 0 && size == lastSize) {
                    file = newest;
                    break;
                }
                lastSize = size;
            }
            if (lastSize < 0 && System.currentTimeMillis() - t0 > 8000 && joined(msgs).matches("(?is).*(isn't|not) running.*|.*no .*profiler.*"))
                break;
        }
        if (file == null)
            throw new McpServer.ToolError("spark saved no profile. spark said: " + joined(msgs));
        startedAt.remove(side);
        last = SparkAnalyzer.load(file);
        Map<String, Object> out = analyze(last, a);
        out.put("side", side);
        out.put("spark_said", msgs);
        return out;
    }

    private Object analyzeTool(JsonObject a) throws Exception {
        String f = J.str(a, "file", null);
        if (f != null) {
            Path p = dir().resolve(f).normalize();
            if (!p.startsWith(dir()) || !Files.isRegularFile(p)) throw new McpServer.ToolError("no such profile: " + f);
            last = SparkAnalyzer.load(p);
        }
        if (last == null) throw new McpServer.ToolError("no profile yet; run spark_start / spark_stop first");
        return analyze(last, a);
    }

    private static Map<String, Object> analyze(SparkAnalyzer.Profile p, JsonObject a) {
        return SparkAnalyzer.analyze(p, J.str(a, "thread", null), J.i(a, "top", 25),
                J.d(a, "min_pct", 1.5), J.i(a, "max_depth", 40), J.b(a, "tree", false), J.b(a, "include_idle", false));
    }

    private Object status() throws IOException {
        Map<String, Object> running = new java.util.LinkedHashMap<>();
        startedAt.forEach((k, v) -> running.put(k, J.obj("for_s", (System.currentTimeMillis() - v) / 1000, "command", startArgs.get(k))));
        return J.obj("installed", present(), "sides", sides.keySet(), "started_here", running,
                "saved_profiles", listProfiles().stream().limit(10).toList(), "dir", dir().toString());
    }

    private static List<String> collect(Runner r, String cmd, long waitMs) throws InterruptedException {
        List<String> msgs = java.util.Collections.synchronizedList(new ArrayList<>());
        r.run(cmd, msgs::add);
        long end = System.currentTimeMillis() + waitMs;
        while (System.currentTimeMillis() < end) {
            Thread.sleep(200);
            String j = joined(msgs);
            if (j.contains("started") || j.contains("already") || j.contains("Error") || j.contains("isn't") || j.contains("Unknown")) break;
        }
        synchronized (msgs) {
            return new ArrayList<>(msgs);
        }
    }

    private static String joined(List<String> msgs) {
        synchronized (msgs) {
            return String.join(" | ", msgs);
        }
    }

    private static List<String> listProfiles() throws IOException {
        if (!Files.isDirectory(dir())) return List.of();
        try (Stream<Path> s = Files.list(dir())) {
            return s.filter(p -> p.toString().endsWith(".sparkprofile"))
                    .sorted(Comparator.comparingLong(SparkBridge::mtime).reversed())
                    .map(p -> p.getFileName().toString()).toList();
        }
    }

    private static Path newestProfile(List<String> before) throws IOException {
        if (!Files.isDirectory(dir())) return null;
        try (Stream<Path> s = Files.list(dir())) {
            return s.filter(p -> p.toString().endsWith(".sparkprofile") && !before.contains(p.getFileName().toString()))
                    .max(Comparator.comparingLong(SparkBridge::mtime)).orElse(null);
        }
    }

    private static long mtime(Path p) {
        try {
            return Files.getLastModifiedTime(p).toMillis();
        } catch (IOException e) {
            return 0;
        }
    }
}
