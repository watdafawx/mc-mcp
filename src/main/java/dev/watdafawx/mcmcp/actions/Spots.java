package dev.watdafawx.mcmcp.actions;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.fml.loading.FMLPaths;

import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;

/** Named positions in {@code config/mcmcp/spots.json}, for repeatable measurements. */
public final class Spots {
    private Spots() {}

    private static Path file() {
        return FMLPaths.CONFIGDIR.get().resolve("mcmcp").resolve("spots.json");
    }

    public static synchronized JsonObject all() {
        try {
            Path f = file();
            if (!Files.isRegularFile(f)) return new JsonObject();
            return JsonParser.parseString(Files.readString(f, StandardCharsets.UTF_8)).getAsJsonObject();
        } catch (Exception e) {
            return new JsonObject();
        }
    }

    public static synchronized Map<String, Object> save(String name, ServerPlayer p) throws IOException {
        JsonObject all = all();
        JsonObject s = new JsonObject();
        s.addProperty("dimension", p.level().dimension().location().toString());
        s.addProperty("x", J.r2(p.getX()));
        s.addProperty("y", J.r2(p.getY()));
        s.addProperty("z", J.r2(p.getZ()));
        s.addProperty("yaw", J.r1(p.getYRot()));
        s.addProperty("pitch", J.r1(p.getXRot()));
        all.add(name, s);
        Files.createDirectories(file().getParent());
        Files.writeString(file(), McpServer.GSON.toJson(all), StandardCharsets.UTF_8);
        return J.obj("saved", name, "spot", s);
    }

    /** Call on the server thread. */
    public static Map<String, Object> teleport(MinecraftServer server, ServerPlayer p, String name) {
        JsonObject s = all().has(name) ? all().getAsJsonObject(name) : null;
        if (s == null) throw new McpServer.ToolError("no spot '" + name + "'; saved: " + all().keySet());
        ResourceKey<net.minecraft.world.level.Level> dim = ResourceKey.create(Registries.DIMENSION, ResourceLocation.parse(s.get("dimension").getAsString()));
        ServerLevel level = server.getLevel(dim);
        if (level == null) throw new McpServer.ToolError("dimension not loaded: " + dim.location());
        p.teleportTo(level, s.get("x").getAsDouble(), s.get("y").getAsDouble(), s.get("z").getAsDouble(),
                s.get("yaw").getAsFloat(), s.get("pitch").getAsFloat());
        return J.obj("teleported", p.getGameProfile().getName(), "to", name, "spot", s,
                "hint", "chunks need a few seconds to load and render; measure with settle_s >= 10");
    }
}
