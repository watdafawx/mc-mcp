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
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.neoforged.fml.loading.FMLPaths;

import dev.watdafawx.mcmcp.Config;
import dev.watdafawx.mcmcp.GameThread;
import dev.watdafawx.mcmcp.McMcp;
import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;

/**
 * Runs the LLM architect (architect/architect.py) as a child process on the machine hosting this client. The architect
 * talks back to this client's MCP server to place ghosts. One job at a time; never blocks the game thread. The
 * Anthropic key lives in architect/.env and is read only by the architect itself: this class never opens, logs or
 * forwards it.
 */
public final class GhostGenerate {
    private GhostGenerate() {}

    public static final List<String> STYLES = List.of("steampunk", "hextech", "gothic", "station_white", "solarpunk");
    public static final List<String> KITS = List.of("steampunk", "hextech", "gothic", "station_white", "solarpunk",
            "cyber_dark", "ae_sky", "rust_industrial");
    public static final List<String> LAYOUTS = List.of("spine", "radial", "cloister", "linear", "terraces");

    private static final Pattern COST = Pattern.compile("cost ~\\$([0-9]+(?:\\.[0-9]+)?)");
    private static final int MAX_MINUTES = 30;
    private static final AtomicInteger SEQ = new AtomicInteger();

    /** One architect run. Fields are guarded by synchronized(this). */
    public static final class Job {
        public final String id;
        public final String style;
        public final int x, y, z;
        final long startedMs = System.currentTimeMillis();
        String status = "running"; // running | done | failed
        String error;
        String site; // one-line site fit summary the architect printed (survey mode)
        String reply; // one-line summary the architect printed on completion
        double cost;
        Process proc;
        final Deque<String> log = new ArrayDeque<>();

        Job(String id, String style, int x, int y, int z) {
            this.id = id;
            this.style = style;
            this.x = x;
            this.y = y;
            this.z = z;
        }

        synchronized void line(String s) {
            if (s.startsWith("SITE ")) {
                site = s.substring(5).trim();
                chat(ChatFormatting.AQUA, "site " + (site.length() > 150 ? site.substring(0, 150) : site));
            } else if (s.startsWith("REPLY ")) {
                reply = s.substring(6).trim();
                chat(ChatFormatting.WHITE, reply.length() > 220 ? reply.substring(0, 220) + "..." : reply);
            }
            log.addLast(s);
            while (log.size() > 40) log.removeFirst();
            Matcher m = COST.matcher(s);
            while (m.find()) cost = Math.max(cost, Double.parseDouble(m.group(1)));
        }

        public synchronized boolean running() {
            return status.equals("running");
        }

        /** Ghost ids this job made (they all live under "<job id>/"). */
        public List<String> ghostIds() {
            List<String> ids = new ArrayList<>();
            for (Ghost g : GhostStore.all()) if (g.id.startsWith(id + "/")) ids.add(g.id);
            return ids;
        }

        public synchronized Map<String, Object> toMap(int tail) {
            List<String> lines = new ArrayList<>(log);
            if (lines.size() > tail) lines = lines.subList(lines.size() - tail, lines.size());
            Map<String, Object> m = J.obj("job", id, "status", status, "style", style,
                    "origin", List.of(x, y, z), "cost_usd", Math.round(cost * 10000) / 10000.0,
                    "seconds", (System.currentTimeMillis() - startedMs) / 1000,
                    "ghosts", ghostIds(), "log", lines);
            if (error != null) m.put("error", error);
            if (site != null) m.put("site", site);
            if (reply != null) m.put("reply", reply);
            return m;
        }
    }

    private static volatile Job current;
    private static volatile Job last;

    public static Job current() {
        return current;
    }

    /** Latest job, running or finished (null if none yet). */
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

    /**
     * Cancels the running job: marks it stopped (so a new one can start at once) and kills the architect process with
     * its children on a short-lived worker, so the game thread never waits. Returns false when nothing was running.
     */
    public static boolean stop() {
        Job job;
        synchronized (GhostGenerate.class) {
            job = current;
        }
        if (job == null) return false;
        Process p;
        synchronized (job) {
            if (!job.status.equals("running")) return false;
            job.status = "stopped";
            job.error = null;
            p = job.proc;
        }
        if (p != null) {
            Thread t = new Thread(() -> {
                p.descendants().forEach(ProcessHandle::destroy);
                p.destroy();
                try {
                    if (!p.waitFor(2, java.util.concurrent.TimeUnit.SECONDS)) p.destroyForcibly();
                } catch (InterruptedException e) {
                    p.destroyForcibly();
                    Thread.currentThread().interrupt();
                }
            }, "mcmcp-ghost-generate-stop");
            t.setDaemon(true);
            t.start();
        }
        GhostCamera.clear();
        McMcp.LOG.info("ghost generate {} stopped by user", job.id);
        chat(ChatFormatting.YELLOW, "Generation stopped");
        return true;
    }

    // ------------------------------------------------------------------ paths and preflight

    static Path architectDir() {
        String cfg = Config.GEN_ARCHITECT_DIR.get().trim();
        if (!cfg.isEmpty()) return Path.of(cfg).toAbsolutePath().normalize();
        return FMLPaths.GAMEDIR.get().toAbsolutePath().normalize().resolveSibling("architect");
    }

    static String python(Path dir) {
        String cfg = Config.GEN_PYTHON.get().trim();
        if (!cfg.isEmpty()) return cfg;
        for (String rel : new String[] {".venv/Scripts/python.exe", "venv/Scripts/python.exe", ".venv/bin/python", "venv/bin/python"}) {
            Path p = dir.resolve(rel);
            if (Files.isRegularFile(p)) return p.toString();
        }
        return "python";
    }

    /** Returns a human-readable problem, or null when the architect can be started. Never reads .env's content. */
    public static String preflight() {
        Path dir = architectDir();
        if (!Files.isRegularFile(dir.resolve("architect.py")))
            return "architect.py not found in " + dir + ". Put the architect folder next to the mod project on this machine "
                    + "or set ghostGenerate.architectDir in config/mcmcp-common.toml.";
        if (!Files.isRegularFile(dir.resolve(".env")))
            return "missing " + dir.resolve(".env") + ": create it with one line ANTHROPIC_API_KEY=... on this machine "
                    + "(the key is never sent anywhere else).";
        String py = python(dir);
        if (!py.equals("python") && !Files.isRegularFile(Path.of(py)))
            return "python not found: " + py + ". Create the venv: python -m venv " + dir.resolve(".venv")
                    + " then pip install anthropic (see architect/README.md).";
        return null;
    }

    // ------------------------------------------------------------------ start

    /** Old entry point: site defaults (look at a block, fit to the terrain) unless x and z are both given. */
    public static Job start(String style, Integer x, Integer z, String kit, String layout) {
        return start(style, x, z, kit, layout, null, true, false);
    }

    /**
     * Starts a job. Throws ToolError with a clear message when busy or not set up. Safe to call from any thread.
     * target: look | here | x,z (default look; explicit x and z win). fit=false: old flat behaviour at x,z (or the player),
     * no survey. useArea: build in the previewed {@link GhostArea} (its survey and rectangle).
     */
    public static Job start(String style, Integer x, Integer z, String kit, String layout, String target, boolean fit,
            boolean useArea) {
        GhostArea.Area area = null;
        if (useArea) {
            area = GhostArea.current();
            if (area == null) throw new McpServer.ToolError("no area preview (or older than 15 min): run /ghost area <style> first");
            if (style == null || style.isBlank()) style = area.style;
        }
        style = style == null ? "" : style.toLowerCase(Locale.ROOT).trim();
        if (!STYLES.contains(style)) throw new McpServer.ToolError("unknown style '" + style + "'. Styles: " + String.join(", ", STYLES));
        if (kit != null && !kit.isBlank() && !KITS.contains(kit.toLowerCase(Locale.ROOT)))
            throw new McpServer.ToolError("unknown kit '" + kit + "'. Kits: " + String.join(", ", KITS));
        if (layout != null && !layout.isBlank() && !LAYOUTS.contains(layout.toLowerCase(Locale.ROOT)))
            throw new McpServer.ToolError("unknown layout '" + layout + "'. Layouts: " + String.join(", ", LAYOUTS));
        String problem = preflight();
        if (problem != null) throw new McpServer.ToolError(problem);
        synchronized (GhostGenerate.class) {
            Job c = current;
            if (c != null && c.running())
                throw new McpServer.ToolError("a generate job is already running (" + c.id + ", " + c.style
                        + "). Wait for it to finish; ghost_generate_status shows progress.");
        }

        Minecraft mc = Minecraft.getInstance();
        int[] at = GameThread.call(mc, () -> {
            var p = mc.player;
            if (p == null) throw new McpServer.ToolError("no player in a world");
            return new int[] {p.blockPosition().getX(), p.blockPosition().getY(), p.blockPosition().getZ()};
        });
        int ox = x != null ? x : at[0];
        int oz = z != null ? z : at[2];
        java.nio.file.Path surveyFile = null;
        String near = null, rect = null;
        if (area != null) {
            surveyFile = area.surveyFile;
            ox = area.x;
            oz = area.z;
            near = area.cx + "," + area.cz;
            rect = area.x + "," + area.z + "," + area.w + "," + area.d + "," + area.rot;
            if (layout == null || layout.isBlank()) layout = area.layout;
        } else if (fit) {
            Object[] r = WorldSurvey.surveyAt(target, x, z, GhostArea.SURVEY_RADIUS, GhostArea.SURVEY_STEP);
            WorldSurvey.Target t = (WorldSurvey.Target) r[0];
            try {
                surveyFile = ((WorldSurvey.Result) r[1]).writeTemp();
            } catch (IOException e) {
                throw new McpServer.ToolError("cannot write survey: " + e.getMessage());
            }
            ox = t.x();
            oz = t.z();
            near = t.x() + "," + t.z();
        }

        String id = "gen_" + style + "_" + LocalTime.now().format(DateTimeFormatter.ofPattern("HHmmss")) + "_" + SEQ.incrementAndGet();
        Job job = new Job(id, style, ox, at[1], oz);
        synchronized (GhostGenerate.class) {
            Job c = current;
            if (c != null && c.running())
                throw new McpServer.ToolError("a generate job is already running (" + c.id + ", " + c.style
                        + "). Wait for it to finish; ghost_generate_status shows progress.");
            current = job;
        }

        Path dir = architectDir();
        List<String> cmd = new ArrayList<>(List.of(python(dir), "-u", "architect.py", "-s", id, "--generate", style,
                "--x", String.valueOf(ox), "--y", String.valueOf(at[1]), "--z", String.valueOf(oz),
                "--max-cost", String.valueOf(Config.GEN_COST_CAP.get())));
        if (kit != null && !kit.isBlank()) cmd.addAll(List.of("--kit", kit.toLowerCase(Locale.ROOT)));
        if (layout != null && !layout.isBlank()) cmd.addAll(List.of("--layout", layout.toLowerCase(Locale.ROOT)));
        if (surveyFile != null) cmd.addAll(List.of("--survey", surveyFile.toString(), "--near=" + near));
        if (rect != null) cmd.addAll(List.of("--site-rect=" + rect));
        if (GhostCamera.freeCam) cmd.add("--freecam");
        ProcessBuilder pb = new ProcessBuilder(cmd).directory(dir.toFile()).redirectErrorStream(true);
        String bind = Config.CLIENT_BIND.get();
        String host = bind.equals("0.0.0.0") || bind.equals("::") ? "127.0.0.1" : bind;
        pb.environment().put("MCMCP_URL", "http://" + host + ":" + Config.CLIENT_PORT.get() + "/mcp");
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        String token = Config.CLIENT_TOKEN.get();
        if (!token.isEmpty()) pb.environment().put("MCMCP_TOKEN", token);
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
        Thread t = new Thread(() -> watch(job), "mcmcp-ghost-generate");
        t.setDaemon(true);
        t.start();
        chat(ChatFormatting.AQUA, "generate " + style + (area != null ? " in area" : surveyFile != null ? " fitted" : "") + " at " + ox + " " + oz + " (job " + id + ", cap $"
                + String.format(Locale.ROOT, "%.2f", Config.GEN_COST_CAP.get()) + ")");
        return job;
    }

    /**
     * Resolves (x, y, z) on the game thread for a free-text/image prompt: crosshair block top ("look"), player feet
     * ("here"), or explicit (x, z) with ground height when loaded.
     */
    private static int[] resolvePoint(String target, Integer x, Integer z) {
        Minecraft mc = Minecraft.getInstance();
        return GameThread.call(mc, () -> {
            var p = mc.player;
            var level = mc.level;
            if (p == null || level == null) throw new McpServer.ToolError("no player in a world");
            var feet = p.blockPosition();
            if (x != null && z != null) {
                int y = level.hasChunk(x >> 4, z >> 4)
                        ? level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z)
                        : feet.getY();
                return new int[] {x, y, z};
            }
            String t = target == null || target.isBlank() ? "look" : target.trim().toLowerCase(Locale.ROOT);
            if (t.equals("here")) return new int[] {feet.getX(), feet.getY(), feet.getZ()};
            if (t.equals("look")) {
                HitResult hit = p.pick(256.0, 1.0F, false);
                if (hit == null || hit.getType() != HitResult.Type.BLOCK) hit = mc.hitResult;
                if (hit instanceof BlockHitResult b && hit.getType() == HitResult.Type.BLOCK) {
                    var pos = b.getBlockPos();
                    return new int[] {pos.getX(), pos.getY() + 1, pos.getZ()};
                }
                return new int[] {feet.getX(), feet.getY(), feet.getZ()};
            }
            WorldSurvey.Target wt = WorldSurvey.resolve(t, null, null);
            int y = level.hasChunk(wt.x() >> 4, wt.z() >> 4)
                    ? level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, wt.x(), wt.z())
                    : feet.getY();
            return new int[] {wt.x(), y, wt.z()};
        });
    }

    /**
     * Starts a free-text / reference-image build or iterates on the latest session. Safe to call from any thread.
     */
    public static Job startPrompt(String prompt, String ref, boolean clipboardRef, Integer x, Integer z, String target,
            String kit, boolean iterate) {
        return startPrompt(prompt, ref, clipboardRef, x, z, target, kit, iterate, false);
    }

    public static Job startPrompt(String prompt, String ref, boolean clipboardRef, Integer x, Integer z, String target,
            String kit, boolean iterate, boolean force3d) {
        String text = prompt == null ? "" : prompt.trim();
        String refStr = ref == null ? "" : ref.trim();
        if (text.isEmpty() && refStr.isEmpty() && !clipboardRef)
            throw new McpServer.ToolError("give a prompt, an image ref, or enable clipboard");
        if (force3d && refStr.isEmpty() && !clipboardRef)
            throw new McpServer.ToolError("3D mesh mode needs an image ref or Clip: on");
        if (kit != null && !kit.isBlank() && !KITS.contains(kit.toLowerCase(Locale.ROOT)))
            throw new McpServer.ToolError("unknown kit '" + kit + "'. Kits: " + String.join(", ", KITS));
        String problem = preflight();
        if (problem != null) throw new McpServer.ToolError(problem);

        String id;
        int ox, oy, oz;
        if (iterate) {
            Job prev = latest();
            if (prev == null)
                throw new McpServer.ToolError("no previous session to iterate on: generate a build first");
            id = prev.id;
            ox = prev.x;
            oy = prev.y;
            oz = prev.z;
        } else {
            int[] pt = resolvePoint(target, x, z);
            ox = pt[0];
            oy = pt[1];
            oz = pt[2];
            id = "pr_" + LocalTime.now().format(DateTimeFormatter.ofPattern("HHmmss")) + "_" + SEQ.incrementAndGet();
        }

        Job job = new Job(id, iterate ? "iterate" : "prompt", ox, oy, oz);
        synchronized (GhostGenerate.class) {
            Job c = current;
            if (c != null && c.running())
                throw new McpServer.ToolError("a generate job is already running (" + c.id + ", " + c.style
                        + "). Wait for it to finish; ghost_generate_status shows progress.");
            current = job;
        }

        // 1-click Undo: remember this session's ghosts as they are before the architect iterates on them.
        if (iterate) GhostStore.snapshot(id + "/");

        Path dir = architectDir();
        List<String> cmd = new ArrayList<>(List.of(python(dir), "-u", "architect.py", "-s", id,
                iterate ? "--iterate" : "--prompt",
                "--x", String.valueOf(ox), "--y", String.valueOf(oy), "--z", String.valueOf(oz),
                "--max-cost", String.valueOf(Config.GEN_COST_CAP.get())));
        if (!iterate && kit != null && !kit.isBlank()) cmd.addAll(List.of("--kit", kit.toLowerCase(Locale.ROOT)));
        if (!refStr.isEmpty()) cmd.addAll(List.of("--ref", refStr));
        if (clipboardRef) cmd.addAll(List.of("--ref", "clipboard:"));
        if (force3d) cmd.add("--force-3d");
        if (GhostCamera.freeCam) cmd.add("--freecam");
        if (!text.isEmpty()) {
            cmd.add("--");
            cmd.add(text);
        }
        ProcessBuilder pb = new ProcessBuilder(cmd).directory(dir.toFile()).redirectErrorStream(true);
        String bind = Config.CLIENT_BIND.get();
        String host = bind.equals("0.0.0.0") || bind.equals("::") ? "127.0.0.1" : bind;
        pb.environment().put("MCMCP_URL", "http://" + host + ":" + Config.CLIENT_PORT.get() + "/mcp");
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        String token = Config.CLIENT_TOKEN.get();
        if (!token.isEmpty()) pb.environment().put("MCMCP_TOKEN", token);
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
        Thread t = new Thread(() -> watch(job), "mcmcp-ghost-generate");
        t.setDaemon(true);
        t.start();
        String tag = iterate ? "iterate " + id : "prompt at " + ox + " " + oy + " " + oz + " (job " + id + ")";
        String refNote = (clipboardRef ? " [clipboard]" : (!refStr.isEmpty() ? " [ref]" : "")) + (force3d ? " [3D]" : "");
        chat(ChatFormatting.AQUA, tag + refNote + ", cap $"
                + String.format(Locale.ROOT, "%.2f", Config.GEN_COST_CAP.get()));
        return job;
    }

    private static void watch(Job job) {
        Process p = job.proc;
        Thread killer = new Thread(() -> {
            try {
                if (!p.waitFor(MAX_MINUTES, java.util.concurrent.TimeUnit.MINUTES)) {
                    synchronized (job) { if (job.status.equals("running")) job.error = "timed out after " + MAX_MINUTES + " min"; }
                    p.destroyForcibly();
                }
            } catch (InterruptedException ignored) {
            }
        }, "mcmcp-ghost-generate-timeout");
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
            if (!job.status.equals("stopped")) {
                if (job.error == null && code != 0) job.error = "architect exited with code " + code;
                job.status = job.error == null ? "done" : "failed";
            }
        }
        finish(job);
    }

    private static void finish(Job job) {
        GhostCamera.clear();
        synchronized (GhostGenerate.class) {
            last = job;
            if (current == job) current = null;
        }
        String cost = String.format(Locale.ROOT, "$%.4f", job.cost);
        boolean ok, stopped;
        String err;
        synchronized (job) {
            ok = job.status.equals("done");
            stopped = job.status.equals("stopped");
            err = job.error;
        }
        if (stopped) chat(ChatFormatting.GRAY, "generate stopped at " + cost + "; ghosts placed so far stay (/ghost clear " + job.id + "/)");
        else if (ok) chat(ChatFormatting.GREEN, "generate done: " + job.ghostIds().size() + " ghosts under " + job.id + "/, cost " + cost
                + ". /ghost list, /ghost hide, /ghost clear " + job.id + "/");
        else chat(ChatFormatting.RED, "generate failed: " + err + " (cost " + cost + "). ghost_generate_status job=" + job.id + " has the log.");
        McMcp.LOG.info("ghost generate {} {} cost {}", job.id, stopped ? "stopped" : ok ? "done" : "failed", cost);
    }

    /** Chat line in this client only. */
    public static void chat(ChatFormatting color, String text) {
        Minecraft mc = Minecraft.getInstance();
        mc.execute(() -> mc.gui.getChat().addMessage(Component.literal("[Ghost] ").withStyle(ChatFormatting.GOLD)
                .append(Component.literal(text).withStyle(color))));
    }

    // ------------------------------------------------------------------ MCP tools

    public static void registerTools(McpServer mcp) {
        mcp.add(new Tool("ghost_generate",
                "Start the LLM architect to design a themed base as ghosts (async: returns a job id at once; poll ghost_generate_status). "
                        + "style: steampunk | hextech | gothic | station_white | solarpunk. WORLD-AWARE by default: surveys the terrain around "
                        + "target (look = the block the crosshair is on (default) | here | x,z; explicit x,z also count), picks the best site "
                        + "(rotation, smaller layout when tight), adds foundations/terraces and lists trees to clear. fit=false skips the survey "
                        + "(old flat behaviour with x,z = site min corner, default the player). use_area=true builds in the area ghost_area "
                        + "previewed (no new survey). kit: optional palette kit; layout: spine | radial | cloister | linear | terraces. "
                        + "Ghosts land under '<job>/'. One job at a time. Costs real API money (capped per job by config ghostGenerate.costCapUsd, "
                        + "default $0.15). Needs architect/.env and a python venv on the machine running this client.",
                J.Schema.of().enumOf("style", "base style", STYLES.toArray(String[]::new)).integer("x", "centre x of the survey (default: target)")
                        .integer("z", "centre z of the survey").str("kit", "palette kit, default = style")
                        .enumOf("layout", "campus layout, default per style / fitted", LAYOUTS.toArray(String[]::new))
                        .str("target", "look | here | x,z (default look)").bool("fit", "survey and fit the site (default true)")
                        .bool("use_area", "build in the previewed ghost_area (default false)").required("style").build(),
                false, a -> {
                    Job j = start(J.str(a, "style", null), a.has("x") ? J.i(a, "x", 0) : null, a.has("z") ? J.i(a, "z", 0) : null,
                            J.str(a, "kit", null), J.str(a, "layout", null), J.str(a, "target", null), J.b(a, "fit", true),
                            J.b(a, "use_area", false));
                    return J.obj("job", j.id, "status", "running", "style", j.style, "origin", List.of(j.x, j.y, j.z),
                            "cost_cap_usd", Config.GEN_COST_CAP.get(), "hint", "poll ghost_generate_status with this job id");
                }));
        mcp.add(new Tool("ghost_prompt",
                "Build a focused structure or component from a free-text prompt and/or reference image (or iterate on the latest session). "
                        + "Async: returns a job id; poll ghost_generate_status. ref: image path, URL, YouTube link, or 'clipboard:'. "
                        + "clipboard=true reads the clipboard image. iterate=true continues the latest session to tweak existing ghosts.",
                J.Schema.of().str("prompt", "what to build or change").str("ref", "optional image/video path or URL")
                        .bool("clipboard", "attach image from clipboard (default false)")
                        .integer("x", "target x").integer("z", "target z")
                        .str("target", "look | here | x,z (default look)").str("kit", "optional palette kit")
                        .bool("iterate", "continue latest session (default false)")
                        .bool("force_3d", "force Hunyuan3D photo->voxel via image_to_3d (default false)").build(),
                false, a -> {
                    Job j = startPrompt(J.str(a, "prompt", null), J.str(a, "ref", null), J.b(a, "clipboard", false),
                            a.has("x") ? J.i(a, "x", 0) : null, a.has("z") ? J.i(a, "z", 0) : null,
                            J.str(a, "target", null), J.str(a, "kit", null), J.b(a, "iterate", false),
                            J.b(a, "force_3d", false));
                    return J.obj("job", j.id, "status", "running", "mode", j.style, "origin", List.of(j.x, j.y, j.z),
                            "cost_cap_usd", Config.GEN_COST_CAP.get(), "hint", "poll ghost_generate_status with this job id");
                }));
        mcp.add(new Tool("ghost_generate_status",
                "Status of a ghost_generate job: running | done | failed | stopped, ghost ids so far, API cost so far, last log lines. "
                        + "job omitted = the latest job.",
                J.Schema.of().str("job", "job id from ghost_generate").integer("lines", "log lines to return (default 12)").build(),
                true, a -> {
                    String id = J.str(a, "job", null);
                    Job j = id == null ? latest() : byId(id);
                    if (j == null) throw new McpServer.ToolError(id == null ? "no generate job yet" : "unknown job '" + id
                            + "' (only the current and the last job are kept)");
                    return j.toMap(Math.max(1, Math.min(40, J.i(a, "lines", 12))));
                }));
    }
}
