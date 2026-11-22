package dev.watdafawx.mcmcp.ghost;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import org.lwjgl.glfw.GLFW;

import net.minecraft.ChatFormatting;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.CycleButton;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.client.ClientCommandHandler;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.RegisterKeyMappingsEvent;
import net.neoforged.neoforge.common.NeoForge;

/**
 * Ghost builder screen: pick a style, where to build, kit, layout and fit, then run exactly what
 * {@code /ghost generate <style> [look|here|x z] [kit] [layout] [nofit]} runs. Stop cancels the job, Clear empties the
 * ghost layers, the other two buttons are the existing show/hide and xray/solid switches. Opened with the {@code G}
 * keybind (rebindable) or {@code /ghost gui}. Never pauses the game, so generation feedback keeps flowing.
 */
public final class GhostScreen extends Screen {
    public static final KeyMapping OPEN = new KeyMapping("key.mcmcp.ghost_gui", GLFW.GLFW_KEY_G, "key.categories.mcmcp");

    /** "auto" = leave it to the architect (the first entry of the kit and layout lists). */
    private static final String AUTO = "auto";
    private static final List<String> POSITIONS = List.of("look", "here", "coords");
    private static final List<String> KIT_OPTIONS = withAuto(GhostGenerate.KITS);
    private static final List<String> LAYOUT_OPTIONS = withAuto(GhostGenerate.LAYOUTS);

    /** Session memory: reopening the screen keeps the last choices. */
    private static String lastStyle = GhostGenerate.STYLES.get(0);
    private static String lastPosition = "look";
    private static String lastKit = AUTO;
    private static String lastLayout = AUTO;
    private static boolean lastFit = true;

    private static final int PANEL = 240, PAD = 10, ROWS = 8, TITLE_H = 16, STATUS_H = 14, MARGIN = 6;

    private CycleButton<String> styleBtn, positionBtn, kitBtn, layoutBtn;
    private Button fitBtn, generateBtn, stopBtn, clearBtn, showBtn, xrayBtn;
    private EditBox xBox, zBox;
    private boolean shown = true;
    private Component status = Component.empty();
    private int statusColor = 0xFFA0A0A0;
    private int left, top, step, hgt, panelH;

    private GhostScreen() {
        super(Component.translatable("mcmcp.ghost.gui.title"));
    }

    /** Registers the keybind and its tick handler (client side). */
    public static void register(IEventBus modBus) {
        modBus.addListener((RegisterKeyMappingsEvent e) -> e.register(OPEN));
        NeoForge.EVENT_BUS.addListener((ClientTickEvent.Post e) -> openOnKey());
    }

    public static void open() {
        Minecraft.getInstance().setScreen(new GhostScreen());
    }

    /** G opens the screen when nothing else is open; the click is consumed either way. */
    private static void openOnKey() {
        Minecraft mc = Minecraft.getInstance();
        boolean pressed = false;
        while (OPEN.consumeClick()) pressed = true;
        if (pressed && mc.screen == null && mc.player != null) open();
    }

    private static List<String> withAuto(List<String> values) {
        List<String> all = new ArrayList<>();
        all.add(AUTO);
        all.addAll(values);
        return List.copyOf(all);
    }

    private static Component label(String value) {
        return AUTO.equals(value) ? Component.translatable("mcmcp.ghost.gui.auto") : Component.literal(value);
    }

    private static Component positionLabel(String value) {
        return Component.translatable("mcmcp.ghost.gui.position." + value);
    }

    private static Component onOff(boolean on) {
        return Component.translatable(on ? "mcmcp.ghost.gui.on" : "mcmcp.ghost.gui.off");
    }

    // ------------------------------------------------------------------ widgets

    @Override
    protected void init() {
        // Rows shrink a little on small (large GUI scale) screens so the whole panel always fits.
        step = Math.max(14, Math.min(22, (this.height - 2 * MARGIN - TITLE_H - STATUS_H) / ROWS));
        hgt = Math.max(12, step - 2);
        panelH = TITLE_H + ROWS * step + STATUS_H;
        left = this.width / 2 - PANEL / 2 + PAD;
        top = (this.height - panelH) / 2 + TITLE_H;
        int w = PANEL - 2 * PAD;
        int y = top;
        // No ghosts at all counts as shown (the button then offers "hide").
        List<Ghost> ghosts = GhostStore.all();
        shown = ghosts.isEmpty() || ghosts.stream().allMatch(g -> g.visible);

        styleBtn = CycleButton.<String>builder(GhostScreen::label)
                .withValues(GhostGenerate.STYLES)
                .withInitialValue(GhostGenerate.STYLES.contains(lastStyle) ? lastStyle : GhostGenerate.STYLES.get(0))
                .create(left, y, w, hgt, Component.translatable("mcmcp.ghost.gui.style"), (b, v) -> lastStyle = v);
        addRenderableWidget(styleBtn);
        y += step;

        positionBtn = CycleButton.<String>builder(GhostScreen::positionLabel)
                .withValues(POSITIONS)
                .withInitialValue(POSITIONS.contains(lastPosition) ? lastPosition : "look")
                .create(left, y, w, hgt, Component.translatable("mcmcp.ghost.gui.position"), (b, v) -> {
                    lastPosition = v;
                    updateCoords();
                });
        addRenderableWidget(positionBtn);
        y += step;

        int half = (w - 4) / 2;
        xBox = new EditBox(this.font, left, y, half, hgt, Component.translatable("mcmcp.ghost.gui.x"));
        zBox = new EditBox(this.font, left + half + 4, y, w - half - 4, hgt, Component.translatable("mcmcp.ghost.gui.z"));
        for (EditBox box : List.of(xBox, zBox)) {
            box.setMaxLength(9);
            box.setFilter(s -> s.isEmpty() || s.equals("-") || s.matches("-?\\d{1,8}"));
            addRenderableWidget(box);
        }
        xBox.setValue(Integer.toString(playerPos(true)));
        zBox.setValue(Integer.toString(playerPos(false)));
        y += step;

        kitBtn = CycleButton.<String>builder(GhostScreen::label)
                .withValues(KIT_OPTIONS)
                .withInitialValue(KIT_OPTIONS.contains(lastKit) ? lastKit : AUTO)
                .create(left, y, half, hgt, Component.translatable("mcmcp.ghost.gui.kit"), (b, v) -> lastKit = v);
        addRenderableWidget(kitBtn);
        layoutBtn = CycleButton.<String>builder(GhostScreen::label)
                .withValues(LAYOUT_OPTIONS)
                .withInitialValue(LAYOUT_OPTIONS.contains(lastLayout) ? lastLayout : AUTO)
                .create(left + half + 4, y, w - half - 4, hgt, Component.translatable("mcmcp.ghost.gui.layout"), (b, v) -> lastLayout = v);
        addRenderableWidget(layoutBtn);
        y += step;

        fitBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.fit", onOff(lastFit)), b -> {
            lastFit = !lastFit;
            b.setMessage(Component.translatable("mcmcp.ghost.gui.fit", onOff(lastFit)));
        }).bounds(left, y, w, hgt).build();
        addRenderableWidget(fitBtn);
        y += step;

        generateBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.generate"), b -> generate())
                .bounds(left, y, half, hgt).build();
        stopBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.stop"), b -> stop())
                .bounds(left + half + 4, y, w - half - 4, hgt).build();
        addRenderableWidget(generateBtn);
        addRenderableWidget(stopBtn);
        y += step;

        clearBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.clear"), b -> run("ghost clear"))
                .bounds(left, y, half, hgt).build();
        showBtn = Button.builder(showLabel(), b -> {
            shown = !shown;
            b.setMessage(showLabel());
            run(shown ? "ghost show" : "ghost hide");
        }).bounds(left + half + 4, y, w - half - 4, hgt).build();
        addRenderableWidget(clearBtn);
        addRenderableWidget(showBtn);
        y += step;

        xrayBtn = Button.builder(xrayLabel(), b -> {
            run("ghost xray " + (GhostRenderer.xray ? "off" : "on"));
            b.setMessage(xrayLabel());
        }).bounds(left, y, w, hgt).build();
        addRenderableWidget(xrayBtn);

        updateCoords();
        updateStatus();
    }

    @Override
    public void tick() {
        super.tick();
        GhostGenerate.Job job = GhostGenerate.current();
        boolean running = job != null && job.running();
        generateBtn.active = !running;
        stopBtn.active = running;
        // Commands and the MCP tools can flip these behind the screen's back: keep the labels honest.
        xrayBtn.setMessage(xrayLabel());
        showBtn.setMessage(showLabel());
        updateStatus();
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }

    private static int playerPos(boolean x) {
        var p = Minecraft.getInstance().player;
        if (p == null) return 0;
        return x ? p.blockPosition().getX() : p.blockPosition().getZ();
    }

    private Component showLabel() {
        return Component.translatable("mcmcp.ghost.gui.ghosts", Component.translatable(
                shown ? "mcmcp.ghost.gui.shown" : "mcmcp.ghost.gui.hidden"));
    }

    private static Component xrayLabel() {
        return Component.translatable("mcmcp.ghost.gui.xray", Component.translatable(
                GhostRenderer.xray ? "mcmcp.ghost.gui.mode.xray" : "mcmcp.ghost.gui.mode.solid"));
    }

    /** Coordinates row is only usable (and only drawn) in Coordinates mode. */
    private void updateCoords() {
        boolean coords = "coords".equals(lastPosition);
        for (EditBox box : List.of(xBox, zBox)) {
            box.visible = coords;
            box.active = coords;
        }
    }

    // ------------------------------------------------------------------ actions

    private void generate() {
        StringBuilder cmd = new StringBuilder("ghost generate ").append(styleBtn.getValue());
        switch (positionBtn.getValue()) {
            case "here" -> cmd.append(" here");
            case "coords" -> {
                Integer x = parseInt(xBox.getValue()), z = parseInt(zBox.getValue());
                if (x == null || z == null) {
                    GhostGenerate.chat(ChatFormatting.RED, "coordinates must be whole numbers, x then z");
                    return;
                }
                cmd.append(' ').append(x).append(' ').append(z);
            }
            default -> cmd.append(" look");
        }
        if (!AUTO.equals(kitBtn.getValue())) cmd.append(' ').append(kitBtn.getValue());
        if (!AUTO.equals(layoutBtn.getValue())) cmd.append(' ').append(layoutBtn.getValue());
        if (!lastFit) cmd.append(" nofit");
        run(cmd.toString());
    }

    private void stop() {
        if (!GhostGenerate.stop()) GhostGenerate.chat(ChatFormatting.YELLOW, "no generate job running");
    }

    /** Runs the same client command a typed line would run (never from the game thread only paths). */
    private void run(String command) {
        if (this.minecraft == null || this.minecraft.player == null) return;
        if (!ClientCommandHandler.runCommand(command)) GhostGenerate.chat(ChatFormatting.RED, "unknown command: /" + command);
    }

    private static Integer parseInt(String s) {
        try {
            return Integer.valueOf(s.trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private void updateStatus() {
        GhostGenerate.Job running = GhostGenerate.current();
        if (running != null && running.running()) {
            long secs;
            synchronized (running) {
                secs = (System.currentTimeMillis() - running.startedMs) / 1000;
            }
            status = Component.translatable("mcmcp.ghost.gui.status.generating", secs);
            statusColor = 0xFF55FFFF;
            return;
        }
        GhostGenerate.Job last = GhostGenerate.latest();
        if (last == null) {
            status = Component.translatable("mcmcp.ghost.gui.status.idle");
            statusColor = 0xFFA0A0A0;
            return;
        }
        String state, error;
        double cost;
        synchronized (last) {
            state = last.status;
            error = last.error;
            cost = last.cost;
        }
        switch (state) {
            case "done" -> {
                status = Component.translatable("mcmcp.ghost.gui.status.done", last.ghostIds().size(),
                        String.format(Locale.ROOT, "$%.4f", cost));
                statusColor = 0xFF55FF55;
            }
            case "stopped" -> {
                status = Component.translatable("mcmcp.ghost.gui.status.stopped");
                statusColor = 0xFFFFFF55;
            }
            case "failed" -> {
                status = Component.translatable("mcmcp.ghost.gui.status.error", error == null ? "?" : error);
                statusColor = 0xFFFF5555;
            }
            default -> {
                status = Component.translatable("mcmcp.ghost.gui.status.idle");
                statusColor = 0xFFA0A0A0;
            }
        }
    }

    // ------------------------------------------------------------------ drawing

    @Override
    public void render(GuiGraphics g, int mouseX, int mouseY, float partialTick) {
        int x0 = this.width / 2 - PANEL / 2;
        int y0 = top - TITLE_H;
        g.fill(x0, y0, x0 + PANEL, y0 + panelH, 0xC8101018);
        g.renderOutline(x0, y0, PANEL, panelH, 0xFF7070B0);
        super.render(g, mouseX, mouseY, partialTick);
        g.drawCenteredString(this.font, this.title, this.width / 2, y0 + 4, 0xFFFFFFFF);
        String line = this.font.plainSubstrByWidth(status.getString(), PANEL - 2 * PAD);
        g.drawCenteredString(this.font, line, this.width / 2, top + ROWS * step + 1, statusColor);
    }

    @Override
    public void renderBackground(GuiGraphics g, int mouseX, int mouseY, float partialTick) {
        // No blur or panorama: the world stays readable while ghosts are being built.
        this.renderTransparentBackground(g);
    }
}
