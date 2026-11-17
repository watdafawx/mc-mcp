package dev.watdafawx.mcmcp.ghost;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.fml.loading.FMLPaths;

import dev.watdafawx.mcmcp.mcp.McpServer.ToolError;

/**
 * Reads a Sponge schematic ({@code .schem}, v2 and v3) or a vanilla structure ({@code .nbt}) into block states at
 * local positions (min corner = 0,0,0). The mirror of {@link SchematicWriter}. Name lookup follows Shapewright's
 * SchematicLibrary (game-dir relative, first match wins) without depending on it.
 */
public final class GhostImport {
    private GhostImport() {}

    /** Search folders, game-dir relative, in priority order. */
    static final List<String> DIRS = List.of("config/shapewright/schematics", "schematics", "config/worldedit/schematics",
            "world/generated/minecraft/structures");
    private static final List<String> EXTS = List.of(".schem", ".nbt");

    public record Loaded(Map<BlockPos, BlockState> blocks, int[] size, Path path, int skipped, Set<String> unknown) {}

    /** Bare name or path to a file. Throws ToolError when nothing matches. */
    public static Path resolve(String nameOrPath) {
        Path game = FMLPaths.GAMEDIR.get();
        String s = nameOrPath.trim();
        List<Path> tried = new ArrayList<>();
        boolean bare = !s.contains("/") && !s.contains("\\") && !s.contains(":");
        if (!bare) {
            Path p = game.resolve(s); // absolute paths resolve to themselves
            for (Path c : withExts(p)) { tried.add(c); if (Files.isRegularFile(c)) return c; }
        } else {
            for (String d : DIRS)
                for (Path c : withExts(game.resolve(d).resolve(s))) { tried.add(c); if (Files.isRegularFile(c)) return c; }
        }
        throw new ToolError("schematic '" + nameOrPath + "' not found. Looked in: " + DIRS + " (game dir relative); try ghost_import with a full path");
    }

    private static List<Path> withExts(Path base) {
        List<Path> l = new ArrayList<>();
        String n = base.getFileName().toString().toLowerCase(Locale.ROOT);
        if (n.endsWith(".schem") || n.endsWith(".nbt")) l.add(base);
        else for (String e : EXTS) l.add(base.resolveSibling(base.getFileName() + e));
        return l;
    }

    /** Stems of every importable file in the search folders (for tab completion), de-duplicated, sorted. */
    public static List<String> available() {
        Path game = FMLPaths.GAMEDIR.get();
        Set<String> out = new LinkedHashSet<>();
        for (String d : DIRS) {
            Path dir = game.resolve(d);
            if (!Files.isDirectory(dir)) continue;
            try (Stream<Path> s = Files.list(dir)) {
                s.map(p -> p.getFileName().toString())
                        .filter(n -> n.endsWith(".schem") || n.endsWith(".nbt"))
                        .map(n -> n.substring(0, n.lastIndexOf('.')))
                        .forEach(out::add);
            } catch (IOException ignored) {
                // unreadable folder: skip
            }
        }
        List<String> l = new ArrayList<>(out);
        l.sort(String.CASE_INSENSITIVE_ORDER);
        return l;
    }

    public static Loaded load(String nameOrPath) {
        Path p = resolve(nameOrPath);
        CompoundTag root;
        try {
            root = NbtIo.readCompressed(p, NbtAccounter.unlimitedHeap());
        } catch (IOException e) {
            throw new ToolError("could not read " + p + ": " + e.getMessage());
        }
        Map<BlockPos, BlockState> blocks = new LinkedHashMap<>();
        Set<String> unknown = new LinkedHashSet<>();
        int[] skipped = {0};
        int[] size;
        if (root.contains("palette", Tag.TAG_LIST) && root.contains("blocks", Tag.TAG_LIST)) {
            size = structure(root, blocks, unknown, skipped);
        } else {
            CompoundTag sch = root.contains("Schematic", Tag.TAG_COMPOUND) ? root.getCompound("Schematic") : root;
            size = sponge(sch, blocks, unknown, skipped);
        }
        return new Loaded(blocks, size, p, skipped[0], unknown);
    }

    private static BlockState state(String s, Set<String> unknown, int[] skipped) {
        try {
            return GhostStore.parseState(s);
        } catch (IllegalArgumentException e) {
            unknown.add(s);
            skipped[0]++;
            return null;
        }
    }

    // Sponge v2: root has Palette/BlockData; v3: Blocks{Palette,Data}. Index (y * length + z) * width + x, varint data.
    private static int[] sponge(CompoundTag sch, Map<BlockPos, BlockState> out, Set<String> unknown, int[] skipped) {
        int w = sch.getShort("Width") & 0xFFFF, h = sch.getShort("Height") & 0xFFFF, l = sch.getShort("Length") & 0xFFFF;
        CompoundTag palTag;
        byte[] data;
        if (sch.contains("Blocks", Tag.TAG_COMPOUND)) {
            CompoundTag b = sch.getCompound("Blocks");
            palTag = b.getCompound("Palette");
            data = b.getByteArray("Data");
        } else {
            palTag = sch.getCompound("Palette");
            data = sch.getByteArray("BlockData");
        }
        if (w == 0 || h == 0 || l == 0 || palTag.isEmpty() || data.length == 0)
            throw new ToolError("not a Sponge schematic (.schem v2/v3) or vanilla structure: missing size/palette/data");
        Map<Integer, BlockState> pal = new LinkedHashMap<>();
        for (String k : palTag.getAllKeys()) pal.put(palTag.getInt(k), state(k, unknown, skipped));
        // Each unknown palette entry counted once above; recount per-cell below instead.
        skipped[0] = 0;
        int pos = 0, i = 0, total = w * h * l;
        while (pos < data.length && i < total) {
            int v = 0, shift = 0, b;
            do {
                b = data[pos++] & 0xFF;
                v |= (b & 0x7F) << shift;
                shift += 7;
            } while ((b & 0x80) != 0 && pos < data.length);
            BlockState s = pal.get(v);
            if (s == null) {
                if (!pal.containsKey(v)) { /* index outside palette: ignore */ } else skipped[0]++;
            } else if (!s.isAir()) {
                int x = i % w, z = (i / w) % l, y = i / (w * l);
                out.put(new BlockPos(x, y, z), s);
            }
            i++;
        }
        return new int[]{w, h, l};
    }

    private static int[] structure(CompoundTag root, Map<BlockPos, BlockState> out, Set<String> unknown, int[] skipped) {
        ListTag palette = root.getList("palette", Tag.TAG_COMPOUND);
        List<BlockState> pal = new ArrayList<>();
        for (int i = 0; i < palette.size(); i++) pal.add(state(describe(palette.getCompound(i)), unknown, skipped));
        skipped[0] = 0;
        ListTag blocks = root.getList("blocks", Tag.TAG_COMPOUND);
        for (int i = 0; i < blocks.size(); i++) {
            CompoundTag b = blocks.getCompound(i);
            ListTag p = b.getList("pos", Tag.TAG_INT);
            int idx = b.getInt("state");
            BlockState s = idx >= 0 && idx < pal.size() ? pal.get(idx) : null;
            if (s == null) { skipped[0]++; continue; }
            if (s.isAir()) continue;
            out.put(new BlockPos(p.getInt(0), p.getInt(1), p.getInt(2)), s);
        }
        ListTag sz = root.getList("size", Tag.TAG_INT);
        return new int[]{sz.getInt(0), sz.getInt(1), sz.getInt(2)};
    }

    /** Structure palette entry {Name, Properties{...}} as "name[k=v,...]". */
    private static String describe(CompoundTag t) {
        StringBuilder sb = new StringBuilder(t.getString("Name"));
        if (t.contains("Properties", Tag.TAG_COMPOUND)) {
            CompoundTag pr = t.getCompound("Properties");
            if (!pr.isEmpty()) {
                sb.append('[');
                boolean first = true;
                for (String k : pr.getAllKeys()) {
                    if (!first) sb.append(',');
                    sb.append(k).append('=').append(pr.getString(k));
                    first = false;
                }
                sb.append(']');
            }
        }
        return sb.toString();
    }

    /** Reads {@code nameOrPath} and stores it as ghost {@code id} (default: file stem) at origin (default: player). */
    public static Map<String, Object> importAs(String nameOrPath, String id, BlockPos origin) {
        Loaded l = load(nameOrPath);
        String stem = l.path().getFileName().toString();
        stem = stem.substring(0, stem.lastIndexOf('.'));
        String gid = id == null || id.isBlank() ? stem : id;
        Ghost g = GhostStore.replaceBlocks(gid, l.blocks(), origin, Map.of("source", l.path().getFileName().toString()));
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", g.id);
        m.put("path", l.path().toAbsolutePath().toString());
        m.put("blocks", l.blocks().size());
        m.put("schematic_size", List.of(l.size()[0], l.size()[1], l.size()[2]));
        m.put("origin", List.of(g.origin.getX(), g.origin.getY(), g.origin.getZ()));
        if (l.skipped() > 0) m.put("skipped", l.skipped());
        if (!l.unknown().isEmpty()) m.put("unknown_blocks", l.unknown());
        return m;
    }
}
