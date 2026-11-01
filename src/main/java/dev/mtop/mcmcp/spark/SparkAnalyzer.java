package dev.mtop.mcmcp.spark;

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import dev.mtop.mcmcp.mcp.J;
import dev.mtop.mcmcp.mcp.McpServer;

/**
 * Turns a saved {@code .sparkprofile} (spark's own protobuf, {@code SamplerData}) into JSON: the
 * per-thread call tree, self time per mod, hot methods and their callers. The protobuf classes are
 * spark's own, reached by reflection so nothing here links against spark.
 */
public final class SparkAnalyzer {
    private SparkAnalyzer() {}

    /** One frame of a call tree. */
    static final class Node {
        String cls, method, desc;
        int line;
        double time, raw, active;
        List<Node> children = new ArrayList<>();
        String key() { return cls + "." + method; }
    }

    static final class Thread {
        final String name;
        final List<Node> roots;
        double time, raw, active;
        Thread(String name, double raw, List<Node> roots) { this.name = name; this.raw = raw; this.time = raw; this.roots = roots; }
    }

    /**
     * Frames where a thread waits rather than works (the whole subtree counts as idle): parking,
     * sleeping, blocking IO, the frame limiter's event wait, and spark's own thread dumps.
     */
    private static boolean idle(Node n) {
        String k = n.key();
        return k.equals("jdk.internal.misc.Unsafe.park") || k.startsWith("java.lang.Thread.sleep") || k.startsWith("java.lang.Thread.yield")
                || k.startsWith("java.lang.Object.wait") || k.equals("java.lang.ref.Reference.waitForReferencePendingList")
                || k.contains("GetQueuedCompletionStatus") || k.contains("WEPoll.wait") || k.endsWith(".poll0") || k.endsWith(".accept0")
                || k.equals("sun.nio.ch.Net.poll") || k.endsWith("SocketDispatcher.read0") || k.endsWith("Iocp.getQueuedCompletionStatus")
                || k.equals("org.lwjgl.glfw.GLFW.glfwWaitEventsTimeout") || k.equals("org.lwjgl.glfw.GLFW.glfwWaitEvents")
                || k.startsWith("sun.management.ThreadImpl.dumpThreads") || k.startsWith("sun.management.ThreadImpl.getThreadInfo")
                || k.equals("java.lang.ProcessImpl.waitForInterruptibly") || k.equals("java.lang.ProcessImpl.waitFor");
    }

    private static double computeActive(Node n, int depth) {
        if (idle(n)) {
            zero(n, depth);
            return 0;
        }
        double childRaw = 0, childActive = 0;
        if (depth < 400) for (Node c : n.children) { childRaw += c.raw; childActive += computeActive(c, depth + 1); }
        n.active = childActive + Math.max(0, n.raw - childRaw);
        return n.active;
    }

    private static void zero(Node n, int depth) {
        n.active = 0;
        if (depth < 400) for (Node c : n.children) zero(c, depth + 1);
    }

    private static void useTimes(Node n, boolean includeIdle, int depth) {
        n.time = includeIdle ? n.raw : n.active;
        if (depth < 400) for (Node c : n.children) useTimes(c, includeIdle, depth + 1);
    }

    public record Profile(Path file, Map<String, Object> meta, List<Thread> threads,
                          Map<String, String> classSources, Map<String, String> methodSources, Map<String, String> lineSources) {}

    public static Profile load(Path file) throws Exception {
        Class<?> dataCls = Class.forName("me.lucko.spark.proto.SparkSamplerProtos$SamplerData");
        Object data = dataCls.getMethod("parseFrom", byte[].class).invoke(null, (Object) Files.readAllBytes(file));
        List<?> threadMsgs = (List<?>) call(data, "getThreadsList");
        List<Thread> threads = new ArrayList<>();
        for (Object t : threadMsgs) {
            List<?> flat = (List<?>) call(t, "getChildrenList");
            List<?> refs = (List<?>) call(t, "getChildrenRefsList");
            List<Node> roots = new ArrayList<>();
            if (refs != null && !refs.isEmpty()) {
                // Current format: one flat node list per thread; children are indices into it.
                Node[] built = new Node[flat.size()];
                for (Object r : refs) roots.add(buildFlat(flat, ((Number) r).intValue(), built, 0));
            } else {
                for (Object c : flat) roots.add(buildNested(c, 0));
            }
            double time = sumTimes(t);
            if (time <= 0) for (Node r : roots) time += r.raw;
            Thread th = new Thread((String) call(t, "getName"), time, roots);
            double childRaw = 0;
            for (Node r : roots) { childRaw += r.raw; th.active += computeActive(r, 0); }
            th.active += Math.max(0, time - childRaw);
            threads.add(th);
        }
        Map<String, Object> meta = new HashMap<>();
        Object md = call(data, "getMetadata");
        if (md != null) {
            for (String g : new String[] {"getStartTime", "getEndTime", "getInterval", "getNumberOfTicks", "getComment"}) {
                Object v = call(md, g);
                if (v != null) meta.put(g.substring(3).toLowerCase(Locale.ROOT), v);
            }
            Object user = call(md, "getCreator");
            if (user != null) meta.put("creator", call(user, "getName"));
            Object platform = call(md, "getPlatformMetadata");
            if (platform != null) meta.put("platform", call(platform, "getName") + " " + call(platform, "getVersion"));
            Object dumper = call(md, "getThreadDumper");
            if (dumper != null) meta.put("thread_dumper", String.valueOf(call(dumper, "getType")) + " " + call(dumper, "getPatternsList"));
        }
        return new Profile(file, meta, threads,
                map(call(data, "getClassSourcesMap")), map(call(data, "getMethodSourcesMap")), map(call(data, "getLineSourcesMap")));
    }

    private static Node buildFlat(List<?> flat, int idx, Node[] built, int depth) throws Exception {
        if (built[idx] != null) return built[idx];
        Object m = flat.get(idx);
        Node n = fill(m);
        built[idx] = n;
        if (depth < 400)
            for (Object r : (List<?>) call(m, "getChildrenRefsList"))
                n.children.add(buildFlat(flat, ((Number) r).intValue(), built, depth + 1));
        return n;
    }

    private static Node buildNested(Object m, int depth) throws Exception {
        Node n = fill(m);
        if (depth < 400)
            for (Object c : (List<?>) call(m, "getChildrenList")) n.children.add(buildNested(c, depth + 1));
        return n;
    }

    private static Node fill(Object m) throws Exception {
        Node n = new Node();
        n.cls = (String) call(m, "getClassName");
        n.method = (String) call(m, "getMethodName");
        n.desc = (String) call(m, "getMethodDesc");
        Object line = call(m, "getLineNumber");
        n.line = line instanceof Number num ? num.intValue() : 0;
        n.raw = sumTimes(m);
        n.time = n.raw;
        return n;
    }

    private static double sumTimes(Object m) throws Exception {
        double s = 0;
        Object list = call(m, "getTimesList");
        if (list instanceof List<?> l) for (Object v : l) s += ((Number) v).doubleValue();
        if (s == 0) {
            Object t = call(m, "getTime");
            if (t instanceof Number num) s = num.doubleValue();
        }
        return s;
    }

    private static Object call(Object o, String name) {
        try {
            Method m = o.getClass().getMethod(name);
            return m.invoke(o);
        } catch (Exception e) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> map(Object o) {
        return o instanceof Map<?, ?> m ? (Map<String, String>) m : Collections.emptyMap();
    }

    // ------------------------------------------------------------------ analysis

    public static synchronized Map<String, Object> analyze(Profile p, String threadFilter, int top, double minPct, int maxDepth, boolean tree, boolean includeIdle) {
        for (Thread t : p.threads()) {
            t.time = includeIdle ? t.raw : t.active;
            for (Node r : t.roots) useTimes(r, includeIdle, 0);
        }
        p.threads().sort((a, b) -> Double.compare(b.time, a.time));
        List<Map<String, Object>> threadList = new ArrayList<>();
        double all = 0;
        for (Thread t : p.threads()) all += t.time;
        for (Thread t : p.threads()) {
            if (threadList.size() >= 25) break;
            threadList.add(J.obj("name", t.name, "time_ms", J.r1(t.time), "raw_ms", J.r1(t.raw), "pct_of_samples", J.r1(100 * t.time / Math.max(all, 1e-9))));
        }
        List<Thread> chosen = choose(p, threadFilter);
        double chosenTotal = 0;
        for (Thread t : chosen) chosenTotal += t.time;
        chosenTotal = Math.max(chosenTotal, 1e-9);

        Map<String, Double> modSelf = new HashMap<>();
        Map<String, Double> modIncl = new HashMap<>();
        Map<String, double[]> methodSelf = new HashMap<>();
        Map<String, String> methodMod = new HashMap<>();
        Map<String, Map<String, Double>> callers = new HashMap<>();
        for (Thread t : chosen)
            for (Node r : t.roots) walk(p, r, null, new HashSet<>(), modSelf, modIncl, methodSelf, methodMod, callers, 0);

        List<Map<String, Object>> mods = new ArrayList<>();
        List<Map.Entry<String, Double>> me = new ArrayList<>(modSelf.entrySet());
        me.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
        for (Map.Entry<String, Double> e : me) {
            if (mods.size() >= top) break;
            mods.add(J.obj("mod", e.getKey(), "self_ms", J.r1(e.getValue()), "self_pct", J.r1(100 * e.getValue() / chosenTotal),
                    "inclusive_pct", J.r1(100 * modIncl.getOrDefault(e.getKey(), 0.0) / chosenTotal)));
        }
        List<Map.Entry<String, double[]>> hm = new ArrayList<>(methodSelf.entrySet());
        hm.sort((a, b) -> Double.compare(b.getValue()[0], a.getValue()[0]));
        List<Map<String, Object>> hot = new ArrayList<>();
        for (Map.Entry<String, double[]> e : hm) {
            if (hot.size() >= top) break;
            Map<String, Double> cs = callers.getOrDefault(e.getKey(), Map.of());
            List<Map.Entry<String, Double>> cl = new ArrayList<>(cs.entrySet());
            cl.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
            List<String> topCallers = new ArrayList<>();
            for (int i = 0; i < cl.size() && i < 4; i++)
                topCallers.add(J.r1(100 * cl.get(i).getValue() / Math.max(e.getValue()[1], 1e-9)) + "% " + cl.get(i).getKey());
            hot.add(J.obj("method", e.getKey(), "mod", methodMod.get(e.getKey()), "self_ms", J.r1(e.getValue()[0]),
                    "self_pct", J.r2(100 * e.getValue()[0] / chosenTotal), "total_pct", J.r1(100 * e.getValue()[1] / chosenTotal),
                    "callers", topCallers));
        }

        Map<String, Object> out = J.obj(
                "file", p.file().getFileName().toString(),
                "meta", p.meta(),
                "threads", threadList,
                "analyzed_threads", chosen.stream().map(t -> t.name).toList(),
                "analyzed_time_ms", J.r1(chosenTotal),
                "mods_by_self_time", mods,
                "hot_methods", hot);
        if (tree) {
            List<Object> trees = new ArrayList<>();
            for (Thread t : chosen) {
                List<String> lines = new ArrayList<>();
                for (Node r : sorted(t.roots)) printTree(p, r, t.time, minPct, maxDepth, 0, lines);
                if (lines.size() > 400) {
                    int more = lines.size() - 400;
                    lines = new ArrayList<>(lines.subList(0, 400));
                    lines.add("... " + more + " more lines (raise min_pct or lower max_depth)");
                }
                trees.add(J.obj("thread", t.name, "time_ms", J.r1(t.time), "tree", lines));
            }
            out.put("trees", trees);
            out.put("tree_format", "pct-of-thread  self-pct  frame [mod]; chains with one significant child are joined by ' > ' (long chains elided)");
        }
        out.put("note", "times in ms of samples. self = time in the frame itself; inclusive = time under any frame of that mod. "
                + (includeIdle ? "Idle (park/sleep/wait) time included." : "Idle time (park/sleep/wait/poll) excluded; raw_ms includes it. include_idle=true to keep it."));
        return out;
    }

    private static List<Thread> choose(Profile p, String filter) {
        List<Thread> out = new ArrayList<>();
        if (filter != null && !filter.isBlank() && !filter.equals("*")) {
            String f = filter.toLowerCase(Locale.ROOT);
            for (Thread t : p.threads()) if (t.name.toLowerCase(Locale.ROOT).contains(f)) out.add(t);
            if (out.isEmpty()) throw new McpServer.ToolError("no thread matching '" + filter + "'");
            return out;
        }
        if (filter != null && filter.equals("*")) return p.threads();
        // Default: the main game threads if present, else the busiest one.
        for (Thread t : p.threads())
            if (t.name.equals("Render thread") || t.name.equals("Server thread")) out.add(t);
        if (out.isEmpty() && !p.threads().isEmpty()) out.add(p.threads().get(0));
        return out;
    }

    private static void walk(Profile p, Node n, Node parent, Set<String> modsOnPath,
                             Map<String, Double> modSelf, Map<String, Double> modIncl,
                             Map<String, double[]> methodSelf, Map<String, String> methodMod,
                             Map<String, Map<String, Double>> callers, int depth) {
        double childSum = 0;
        for (Node c : n.children) childSum += c.time;
        double self = Math.max(0, n.time - childSum);
        String mod = modOf(p, n);
        modSelf.merge(mod, self, Double::sum);
        boolean first = modsOnPath.add(mod);
        if (first) modIncl.merge(mod, n.time, Double::sum);
        String key = n.key();
        double[] acc = methodSelf.computeIfAbsent(key, k -> new double[2]);
        acc[0] += self;
        acc[1] += n.time; // may double count recursion; fine for ranking
        methodMod.putIfAbsent(key, mod);
        if (parent != null)
            callers.computeIfAbsent(key, k -> new HashMap<>()).merge(parent.key(), n.time, Double::sum);
        if (depth < 400)
            for (Node c : n.children) walk(p, c, n, modsOnPath, modSelf, modIncl, methodSelf, methodMod, callers, depth + 1);
        if (first) modsOnPath.remove(mod);
    }

    static String modOf(Profile p, Node n) {
        String m = p.methodSources().get(n.cls + ";" + n.method + ";" + n.desc);
        if (m == null) m = p.lineSources().get(n.cls + ";" + n.method + ";" + n.line);
        if (m == null) m = p.classSources().get(n.cls);
        if (m != null) return m;
        String c = n.cls;
        if (c.startsWith("net.minecraft.") || c.startsWith("com.mojang.")) return "minecraft";
        if (c.startsWith("java.") || c.startsWith("jdk.") || c.startsWith("sun.") || c.startsWith("javax.")) return "java";
        if (c.startsWith("net.neoforged.")) return "neoforge";
        if (c.startsWith("org.lwjgl.")) return "lwjgl";
        if (c.startsWith("native") || c.isEmpty()) return "native";
        return "unattributed";
    }

    private static List<Node> sorted(List<Node> nodes) {
        List<Node> s = new ArrayList<>(nodes);
        s.sort((a, b) -> Double.compare(b.time, a.time));
        return s;
    }

    private static void printTree(Profile p, Node n, double threadTime, double minPct, int maxDepth, int depth, List<String> out) {
        if (threadTime <= 0 || 100 * n.time / threadTime < minPct || depth > maxDepth || out.size() > 2000) return;
        StringBuilder chain = new StringBuilder(frame(p, n));
        Node cur = n;
        // Join pass-through chains: a single significant child holding ~all of the parent's time.
        while (true) {
            List<Node> sig = new ArrayList<>();
            for (Node c : cur.children) if (100 * c.time / threadTime >= minPct) sig.add(c);
            if (sig.size() == 1 && sig.get(0).time >= cur.time * 0.97 && chain.length() < 600) {
                cur = sig.get(0);
                chain.append(" > ").append(frame(p, cur));
            } else break;
        }
        double childSum = 0;
        for (Node c : cur.children) childSum += c.time;
        double self = Math.max(0, cur.time - childSum);
        String[] parts = chain.toString().split(" > ");
        if (parts.length > 6)
            chain = new StringBuilder(parts[0] + " > " + parts[1] + " > ...(" + (parts.length - 5) + " frames)... > "
                    + parts[parts.length - 3] + " > " + parts[parts.length - 2] + " > " + parts[parts.length - 1]);
        out.add("  ".repeat(depth) + J.r1(100 * n.time / threadTime) + "%  self " + J.r1(100 * self / threadTime) + "%  " + chain);
        for (Node c : sorted(cur.children)) printTree(p, c, threadTime, minPct, maxDepth, depth + 1, out);
    }

    private static String frame(Profile p, Node n) {
        String cls = n.cls;
        int dot = cls.lastIndexOf('.');
        String shortCls = dot >= 0 ? cls.substring(dot + 1) : cls;
        String mod = modOf(p, n);
        String tag = mod.equals("minecraft") || mod.equals("java") ? "" : " [" + mod + "]";
        return shortCls + "." + n.method + (n.line > 0 ? ":" + n.line : "") + tag;
    }
}
