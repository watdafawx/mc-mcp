package dev.mtop.mcmcp.mcp;

import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.util.List;
import java.util.function.Predicate;

/** Who may talk to the MCP server. */
public final class NetRules {
    private NetRules() {}

    public static Predicate<InetAddress> loopbackOnly() {
        return InetAddress::isLoopbackAddress;
    }

    /** LAN-only (loopback, site-local, link-local, IPv6 ULA) and in the allowlist. */
    public static Predicate<InetAddress> lanAllowlist(List<? extends String> allow) {
        return a -> isLan(a) && allow.stream().anyMatch(rule -> matches(a, rule.trim()));
    }

    public static boolean isLan(InetAddress a) {
        if (a.isLoopbackAddress() || a.isSiteLocalAddress() || a.isLinkLocalAddress()) return true;
        if (a instanceof Inet6Address) {
            byte b = a.getAddress()[0];
            return (b & 0xfe) == 0xfc; // fc00::/7
        }
        return false;
    }

    static boolean matches(InetAddress a, String rule) {
        try {
            String host = rule;
            int bits = -1;
            int slash = rule.indexOf('/');
            if (slash >= 0) {
                host = rule.substring(0, slash);
                bits = Integer.parseInt(rule.substring(slash + 1));
            }
            InetAddress net = InetAddress.getByName(host);
            byte[] x = a.getAddress();
            byte[] y = net.getAddress();
            if (a instanceof Inet6Address v6 && net instanceof Inet4Address) {
                // IPv4-mapped IPv6 client address
                byte[] raw = v6.getAddress();
                boolean mapped = true;
                for (int i = 0; i < 10; i++) if (raw[i] != 0) mapped = false;
                if (mapped && raw[10] == (byte) 0xff && raw[11] == (byte) 0xff) {
                    x = new byte[] {raw[12], raw[13], raw[14], raw[15]};
                }
            }
            if (x.length != y.length) return false;
            if (bits < 0) bits = x.length * 8;
            for (int i = 0; i < x.length && bits > 0; i++, bits -= 8) {
                int mask = bits >= 8 ? 0xff : (0xff << (8 - bits)) & 0xff;
                if ((x[i] & mask) != (y[i] & mask)) return false;
            }
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
