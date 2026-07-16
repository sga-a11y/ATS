"""Build the compact runtime navigation asset from game data files."""

import argparse
import hashlib
import json
import os
import struct


def parse_warps(data, flags_by_city):
    count = struct.unpack_from("<i", data, 0)[0]
    warps = []
    for index in range(count):
        name_id, city, mark, x, y = struct.unpack_from(
            "<IHHii", data, 4 + index * 16
        )
        flag = flags_by_city.get(city)
        if flag is None:
            continue
        warps.append({
            "city": city,
            "flag": flag,
            "mark": mark,
            "arrival": [x, y],
            "name_id": name_id,
        })
    return warps


def parse_door_graph(data):
    cursor = 0
    edges = []
    while cursor < len(data):
        scene = struct.unpack_from("<i", data, cursor)[0]
        cursor += 4
        target_count = data[cursor]
        cursor += 1
        for _ in range(target_count):
            target_scene = struct.unpack_from("<i", data, cursor)[0]
            cursor += 4
            door_count = data[cursor]
            cursor += 1
            for _ in range(door_count):
                door, priority, target_area, area = struct.unpack_from(
                    "<4B", data, cursor
                )
                cursor += 4
                edges.append({
                    "from": scene * 1000 + area,
                    "to": target_scene * 1000 + target_area,
                    "scene": scene,
                    "target_scene": target_scene,
                    "door": door,
                    "priority": priority,
                })
    return edges


def parse_eve_index(data):
    count = struct.unpack_from("<H", data, 0)[0]
    cursor = 2
    entries = {}
    for _ in range(count):
        name_length = data[cursor]
        raw_name = data[cursor + 1:cursor + 1 + name_length]
        offset, size = struct.unpack_from("<ii", data, cursor + 24)
        cursor += 32
        name = raw_name.decode("ascii")
        stem, _ = os.path.splitext(name)
        if stem.isdigit():
            entries[int(stem)] = (offset + 103, size)
    return entries


def _skip_npcs_and_goods(data, offset):
    cursor = offset
    npc_count = struct.unpack_from("<i", data, cursor)[0]
    cursor += 4
    for _ in range(npc_count):
        event_count = struct.unpack_from("<H", data, cursor + 4)[0]
        cursor += 6 + event_count
        sale_count = data[cursor]
        cursor += 1 + sale_count
        motion_node_count = data[cursor]
        cursor += 1 + (motion_node_count + 1) * 8 + 81
    goods_count = struct.unpack_from("<H", data, cursor)[0]
    return cursor + 2 + goods_count * 13


def parse_eve_doors(data, offset):
    cursor = _skip_npcs_and_goods(data, offset)
    count = struct.unpack_from("<H", data, cursor)[0]
    cursor += 2
    doors = {}
    for _ in range(count):
        door_id, event_count = struct.unpack_from("<HH", data, cursor)
        cursor += 4
        events = list(data[cursor:cursor + event_count])
        cursor += event_count
        x, y, width, height = struct.unpack_from("<iiii", data, cursor)
        cursor += 16
        image_kind = data[cursor]
        image_x, image_y = struct.unpack_from("<HH", data, cursor + 1)
        closed = bool(data[cursor + 5])
        cursor += 6
        doors[door_id] = {
            "events": events,
            "grid": [x, y, width, height],
            "center": [
                (x - 1) * 20 + width * 10,
                (y - 1) * 20 + height * 10,
            ],
            "image": [image_kind, image_x, image_y],
            "closed": closed,
        }
    return doors


def build_world_nav(warp_data, door_data, eve_data, flags_by_city):
    cities = parse_warps(warp_data, flags_by_city)
    edges = parse_door_graph(door_data)
    eve_index = parse_eve_index(eve_data)
    referenced = {(edge["scene"], edge["door"]) for edge in edges}
    gates = {}
    for scene, _ in sorted(referenced):
        if str(scene) in gates or scene not in eve_index:
            continue
        doors = parse_eve_doors(eve_data, eve_index[scene][0])
        selected = {
            str(door_id): door
            for door_id, door in doors.items()
            if (scene, door_id) in referenced
        }
        if selected:
            gates[str(scene)] = selected

    digest = hashlib.sha256()
    for raw in (warp_data, door_data, eve_data):
        digest.update(raw)
    return {
        "version": 1,
        "fingerprint": digest.hexdigest(),
        "cities": cities,
        "edges": edges,
        "gates": gates,
    }


def _city_flags(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        int(city["city_id"]): int(city["flag"])
        for city in data["cities"].values()
    }


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warp", required=True)
    parser.add_argument("--doors", required=True)
    parser.add_argument("--eve", required=True)
    parser.add_argument("--cities", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    warp_data = _read(args.warp)
    door_data = _read(args.doors)
    eve_data = _read(args.eve)
    nav = build_world_nav(
        warp_data,
        door_data,
        eve_data,
        _city_flags(args.cities),
    )
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(nav, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")

    states = {edge["from"] for edge in nav["edges"]}
    states.update(edge["to"] for edge in nav["edges"])
    print(f"{len(parse_eve_index(eve_data))} Eve scenes")
    print(f"{len(states)} navigation states")
    print(f"{len(nav['cities'])} teleport cities with known flags")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
