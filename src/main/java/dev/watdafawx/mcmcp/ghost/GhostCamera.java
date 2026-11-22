package dev.watdafawx.mcmcp.ghost;

import java.util.List;

import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;

/**
 * Client-only detached camera override used by {@code architect.py}'s {@code view()} when FreeCam mode is enabled.
 * Moves the rendered camera without teleporting the player or changing gamemode (works in survival / multiplayer
 * without cheats). Applied by {@code CameraMixin} and always cleared when a generation job finishes or stops.
 */
public final class GhostCamera {
    private GhostCamera() {}

    /** User toggle in GhostScreen / /ghost freecam: when true, architect runs use this detached camera instead of /tp. */
    public static volatile boolean freeCam = false;

    public static volatile boolean active = false;
    public static volatile double x, y, z;
    public static volatile float yaw, pitch;

    public static void set(double cx, double cy, double cz, double lookX, double lookY, double lookZ) {
        double dx = lookX - cx;
        double dy = lookY - cy;
        double dz = lookZ - cz;
        double horiz = Math.sqrt(dx * dx + dz * dz);
        float yRot = (float) Math.toDegrees(Math.atan2(-dx, dz));
        float xRot = (float) Math.toDegrees(-Math.atan2(dy, horiz));
        x = cx;
        y = cy;
        z = cz;
        yaw = yRot;
        pitch = Math.max(-90f, Math.min(90f, xRot));
        active = true;
    }

    public static void clear() {
        active = false;
    }

    public static void registerTools(McpServer mcp) {
        mcp.add(new Tool("ghost_camera",
                "Client-side detached screenshot camera (no cheats, never teleports the player). "
                        + "Pass x, y, z and look_x, look_y, look_z to position the camera, or off=true to restore the normal player camera.",
                J.Schema.of().bool("off", "true to restore normal player camera")
                        .num("x", "camera x").num("y", "camera y").num("z", "camera z")
                        .num("look_x", "target x").num("look_y", "target y").num("look_z", "target z").build(),
                false, a -> {
                    if (J.b(a, "off", false)) {
                        clear();
                        return J.obj("active", false);
                    }
                    double cx = J.d(a, "x", 0), cy = J.d(a, "y", 64), cz = J.d(a, "z", 0);
                    double lx = J.d(a, "look_x", cx), ly = J.d(a, "look_y", cy), lz = J.d(a, "look_z", cz + 1);
                    set(cx, cy, cz, lx, ly, lz);
                    return J.obj("active", true, "pos", List.of(x, y, z), "yaw", yaw, "pitch", pitch);
                }));
    }
}
