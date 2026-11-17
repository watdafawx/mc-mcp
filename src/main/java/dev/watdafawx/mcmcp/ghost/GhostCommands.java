package dev.watdafawx.mcmcp.ghost;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Supplier;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import com.mojang.brigadier.suggestion.SuggestionsBuilder;

import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.Component;
import net.neoforged.neoforge.client.event.RegisterClientCommandsEvent;
import net.neoforged.neoforge.common.NeoForge;

import dev.watdafawx.mcmcp.mcp.McpServer;

/** Client-side /ghost commands (ghosts live only in this client's memory). */
public final class GhostCommands {
    private GhostCommands() {}

    public static void init() {
        NeoForge.EVENT_BUS.addListener((RegisterClientCommandsEvent e) -> register(e.getDispatcher()));
    }

    private static final SuggestionProvider<CommandSourceStack> IDS = (ctx, b) -> {
        List<String> ids = new ArrayList<>();
        ids.add("*");
        for (Ghost g : GhostStore.all()) ids.add(g.id);
        return SharedSuggestionProvider.suggest(ids, b);
    };

    private static final SuggestionProvider<CommandSourceStack> SCHEMATICS =
            (ctx, b) -> SharedSuggestionProvider.suggest(GhostImport.available(), b);

    private static final SuggestionProvider<CommandSourceStack> STYLES =
            (ctx, b) -> SharedSuggestionProvider.suggest(GhostGenerate.STYLES, b);

    /** Free-form tail of /ghost generate <style> [x z] [kit] [layout]: completes the last word with kits and layouts. */
    private static final SuggestionProvider<CommandSourceStack> TAIL = (ctx, b) -> {
        String rest = b.getRemaining();
        int sp = rest.lastIndexOf(' ');
        SuggestionsBuilder w = b.createOffset(b.getStart() + sp + 1);
        List<String> all = new ArrayList<>(GhostGenerate.KITS);
        all.addAll(GhostGenerate.LAYOUTS);
        return SharedSuggestionProvider.suggest(all, w);
    };

    private static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("ghost")
                .then(Commands.literal("hide").executes(c -> show("*", false))
                        .then(Commands.argument("id", StringArgumentType.greedyString()).suggests(IDS)
                                .executes(c -> show(StringArgumentType.getString(c, "id"), false))))
                .then(Commands.literal("show").executes(c -> show("*", true))
                        .then(Commands.argument("id", StringArgumentType.greedyString()).suggests(IDS)
                                .executes(c -> show(StringArgumentType.getString(c, "id"), true))))
                .then(Commands.literal("list").executes(c -> list()))
                .then(Commands.literal("clear").executes(c -> clear("*"))
                        .then(Commands.argument("id", StringArgumentType.greedyString()).suggests(IDS)
                                .executes(c -> clear(StringArgumentType.getString(c, "id")))))
                .then(Commands.literal("import")
                        .then(Commands.argument("name", StringArgumentType.string()).suggests(SCHEMATICS)
                                .executes(c -> importSchem(StringArgumentType.getString(c, "name"), null))
                                .then(Commands.argument("x", IntegerArgumentType.integer())
                                        .then(Commands.argument("y", IntegerArgumentType.integer())
                                                .then(Commands.argument("z", IntegerArgumentType.integer())
                                                        .executes(c -> importSchem(StringArgumentType.getString(c, "name"),
                                                                new net.minecraft.core.BlockPos(IntegerArgumentType.getInteger(c, "x"),
                                                                        IntegerArgumentType.getInteger(c, "y"),
                                                                        IntegerArgumentType.getInteger(c, "z")))))))))
                .then(Commands.literal("generate")
                        .then(Commands.argument("style", StringArgumentType.word()).suggests(STYLES)
                                .executes(c -> generate(StringArgumentType.getString(c, "style"), ""))
                                .then(Commands.argument("args", StringArgumentType.greedyString()).suggests(TAIL)
                                        .executes(c -> generate(StringArgumentType.getString(c, "style"),
                                                StringArgumentType.getString(c, "args")))))));
    }

    private static void say(ChatFormatting color, String text) {
        GhostGenerate.chat(color, text);
    }

    private static int guard(Supplier<Integer> body) {
        try {
            return body.get();
        } catch (RuntimeException e) {
            say(ChatFormatting.RED, String.valueOf(e.getMessage()));
            return 0;
        }
    }

    private static int show(String id, boolean visible) {
        return guard(() -> {
            int n = GhostTools.setShown(id, visible, null);
            say(ChatFormatting.GREEN, (visible ? "shown " : "hidden ") + n + " ghost" + (n == 1 ? "" : "s"));
            return n;
        });
    }

    private static int importSchem(String name, net.minecraft.core.BlockPos at) {
        return guard(() -> {
            var r = GhostImport.importAs(name, null, at);
            say(ChatFormatting.GREEN, "imported '" + r.get("id") + "': " + r.get("blocks") + " blocks @ " + r.get("origin")
                    + (r.containsKey("skipped") ? " (" + r.get("skipped") + " skipped)" : ""));
            return (Integer) r.get("blocks");
        });
    }

    private static int clear(String id) {
        return guard(() -> {
            List<String> gone = GhostTools.clearGhosts(id);
            say(gone.isEmpty() ? ChatFormatting.YELLOW : ChatFormatting.GREEN,
                    "cleared " + gone.size() + " ghost" + (gone.size() == 1 ? "" : "s"));
            return gone.size();
        });
    }

    private static int list() {
        return guard(() -> {
            List<Ghost> all = GhostStore.all();
            if (all.isEmpty()) {
                say(ChatFormatting.YELLOW, "no ghosts");
                return 0;
            }
            Minecraft mc = Minecraft.getInstance();
            say(ChatFormatting.WHITE, all.size() + " ghost" + (all.size() == 1 ? "" : "s") + ":");
            for (Ghost g : all) {
                String line;
                synchronized (GhostStore.LOCK) {
                    line = g.id + "  " + g.blocks.size() + " blocks  @ " + g.origin.getX() + " " + g.origin.getY() + " "
                            + g.origin.getZ() + (g.visible ? "" : "  [hidden]");
                }
                mc.gui.getChat().addMessage(Component.literal("  " + line).withStyle(ChatFormatting.GRAY));
            }
            return all.size();
        });
    }

    private static int generate(String style, String tail) {
        return guard(() -> {
            Integer x = null, z = null;
            String kit = null, layout = null;
            String[] t = tail.trim().isEmpty() ? new String[0] : tail.trim().split("\\s+");
            int i = 0;
            if (t.length >= 2 && isInt(t[0]) && isInt(t[1])) {
                x = Integer.parseInt(t[0]);
                z = Integer.parseInt(t[1]);
                i = 2;
            } else if (t.length >= 1 && isInt(t[0])) {
                throw new McpServer.ToolError("give both x and z, or neither");
            }
            for (; i < t.length; i++) {
                String w = t[i].toLowerCase(Locale.ROOT);
                if (GhostGenerate.LAYOUTS.contains(w) && layout == null) layout = w;
                else if (kit == null) kit = w;
                else throw new McpServer.ToolError("unexpected '" + t[i] + "'. Usage: /ghost generate <style> [x z] [kit] [layout]");
            }
            GhostGenerate.start(style, x, z, kit, layout);
            return 1;
        });
    }

    private static boolean isInt(String s) {
        try {
            Integer.parseInt(s);
            return true;
        } catch (NumberFormatException e) {
            return false;
        }
    }
}
