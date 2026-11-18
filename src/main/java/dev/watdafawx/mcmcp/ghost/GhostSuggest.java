package dev.watdafawx.mcmcp.ghost;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;

import dev.watdafawx.mcmcp.Config;
import dev.watdafawx.mcmcp.McMcp;
import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;

/**
 * "Look at an area and suggest improvements": surveys the REAL blocks around a target ({@link WorldSurvey#region}: palette,
 * buildings, roofs, lights, features), then runs architect/suggest.py as a child process (one Haiku call, own cost cap,
 * 5 min timeout). Results: 3-6 short suggestions in chat and, optionally, the ghost {@value #GHOST_ID} with the
 * proposed additions (cheap survival blocks, drawn in their own colours like area ghosts). One job at a time. The
 * Anthropic key lives in architect/.env and is read only by the Python side: this class never opens, logs or forwards it.
 */
public final class GhostSuggest {
    private GhostSuggest() {}

    public static final String GHOST_ID = "suggest";
    public static final int DEFAULT_RADIUS = 24, MIN_RADIUS = 8, MAX_RADIUS = 40;
    private static final int MAX_MINUTES = 5;
    private static final Pattern COST = Pattern.compile("cost ~\\$([0-9]+(?:\\.[0-9]+)?)");
    private static final AtomicInteger SEQ = new AtomicInteger();

    /** One suggest run. Fields are guarded by synchronized(this). */
    public static final class Job {
        public final String id;
        public final int x, z, radius;
        final boolean overlay;
        final long startedMs = System.currentTimeMillis();
        String status = "running"; // running | done | failed
        String error;
        double cost;
        int overlayBlocks, overlaySkipped;
        Process proc;
        Path out;
        final List<String> suggestions = new ArrayList<>();
        final Deque<String> log = new ArrayDeque<>();

        Job(String id, int x, int z, int radius, boolean overlay) {
            this.id = id;
            this.x = x;
            this.z = z;
            this.radius = radius;
            this.overlay = overlay;
        }

        synchronized void line(String s) {
            log.addLast(s);
            while (log.size() > 40) log.removeFirst();
            Matcher m = COST.matcher(s);
            while (m.find()) cost = Math.max(cost, Double.parseDouble(m.group(1)));
        }

        public synchronized boolean running() {
            return status.equals("running");
        }

        public synchronized Map<String, Object> toMap(int tail) {
            List<String> lines = new ArrayList<>(log);
            if (lines.size() > tail) lines = lines.subList(lines.size() - tail, lines.size());
            Map<String, Object> m = J.obj("job", id, "status", status, "center", List.of(x, z), "radius", radius,
                    "cost_usd", Math.round(cost * 10000) / 10000.0, "seconds", (System.currentTimeMillis() - startedMs) / 1000,
                    "suggestions", new ArrayList<>(suggestions), "log", lines);
            if (overlay) {
                m.put("ghost", overlayBlocks > 0 ? GHOST_ID : null);
                m.put("overlay_blocks", overlayBlocks);
            }
            if (error != null) m.put("error", error);
            return m;
        }
    }

    private static volatile Job current;
    private static volatile Job last;

    public static Job latest() {
        Job c = current;
        return c != null ? c : last;
    }

    public static Job byId(String id) {
        Job c = current, l = last;
        if (c != null && c.id.equals(id)) return c;
        if (l != null && l.id.equals(id)) return l;
        return null;
    }

    static String preflight() {
        String p = GhostGenerate.preflight();
        if (p != null) return p;
        Path dir = GhostGenerate.architectDir();
        if (!Files.isRegularFile(dir.resolve("suggest.py")))
            return "suggest.py not found in " + dir + " (architect folder out of date on this machine)";
        return null;
    }

    // ------------------------------------------------------------------ start

    /**
     * Starts a job. Throws ToolError when busy or not set up. Blocks while the survey runs on the game thread, so call it
     * from a worker or a tool thread. target: look | here | x,z (default look); explicit x and z win.
     */
    public static Job start(String target, Integer x, Integer z, int radius, boolean overlay) {
        radius = Math.max(MIN_RADIUS, Math.min(MAX_RADIUS, radius));
        String problem = preflight();
        if (problem != null) throw new McpServer.ToolError(problem);
        synchronized (GhostSuggest.class) {
            Job c = current;
            if (c != null && c.running())
                throw new McpServer.ToolError("a suggest job is already running (" + c.id + "). ghost_suggest_status shows progress.");
        }
        Object[] r = WorldSurvey.regionAt(target, x, z, radius);
        WorldSurvey.Target t = (WorldSurvey.Target) r[0];
        WorldSurvey.Result sv = (WorldSurvey.Result) r[1];
        Path surveyFile, outFile;
        try {
            surveyFile = sv.writeTemp();
            outFile = Files.createTempFile("mcmcp-suggest-", ".json");
            outFile.toFile().deleteOnExit();
        } catch (IOException e) {
            throw new McpServer.ToolError("cannot write survey: " + e.getMessage());
        }
        String id = "suggest_" + LocalTime.now().format(DateTimeFormatter.ofPattern("HHmmss")) + "_" + SEQ.incrementAndGet();
        Job job = new Job(id, t.x(), t.z(), sv.radius, overlay);
        job.out = outFile;
        synchronized (GhostSuggest.class) {
            Job c = current;
            if (c != null && c.running())
                throw new McpServer.ToolError("a suggest job is already running (" + c.id + "). ghost_suggest_status shows progress.");
            current = job;
        }
        Path dir = GhostGenerate.architectDir();
        List<String> cmd = new ArrayList<>(List.of(GhostGenerate.python(dir), "-u", "suggest.py", "-s", id,
                "--survey", surveyFile.toString(), "--out", outFile.toString(),
                "--max-cost", String.valueOf(Config.SUGGEST_COST_CAP.get())));
        if (!overlay) cmd.add("--no-overlay");
        ProcessBuilder pb = new ProcessBuilder(cmd).directory(dir.toFile()).redirectErrorStream(true);
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        try {
            job.proc = pb.start();
        } catch (IOException e) {
            synchronized (job) {
                job.status = "failed";
                job.error = "could not start " + cmd.get(0) + ": " + e.getMessage();
            }
            finish(job);
            throw new McpServer.ToolError(job.error);
        }
        Thread th = new Thread(() -> watch(job), "mcmcp-ghost-suggest");
        th.setDaemon(true);
        th.start();
        GhostGenerate.chat(ChatFormatting.AQUA, "suggest: reading " + (2 * sv.radius + 1) + "x" + (2 * sv.radius + 1) + " blocks around "
                + t.x() + " " + t.z() + " (job " + id + ", cap $" + String.format(Locale.ROOT, "%.2f", Config.SUGGEST_COST_CAP.get()) + ")");
        return job;
    }

    private static void watch(Job job) {
        Process p = job.proc;
        Thread killer = new Thread(() -> {
            try {
                if (!p.waitFor(MAX_MINUTES, TimeUnit.MINUTES)) {
                    synchronized (job) { job.error = "timed out after " + MAX_MINUTES + " min"; }
                    p.destroyForcibly();
                }
            } catch (InterruptedException ignored) {
            }
        }, "mcmcp-ghost-suggest-timeout");
        killer.setDaemon(true);
        killer.start();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) job.line(line);
        } catch (IOException ignored) {
        }
        int code;
        try {
            code = p.waitFor();
        } catch (InterruptedException e) {
            code = -1;
        }
        killer.interrupt();
        synchronized (job) {
            if (job.error == null && code != 0) job.error = lastError(job, "suggest.py exited with code " + code);
        }
        if (job.error == null) {
            try {
                readResult(job);
            } catch (RuntimeException | IOException e) {
                synchronized (job) { job.error = "bad result: " + e.getMessage(); }
            }
        }
        synchronized (job) { job.status = job.error == null ? "done" : "failed"; }
        finish(job);
    }

    private static String lastError(Job job, String dflt) {
        synchronized (job) {
            for (String s : job.log.reversed()) if (s.startsWith("error:")) return s.substring(6).trim();
        }
        return dflt;
    }

    /** Parses the result file, fills the job and draws the overlay ghost. */
    private static void readResult(Job job) throws IOException {
        JsonObject res = JsonParser.parseString(Files.readString(job.out, StandardCharsets.UTF_8)).getAsJsonObject();
        JsonArray sug = res.getAsJsonArray("suggestions");
        synchronized (job) {
            for (JsonElement e : sug) job.suggestions.add(e.getAsJsonObject().get("text").getAsString());
            if (res.has("cost")) job.cost = Math.max(job.cost, res.get("cost").getAsDouble());
        }
        Files.deleteIfExists(job.out);
        JsonArray blocks = res.has("blocks") ? res.getAsJsonArray("blocks") : new JsonArray();
        if (!job.overlay || blocks.isEmpty()) return;
        Map<BlockPos, BlockState> m = new LinkedHashMap<>();
        int minX = Integer.MAX_VALUE, minY = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE, skipped = 0;
        List<Object[]> parsed = new ArrayList<>();
        for (JsonElement e : blocks) {
            JsonArray a = e.getAsJsonArray();
            BlockState st;
            try {
                st = GhostStore.parseState(a.get(3).getAsString());
            } catch (RuntimeException ex) {
                skipped++;
                continue;
            }
            int bx = a.get(0).getAsInt(), by = a.get(1).getAsInt(), bz = a.get(2).getAsInt();
            minX = Math.min(minX, bx); minY = Math.min(minY, by); minZ = Math.min(minZ, bz);
            parsed.add(new Object[] {bx, by, bz, st});
        }
        if (parsed.isEmpty()) return;
        for (Object[] o : parsed) m.put(new BlockPos((int) o[0] - minX, (int) o[1] - minY, (int) o[2] - minZ), (BlockState) o[3]);
        Ghost g = GhostStore.replaceBlocks(GHOST_ID, m, new BlockPos(minX, minY, minZ),
                Map.of("kind", "area", "class", "lime", "style", "suggest"));
        synchronized (GhostStore.LOCK) {
            g.alpha = 0.75f;
            g.visible = true;
        }
        GhostStore.save(g);
        synchronized (job) {
            job.overlayBlocks = m.size();
            job.overlaySkipped = skipped;
        }
    }

    private static void finish(Job job) {
        synchronized (GhostSuggest.class) {
            last = job;
            if (current == job) current = null;
        }
        String cost = String.format(Locale.ROOT, "$%.4f", job.cost);
        boolean ok;
        String err;
        List<String> sug;
        int blocks;
        synchronized (job) {
            ok = job.status.equals("done");
            err = job.error;
            sug = new ArrayList<>(job.suggestions);
            blocks = job.overlayBlocks;
        }
        if (ok) {
            int i = 1;
            for (String s : sug) GhostGenerate.chat(ChatFormatting.YELLOW, (i++) + ". " + s);
            GhostGenerate.chat(ChatFormatting.GREEN, "suggest done, cost " + cost
                    + (blocks > 0 ? ". Overlay ghost '" + GHOST_ID + "' (" + blocks + " blocks): /ghost hide suggest, /ghost clear suggest" : ""));
        } else {
            GhostGenerate.chat(ChatFormatting.RED, "suggest failed: " + err + " (cost " + cost + "). ghost_suggest_status job=" + job.id + " has the log.");
        }
        McMcp.LOG.info("ghost suggest {} {} cost {}", job.id, ok ? "done" : "failed", cost);
    }

    // ------------------------------------------------------------------ MCP tools

    public static void registerTools(McpServer mcp) {
        mcp.add(new Tool("ghost_suggest",
                "Look at an area and suggest improvements (async: returns a job id at once; poll ghost_suggest_status). Surveys the REAL "
                        + "blocks around target (look = the block the crosshair is on (default) | here | x,z; explicit x,z also count) within "
                        + "radius (8..40, default 24): block palette, buildings (bounding box, roof flatness, lights per wall, glass, doors), "
                        + "water/lava/ores. Then architect/suggest.py (one Claude Haiku call, cost-capped by config ghostGenerate.suggestCostCapUsd, "
                        + "default $0.10, 5 min timeout) returns 3-6 short suggestions (posted in chat and in the status) and, with overlay=true "
                        + "(default), a ghost 'suggest' with the proposed additions (gable roof, lanterns, corner posts: cheap survival blocks; "
                        + "clear with ghost_clear id=suggest). Costs real API money. Needs architect/.env and a python venv on the machine "
                        + "running this client. One job at a time. Natural stone/andesite/granite/diorite builds read as terrain.",
                J.Schema.of().str("target", "look | here | x,z (default look)").integer("x", "centre x").integer("z", "centre z")
                        .integer("radius", "blocks from the centre, 8..40, default 24").bool("overlay", "draw the 'suggest' ghost (default true)")
                        .build(),
                false, a -> {
                    Integer x = a.has("x") ? J.i(a, "x", 0) : null, z = a.has("z") ? J.i(a, "z", 0) : null;
                    if ((x == null) != (z == null)) throw new McpServer.ToolError("give x and z together, or neither");
                    Job j = start(J.str(a, "target", null), x, z, J.i(a, "radius", DEFAULT_RADIUS), J.b(a, "overlay", true));
                    return J.obj("job", j.id, "status", "running", "center", List.of(j.x, j.z), "radius", j.radius,
                            "cost_cap_usd", Config.SUGGEST_COST_CAP.get(), "hint", "poll ghost_suggest_status with this job id");
                }));
        mcp.add(new Tool("ghost_suggest_status",
                "Status of a ghost_suggest job: running | done | failed, the suggestions, overlay ghost + block count, API cost so far, last log lines. "
                        + "job omitted = the latest job.",
                J.Schema.of().str("job", "job id from ghost_suggest").integer("lines", "log lines to return (default 12)").build(),
                true, a -> {
                    String id = J.str(a, "job", null);
                    Job j = id == null ? latest() : byId(id);
                    if (j == null) throw new McpServer.ToolError(id == null ? "no suggest job yet" : "unknown job '" + id
                            + "' (only the current and the last job are kept)");
                    return j.toMap(Math.max(1, Math.min(40, J.i(a, "lines", 12))));
                }));
    }
}
