package dev.watdafawx.mcmcp.ghost;

import java.util.HashMap;
import java.util.HashSet;
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
    private record Baked(int version, int clipY, VertexBuffer vbo, AABB box) {}

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
        if (xray) RenderSystem.clear(org.lwjgl.opengl.GL11.GL_DEPTH_BUFFER_BIT, Minecraft.ON_OSX);
        for (Ghost g : GhostStore.all()) {
            live.add(g.id);
            if (!g.visible || !dim.equals(g.dimension)) continue;
            Baked baked = BAKED.get(g.id);
            if (baked == null || baked.version != g.version || baked.clipY != clipY) {
                if (baked != null && baked.vbo != null) baked.vbo.close();
                baked = bake(g);
                BAKED.put(g.id, baked);
            }
            if (baked.vbo == null) continue;
            BlockPos o = g.origin;
            RenderType rt = RenderType.translucent();
            rt.setupRenderState();
            if (solid || "area".equals(g.tags.get("kind"))) RenderSystem.setShaderColor(1f, 1f, 1f, 1f);
            else RenderSystem.setShaderColor(0.85f, 0.95f, 1f, g.alpha);
            // The camera offset goes in ChunkOffset, like chunk sections: the shader computes fog from
            // Position + ChunkOffset, so a translated model-view would fog ghosts by their distance from their own
            // origin (a ghost set in world coordinates with origin 0,0,0 came out as flat fog-white shapes).
            ShaderInstance sh = GameRenderer.getRendertypeTranslucentShader();
            if (sh.CHUNK_OFFSET != null)
                sh.CHUNK_OFFSET.set((float) (o.getX() - cam.x), (float) (o.getY() - cam.y), (float) (o.getZ() - cam.z));
            baked.vbo.bind();
            baked.vbo.drawWithShader(e.getModelViewMatrix(), e.getProjectionMatrix(), sh);
            VertexBuffer.unbind();
            if (sh.CHUNK_OFFSET != null) sh.CHUNK_OFFSET.set(0f, 0f, 0f);
            RenderSystem.setShaderColor(1f, 1f, 1f, 1f);
            rt.clearRenderState();

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
            if (en.getValue().vbo != null) en.getValue().vbo.close();
            return true;
        });
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
        if (b == null) return new Baked(version, clip, null, new AABB(0, 0, 0, 1, 1, 1));
        AABB box = new AABB(b[0], b[1], b[2], b[3] + 1, b[4] + 1, b[5] + 1);
        Minecraft mc = Minecraft.getInstance();
        BlockRenderDispatcher dispatcher = mc.getBlockRenderer();
        GhostLevel level = new GhostLevel(blocks, g.origin);
        RandomSource rand = RandomSource.create();
        PoseStack ps = new PoseStack();
        try (ByteBufferBuilder bytes = new ByteBufferBuilder(Math.max(1 << 16, blocks.size() * 512))) {
            BufferBuilder bb = new BufferBuilder(bytes, VertexFormat.Mode.QUADS, DefaultVertexFormat.BLOCK);
            BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
            VertexRecorder rec = new VertexRecorder();
            for (var en : blocks.long2ObjectEntrySet()) {
                BlockState st = en.getValue();
                if (st.getRenderShape() != RenderShape.MODEL) continue;
                pos.set(en.getLongKey());
                ps.pushPose();
                ps.translate(pos.getX(), pos.getY(), pos.getZ());
                rand.setSeed(st.getSeed(pos));
                rec.reset();
                try {
                    dispatcher.renderBatched(st, pos, level, ps, rec, true, rand, ModelData.EMPTY, null);
                    rec.flushTo(bb); // only whole, finished blocks reach the mesh
                } catch (RuntimeException ex) {
                    // Some modded models expect real block entity data; skip them rather than break the ghost.
                    if (FAILED.add(st.getBlock())) LOG.warn("ghost {}: skipping {} ({})", g.id, st, ex.toString());
                }
                ps.popPose();
            }
            MeshData mesh = bb.build();
            if (mesh == null) return new Baked(version, clip, null, box);
            VertexBuffer vbo = new VertexBuffer(VertexBuffer.Usage.STATIC);
            vbo.bind();
            vbo.upload(mesh);
            VertexBuffer.unbind();
            return new Baked(version, clip, vbo, box);
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
