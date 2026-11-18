package dev.watdafawx.mcmcp.ghost;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;

import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;

/**
 * The area preview: where a generated base would go. A survey of the looked-at (or given) spot is scored by
 * architect/site.py (deterministic, no LLM, no API cost) and shown as a thin outline ghost with corner posts, lime =
 * fits, yellow = needs foundations/terracing, red = blocked/water. The accepted area is what ghost_generate builds in.
 */
public final class GhostArea {
    private GhostArea() {}

    public static final String GHOST_ID = "area/preview";
    public static final int SURVEY_RADIUS = 72, SURVEY_STEP = 3;
    private static final long MAX_AGE_MS = 15 * 60 * 1000L;

    /** One previewed area; immutable, replaced on every move/rotate. */
    public static final class Area {
        public final String style, layout, cls, summary, target;
        public final int x, z, w, d, rot, ref, fit, wings, cx, cz;
        public final WorldSurvey.Result survey;
        public final Path surveyFile;
        final long madeMs = System.currentTimeMillis();

        Area(String style, String target, WorldSurvey.Result survey, Path surveyFile, JsonObject p, String layout, int wings) {
            this.style = style;
            this.target = target;
            this.survey = survey;
            this.surveyFile = surveyFile;
            this.x = p.get("x").getAsInt();
            this.z = p.get("z").getAsInt();
            this.w = p.get("w").getAsInt();
            this.d = p.get("d").getAsInt();
            this.rot = p.get("rot").getAsInt();
            this.ref = p.get("ref").getAsInt();
            this.fit = p.get("fit").getAsInt();
            this.cls = p.get("class").getAsString();
            this.layout = layout;
            this.wings = wings;
            this.cx = survey.cx;
            this.cz = survey.cz;
            this.summary = p.has("summary") ? p.get("summary").getAsString() : "";
        }

        /** Chat line: fit, platform, fill/cut, obstacles, layout. */
        public String line() {
            String s = cls + " " + fit + "/100, " + w + "x" + d + " @" + x + "," + z + " rot" + rot + ", y" + ref;
            if (cutFill != null) s += ", " + cutFill;
            if (obstacles != null) s += ", " + obstacles;
            return s + (layout != null ? ", " + layout + " x" + wings : "");
        }

        String cutFill, obstacles;

        public Map<String, Object> toMap() {
            return J.obj("style", style, "class", cls, "fit", fit, "x", x, "z", z, "w", w, "d", d, "rot", rot,
                    "platform_y", ref, "layout", layout, "wings", wings, "target", target, "summary", summary,
                    "chat", line(), "survey_file", surveyFile.toString());
        }
    }

    private static volatile Area current;

    /** The previewed area, or null (also null when it is older than 15 minutes). */
    public static Area current() {
        Area a = current;
        return a != null && System.currentTimeMillis() - a.madeMs < MAX_AGE_MS ? a : null;
    }

    // ------------------------------------------------------------------ site.py

    static String problem() {
        Path dir = GhostGenerate.architectDir();
        if (!java.nio.file.Files.isRegularFile(dir.resolve("site.py")))
            return "site.py not found in " + dir + " (architect folder missing on this machine)";
        String py = GhostGenerate.python(dir);
        if (!py.equals("python") && !java.nio.file.Files.isRegularFile(Path.of(py))) return "python not found: " + py;
        return null;
    }

    /** Runs architect/site.py <args> and returns its JSON line. Blocking: call off the game thread. */
    static JsonObject site(List<String> args) {
        String pr = problem();
        if (pr != null) throw new McpServer.ToolError(pr);
        Path dir = GhostGenerate.architectDir();
        List<String> cmd = new ArrayList<>(List.of(GhostGenerate.python(dir), "-u", "site.py"));
        cmd.addAll(args);
        try {
            ProcessBuilder pb = new ProcessBuilder(cmd).directory(dir.toFile()).redirectErrorStream(true);
            pb.environment().put("PYTHONIOENCODING", "utf-8");
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            if (!p.waitFor(60, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                throw new McpServer.ToolError("site.py timed out");
            }
            for (String line : out.split("\\R")) {
                if (line.startsWith("{")) return JsonParser.parseString(line).getAsJsonObject();
            }
            throw new McpServer.ToolError("site.py failed: " + out.strip().replaceAll("\\s+", " "));
        } catch (IOException | InterruptedException e) {
            throw new McpServer.ToolError("site.py failed: " + e.getMessage());
        }
    }

    private static Area fromPlan(String style, String target, WorldSurvey.Result sv, Path file, JsonObject p) {
        String layout = p.has("layout") ? p.get("layout").getAsString() : null;
        int wings = p.has("wings") ? p.get("wings").getAsInt() : 0;
        Area a = new Area(style, target, sv, file, p, layout, wings);
        int fill = p.get("fill").getAsInt(), cut = p.get("cut").getAsInt();
        if (fill > 0 || cut > 0) a.cutFill = "fill~" + fill + " cut~" + cut;
        int trees = p.get("tree_cells").getAsInt();
        double water = p.get("water_pct").getAsDouble();
        List<String> ob = new ArrayList<>();
        if (trees > 0) ob.add(trees + " tree blocks");
        if (water > 0) ob.add(water + "% water");
        if (p.get("unknown_pct").getAsDouble() > 0) ob.add(p.get("unknown_pct").getAsDouble() + "% unloaded");
        if (!ob.isEmpty()) a.obstacles = String.join(", ", ob);
        return a;
    }

    // ------------------------------------------------------------------ preview

    /** Survey + score + draw. Blocking (call off the game thread). target: look | here | x,z; layout optional. */
    public static Area preview(String style, String target, Integer x, Integer z, String layout) {
        style = style == null ? "" : style.toLowerCase(Locale.ROOT).trim();
        if (!GhostGenerate.STYLES.contains(style))
            throw new McpServer.ToolError("unknown style '" + style + "'. Styles: " + String.join(", ", GhostGenerate.STYLES));
        Object[] r = WorldSurvey.surveyAt(target, x, z, SURVEY_RADIUS, SURVEY_STEP);
        WorldSurvey.Target t = (WorldSurvey.Target) r[0];
        WorldSurvey.Result sv = (WorldSurvey.Result) r[1];
        Path file;
        try {
            file = sv.writeTemp();
        } catch (IOException e) {
            throw new McpServer.ToolError("cannot write survey: " + e.getMessage());
        }
        List<String> args = new ArrayList<>(List.of("plan", "--survey", file.toString(), "--style", style, "--near=" + t.x() + "," + t.z()));
        if (layout != null && !layout.isBlank()) args.addAll(List.of("--layout", layout.toLowerCase(Locale.ROOT)));
        Area a = fromPlan(style, t.source(), sv, file, site(args));
        current = a;
        render(a);
        return a;
    }

    /** Re-score the same survey with the rectangle moved / rotated. dx,dz in blocks; quarterTurns 0 or 1. */
    public static Area adjust(int dx, int dz, int quarterTurns) {
        Area o = current();
        if (o == null) throw new McpServer.ToolError("no area preview yet: /ghost area <style>");
        int nx = o.x + dx, nz = o.z + dz, nw = o.w, nd = o.d, rot = o.rot;
        if (quarterTurns % 2 != 0) {
            int cx = o.x + o.w / 2, cz = o.z + o.d / 2;
            nw = o.d;
            nd = o.w;
            nx = cx - nw / 2 + dx;
            nz = cz - nd / 2 + dz;
            rot = (rot + 90 * quarterTurns) % 360;
        }
        List<String> args = List.of("eval", "--survey", o.surveyFile.toString(), "--x=" + nx, "--z=" + nz,
                "--w", String.valueOf(nw), "--d", String.valueOf(nd), "--rot", String.valueOf(rot), "--near=" + o.cx + "," + o.cz);
        JsonObject p = site(args);
        JsonObject merged = p;
        Area a = fromPlan(o.style, o.target, o.survey, o.surveyFile, merged);
        // keep the chosen layout and wing count: they came from the plan, not the rectangle
        Area b = new Area(o.style, o.target, o.survey, o.surveyFile, merged, o.layout, o.wings);
        b.cutFill = a.cutFill;
        b.obstacles = a.obstacles;
        current = b;
        render(b);
        return b;
    }

    public static boolean clear() {
        boolean had = current != null;
        current = null;
        try {
            GhostStore.remove(GHOST_ID);
        } catch (RuntimeException ignored) {
        }
        return had;
    }

    /** Outline hugging the ground, dotted level ring, corner posts; all coloured by fit. */
    static void render(Area a) {
        String col = switch (a.cls) {
            case "lime" -> "minecraft:lime_concrete";
            case "yellow" -> "minecraft:yellow_concrete";
            default -> "minecraft:red_concrete";
        };
        BlockState c = GhostStore.parseState(col), ring = GhostStore.parseState("minecraft:white_concrete");
        Map<BlockPos, BlockState> m = new LinkedHashMap<>();
        BlockPos origin = new BlockPos(a.x, a.ref, a.z);
        for (int i = 0; i < a.w; i++) {
            for (int k : new int[] {0, a.d - 1}) edge(a, m, c, ring, i, k);
        }
        for (int k = 1; k < a.d - 1; k++) {
            for (int i : new int[] {0, a.w - 1}) edge(a, m, c, ring, i, k);
        }
        for (int[] q : new int[][] {{0, 0}, {a.w - 1, 0}, {0, a.d - 1}, {a.w - 1, a.d - 1}})
            for (int y = 1; y <= 8; y++) m.put(new BlockPos(q[0], y, q[1]), c);
        Ghost g = GhostStore.replaceBlocks(GHOST_ID, m, origin, Map.of("kind", "area", "class", a.cls, "style", a.style));
        synchronized (GhostStore.LOCK) {
            g.alpha = 0.85f;
            g.visible = true;
        }
        GhostStore.save(g);
    }

    private static void edge(Area a, Map<BlockPos, BlockState> m, BlockState c, BlockState ring, int i, int k) {
        int gy = a.survey.heightAt(a.x + i, a.z + k);
        int y = (gy == WorldSurvey.UNKNOWN ? a.ref : gy) + 1 - a.ref; // local to origin y = ref
        m.put(new BlockPos(i, y, k), c);
        if ((i + k) % 4 == 0) m.put(new BlockPos(i, 1, k), ring); // dotted platform level
    }

    // ------------------------------------------------------------------ MCP tool

    public static void registerTools(McpServer mcp) {
        mcp.add(new Tool("ghost_area",
                "Preview where a generated base would go, WITHOUT the LLM (no API cost): surveys the terrain, scores it (architect/site.py), "
                        + "and shows a thin outline ghost 'area/preview' with corner posts coloured by fit: lime = fits, yellow = needs "
                        + "foundations/terracing, red = blocked/water. action: preview (default) | move (dx,dz) | rotate | clear | status. "
                        + "target: look (crosshair, default) | here | x,z. Then ghost_generate with use_area=true builds in it.",
                J.Schema.of().enumOf("action", "preview | move | rotate | clear | status", "preview", "move", "rotate", "clear", "status")
                        .enumOf("style", "base style (preview only)", GhostGenerate.STYLES.toArray(String[]::new))
                        .str("target", "look | here | x,z").integer("x", "centre x").integer("z", "centre z")
                        .enumOf("layout", "force a layout instead of the fitted one", GhostGenerate.LAYOUTS.toArray(String[]::new))
                        .integer("dx", "move: blocks east").integer("dz", "move: blocks south").build(),
                false, a -> {
                    String act = J.str(a, "action", "preview");
                    switch (act) {
                        case "clear":
                            return J.obj("cleared", clear());
                        case "status": {
                            Area cur = current();
                            return cur == null ? J.obj("area", null) : cur.toMap();
                        }
                        case "move":
                            return adjust(J.i(a, "dx", 0), J.i(a, "dz", 0), 0).toMap();
                        case "rotate":
                            return adjust(J.i(a, "dx", 0), J.i(a, "dz", 0), 1).toMap();
                        default: {
                            Integer x = a.has("x") ? J.i(a, "x", 0) : null, z = a.has("z") ? J.i(a, "z", 0) : null;
                            if ((x == null) != (z == null)) throw new McpServer.ToolError("give x and z together, or neither");
                            String style = J.str(a, "style", null);
                            if (style == null) throw new McpServer.ToolError("style is required for a preview");
                            return preview(style, J.str(a, "target", null), x, z, J.str(a, "layout", null)).toMap();
                        }
                    }
                }));
    }

    /** Chat helper used by the slash commands: runs the body on a worker thread, reports errors in chat. */
    public static void async(String name, java.util.function.Supplier<Area> body) {
        Thread t = new Thread(() -> {
            try {
                Area a = body.get();
                if (a != null) GhostGenerate.chat(colour(a.cls), "area " + a.line());
            } catch (RuntimeException e) {
                GhostGenerate.chat(ChatFormatting.RED, String.valueOf(e.getMessage()));
            }
        }, "mcmcp-ghost-area-" + name);
        t.setDaemon(true);
        t.start();
    }

    static ChatFormatting colour(String cls) {
        return switch (cls) {
            case "lime" -> ChatFormatting.GREEN;
            case "yellow" -> ChatFormatting.YELLOW;
            default -> ChatFormatting.RED;
        };
    }
}
