package dev.watdafawx.mcmcp;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.function.Supplier;

import net.minecraft.util.thread.BlockableEventLoop;

import dev.watdafawx.mcmcp.mcp.McpServer;

/** Runs a read on the game's own thread and waits for it from an HTTP worker thread. */
public final class GameThread {
    private GameThread() {}

    public static <T> T call(BlockableEventLoop<?> loop, Supplier<T> work) {
        return call(loop, work, 10);
    }

    public static <T> T call(BlockableEventLoop<?> loop, Supplier<T> work, int timeoutSeconds) {
        if (loop == null) throw new McpServer.ToolError("game thread not available");
        if (loop.isSameThread()) return work.get();
        CompletableFuture<T> f = loop.submit(work);
        try {
            return f.get(timeoutSeconds, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new McpServer.ToolError("game thread did not answer within " + timeoutSeconds + " s (frozen or loading?)");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new McpServer.ToolError("interrupted");
        } catch (java.util.concurrent.ExecutionException e) {
            Throwable c = e.getCause();
            if (c instanceof RuntimeException re) throw re;
            throw new RuntimeException(c);
        }
    }
}
