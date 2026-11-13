#!/usr/bin/env python3
"""Activate the real tray menu in Linux CI without requiring a desktop panel."""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET


def busctl(*args):
    return subprocess.check_output(
        ["busctl", "--user", "--no-pager", "--timeout=10", *args], text=True, timeout=15
    )


def menu_items(value):
    if isinstance(value, list):
        if len(value) == 3 and isinstance(value[0], int) and isinstance(value[1], dict):
            yield value
        for child in value:
            yield from menu_items(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from menu_items(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("label", choices=["Open AliasMode", "Quit AliasMode"])
    args = parser.parse_args()
    # Restrict discovery to connections owned by this test's desktop process.
    destinations = [
        fields[0]
        for line in busctl("list", "--no-legend").splitlines()
        if len(fields := line.split()) > 1
        and fields[0].startswith(":")
        and fields[1] == str(args.pid)
    ]
    for destination in destinations:
        # A desktop has several bus connections; inspect only the indicator subtree.
        parent = "/org/ayatana/NotificationItem"
        try:
            xml = subprocess.check_output([
                "gdbus", "introspect", "--session", "--dest", destination,
                "--object-path", parent, "--xml",
            ], text=True, stderr=subprocess.DEVNULL, timeout=5)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        for node in ET.fromstring(xml).findall("node"):
            path = f"{parent}/{node.attrib['name']}/Menu"
            layout = json.loads(busctl(
                "--json=short", "call", destination, path,
                "com.canonical.dbusmenu", "GetLayout", "iias", "0", "1", "0",
            ))
            for item_id, properties, _ in menu_items(layout):
                label = properties.get("label", {}).get("data", "")
                if isinstance(label, list) and len(label) == 1:
                    label = label[0]
                if label.replace("_", "") == args.label:
                    busctl(
                        "call", destination, path, "com.canonical.dbusmenu",
                        "Event", "isvu", str(item_id), "clicked", "s", "", "0",
                    )
                    print(f"Activated tray menu: {args.label}")
                    return
    raise SystemExit(f"No {args.label!r} tray action for desktop PID {args.pid}")


if __name__ == "__main__":
    main()
