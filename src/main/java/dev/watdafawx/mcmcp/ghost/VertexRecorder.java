package dev.watdafawx.mcmcp.ghost;

import java.util.Arrays;

import com.mojang.blaze3d.vertex.VertexConsumer;

/**
 * Holds one block's vertices until its model has rendered without throwing, then copies them to the real buffer.
 * A model that throws halfway through a quad would otherwise leave a partial quad in the BufferBuilder, shifting every
 * later vertex and turning the whole ghost into untextured white shapes.
 */
final class VertexRecorder implements VertexConsumer {
    private static final int STRIDE = 11; // x y z color u v overlay light nx ny nz
    private int[] data = new int[STRIDE * 64];
    private int count; // vertices
    private int cur = -1;

    void reset() {
        count = 0;
        cur = -1;
    }

    int size() {
        return count;
    }

    /** Copies the recorded whole quads to out. */
    void flushTo(VertexConsumer out) {
        flushTo(out, false);
    }

    /**
     * Copies the recorded whole quads to out. shade: multiply the colour by vanilla's directional face shade from the
     * normal (up 1, down 0.5, north/south 0.8, east/west 0.6), for entity models drawn with a shader that has no lighting.
     */
    void flushTo(VertexConsumer out, boolean shade) {
        int n = count - count % 4;
        for (int i = 0; i < n; i++) {
            int o = i * STRIDE;
            int color = data[o + 3];
            if (shade) color = shade(color, f(o + 8), f(o + 9), f(o + 10));
            out.addVertex(f(o), f(o + 1), f(o + 2), color, f(o + 4), f(o + 5), data[o + 6], data[o + 7],
                    f(o + 8), f(o + 9), f(o + 10));
        }
        reset();
    }

    private static int shade(int argb, float nx, float ny, float nz) {
        float len = nx * nx + ny * ny + nz * nz;
        if (len < 1e-6f) return argb;
        float s = (nx * nx * 0.6f + ny * ny * (ny > 0 ? 1f : 0.5f) + nz * nz * 0.8f) / len;
        int r = Math.round(((argb >> 16) & 255) * s), g = Math.round(((argb >> 8) & 255) * s), b = Math.round((argb & 255) * s);
        return argb & 0xFF000000 | r << 16 | g << 8 | b;
    }

    private float f(int i) {
        return Float.intBitsToFloat(data[i]);
    }

    @Override
    public VertexConsumer addVertex(float x, float y, float z) {
        if ((count + 1) * STRIDE > data.length) data = Arrays.copyOf(data, data.length * 2);
        cur = count++ * STRIDE;
        data[cur] = Float.floatToRawIntBits(x);
        data[cur + 1] = Float.floatToRawIntBits(y);
        data[cur + 2] = Float.floatToRawIntBits(z);
        data[cur + 3] = -1;
        data[cur + 4] = 0;
        data[cur + 5] = 0;
        data[cur + 6] = 0;
        data[cur + 7] = 0xF000F0;
        data[cur + 8] = 0;
        data[cur + 9] = Float.floatToRawIntBits(1f);
        data[cur + 10] = 0;
        return this;
    }

    @Override
    public VertexConsumer setColor(int r, int g, int b, int a) {
        if (cur >= 0) data[cur + 3] = (a & 255) << 24 | (r & 255) << 16 | (g & 255) << 8 | (b & 255);
        return this;
    }

    @Override
    public VertexConsumer setUv(float u, float v) {
        if (cur >= 0) {
            data[cur + 4] = Float.floatToRawIntBits(u);
            data[cur + 5] = Float.floatToRawIntBits(v);
        }
        return this;
    }

    @Override
    public VertexConsumer setUv1(int u, int v) {
        if (cur >= 0) data[cur + 6] = (u & 0xFFFF) | (v & 0xFFFF) << 16;
        return this;
    }

    @Override
    public VertexConsumer setUv2(int u, int v) {
        if (cur >= 0) data[cur + 7] = (u & 0xFFFF) | (v & 0xFFFF) << 16;
        return this;
    }

    @Override
    public VertexConsumer setNormal(float x, float y, float z) {
        if (cur >= 0) {
            data[cur + 8] = Float.floatToRawIntBits(x);
            data[cur + 9] = Float.floatToRawIntBits(y);
            data[cur + 10] = Float.floatToRawIntBits(z);
        }
        return this;
    }
}
