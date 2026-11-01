package dev.mtop.mcmcp.metrics;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

import org.spongepowered.asm.mixin.MixinEnvironment;
import org.spongepowered.asm.mixin.Mixins;
import org.spongepowered.asm.mixin.extensibility.IMixinConfig;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;
import org.spongepowered.asm.mixin.transformer.Config;

import dev.mtop.mcmcp.mcp.J;

/**
 * Which mixins exist, which applied, and which were skipped. Mixin keeps no public record of this,
 * so it is read from its internals by reflection (best effort: a field that moved is reported, not
 * thrown).
 *
 * <ul>
 * <li><b>applied</b>: woven into at least one loaded class (Mixin does not record which, so targets lists all).</li>
 * <li><b>pending</b>: accepted, but no target class has loaded yet (normal for lazily used classes).</li>
 * <li><b>skipped</b>: listed in the config but never accepted: target class missing, rejected by the
 * config's plugin, or failed to prepare. The log has the reason.</li>
 * </ul>
 */
public final class MixinReport {
    private MixinReport() {}

    public static Map<String, Object> report(String filter, String status, boolean client, int limit) {
        String f = filter == null ? "" : filter.toLowerCase(Locale.ROOT);
        Map<String, Set<String>> appliedByTarget = new HashMap<>();
        List<Map<String, Object>> configs = new ArrayList<>();
        List<Map<String, Object>> details = new ArrayList<>();
        int totDeclared = 0, totApplied = 0, totPending = 0, totSkipped = 0;
        List<String> errors = new ArrayList<>();

        List<IMixinConfig> all = allConfigs(errors);
        for (IMixinConfig cfg : all) {
            String name = cfg.getName();
            String pkg = cfg.getMixinPackage();
            String pkgPrefix = pkg == null || pkg.isEmpty() ? "" : (pkg.endsWith(".") ? pkg : pkg + ".");
            String source = source(cfg);
            Set<String> declared = new LinkedHashSet<>();
            Set<String> prepared = new LinkedHashSet<>();
            Map<String, List<String>> preparedTargets = new HashMap<>();
            try {
                for (String fld : client ? new String[] {"mixinClasses", "mixinClassesClient"} : new String[] {"mixinClasses", "mixinClassesServer"}) {
                    Object v = field(cfg, fld);
                    if (v instanceof Collection<?> list)
                        for (Object o : list) if (o != null) declared.add(pkgPrefix + o.toString().replace('/', '.'));
                }
                for (String fld : new String[] {"mixins", "pendingMixins"}) {
                    Object v = field(cfg, fld);
                    if (v instanceof Collection<?> list)
                        for (Object o : list) if (o instanceof IMixinInfo mi) {
                            prepared.add(mi.getClassName());
                            preparedTargets.put(mi.getClassName(), mi.getTargetClasses());
                        }
                }
            } catch (Exception e) {
                errors.add(name + ": " + e);
            }
            declared.addAll(prepared);

            boolean match = f.isEmpty() || name.toLowerCase(Locale.ROOT).contains(f) || source.toLowerCase(Locale.ROOT).contains(f);
            int applied = 0, pending = 0, skipped = 0;
            for (String m : declared) {
                // Mixin records an application on the mixin's own ClassInfo (MixinInfo#postApply), so
                // asking for the mixin class's "applied mixins" says whether it has been woven yet.
                boolean wasApplied = appliedByTarget.computeIfAbsent(m, MixinReport::appliedAt).contains(m);
                String st = wasApplied ? "applied" : prepared.contains(m) ? "pending" : "skipped";
                switch (st) {
                    case "applied" -> applied++;
                    case "pending" -> pending++;
                    default -> skipped++;
                }
                boolean wanted = status == null || status.isEmpty() || status.equals("all") || status.equals(st);
                boolean nameMatch = match || m.toLowerCase(Locale.ROOT).contains(f);
                if (wanted && nameMatch && (!f.isEmpty() || (status != null && !status.isEmpty() && !status.equals("all")))) {
                    if (details.size() < limit) {
                        Map<String, Object> d = J.obj("mixin", m, "config", name, "status", st);
                        List<String> targets = preparedTargets.get(m);
                        if (targets != null) d.put("targets", targets.stream().map(t -> t.replace('/', '.')).toList());
                        details.add(d);
                    }
                }
            }
            totDeclared += declared.size();
            totApplied += applied;
            totPending += pending;
            totSkipped += skipped;
            if (match)
                configs.add(J.obj("config", name, "source", source, "mixins", declared.size(),
                        "applied", applied, "pending", pending, "skipped", skipped));
        }
        configs.sort((a, b) -> (int) b.get("skipped") - (int) a.get("skipped"));
        if (configs.size() > limit && f.isEmpty()) {
            // Without a filter, keep the list short: configs with skips first, then the rest dropped.
            configs = new ArrayList<>(configs.subList(0, limit));
        }
        Map<String, Object> out = J.obj(
                "totals", J.obj("configs", all.size(), "mixins", totDeclared,
                        "applied", totApplied, "pending", totPending, "skipped", totSkipped),
                "configs", configs);
        if (!details.isEmpty()) out.put("mixins", details);
        if (lastError != null) errors.add("applied lookup: " + lastError);
        if (!errors.isEmpty()) out.put("errors", errors.subList(0, Math.min(10, errors.size())));
        out.put("hint", "filter=<mod or config> for per-mixin detail; status=skipped lists every skipped mixin. Skips are normal for optional compat mixins.");
        return out;
    }

    /**
     * Every config the transformer has selected. {@link Mixins#getConfigs()} only holds configs not
     * yet visited, so it is empty in a running game; the processor's own list is the real one.
     */
    private static List<IMixinConfig> allConfigs(List<String> errors) {
        List<IMixinConfig> out = new ArrayList<>();
        Set<String> seen = new java.util.HashSet<>();
        try {
            Object transformer = MixinEnvironment.getCurrentEnvironment().getActiveTransformer();
            Object processor = transformer == null ? null : field(transformer, "processor");
            for (String fld : new String[] {"configs", "pendingConfigs"}) {
                Object v = processor == null ? null : field(processor, fld);
                if (v instanceof Collection<?> list)
                    for (Object o : new ArrayList<>(list))
                        if (o instanceof IMixinConfig c && seen.add(c.getName())) out.add(c);
            }
        } catch (Exception e) {
            errors.add("processor: " + e);
        }
        for (Config c : Mixins.getConfigs())
            if (seen.add(c.getName())) out.add(c.getConfig());
        return out;
    }

    /** Mixin class names recorded as applied on this class's ClassInfo. Public Mixin API. */
    private static Set<String> appliedAt(String target) {
        Set<String> out = new java.util.HashSet<>();
        try {
            Set<IMixinInfo> infos = Mixins.getMixinsForClass(target.replace('/', '.'));
            if (infos != null) for (IMixinInfo mi : new ArrayList<>(infos)) out.add(mi.getClassName());
        } catch (Throwable t) {
            lastError = t.toString();
        }
        return out;
    }

    private static volatile String lastError;

    private static Object field(Object o, String name) throws Exception {
        Class<?> c = o.getClass();
        while (c != null) {
            try {
                Field f = c.getDeclaredField(name);
                f.setAccessible(true);
                return f.get(o);
            } catch (NoSuchFieldException e) {
                c = c.getSuperclass();
            }
        }
        return null;
    }

    private static String source(IMixinConfig cfg) {
        try {
            Method m = cfg.getClass().getMethod("getSource");
            Object src = m.invoke(cfg);
            if (src == null) return "";
            Method id = src.getClass().getMethod("getId");
            id.setAccessible(true);
            return String.valueOf(id.invoke(src));
        } catch (Exception e) {
            return "";
        }
    }
}
