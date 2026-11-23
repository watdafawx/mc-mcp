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
 * Ghost builder screen: two modes.
 * <ul>
 *   <li><b>Prompt / Image</b>: free-text description and/or image reference (path, URL, or clipboard) to generate a
 *       focused structure or component, plus <b>Iterate</b> to refine the latest session in place.</li>
 *   <li><b>Base Style</b>: full themed base via {@code /ghost generate <style> [look|here|x z] [kit] [layout] [nofit]}.</li>
 * </ul>
 * Opened with the {@code G} keybind (rebindable) or {@code /ghost gui}. Never pauses the game.
 */
public final class GhostScreen extends Screen {
    public static final KeyMapping OPEN = new KeyMapping("key.mcmcp.ghost_gui", GLFW.GLFW_KEY_G, "key.categories.mcmcp");

    private static final String AUTO = "auto";
    private static final String MODE_PROMPT = "prompt";
    private static final String MODE_STYLE = "style";
    private static final List<String> MODES = List.of(MODE_PROMPT, MODE_STYLE);
    private static final List<String> POSITIONS = List.of("look", "here", "coords");
    private static final List<String> KIT_OPTIONS = withAuto(GhostGenerate.KITS);
    private static final List<String> LAYOUT_OPTIONS = withAuto(GhostGenerate.LAYOUTS);

    /** Session memory: reopening the screen keeps the last choices. */
    private static String lastMode = MODE_PROMPT;
    private static String lastPrompt = "";
    private static String lastRef = "";
    private static boolean lastClip = false;
    private static boolean lastForce3d = false;
    private static String lastStyle = GhostGenerate.STYLES.get(0);
    private static String lastPosition = "look";
    private static String lastKit = AUTO;
    private static String lastLayout = AUTO;
    private static boolean lastFit = true;

    private static final int PANEL = 280, PAD = 10, TITLE_H = 16, STATUS_H = 14, MARGIN = 6;

    private CycleButton<String> modeBtn, styleBtn, positionBtn, kitBtn, layoutBtn;
    private Button clipBtn, force3dBtn, fitBtn, generateBtn, iterateBtn, stopBtn, undoBtn, exportBtn, clearBtn, showBtn, xrayBtn, freeCamBtn;
    private EditBox promptBox, refBox, xBox, zBox;
    private boolean shown = true;
    private Component status = Component.empty();
    private int statusColor = 0xFFA0A0A0;
    private int left, top, step, hgt, panelH, rows;

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

    private static Component modeLabel(String value) {
        return Component.translatable("mcmcp.ghost.gui.mode." + value);
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
        boolean promptMode = MODE_PROMPT.equals(lastMode);
        rows = promptMode ? 8 : 9;
        // Rows shrink a little on small (large GUI scale) screens so the whole panel always fits.
        step = Math.max(14, Math.min(22, (this.height - 2 * MARGIN - TITLE_H - STATUS_H) / rows));
        hgt = Math.max(12, step - 2);
        panelH = TITLE_H + rows * step + STATUS_H;
        left = this.width / 2 - PANEL / 2 + PAD;
        top = (this.height - panelH) / 2 + TITLE_H;
        int w = PANEL - 2 * PAD;
        int half = (w - 4) / 2;
        int y = top;

        List<Ghost> ghosts = GhostStore.all();
        shown = ghosts.isEmpty() || ghosts.stream().allMatch(g -> g.visible);

        modeBtn = CycleButton.<String>builder(GhostScreen::modeLabel)
                .withValues(MODES)
                .withInitialValue(MODES.contains(lastMode) ? lastMode : MODE_PROMPT)
                .create(left, y, w, hgt, Component.translatable("mcmcp.ghost.gui.mode"), (b, v) -> {
                    lastMode = v;
                    this.rebuildWidgets();
                });
        addRenderableWidget(modeBtn);
        y += step;

        promptBox = null;
        refBox = null;
        clipBtn = null;
        force3dBtn = null;
        styleBtn = null;
        layoutBtn = null;
        fitBtn = null;
        iterateBtn = null;

        if (promptMode) {
            promptBox = new EditBox(this.font, left, y, w, hgt, Component.translatable("mcmcp.ghost.gui.prompt"));
            promptBox.setMaxLength(500);
            promptBox.setHint(Component.translatable("mcmcp.ghost.gui.prompt.hint").withStyle(ChatFormatting.DARK_GRAY));
            promptBox.setValue(lastPrompt);
            promptBox.setResponder(s -> lastPrompt = s);
            addRenderableWidget(promptBox);
            y += step;

            int clipW = 54;
            int d3W = 46;
            int refW = w - clipW - d3W - 8;
            refBox = new EditBox(this.font, left, y, refW, hgt, Component.translatable("mcmcp.ghost.gui.ref"));
            refBox.setMaxLength(400);
            refBox.setHint(Component.translatable("mcmcp.ghost.gui.ref.hint").withStyle(ChatFormatting.DARK_GRAY));
            refBox.setValue(lastRef);
            refBox.setResponder(s -> lastRef = s);
            addRenderableWidget(refBox);

            clipBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.clip", onOff(lastClip)), b -> {
                lastClip = !lastClip;
                b.setMessage(Component.translatable("mcmcp.ghost.gui.clip", onOff(lastClip)));
            }).bounds(left + refW + 4, y, clipW, hgt).build();
            addRenderableWidget(clipBtn);

            force3dBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.force3d", onOff(lastForce3d)), b -> {
                lastForce3d = !lastForce3d;
                b.setMessage(Component.translatable("mcmcp.ghost.gui.force3d", onOff(lastForce3d)));
            }).bounds(left + refW + 4 + clipW + 4, y, d3W, hgt).build();
            addRenderableWidget(force3dBtn);
            y += step;

            positionBtn = CycleButton.<String>builder(GhostScreen::positionLabel)
                    .withValues(POSITIONS)
                    .withInitialValue(POSITIONS.contains(lastPosition) ? lastPosition : "look")
                    .create(left, y, half, hgt, Component.translatable("mcmcp.ghost.gui.position"), (b, v) -> {
                        lastPosition = v;
                        updateCoords();
                    });
            addRenderableWidget(positionBtn);

            kitBtn = CycleButton.<String>builder(GhostScreen::label)
                    .withValues(KIT_OPTIONS)
                    .withInitialValue(KIT_OPTIONS.contains(lastKit) ? lastKit : AUTO)
                    .create(left + half + 4, y, w - half - 4, hgt, Component.translatable("mcmcp.ghost.gui.kit"), (b, v) -> lastKit = v);
            addRenderableWidget(kitBtn);
            y += step;

            addCoordBoxes(y, w, half);
            y += step;

            int third = (w - 8) / 3;
            generateBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.generate"), b -> generatePrompt(false))
                    .bounds(left, y, third, hgt).build();
            iterateBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.iterate"), b -> generatePrompt(true))
                    .bounds(left + third + 4, y, third, hgt).build();
            stopBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.stop"), b -> stop())
                    .bounds(left + 2 * (third + 4), y, w - 2 * (third + 4), hgt).build();
            addRenderableWidget(generateBtn);
            addRenderableWidget(iterateBtn);
            addRenderableWidget(stopBtn);
            y += step;
        } else {
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

            addCoordBoxes(y, w, half);
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

            generateBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.generate"), b -> generateStyle())
                    .bounds(left, y, half, hgt).build();
            stopBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.stop"), b -> stop())
                    .bounds(left + half + 4, y, w - half - 4, hgt).build();
            addRenderableWidget(generateBtn);
            addRenderableWidget(stopBtn);
            y += step;
        }

        // Utility row: Undo | Export | Clear | Ghosts: shown/hidden (Undo keeps the widest label readable).
        int undoW = 52, exportW = 56, clearW = 52;
        undoBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.undo"), b -> run("ghost undo"))
                .bounds(left, y, undoW, hgt).build();
        exportBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.export"), b -> run("ghost export"))
                .bounds(left + undoW + 4, y, exportW, hgt).build();
        clearBtn = Button.builder(Component.translatable("mcmcp.ghost.gui.clear"), b -> run("ghost clear"))
                .bounds(left + undoW + exportW + 8, y, clearW, hgt).build();
        int showX = left + undoW + exportW + clearW + 12;
        showBtn = Button.builder(showLabel(), b -> {
            shown = !shown;
            b.setMessage(showLabel());
            run(shown ? "ghost show" : "ghost hide");
        }).bounds(showX, y, left + w - showX, hgt).build();
        addRenderableWidget(undoBtn);
        addRenderableWidget(exportBtn);
        addRenderableWidget(clearBtn);
        addRenderableWidget(showBtn);
        y += step;

        xrayBtn = Button.builder(xrayLabel(), b -> {
            run("ghost xray " + (GhostRenderer.xray ? "off" : "on"));
            b.setMessage(xrayLabel());
        }).bounds(left, y, half, hgt).build();
        freeCamBtn = Button.builder(freeCamLabel(), b -> {
            run("ghost freecam " + (GhostCamera.freeCam ? "off" : "on"));
            b.setMessage(freeCamLabel());
        }).bounds(left + half + 4, y, w - half - 4, hgt).build();
        addRenderableWidget(xrayBtn);
        addRenderableWidget(freeCamBtn);

        if (promptBox != null) setInitialFocus(promptBox);
        updateCoords();
        updateStatus();
    }

    private void addCoordBoxes(int y, int w, int half) {
        xBox = new EditBox(this.font, left, y, half, hgt, Component.translatable("mcmcp.ghost.gui.x"));
        zBox = new EditBox(this.font, left + half + 4, y, w - half - 4, hgt, Component.translatable("mcmcp.ghost.gui.z"));
        for (EditBox box : List.of(xBox, zBox)) {
            box.setMaxLength(9);
            box.setFilter(s -> s.isEmpty() || s.equals("-") || s.matches("-?\\d{1,8}"));
            addRenderableWidget(box);
        }
        xBox.setValue(Integer.toString(playerPos(true)));
        zBox.setValue(Integer.toString(playerPos(false)));
    }

    @Override
    public void tick() {
        super.tick();
        GhostGenerate.Job job = GhostGenerate.current();
        boolean running = job != null && job.running();
        generateBtn.active = !running;
        stopBtn.active = running;
        if (iterateBtn != null) iterateBtn.active = !running && GhostGenerate.latest() != null;
        if (undoBtn != null) undoBtn.active = !running && GhostStore.canUndo();
        if (exportBtn != null) exportBtn.active = !GhostStore.all().isEmpty();
        xrayBtn.setMessage(xrayLabel());
        freeCamBtn.setMessage(freeCamLabel());
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

    private static Component freeCamLabel() {
        return Component.translatable("mcmcp.ghost.gui.freecam", onOff(GhostCamera.freeCam));
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

    private void generatePrompt(boolean iterate) {
        String text = promptBox == null ? "" : promptBox.getValue().trim();
        String ref = refBox == null ? "" : refBox.getValue().trim();
        boolean clip = lastClip;
        boolean force3d = !iterate && lastForce3d;
        if (text.isEmpty() && ref.isEmpty() && !clip) {
            GhostGenerate.chat(ChatFormatting.RED, "enter a prompt, an image ref, or turn Clip on");
            return;
        }
        if (force3d && ref.isEmpty() && !clip) {
            GhostGenerate.chat(ChatFormatting.RED, "3D mode needs an image ref or Clip: on");
            return;
        }
        Integer x = null, z = null;
        String target = positionBtn.getValue();
        if ("coords".equals(target)) {
            x = parseInt(xBox.getValue());
            z = parseInt(zBox.getValue());
            if (x == null || z == null) {
                GhostGenerate.chat(ChatFormatting.RED, "coordinates must be whole numbers, x then z");
                return;
            }
            target = null;
        }
        String kit = AUTO.equals(kitBtn.getValue()) ? null : kitBtn.getValue();
        Integer fx = x, fz = z;
        String ft = target;
        Thread t = new Thread(() -> {
            try {
                GhostGenerate.startPrompt(text, ref, clip, fx, fz, ft, kit, iterate, force3d);
            } catch (RuntimeException e) {
                GhostGenerate.chat(ChatFormatting.RED, String.valueOf(e.getMessage()));
            }
        }, "mcmcp-ghost-prompt");
        t.setDaemon(true);
        t.start();
    }

    private void generateStyle() {
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
        g.drawCenteredString(this.font, line, this.width / 2, top + rows * step + 1, statusColor);
    }

    @Override
    public void renderBackground(GuiGraphics g, int mouseX, int mouseY, float partialTick) {
        // No blur or panorama: the world stays readable while ghosts are being built.
        this.renderTransparentBackground(g);
    }
}
