from . import ModRoom, register_signage

F = "functionalstorage:"
OAK1, OAK2, OAK4 = F + "oak_1", F + "oak_2", F + "oak_4"
DOAK4, SPR4 = F + "dark_oak_4", F + "spruce_4"
CTRL, EXT = F + "storage_controller", F + "controller_extension"
GLASS = "minecraft:glass"  # Functional Storage ships drawers only


def _emblem():
    # v28: a wall of drawers: framed rim, oak field, a 3x3 grid of drawer fronts and the controller as the hub
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            d = (u * u + v * v) ** 0.5
            if d > 5.3:
                continue
            out.append((u, v, F + "framed_4" if d > 4.3 else "minecraft:black_concrete"))
    for u in range(-3, 4):
        for v in range(-3, 4):
            if abs(u) % 2 == 1 and abs(v) % 2 == 1:
                out = [c for c in out if (c[0], c[1]) != (u, v)] + [(u, v, OAK2)]
    out = [c for c in out if (c[0], c[1]) != (0, 0)] + [(0, 0, CTRL)]
    return out


# v28 Functional Storage: the drawer warehouse. It ships nothing but drawers and the controller, so the room is a grid of
# drawer banks (one and two-block drawers by wood type), fluid drawers, compacting drawers and a controller tower.
ROOM = ModRoom(
    theme="functionalstorage", name="Functional Storage", namespaces=("functionalstorage",),
    style="hextech", alt_styles=("solarpunk", "station_white"),
    pad=(F + "framed_1", OAK1),
    brief="Drawer warehouse: a four-high storage-controller column circled by controller extensions on a framed-drawer "
          "plinth, long banks of two- and four-slot oak, spruce and dark-oak drawers on the plinths and along the walls, "
          "jumbo framed drawers round a compacting drawer inside a framed cube, a fluid-drawer rack beside an ender drawer "
          "and an armory cabinet, glass windows over the banks.",
    deck="minecraft:smooth_sandstone", plinth=("minecraft:lime_concrete", "minecraft:gray_concrete"),
    pieces=(
        ("group", (0, 0, ("stack", CTRL, 4)),
         *[(dx, dz, ("stack", EXT, 2)) for dx, dz in ((-2, 0), (2, 0), (0, 2), (0, -2))],
         (-3, -3, ("column", F + "framed_1", OAK4, OAK4)), (3, -3, ("column", F + "framed_1", OAK4, OAK4)),
         (-3, 3, ("column", F + "framed_1", SPR4, SPR4)), (3, 3, ("column", F + "framed_1", SPR4, SPR4))),
        ("group", (0, 0, ("cube", F + "framed_2", GLASS, F + "compacting_drawer")),
         (-2, 0, ("stack", F + "framed_4", 2)), (2, 0, ("stack", F + "framed_4", 2)),
         (0, 2, ("stack", F + "framed_simple_compacting_drawer", 2)),
         (0, -2, ("stack", F + "simple_compacting_drawer", 2)),
         (-3, -3, ("column", F + "framed_1", DOAK4, DOAK4)), (3, -3, ("column", F + "framed_1", DOAK4, DOAK4)),
         (-3, 3, ("column", F + "framed_1", OAK2, OAK2)), (3, 3, ("column", F + "framed_1", OAK2, OAK2))),
        ("group", (0, 0, ("stack", F + "fluid_2", 3)),
         (-2, 0, ("stack", F + "fluid_1", 3)), (2, 0, ("stack", F + "fluid_4", 3)),
         (0, 2, ("stack", F + "framed_fluid_2", 2)), (0, -2, ("stack", F + "framed_fluid_4", 2)),
         (-3, -3, ("column", F + "framed_1", F + "ender_drawer")), (3, -3, ("column", F + "framed_1", F + "armory_cabinet")),
         (-3, 3, ("column", F + "framed_1", F + "cherry_4", F + "cherry_4")),
         (3, 3, ("column", F + "framed_1", F + "warped_4", F + "warped_4"))),
        ("group", (0, 0, ("stack", F + "framed_storage_controller", 3)),
         *[(dx, dz, ("column", F + "framed_1", F + "framed_controller_extension")) for dx, dz in ((-2, 0), (2, 0), (0, 2), (0, -2))],
         (-3, -3, ("column", F + "oak_1", OAK1, OAK4)), (3, -3, ("column", F + "oak_1", OAK1, OAK4)),
         (-3, 3, ("column", F + "spruce_1", F + "spruce_2", SPR4)),
         (3, 3, ("column", F + "birch_1", F + "birch_2", F + "birch_4"))),
    ),
    wall=tuple(F + n for n in (
        "oak_1 oak_2 oak_4 spruce_2 spruce_4 birch_4 dark_oak_4 framed_2 framed_4 framed_storage_controller "
        "storage_controller controller_extension fluid_2 ender_drawer armory_cabinet compacting_drawer").split()),
    extra={"gate": (F + "framed_1", F + "framed_4", F + "framed_2", "minecraft:shroomlight")},
    ghost_rules="Drawers are plain textured cubes: the number of slots is the block id (1/2/4). All of them are placed "
                "without a state (default facing works). The drawer FRONTS are the interesting face, so turn a bank toward "
                "the aisle with [facing=north|south|east|west] only if you have verified the key in this pack. Storage "
                "controllers, extensions, the ender drawer and the armory cabinet are single blocks; a controller network "
                "does not form in a ghost, show it as a column. No glass or metal in this mod: use the kit's glass.",
    blocks=tuple(F + n for n in (
        "oak_1 oak_2 oak_4 spruce_1 spruce_2 spruce_4 birch_1 birch_2 birch_4 jungle_1 jungle_2 jungle_4 "
        "acacia_1 acacia_2 acacia_4 dark_oak_1 dark_oak_2 dark_oak_4 mangrove_1 mangrove_2 mangrove_4 "
        "cherry_1 cherry_2 cherry_4 crimson_1 crimson_2 crimson_4 warped_1 warped_2 warped_4 "
        "framed_1 framed_2 framed_4 fluid_1 fluid_2 fluid_4 framed_fluid_1 framed_fluid_2 framed_fluid_4 "
        "storage_controller framed_storage_controller controller_extension framed_controller_extension "
        "compacting_drawer simple_compacting_drawer framed_simple_compacting_drawer ender_drawer armory_cabinet").split()),
)

register_signage("functionalstorage", _emblem, (F + "framed_4", "minecraft:oak_planks"))
