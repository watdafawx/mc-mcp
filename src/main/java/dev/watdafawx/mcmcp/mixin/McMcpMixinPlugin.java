package dev.watdafawx.mcmcp.mixin;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;

import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

import net.neoforged.fml.loading.FMLPaths;

/**
 * Mixins load before NeoForge configs, so the toggle is read straight from the TOML file:
 * {@code chatBridge = false} skips the chat capture mixin.
 */
public final class McMcpMixinPlugin implements IMixinConfigPlugin {
    private boolean chat = true;

    @Override
    public void onLoad(String mixinPackage) {
        try {
            Path p = FMLPaths.CONFIGDIR.get().resolve("mcmcp-common.toml");
            if (Files.isRegularFile(p))
                for (String line : Files.readAllLines(p))
                    if (line.trim().replace(" ", "").equalsIgnoreCase("chatBridge=false")) chat = false;
        } catch (Exception ignored) {
        }
    }

    @Override
    public boolean shouldApplyMixin(String targetClassName, String mixinClassName) {
        return !mixinClassName.endsWith("ChatComponentMixin") || chat;
    }

    @Override public String getRefMapperConfig() { return null; }
    @Override public void acceptTargets(Set<String> myTargets, Set<String> otherTargets) {}
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String t, ClassNode c, String m, IMixinInfo i) {}
    @Override public void postApply(String t, ClassNode c, String m, IMixinInfo i) {}
}
