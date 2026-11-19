package dev.watdafawx.mcmcp.ghost;

import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.ArrayList;
import java.util.function.Function;
import java.util.Map;
import java.util.Set;


import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.ByteBufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.MeshData;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexBuffer;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;

import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.client.renderer.block.BlockRenderDispatcher;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.ColorResolver;
import net.minecraft.world.level.LightLayer;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.lighting.LevelLightEngine;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.client.event.RenderLevelStageEvent;
import net.neoforged.neoforge.client.model.data.ModelData;
import net.neoforged.neoforge.common.NeoForge;

/** Draws every visible ghost as see-through blocks plus a bounding box. Meshes are rebuilt only when a ghost changes. */
public final class GhostRenderer {
    /** A mesh drawn with one texture: block-entity quads from chest, sign, banner... sheets. */
    private record Part(ResourceLocation tex, VertexBuffer vbo) {}

    private record Baked(int version, int clipY, VertexBuffer vbo, List<Part> parts, AABB box) {
        void close() {
            if (vbo != null) vbo.close();
            for (Part p : parts) p.vbo.close();
        }

        boolean empty() {
            return vbo == null && parts.isEmpty();
        }
    }

    private static final Map<String, Baked> BAKED = new HashMap<>();
    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger("mcmcp-ghost");
    private static final Set<net.minecraft.world.level.block.Block> FAILED = java.util.concurrent.ConcurrentHashMap.newKeySet();
    /** Draw ghosts over the world: terrain can't hide them, but they still hide their own back faces. */
    public static volatile boolean xray;
    /** Full opacity and no tint, for screenshots that should show the design itself. */
    public static volatile boolean solid;
    /** Cutaway: blocks above this world y are not drawn (Integer.MAX_VALUE = off), to look into rooms from above. */
    public static volatile int clipY = Integer.MAX_VALUE;

    private GhostRenderer() {}

    public static void init() {
        NeoForge.EVENT_BUS.addListener(GhostRenderer::onRender);
    }

    private static void onRender(RenderLevelStageEvent e) {
        if (e.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null) return;
        String dim = mc.level.dimension().location().toString();
        Vec3 cam = e.getCamera().getPosition();
        Set<String> live = new HashSet<>();
        for (Ghost g : GhostStore.all()) {
            live.add(g.id);
            if (!g.visible || !dim.equals(g.dimension)) continue;
            Baked baked = BAKED.get(g.id);
            if (baked == null || baked.version != g.version || baked.clipY != clipY) {
                if (baked != null) baked.close();
                baked = bake(g);
                BAKED.put(g.id, baked);
            }
            if (baked.empty()) continue;
            BlockPos o = g.origin;
            RenderType rt = RenderType.translucent();
            rt.setupRenderState();
            // Xray: ignore terrain depth by turning the depth test and depth writes off for this draw. The depth buffer
            // is never cleared or written, so later stages (particles, weather, hand) still depth-test against terrain.
            if (xray) {
                RenderSystem.disableDepthTest();
                RenderSystem.depthMask(false);
            }
            if (solid || "area".equals(g.tags.get("kind"))) RenderSystem.setShaderColor(1f, 1f, 1f, 1f);
            else RenderSystem.setShaderColor(0.85f, 0.95f, 1f, g.alpha);
            // The camera offset goes in ChunkOffset, like chunk sections: the shader computes fog from
            // Position + ChunkOffset, so a translated model-view would fog ghosts by their distance from their own
            // origin (a ghost set in world coordinates with origin 0,0,0 came out as flat fog-white shapes).
            ShaderInstance sh = GameRenderer.getRendertypeTranslucentShader();
            if (sh.CHUNK_OFFSET != null)
                sh.CHUNK_OFFSET.set((float) (o.getX() - cam.x), (float) (o.getY() - cam.y), (float) (o.getZ() - cam.z));
            if (baked.vbo != null) {
                baked.vbo.bind();
                baked.vbo.drawWithShader(e.getModelViewMatrix(), e.getProjectionMatrix(), sh);
            }
            for (Part p : baked.parts) {
                RenderSystem.setShaderTexture(0, p.tex);
                p.vbo.bind();
                p.vbo.drawWithShader(e.getModelViewMatrix(), e.getProjectionMatrix(), sh);
            }
            VertexBuffer.unbind();
            if (!baked.parts.isEmpty()) RenderSystem.setShaderTexture(0, TextureAtlas.LOCATION_BLOCKS);
            if (sh.CHUNK_OFFSET != null) sh.CHUNK_OFFSET.set(0f, 0f, 0f);
            RenderSystem.setShaderColor(1f, 1f, 1f, 1f);
            rt.clearRenderState();
            restoreDepth();

            if (mc.options.hideGui) continue; // HUD off (F1 / ghost_show hud=false): clean shots, no outline box
            MultiBufferSource.BufferSource buf = mc.renderBuffers().bufferSource();
            VertexConsumer lines = buf.getBuffer(RenderType.lines());
            // RenderSystem's model-view stack already holds the camera rotation in 1.21; an identity pose is right here.
            PoseStack ps = new PoseStack();
            LevelRenderer.renderLineBox(ps, lines, baked.box.move(o.getX() - cam.x, o.getY() - cam.y, o.getZ() - cam.z),
                    0.55f, 0.35f, 1f, 0.9f);
            buf.endBatch(RenderType.lines());
        }
        BAKED.entrySet().removeIf(en -> {
            if (live.contains(en.getKey())) return false;
            en.getValue().close();
            return true;
        });
        GhostBlockEntities.retain(live);
    }

    /** Exact vanilla state after the translucent pass: depth test on, LEQUAL, depth writes on. */
    private static void restoreDepth() {
        RenderSystem.enableDepthTest();
        RenderSystem.depthFunc(org.lwjgl.opengl.GL11.GL_LEQUAL);
        RenderSystem.depthMask(true);
    }

    private static Baked bake(Ghost g) {
        int clip = clipY;
        Long2ObjectMap<BlockState> blocks;
        int version;
        int[] b;
        synchronized (GhostStore.LOCK) {
            blocks = new Long2ObjectOpenHashMap<>(g.blocks);
            version = g.version;
            b = g.bounds();
        }
        if (clip != Integer.MAX_VALUE) { // drop blocks above the cut, also from the cull level so cut faces are drawn
            int localMax = clip - g.origin.getY();
            blocks.long2ObjectEntrySet().removeIf(en -> BlockPos.getY(en.getLongKey()) > localMax);
        }
        if (b == null) return new Baked(version, clip, null, List.of(), new AABB(0, 0, 0, 1, 1, 1));
        AABB box = new AABB(b[0], b[1], b[2], b[3] + 1, b[4] + 1, b[5] + 1);
        Minecraft mc = Minecraft.getInstance();
        BlockRenderDispatcher dispatcher = mc.getBlockRenderer();
        GhostLevel level = new GhostLevel(blocks, g.origin);
        RandomSource rand = RandomSource.create();
        PoseStack ps = new PoseStack();
        boolean bes = GhostBlockEntities.enabled() && mc.level != null;
        Map<ResourceLocation, ByteBufferBuilder> extraBytes = new LinkedHashMap<>();
        Map<ResourceLocation, BufferBuilder> extra = new LinkedHashMap<>();
        try (ByteBufferBuilder bytes = new ByteBufferBuilder(Math.max(1 << 16, blocks.size() * 512))) {
            BufferBuilder bb = new BufferBuilder(bytes, VertexFormat.Mode.QUADS, DefaultVertexFormat.BLOCK);
            // Block-entity quads on the block atlas join the main mesh; other sheets (chest, sign...) get their own.
            Function<ResourceLocation, VertexConsumer> sink = tex -> tex.equals(TextureAtlas.LOCATION_BLOCKS) ? bb
                    : extra.computeIfAbsent(tex, t -> {
                        ByteBufferBuilder by = new ByteBufferBuilder(1 << 14);
                        extraBytes.put(t, by);
                        return new BufferBuilder(by, VertexFormat.Mode.QUADS, DefaultVertexFormat.BLOCK);
                    });
            Runnable draw = () -> {
                BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
                BlockPos.MutableBlockPos world = new BlockPos.MutableBlockPos();
                VertexRecorder rec = new VertexRecorder();
                GhostBlockEntities.Capture cap = bes ? new GhostBlockEntities.Capture() : null;
                for (var en : blocks.long2ObjectEntrySet()) {
                    BlockState st = en.getValue();
                    RenderShape shape = st.getRenderShape();
                    // INVISIBLE blocks can still have a renderer (BaseEntityBlock default: signs, banners, skulls).
                    if (shape != RenderShape.MODEL && !bes) continue;
                    pos.set(en.getLongKey());
                    ps.pushPose();
                    ps.translate(pos.getX(), pos.getY(), pos.getZ());
                    // Block-entity renderer (chest, sign, Create shaft/cog/belt...) through a client-only dummy.
                    int beVerts = 0;
                    boolean hasBe = false;
                    if (bes) {
                        world.setWithOffset(pos, g.origin);
                        BlockEntity be = GhostBlockEntities.dummy(g.id, en.getLongKey(), world, st);
                        if (be != null) {
                            hasBe = true;
                            if (GhostBlockEntities.render(g.id, be, ps, cap)) beVerts = cap.flush(sink);
                        }
                    }
                    // Block model: always for MODEL blocks; for animated ones only when their renderer drew nothing.
                    if (shape == RenderShape.MODEL || (shape == RenderShape.ENTITYBLOCK_ANIMATED && beVerts == 0)) {
                        int n = model(g, dispatcher, st, pos, level, ps, rec, rand, bb, ModelData.EMPTY);
                        // Create's kinetic models (shaft, cogwheel...) are empty unless asked for their "virtual" model.
                        if (n == 0 && hasBe && beVerts == 0 && GhostBlockEntities.VIRTUAL != ModelData.EMPTY)
                            model(g, dispatcher, st, pos, level, ps, rec, rand, bb, GhostBlockEntities.VIRTUAL);
                    }
                    ps.popPose();
                }
            };
            if (bes) GhostBlockEntities.withFlywheelOff(draw);
            else draw.run();
            List<Part> parts = new ArrayList<>();
            for (var en : extra.entrySet()) {
                MeshData m = en.getValue().build();
                if (m != null) parts.add(new Part(en.getKey(), upload(m)));
            }
            MeshData mesh = bb.build();
            return new Baked(version, clip, mesh == null ? null : upload(mesh), parts, box);
        } finally {
            for (ByteBufferBuilder by : extraBytes.values()) by.close();
        }
    }

    private static VertexBuffer upload(MeshData mesh) {
        VertexBuffer vbo = new VertexBuffer(VertexBuffer.Usage.STATIC);
        vbo.bind();
        vbo.upload(mesh);
        VertexBuffer.unbind();
        return vbo;
    }

    /** Bakes one block model into bb; returns the vertices it added (0 if empty or it threw). */
    private static int model(Ghost g, BlockRenderDispatcher dispatcher, BlockState st, BlockPos pos, GhostLevel level,
            PoseStack ps, VertexRecorder rec, RandomSource rand, BufferBuilder bb, ModelData data) {
        rand.setSeed(st.getSeed(pos));
        rec.reset();
        try {
            dispatcher.renderBatched(st, pos, level, ps, rec, true, rand, data, null);
            int n = rec.size() - rec.size() % 4;
            rec.flushTo(bb); // only whole, finished blocks reach the mesh
            return n;
        } catch (RuntimeException ex) {
            // Some modded models expect real block entity data; skip them rather than break the ghost.
            if (FAILED.add(st.getBlock())) LOG.warn("ghost {}: skipping {} ({})", g.id, st, ex.toString());
            rec.reset();
            return 0;
        }
    }

    /** The ghost's own blocks as a level: neighbours cull faces, light is full bright, tint comes from the real biome. */
    private record GhostLevel(Long2ObjectMap<BlockState> blocks, BlockPos origin) implements BlockAndTintGetter {
        @Override public float getShade(Direction d, boolean shade) {
            var l = Minecraft.getInstance().level;
            return l != null ? l.getShade(d, shade) : 1f;
        }
        @Override public LevelLightEngine getLightEngine() { return Minecraft.getInstance().level.getLightEngine(); }
        @Override public int getBlockTint(BlockPos pos, ColorResolver r) {
            var l = Minecraft.getInstance().level;
            return l != null ? l.getBlockTint(pos.offset(origin), r) : -1;
        }
        @Override public int getBrightness(LightLayer layer, BlockPos pos) { return 15; }
        @Override public int getRawBrightness(BlockPos pos, int amount) { return 15; }
        @Override public BlockEntity getBlockEntity(BlockPos pos) { return null; }
        @Override public BlockState getBlockState(BlockPos pos) {
            BlockState s = blocks.get(pos.asLong());
            return s != null ? s : Blocks.AIR.defaultBlockState();
        }
        @Override public FluidState getFluidState(BlockPos pos) { return getBlockState(pos).getFluidState(); }
        @Override public int getHeight() { return 4096; }
        @Override public int getMinBuildHeight() { return -2048; }
    }
}
