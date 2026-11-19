package dev.watdafawx.mcmcp.ghost;

import java.lang.reflect.Field;
import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;

import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.neoforge.client.model.data.ModelData;

/**
 * Draws blocks that a {@link BlockEntityRenderer} draws (chests, signs, banners, Create shafts/cogs/belts/water wheels...)
 * into a ghost mesh. Each such ghost block gets a client-only dummy block entity: made by the block's own
 * {@code newBlockEntity}, given the client level so renderers that check {@code hasLevel()} run, and never added to the
 * world. Its renderer draws into {@link Capture}, which keeps the quads per texture so they can be baked once and drawn
 * with the ghost tint like every other ghost block.
 * <p>
 * Create draws its rotating parts through Flywheel instancing when a Flywheel backend is on, and its renderers then draw
 * nothing for the real client level. {@link #withFlywheelOff} switches Flywheel's backend to "off" for the length of a
 * bake (render thread, a few ms) so those renderers take their plain-BER path. Without Flywheel this is a no-op.
 * <p>
 * Nothing here references another mod's classes at compile time: Flywheel and Ponder are reached by reflection only, so
 * the mod loads on a clean NeoForge install.
 */
final class GhostBlockEntities {
    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger("mcmcp-ghost");
    private static final Set<Block> FAILED = ConcurrentHashMap.newKeySet();
    private static final Map<String, Long2ObjectMap<BlockEntity>> DUMMIES = new ConcurrentHashMap<>();
    private static volatile boolean flywheelWarned;

    private GhostBlockEntities() {}

    static boolean enabled() {
        try {
            return dev.watdafawx.mcmcp.Config.GHOST_BLOCK_ENTITIES.get();
        } catch (RuntimeException notLoaded) {
            return true;
        }
    }

    /**
     * Ponder's "virtual" model data: Create's bracketed kinetic models (shaft, cogwheel...) return no quads in normal
     * chunk rendering (the block entity draws them) and their full model with this. {@link ModelData#EMPTY} without
     * Create/Ponder.
     */
    static final ModelData VIRTUAL = virtualData();

    private static ModelData virtualData() {
        try {
            Class<?> c = Class.forName("net.createmod.ponder.render.VirtualRenderHelper");
            Object v = c.getField("VIRTUAL_DATA").get(null);
            if (v instanceof ModelData md) return md;
        } catch (ReflectiveOperationException | LinkageError absent) {
            // no Ponder: no virtual models
        }
        return ModelData.EMPTY;
    }

    /** Runs body with Flywheel's backend switched off (if Flywheel is present and on), restoring it afterwards. */
    static void withFlywheelOff(Runnable body) {
        Field f = null;
        Object prev = null;
        try {
            Class<?> c = Class.forName("dev.engine_room.flywheel.impl.BackendManagerImpl");
            Field backend = c.getDeclaredField("backend");
            backend.setAccessible(true);
            Object off = c.getField("OFF_BACKEND").get(null);
            Object cur = backend.get(null);
            if (cur != off) {
                backend.set(null, off);
                f = backend;
                prev = cur;
            }
        } catch (ClassNotFoundException absent) {
            // no Flywheel
        } catch (ReflectiveOperationException | RuntimeException | LinkageError ex) {
            if (!flywheelWarned) {
                flywheelWarned = true;
                LOG.warn("ghost: cannot switch Flywheel off for block-entity ghosts, Create kinetics may stay invisible ({})", ex.toString());
            }
        }
        try {
            body.run();
        } finally {
            if (f != null) {
                try {
                    f.set(null, prev);
                } catch (ReflectiveOperationException ex) {
                    LOG.error("ghost: could not restore the Flywheel backend", ex);
                }
            }
        }
    }

    /** The dummy block entity for a ghost block, or null if the block has none or no renderer. Cached per ghost. */
    static BlockEntity dummy(String ghostId, long local, BlockPos world, BlockState st) {
        Block block = st.getBlock();
        if (!(block instanceof EntityBlock eb) || FAILED.contains(block)) return null;
        Long2ObjectMap<BlockEntity> cache = DUMMIES.computeIfAbsent(ghostId, k -> new Long2ObjectOpenHashMap<>());
        BlockEntity be = cache.get(local);
        if (be != null && be.getBlockState() == st && be.getBlockPos().equals(world)) return be;
        try {
            be = eb.newBlockEntity(world.immutable(), st);
            if (be == null) return null;
            be.setLevel(Minecraft.getInstance().level);
            if (Minecraft.getInstance().getBlockEntityRenderDispatcher().getRenderer(be) == null) {
                cache.remove(local);
                return null;
            }
            cache.put(local, be);
            return be;
        } catch (RuntimeException | LinkageError ex) {
            if (FAILED.add(block)) LOG.warn("ghost {}: no dummy block entity for {} ({})", ghostId, st, ex.toString());
            return null;
        }
    }

    /** Draws one dummy through its renderer into cap. False (and the block is logged once and skipped) if it threw. */
    static boolean render(String ghostId, BlockEntity be, PoseStack ps, Capture cap) {
        BlockState st = be.getBlockState();
        BlockEntityRenderer<BlockEntity> r = Minecraft.getInstance().getBlockEntityRenderDispatcher().getRenderer(be);
        if (r == null) return false;
        cap.begin();
        try {
            r.render(be, 0f, ps, cap, 0xF000F0, OverlayTexture.NO_OVERLAY);
            return true;
        } catch (RuntimeException | LinkageError ex) {
            cap.begin(); // drop whatever this block drew halfway
            if (FAILED.add(st.getBlock())) LOG.warn("ghost {}: block-entity renderer failed for {} ({})", ghostId, st, ex.toString());
            return false;
        }
    }

    /** Forget the dummies of ghosts that no longer exist. */
    static void retain(Collection<String> live) {
        DUMMIES.keySet().retainAll(live);
    }

    /** Texture a render type samples, or empty (lines, end portal, custom shaders...: those are not drawn). */
    private static final Map<RenderType, Optional<ResourceLocation>> TEX = new IdentityHashMap<>();

    @SuppressWarnings("unchecked")
    static Optional<ResourceLocation> texture(RenderType rt) {
        return TEX.computeIfAbsent(rt, t -> {
            if (t.mode() != VertexFormat.Mode.QUADS) return Optional.empty();
            try {
                Reflect r = Reflect.get();
                if (r == null || !r.composite.isInstance(t)) return Optional.empty();
                Object state = r.state.invoke(t);
                Object shard = r.textureState.get(state);
                return (Optional<ResourceLocation>) r.cutoutTexture.invoke(shard);
            } catch (ReflectiveOperationException | RuntimeException ex) {
                return Optional.empty();
            }
        });
    }

    /** RenderType internals (Mojang names, which NeoForge 1.21 uses at runtime). Null if they cannot be reached. */
    private record Reflect(Class<?> composite, java.lang.reflect.Method state, Field textureState, java.lang.reflect.Method cutoutTexture) {
        private static Reflect cached;
        private static boolean tried;

        static synchronized Reflect get() {
            if (tried) return cached;
            tried = true;
            try {
                Class<?> comp = Class.forName("net.minecraft.client.renderer.RenderType$CompositeRenderType");
                var state = comp.getDeclaredMethod("state");
                state.setAccessible(true);
                Class<?> cs = Class.forName("net.minecraft.client.renderer.RenderType$CompositeState");
                Field tex = cs.getDeclaredField("textureState");
                tex.setAccessible(true);
                var cut = net.minecraft.client.renderer.RenderStateShard.EmptyTextureStateShard.class.getDeclaredMethod("cutoutTexture");
                cut.setAccessible(true);
                cached = new Reflect(comp, state, tex, cut);
            } catch (ReflectiveOperationException | RuntimeException ex) {
                LOG.warn("ghost: cannot read render type textures, block-entity ghost parts are skipped ({})", ex.toString());
            }
            return cached;
        }
    }

    /**
     * A MultiBufferSource that records quads per (texture, entity-shading) until the current block finished. Entity
     * render types get their face shading baked into the colour (the block shader ghosts use ignores normals).
     */
    static final class Capture implements MultiBufferSource {
        record Key(ResourceLocation tex, boolean shade) {}

        private final Map<Key, VertexRecorder> recs = new LinkedHashMap<>();

        void begin() {
            for (VertexRecorder r : recs.values()) r.reset();
        }

        @Override
        public VertexConsumer getBuffer(RenderType rt) {
            Optional<ResourceLocation> tex = texture(rt);
            if (tex.isEmpty()) return NoopConsumer.INSTANCE;
            Key k = new Key(tex.get(), rt.format() == DefaultVertexFormat.NEW_ENTITY);
            return recs.computeIfAbsent(k, x -> new VertexRecorder());
        }

        /** Hands the finished block's quads to sink (per texture). Returns the number of vertices moved. */
        int flush(java.util.function.Function<ResourceLocation, VertexConsumer> sink) {
            int n = 0;
            for (var en : recs.entrySet()) {
                VertexRecorder r = en.getValue();
                int c = r.size();
                if (c < 4) {
                    r.reset();
                    continue;
                }
                n += c - c % 4;
                r.flushTo(sink.apply(en.getKey().tex()), en.getKey().shade());
            }
            return n;
        }
    }

    /** Swallows vertices of render types ghosts cannot draw. */
    private enum NoopConsumer implements VertexConsumer {
        INSTANCE;

        @Override public VertexConsumer addVertex(float x, float y, float z) { return this; }
        @Override public VertexConsumer setColor(int r, int g, int b, int a) { return this; }
        @Override public VertexConsumer setUv(float u, float v) { return this; }
        @Override public VertexConsumer setUv1(int u, int v) { return this; }
        @Override public VertexConsumer setUv2(int u, int v) { return this; }
        @Override public VertexConsumer setNormal(float x, float y, float z) { return this; }
    }
}
