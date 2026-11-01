package dev.mtop.mcmcp.chat;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;

import dev.mtop.mcmcp.mcp.J;

/**
 * Two logs: everything shown in chat ({@link #shown}), and the inbox of player messages addressed
 * to Claude ({@link #inbox}). Ids grow across both so a caller can resume with {@code since}.
 */
public final class ChatLog {
    private static final int CAP = 400;
    private final Deque<Map<String, Object>> shown = new ArrayDeque<>();
    private final Deque<Map<String, Object>> inbox = new ArrayDeque<>();
    private long nextId = 1;
    private long delivered; // highest inbox id handed out by poll/wait

    public synchronized void shown(String kind, String text) {
        add(shown, J.obj("id", nextId++, "at_ms", System.currentTimeMillis(), "kind", kind, "text", text));
    }

    public synchronized void toClaude(String player, String text) {
        Map<String, Object> m = J.obj("id", nextId++, "at_ms", System.currentTimeMillis(), "player", player, "text", text);
        add(inbox, m);
        notifyAll();
    }

    private static void add(Deque<Map<String, Object>> q, Map<String, Object> m) {
        q.addLast(m);
        while (q.size() > CAP) q.removeFirst();
    }

    public synchronized List<Map<String, Object>> read(long since, int limit, String kind) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> m : shown)
            if ((long) m.get("id") > since && (kind == null || kind.equals(m.get("kind")))) out.add(m);
        return out.size() > limit ? new ArrayList<>(out.subList(out.size() - limit, out.size())) : out;
    }

    /** Inbox messages newer than {@code since}; since < 0 means "not yet delivered". */
    public synchronized List<Map<String, Object>> poll(long since) {
        long from = since < 0 ? delivered : since;
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> m : inbox) if ((long) m.get("id") > from) out.add(m);
        for (Map<String, Object> m : out) delivered = Math.max(delivered, (long) m.get("id"));
        return out;
    }

    public synchronized List<Map<String, Object>> await(long since, long timeoutMs) throws InterruptedException {
        long end = System.currentTimeMillis() + timeoutMs;
        while (true) {
            List<Map<String, Object>> got = poll(since);
            if (!got.isEmpty()) return got;
            long left = end - System.currentTimeMillis();
            if (left <= 0) return got;
            wait(left);
        }
    }

    public synchronized long lastId() {
        return nextId - 1;
    }
}
