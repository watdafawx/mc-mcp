package dev.watdafawx.mcmcp.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import net.minecraft.client.Camera;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.BlockGetter;

import dev.watdafawx.mcmcp.ghost.GhostCamera;

/** Positions the client camera at {@link GhostCamera} when FreeCam screenshot mode is active (no cheats/teleport). */
@Mixin(Camera.class)
public abstract class CameraMixin {
    @Shadow private boolean detached;
    @Shadow protected abstract void setPosition(double x, double y, double z);
    @Shadow protected abstract void setRotation(float yRot, float xRot);

    @Inject(method = "setup", at = @At("TAIL"))
    private void mcmcp$ghostCamera(BlockGetter level, Entity entity, boolean detached, boolean thirdPersonReverse,
            float partialTick, CallbackInfo ci) {
        if (!GhostCamera.active) return;
        this.detached = true;
        this.setRotation(GhostCamera.yaw, GhostCamera.pitch);
        this.setPosition(GhostCamera.x, GhostCamera.y, GhostCamera.z);
    }
}
