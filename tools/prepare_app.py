#!/usr/bin/env python3
"""Prepare the compact Temp433 overlay source for the build."""
import pathlib
import sys


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected one source anchor, found {count}: {old[:70]!r}")
    return source.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: prepare_app.py INPUT.c OUTPUT.c")
    source = pathlib.Path(sys.argv[1]).read_text()

    source = replace_once(source, "#define N_SENS      12u", "#define N_SENS      24u")
    source = replace_once(
        source,
        "uint8_t running, prev, saver, sens, spk, vhf, is_auto, pt, nrows, off, hold_pt, aborted, pkt;",
        "uint8_t running, prev, saver, sens, spk, vhf, is_auto, pt, nrows, off, hold_pt, aborted, pkt, detail;",
    )
    source = replace_once(
        source,
        """    } else if (i == N_SENS) {
        for (i = old; i + 1u < N_SENS; i++)
            t[i] = t[i + 1u];
""",
        """    } else if (i == N_SENS) {
        if (g.sel > old)
            g.sel--;
        for (i = old; i + 1u < N_SENS; i++)
            t[i] = t[i + 1u];
""",
    )
    source = replace_once(
        source,
        """    if (g.vhf) {
        tiny(s + T_VHF1, 17);
        tiny(s + T_VHF2, 25);
        return;
    }

    if (!g.n && !g.is_auto)""",
        """    if (g.vhf) {
        tiny(s + T_VHF1, 17);
        tiny(s + T_VHF2, 25);
        return;
    }
    if (g.detail && g.n) {
        e = g.tab + g.sel;
        memset(b, ' ', 32);
        asset((uint16_t)(T_NAME + e->proto * T_NAME_STRIDE), b, T_NAME_STRIDE);
        b[T_NAME_STRIDE] = 0;
        unsigned len = T_NAME_STRIDE;
        while (len && b[len - 1u] == ' ')
            b[--len] = 0;
        a->print_tiny(b, (uint8_t)(64u - 2u * len), 10, false, true);

        char *o = b;
        *o++ = 'C'; *o++ = 'H'; *o++ = ' ';
        o = putu(o, e->ch); *o++ = ' '; *o++ = 'I'; *o++ = 'D'; *o++ = ' ';
        o = putu(o, e->id); *o = 0;
        a->print_tiny(b, 0, 19, false, true);

        o = put_t10(b, e->t10); *o++ = 'C'; *o = 0;
        a->print_bold(b, 0, 127, 2);

        o = put(b, "HUM ");
        if (e->hum == NO_HUM) { *o++ = '-'; *o++ = '-'; }
        else { o = putu(o, e->hum); *o++ = '%'; }
        o = put(o, e->low ? "  BAT LOW" : "  BAT OK"); *o = 0;
        a->print_tiny(b, 0, 32, false, true);

        o = put(b, "RSSI -"); o = putu(o, 160u - e->rssi);
        o = put(o, s + T_DBM); o = put(o, " AGE ");
        o = put_age(o, now - e->seen); *o = 0;
        a->print_tiny(b, 0, 40, false, true);

        o = put_freq(b, e->f); *o = 0;
        a->print_tiny(b, 0, 49, false, true);
        return;
    }

    if (!g.n && !g.is_auto)""",
    )
    source = replace_once(
        source,
        """    case APP_KEY_EXIT:
        g.running = 0;
        break;
""",
        """    case APP_KEY_EXIT:
        if (g.detail)
            g.detail = 0;
        else
            g.running = 0;
        break;
""",
    )
    source = replace_once(
        source,
        """    case APP_KEY_2:
        g.n = g.sel = g.top = 0;       /* the table and the count start over */
""",
        """    case APP_KEY_2:
        g.detail = 0;
        g.n = g.sel = g.top = 0;       /* the table and the count start over */
""",
    )
    source = replace_once(
        source,
        """    case APP_KEY_5:
        if (!g.vhf) {
""",
        """    case APP_KEY_MENU:
        if (g.n && !g.vhf)
            g.detail = 1;
        break;
    case APP_KEY_5:
        if (!g.vhf) {
""",
    )

    pathlib.Path(sys.argv[2]).write_text(source)


if __name__ == "__main__":
    main()
