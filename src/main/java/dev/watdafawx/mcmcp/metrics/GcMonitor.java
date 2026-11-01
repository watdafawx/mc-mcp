package dev.watdafawx.mcmcp.metrics;

import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.MemoryPoolMXBean;
import java.lang.management.MemoryUsage;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;

import javax.management.NotificationEmitter;
import javax.management.openmbean.CompositeData;

import com.sun.management.GarbageCollectionNotificationInfo;

import dev.watdafawx.mcmcp.mcp.J;

/** Records every GC event the JVM reports, plus heap/JVM snapshots. */
public final class GcMonitor {
    private static final int CAP = 500;
    private static final Deque<Map<String, Object>> EVENTS = new ArrayDeque<>();
    private static boolean installed;

    private GcMonitor() {}

    public static synchronized void install() {
        if (installed) return;
        installed = true;
        for (GarbageCollectorMXBean gc : ManagementFactory.getGarbageCollectorMXBeans()) {
            if (!(gc instanceof NotificationEmitter emitter)) continue;
            emitter.addNotificationListener((n, h) -> {
                if (!GarbageCollectionNotificationInfo.GARBAGE_COLLECTION_NOTIFICATION.equals(n.getType())) return;
                GarbageCollectionNotificationInfo info = GarbageCollectionNotificationInfo.from((CompositeData) n.getUserData());
                long before = 0, after = 0;
                for (MemoryUsage u : info.getGcInfo().getMemoryUsageBeforeGc().values()) before += u.getUsed();
                for (MemoryUsage u : info.getGcInfo().getMemoryUsageAfterGc().values()) after += u.getUsed();
                Map<String, Object> e = J.obj(
                        "at_ms", System.currentTimeMillis(),
                        "gc", info.getGcName(),
                        "action", info.getGcAction(),
                        "cause", info.getGcCause(),
                        "duration_ms", info.getGcInfo().getDuration(),
                        // ZGC/Shenandoah "Cycles" beans are concurrent work, not stop-the-world pauses
                        "pause", !info.getGcName().contains("Cycles"),
                        "freed_mb", (before - after) / (1024 * 1024));
                synchronized (EVENTS) {
                    EVENTS.addLast(e);
                    while (EVENTS.size() > CAP) EVENTS.removeFirst();
                }
            }, null, null);
        }
    }

    public static Map<String, Object> snapshot(int seconds, boolean details) {
        MemoryMXBean mem = ManagementFactory.getMemoryMXBean();
        MemoryUsage heap = mem.getHeapMemoryUsage();
        MemoryUsage nonHeap = mem.getNonHeapMemoryUsage();
        long cutoff = System.currentTimeMillis() - seconds * 1000L;
        List<Map<String, Object>> recent = new ArrayList<>();
        long pauseCount = 0, pauseTotal = 0, pauseMax = 0, cycles = 0, cycleMs = 0;
        synchronized (EVENTS) {
            for (Map<String, Object> e : EVENTS) {
                if ((long) e.get("at_ms") < cutoff) continue;
                recent.add(e);
                long d = (long) e.get("duration_ms");
                if ((boolean) e.get("pause")) {
                    pauseCount++;
                    pauseTotal += d;
                    pauseMax = Math.max(pauseMax, d);
                } else {
                    cycles++;
                    cycleMs += d;
                }
            }
        }
        if (recent.size() > 30) recent = new ArrayList<>(recent.subList(recent.size() - 30, recent.size()));
        double cpu = -1;
        if (ManagementFactory.getOperatingSystemMXBean() instanceof com.sun.management.OperatingSystemMXBean os)
            cpu = os.getProcessCpuLoad();
        Map<String, Object> out = J.obj(
                "heap_used_mb", heap.getUsed() >> 20,
                "heap_committed_mb", heap.getCommitted() >> 20,
                "heap_max_mb", heap.getMax() >> 20,
                "non_heap_used_mb", nonHeap.getUsed() >> 20,
                "process_cpu_load", J.r2(cpu),
                "cpus", Runtime.getRuntime().availableProcessors(),
                "threads", ManagementFactory.getThreadMXBean().getThreadCount(),
                "uptime_s", ManagementFactory.getRuntimeMXBean().getUptime() / 1000,
                "window_s", seconds,
                "gc_pauses_in_window", J.obj("count", pauseCount, "total_ms", pauseTotal, "max_ms", pauseMax),
                "gc_concurrent_cycles_in_window", J.obj("count", cycles, "total_ms", cycleMs),
                "recent_gc_events", recent,
                "jvm", System.getProperty("java.vm.name") + " " + System.getProperty("java.version"));
        if (details) {
            List<Map<String, Object>> collectors = new ArrayList<>();
            for (GarbageCollectorMXBean gc : ManagementFactory.getGarbageCollectorMXBeans())
                collectors.add(J.obj("name", gc.getName(), "count", gc.getCollectionCount(), "total_ms", gc.getCollectionTime()));
            List<Map<String, Object>> pools = new ArrayList<>();
            for (MemoryPoolMXBean p : ManagementFactory.getMemoryPoolMXBeans()) {
                MemoryUsage u = p.getUsage();
                if (u == null) continue;
                pools.add(J.obj("name", p.getName(), "type", p.getType().toString(), "used_mb", u.getUsed() >> 20,
                        "max_mb", u.getMax() < 0 ? -1 : u.getMax() >> 20));
            }
            out.put("collectors", collectors);
            out.put("memory_pools", pools);
            out.put("jvm_args", ManagementFactory.getRuntimeMXBean().getInputArguments());
        }
        return out;
    }
}
