from . import ModRoom

B = "bigreactors:"
ROOM = ModRoom(
    theme="bigreactors", name="Extreme Reactors", namespaces=("bigreactors",),
    style="station_white", alt_styles=("hextech",),
    pad=("bigreactors:graphite_block", "bigreactors:reinforced_reactorcasing"),
    brief="Reactor hall: a big reactor block of reinforced casing with a glass window band, controller and power taps on "
          "its faces, fuel rod and control rod columns visible through glass; next to it a turbine hall with rotor "
          "bearing/shaft/blades column in a glass-sided casing; yellorium and blutonium blocks as fuel stock.",
    pieces=(("tower", B + "reinforced_reactorcasing", B + "reinforced_reactorglass", 6, B + "reinforced_reactorfuelrod"),
            ("tower", B + "basic_turbinecasing", B + "basic_turbineglass", 5, B + "basic_turbinerotorshaft"),
            ("stack", B + "reinforced_reactorfuelrod", 4),
            ("stack", B + "reinforced_turbinerotorshaft", 4),
            ("cube", B + "basic_reactorcasing", B + "basic_reactorglass", B + "basic_reactorfuelrod")),
    wall=tuple(B + n for n in "reinforced_reactorcasing reinforced_reactorcontroller reinforced_reactorpowertapfe_passive basic_turbinecasing basic_turbinecontroller reinforced_reactorcontrolrod energizercell yellorium_block".split()),
    ghost_rules="Reactor and turbine are multiblocks that do not form in a ghost: build them as static casing + glass "
                "shells with fuel/control rods and rotor shaft/blades visible inside. No active glow or steam. Ports and "
                "controller sit on the faces of the casing shell.",
    blocks=tuple(B + n for n in (
        "basic_reactorcasing basic_reactorglass basic_reactorcontroller basic_reactorcontrolrod basic_reactorfuelrod "
        "basic_reactorpowertapfe_passive basic_reactorsolidaccessport basic_reactorredstoneport basic_turbinecasing "
        "basic_turbineglass basic_turbinecontroller basic_turbinerotorbearing basic_turbinerotorshaft "
        "basic_turbinerotorblade basic_turbinepowertapfe_passive reinforced_reactorcasing reinforced_reactorglass "
        "reinforced_reactorcontroller reinforced_reactorcontrolrod reinforced_reactorfuelrod "
        "reinforced_reactorpowertapfe_passive reinforced_reactorfluidaccessport reinforced_reactorsolidaccessport "
        "reinforced_turbinecasing reinforced_turbineglass reinforced_turbinecontroller reinforced_turbinerotorbearing "
        "reinforced_turbinerotorshaft reinforced_turbinerotorblade reinforced_turbinepowertapfe_passive "
        "energizercasing energizercell energizercontroller fluidizercasing fluidizerglass fluidizercontroller "
        "reprocessorcasing reprocessorglass reprocessorcontroller yellorium_block blutonium_block cyanite_block "
        "graphite_block ludicrite_block ridiculite_block").split()),
)
