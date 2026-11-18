package dev.watdafawx.mcmcp.ghost;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import com.google.gson.Gson;

import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.chunk.status.ChunkStatus;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;

import dev.watdafawx.mcmcp.GameThread;
import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;

/**
 * Terrain survey of the CLIENT level (never loads chunks: unloaded columns come back as unknown). A square grid of
 * columns around a centre: surface y per cell (a MOTION_BLOCKING scan that skips leaves, logs, plants and snow layers
 * down to real ground; water cells report the bed), a one-char flag per cell and summary numbers.
 *
 * <p>Wire format (also what architect/site.py reads): {@code y} = one string per z-row (north to south), two base-36
 * chars per cell, x west to east: value = y + 128, {@code ??} = unknown. {@code f} = one string per row, one char per
 * cell: {@code .} land, {@code w} water, {@code l} lava, {@code t} tree (log/leaves above the ground), {@code s}
 * snow, {@code ?} unknown (unloaded). Cell (i, j) is the column at (x0 + i*step, z0 + j*step) and stands for the
 * step x step blocks starting there.
 */
public final class WorldSurvey {
    private WorldSurvey() {}

    public static final int UNKNOWN = Integer.MIN_VALUE;
    private static final int YOFF = 128;
    private static final int MAX_CELLS = 24_000;
    private static final Gson GSON = new Gson();

    public static final String FORMAT = "y[j] = row at z0+j*step, 2 base-36 chars per cell (x west->east), value = y+128, '??' unknown; "
            + "f[j] = 1 char per cell: . land, w water (y = bed), l lava, t tree, s snow, ? unknown. Cell (i,j) = column (x0+i*step, z0+j*step).";

    /** What a survey is centred on. */
    public record Target(int x, int z, String source) {}

    public static final class Result {
        public int x0, z0, step, w, h, cx, cz, radius;
        public int[][] y;
        public char[][] f;
        public String biome = "?", dim = "?";
        public final Map<String, Object> stats = new LinkedHashMap<>();

        /** Ground y at a block column (nearest cell); UNKNOWN outside / unloaded. */
        public int heightAt(int bx, int bz) {
            int i = Math.floorDiv(bx - x0, step), j = Math.floorDiv(bz - z0, step);
            return i < 0 || j < 0 || i >= w || j >= h ? UNKNOWN : y[j][i];
        }

        public Map<String, Object> toMap() {
            List<String> ys = new ArrayList<>(), fs = new ArrayList<>();
            for (int j = 0; j < h; j++) {
                StringBuilder sy = new StringBuilder(w * 2);
                for (int i = 0; i < w; i++) {
                    if (y[j][i] == UNKNOWN) sy.append("??");
                    else {
                        String s = Integer.toString(Math.max(0, Math.min(1295, y[j][i] + YOFF)), 36);
                        sy.append(s.length() < 2 ? "0" + s : s);
                    }
                }
                ys.add(sy.toString());
                fs.add(new String(f[j]));
            }
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("v", 1);
            m.put("x0", x0); m.put("z0", z0); m.put("step", step); m.put("w", w); m.put("h", h);
            m.put("center", List.of(cx, cz)); m.put("radius", radius);
            m.put("dim", dim); m.put("biome", biome);
            m.putAll(stats);
            m.put("format", FORMAT);
            m.put("y", ys);
            m.put("f", fs);
            return m;
        }

        /** Writes the survey JSON to a temp file (deleted on exit) and returns it. */
        public Path writeTemp() throws IOException {
            Path p = Files.createTempFile("mcmcp-survey-", ".json");
            Files.writeString(p, GSON.toJson(toMap()), StandardCharsets.UTF_8);
            p.toFile().deleteOnExit();
            return p;
        }
    }

    // ------------------------------------------------------------------ target

    /** Game thread. target: "look" (default) | "here" | "x,z". Explicit x and z win. Falls back to the player's feet. */
    public static Target resolve(String target, Integer x, Integer z) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null) throw new McpServer.ToolError("not in a world");
        if (x != null && z != null) return new Target(x, z, "xz");
        String t = target == null || target.isBlank() ? "look" : target.trim().toLowerCase(Locale.ROOT);
        var feet = mc.player.blockPosition();
        if (t.equals("here")) return new Target(feet.getX(), feet.getZ(), "here");
        if (t.equals("look")) {
            HitResult hit = mc.player.pick(256.0, 1.0F, false);
            if (hit == null || hit.getType() != HitResult.Type.BLOCK) hit = mc.hitResult;
            if (hit instanceof BlockHitResult b && hit.getType() == HitResult.Type.BLOCK)
                return new Target(b.getBlockPos().getX(), b.getBlockPos().getZ(), "look");
            return new Target(feet.getX(), feet.getZ(), "here (not looking at a block)");
        }
        String[] p = t.split("[,\\s]+");
        if (p.length == 2) {
            try {
                return new Target(Integer.parseInt(p[0]), Integer.parseInt(p[1]), "xz");
            } catch (NumberFormatException ignored) {
            }
        }
        throw new McpServer.ToolError("bad target '" + target + "': use look | here | x,z");
    }

    // ------------------------------------------------------------------ survey

    /** Game thread. */
    public static Result run(int cx, int cz, int radius, int step) {
        Minecraft mc = Minecraft.getInstance();
        ClientLevel level = mc.level;
        if (level == null) throw new McpServer.ToolError("not in a world");
        radius = Math.max(8, Math.min(160, radius));
        step = Math.max(1, Math.min(8, step));
        int x0 = Math.floorDiv(cx - radius, step) * step, z0 = Math.floorDiv(cz - radius, step) * step;
        int n = (2 * radius) / step + 1;
        if ((long) n * n > MAX_CELLS)
            throw new McpServer.ToolError("too many cells (" + n * n + " > " + MAX_CELLS + "): raise step or lower radius");
        Result r = new Result();
        r.x0 = x0; r.z0 = z0; r.step = step; r.w = n; r.h = n; r.cx = cx; r.cz = cz; r.radius = radius;
        r.dim = level.dimension().location().toString();
        r.y = new int[n][n];
        r.f = new char[n][n];
        Map<Long, LevelChunk> chunks = new HashMap<>();
        Map<String, Integer> ground = new HashMap<>();
        BlockPos.MutableBlockPos p = new BlockPos.MutableBlockPos();
        int minY = level.getMinBuildHeight();
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                int x = x0 + i * step, z = z0 + j * step;
                long key = ((long) (x >> 4) << 32) ^ ((z >> 4) & 0xffffffffL);
                LevelChunk ch = chunks.computeIfAbsent(key,
                        k -> level.getChunkSource().getChunk(x >> 4, z >> 4, ChunkStatus.FULL, false));
                r.y[j][i] = UNKNOWN;
                r.f[j][i] = '?';
                if (ch == null) continue;
                // not the heightmap: client heightmaps go stale after block updates. Scan from the top of the highest section.
                if (ch.getHighestFilledSectionIndex() < 0) continue; // empty chunk: unknown
                int hm = Math.min(level.getMaxBuildHeight(), ch.getHighestSectionPosition() + 16);
                boolean water = false, lava = false, tree = false, snow = false;
                String gname = null;
                int y = hm - 1;
                for (; y >= minY; y--) {
                    BlockState st = ch.getBlockState(p.set(x, y, z));
                    if (st.isAir()) continue;
                    if (!st.getFluidState().isEmpty()) {
                        if (st.getFluidState().is(FluidTags.LAVA)) lava = true;
                        else water = true;
                        continue;
                    }
                    if (st.is(BlockTags.LEAVES) || st.is(BlockTags.LOGS)) { tree = true; continue; }
                    if (st.is(Blocks.SNOW)) { snow = true; continue; }
                    if (st.getCollisionShape(level, p).isEmpty()) continue;
                    gname = BuiltInRegistries.BLOCK.getKey(st.getBlock()).toString();
                    break;
                }
                if (gname == null) continue;
                if (gname.contains("snow")) snow = true;
                r.y[j][i] = y;
                r.f[j][i] = lava ? 'l' : water ? 'w' : tree ? 't' : snow ? 's' : '.';
                if (!water && !lava) ground.merge(gname, 1, Integer::sum);
            }
        }
        stats(r, ground);
        int cy = r.heightAt(cx, cz);
        if (cy == UNKNOWN) cy = mc.player != null ? mc.player.blockPosition().getY() : 64;
        try {
            if (chunks.getOrDefault(((long) (cx >> 4) << 32) ^ ((cz >> 4) & 0xffffffffL), null) != null
                    || level.getChunkSource().getChunk(cx >> 4, cz >> 4, ChunkStatus.FULL, false) != null)
                r.biome = level.getBiome(new BlockPos(cx, cy, cz)).unwrapKey().map(k -> k.location().toString()).orElse("?");
        } catch (RuntimeException ignored) {
        }
        return r;
    }

    private static void stats(Result r, Map<String, Integer> ground) {
        int total = r.w * r.h, water = 0, lava = 0, tree = 0, snow = 0, unk = 0;
        List<Integer> land = new ArrayList<>();
        for (int j = 0; j < r.h; j++)
            for (int i = 0; i < r.w; i++) {
                char c = r.f[j][i];
                switch (c) {
                    case '?' -> unk++;
                    case 'w' -> water++;
                    case 'l' -> lava++;
                    case 't' -> { tree++; land.add(r.y[j][i]); }
                    case 's' -> { snow++; land.add(r.y[j][i]); }
                    default -> land.add(r.y[j][i]);
                }
            }
        Map<String, Object> s = r.stats;
        if (!land.isEmpty()) {
            int[] a = land.stream().mapToInt(Integer::intValue).sorted().toArray();
            s.put("ymin", a[0]);
            s.put("ymax", a[a.length - 1]);
            s.put("ymed", a[a.length / 2]);
        }
        s.put("water_pct", pct(water, total));
        s.put("lava_pct", pct(lava, total));
        s.put("tree_pct", pct(tree, total));
        s.put("snow_pct", pct(snow, total));
        s.put("unknown_pct", pct(unk, total));
        // slope per block to the steepest 4-neighbour, over land cells
        List<Double> sl = new ArrayList<>();
        int[][] d4 = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int j = 0; j < r.h; j++)
            for (int i = 0; i < r.w; i++) {
                char c = r.f[j][i];
                if (c == '?' || c == 'w' || c == 'l') continue;
                double best = 0;
                for (int[] d : d4) {
                    int a = i + d[0], b = j + d[1];
                    if (a < 0 || b < 0 || a >= r.w || b >= r.h || r.y[b][a] == UNKNOWN) continue;
                    best = Math.max(best, Math.abs(r.y[b][a] - r.y[j][i]) / (double) r.step);
                }
                sl.add(best);
            }
        double[] sa = sl.stream().mapToDouble(Double::doubleValue).sorted().toArray();
        double mean = Arrays.stream(sa).average().orElse(0);
        s.put("slope", J.obj("mean", J.r2(mean), "p90", J.r2(sa.length == 0 ? 0 : sa[(int) (sa.length * 0.9)]),
                "max", J.r2(sa.length == 0 ? 0 : sa[sa.length - 1]), "unit", "blocks of height per block, steepest neighbour"));
        List<Object> g = new ArrayList<>();
        int landN = Math.max(1, land.size());
        ground.entrySet().stream().sorted((e1, e2) -> e2.getValue() - e1.getValue()).limit(3)
                .forEach(e -> g.add(J.obj("block", e.getKey(), "pct", pct(e.getValue(), landN))));
        s.put("ground", g);
        s.put("dominant_ground", g.isEmpty() ? "?" : ((Map<?, ?>) g.get(0)).get("block"));
    }

    private static double pct(int a, int b) {
        return Math.round(1000.0 * a / Math.max(1, b)) / 10.0;
    }

    /** Any thread: resolves the target and surveys on the game thread. Returns {target, result}. */
    public static Object[] surveyAt(String target, Integer x, Integer z, int radius, int step) {
        Minecraft mc = Minecraft.getInstance();
        return GameThread.call(mc, () -> {
            Target t = resolve(target, x, z);
            return new Object[] {t, run(t.x(), t.z(), radius, step)};
        }, 30);
    }

    // ------------------------------------------------------------------ MCP tool

    public static void registerTools(McpServer mcp) {
        mcp.add(new Tool("world_survey",
                "Terrain survey of the loaded client world around a point (read-only, never loads chunks; unloaded columns = unknown). "
                        + "x,z default: the block the crosshair is on (up to 256 blocks away), else the player's feet; or target=look|here|x,z. "
                        + "Returns a compact heightmap grid plus summary: ymin/ymax/ymed, water/lava/tree/snow/unknown %, slope stats, "
                        + "biome, dominant ground block. Grid format: " + FORMAT,
                J.Schema.of().integer("x", "centre x (default: looked-at block)").integer("z", "centre z")
                        .integer("radius", "blocks from the centre, 8..160, default 48")
                        .integer("step", "blocks per cell, 1..8, default 2").str("target", "look | here | x,z (default look)")
                        .bool("grid", "false = summary only, without the y/f grids (default true)").build(),
                true, a -> {
                    Integer x = a.has("x") ? J.i(a, "x", 0) : null, z = a.has("z") ? J.i(a, "z", 0) : null;
                    if ((x == null) != (z == null)) throw new McpServer.ToolError("give x and z together, or neither");
                    Object[] r = surveyAt(J.str(a, "target", null), x, z, J.i(a, "radius", 48), J.i(a, "step", 2));
                    Target t = (Target) r[0];
                    Map<String, Object> m = ((Result) r[1]).toMap();
                    m.put("target", t.source());
                    if (!J.b(a, "grid", true)) {
                        m.remove("y");
                        m.remove("f");
                    }
                    return m;
                }));
    }
}
