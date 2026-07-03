#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

BLP_CONV = Path("/Users/biagiogennuso/.cargo/bin/blp-conv")


SKILLLINE_REDIANCE = 9003
SPELL_INNER_FERVOR = 900201
SPELL_FERVOR_AURA_FIRST = 900202
SPELL_FERVOR_AURA_LAST = 900206
SPELL_FLAME_OF_JUDGMENT_FIRST = 900210
SPELL_MARK_OF_SIN_FIRST = 900230
SPELL_DIVINE_JUDGMENT_FIRST = 900250
SPELL_RADIANT_STRIKE_FIRST = 900260
SPELL_HOLY_CHASTISEMENT_FIRST = 900270
SPELL_STEP_OF_LIGHT_FIRST = 900280
SPELL_JUDGES_GAZE_FIRST = 900290
SPELL_PURIFYING_GLARE_FIRST = 900300
SPELL_BURNING_SHIELD_FIRST = 900310
SPELLICON_REDIANCE = 90020
SPELLICON_FERVOR = 90021
SPELLICON_FLAME_OF_JUDGMENT = 90022
SPELLICON_MARK_OF_SIN = 90023
SPELLICON_DIVINE_JUDGMENT = 90024
SPELLICON_RADIANT_STRIKE = 90025
SPELLICON_HOLY_CHASTISEMENT = 90026
SPELLICON_STEP_OF_LIGHT = 90027
SPELLICON_JUDGES_GAZE = 90028
SPELLICON_PURIFYING_GLARE = 90029
SPELLICON_BURNING_SHIELD = 90030
SKILLLINEABILITY_INNER_FERVOR = 900200
SKILLLINEABILITY_FERVOR_AURA = 900201
SKILLLINEABILITY_FLAME_OF_JUDGMENT_FIRST = 900210
SKILLLINEABILITY_MARK_OF_SIN_FIRST = 900230
SKILLLINEABILITY_DIVINE_JUDGMENT_FIRST = 900250
SKILLLINEABILITY_RADIANT_STRIKE_FIRST = 900260
SKILLLINEABILITY_HOLY_CHASTISEMENT_FIRST = 900270
SKILLLINEABILITY_STEP_OF_LIGHT_FIRST = 900280
SKILLLINEABILITY_JUDGES_GAZE_FIRST = 900290
SKILLLINEABILITY_PURIFYING_GLARE_FIRST = 900300
SKILLLINEABILITY_BURNING_SHIELD_FIRST = 900310
SKILLRACECLASS_REDIANCE = 9003
PRIEST_CLASSMASK = 16
ALL_RACES_MASK = 0
ALL_RACES = 0xFFFF_FFFF
SPELL_SCHOOL_RADIANT = 6

FLAME_OF_JUDGMENT_RANKS = [
    (1, 10, 34, 40),
    (2, 16, 68, 80),
    (3, 24, 137, 160),
    (4, 32, 238, 276),
    (5, 40, 371, 430),
    (6, 48, 542, 628),
    (7, 56, 759, 879),
    (8, 64, 1002, 1162),
    (9, 72, 1211, 1405),
    (10, 80, 1410, 1636),
]

MARK_OF_SIN_RANKS = [
    (1, 12, 24, 45),
    (2, 20, 46, 90),
    (3, 28, 74, 140),
    (4, 36, 106, 190),
    (5, 44, 140, 235),
    (6, 52, 168, 275),
    (7, 60, 180, 320),
    (8, 70, 205, 355),
    (9, 80, 230, 390),
]

DIVINE_JUDGMENT_RANKS = [
    (1, 20, 100),
    (2, 30, 160),
    (3, 40, 220),
    (4, 50, 280),
    (5, 60, 330),
    (6, 70, 380),
    (7, 80, 430),
]

RADIANT_STRIKE_RANKS = [
    (1, 24, 95),
    (2, 32, 150),
    (3, 40, 220),
    (4, 48, 300),
    (5, 56, 380),
    (6, 64, 450),
    (7, 72, 535),
    (8, 80, 620),
]

HOLY_CHASTISEMENT_RANKS = [
    (1, 30, 120),
    (2, 46, 210),
    (3, 62, 300),
    (4, 78, 390),
]

# rank, required level, SpellRadius.dbc index (10/13/15 yd, verified against ChromieCraft_3.3.5a/dbc/SpellRadius.dbc)
STEP_OF_LIGHT_RANKS = [
    (1, 34, 13, 10),
    (2, 54, 17, 13),
    (3, 74, 18, 15),
]

# rank, required level, SpellDuration.dbc index, fear duration sec (verified against
# ChromieCraft_3.3.5a/dbc/SpellDuration.dbc: 28=5000ms, 165=7000ms, 31=8000ms)
JUDGES_GAZE_RANKS = [
    (1, 38, 28, 5),
    (2, 56, 165, 7),
    (3, 74, 31, 8),
]

# rank, required level, bonus Radiant damage dealt only when the dispel succeeds
PURIFYING_GLARE_RANKS = [
    (1, 42, 100),
    (2, 54, 165),
    (3, 66, 250),
    (4, 78, 340),
]

# rank, required level, base absorb (before spell power), absorb per current Fervor stack
BURNING_SHIELD_RANKS = [
    (1, 44, 220, 70),
    (2, 56, 310, 100),
    (3, 68, 400, 150),
    (4, 80, 520, 180),
]


class Dbc:
    def __init__(self, path: Path):
        self.path = path
        data = path.read_bytes()
        magic, records, fields, record_size, string_size = struct.unpack_from("<4s4I", data, 0)
        if magic != b"WDBC":
            raise ValueError(f"{path} is not a WDBC file")
        if record_size != fields * 4:
            raise ValueError(f"{path} has unsupported record size {record_size} for {fields} fields")
        self.fields = fields
        rows_start = 20
        rows_end = rows_start + records * record_size
        self.rows = [
            list(struct.unpack_from(f"<{fields}I", data, rows_start + i * record_size))
            for i in range(records)
        ]
        self.strings = bytearray(data[rows_end:rows_end + string_size])
        if not self.strings:
            self.strings = bytearray(b"\0")

    def find(self, id_: int) -> list[int]:
        for row in self.rows:
            if row[0] == id_:
                return row
        raise KeyError(f"{self.path.name}: ID {id_} not found")

    def find_by_field(self, field: int, value: int) -> list[int]:
        for row in self.rows:
            if row[field] == value:
                return row
        raise KeyError(f"{self.path.name}: field {field}={value} not found")

    def delete_ids(self, ids: Iterable[int]) -> None:
        owned = set(ids)
        self.rows = [row for row in self.rows if row[0] not in owned]

    def add_string(self, value: str) -> int:
        if value == "":
            return 0
        raw = value.encode("utf-8") + b"\0"
        offset = len(self.strings)
        self.strings.extend(raw)
        return offset

    def set_loc(self, row: list[int], start: int, mask_index: int, value: str) -> None:
        offset = self.add_string(value)
        for idx in range(start, start + 16):
            row[idx] = offset
        row[mask_index] = 0x00FF_FFFE

    def append(self, row: list[int]) -> None:
        if len(row) != self.fields:
            raise ValueError(f"{self.path.name}: row has {len(row)} fields, expected {self.fields}")
        self.rows.append(row)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = bytearray()
        for row in self.rows:
            body.extend(struct.pack(f"<{self.fields}I", *row))
        header = struct.pack("<4s4I", b"WDBC", len(self.rows), self.fields, self.fields * 4, len(self.strings))
        path.write_bytes(header + body + self.strings)


def f32(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def flame_description() -> str:
    return (
        "Hurls a punishing flame of holy judgment at the enemy, dealing $s1 Radiant damage and "
        "generating 1 Fervor. If the target is affected by Mark of Sin, Flame of Judgment deals "
        "15% additional damage."
    )


def mark_description(tick_damage: int, explosion_damage: int) -> str:
    return (
        "Brands the enemy, causing $o1 Radiant damage over $d. When Mark of Sin expires naturally, "
        f"it explodes for at least {explosion_damage} Radiant damage per snapshotted Fervor. "
        "Can be cast while moving. Recasting before expiration prevents the explosion."
    )


def divine_judgment_description() -> str:
    return (
        "Releases accumulated Fervor in a burst of divine fire, dealing $s1 Radiant damage per "
        "Fervor consumed to the primary target, and 50% of that amount to nearby enemies within "
        "8 yards. Requires at least 1 Fervor and consumes all Fervor."
    )


def radiant_strike_description() -> str:
    return (
        "Strikes the enemy with a flash of Radiant force, dealing $s1 Radiant damage. "
        "Does not generate or consume Fervor. Deals 50% additional damage while you have 5 Fervor."
    )


def holy_chastisement_description() -> str:
    return (
        "Chastises the enemy with holy fire, interrupting spellcasting and silencing the target "
        "for 3 sec. Also deals $s1 Radiant damage."
    )


def step_of_light_description(distance_yd: int) -> str:
    return (
        f"Dashes {distance_yd} yards forward in a straight line. Cannot be used while stunned."
    )


def judges_gaze_description(fear_duration_sec: int) -> str:
    return (
        f"Fixes the enemy beneath the gaze of judgment, fearing the target for {fear_duration_sec} sec. "
        "Damage may break the effect."
    )


def purifying_glare_description() -> str:
    return (
        "Removes 1 beneficial Magic effect from the enemy. If a Magic effect is removed, Purifying Glare "
        "deals $s1 Radiant damage. If the target has no dispellable Magic effect, the spell fails and "
        "consumes no mana."
    )


def burning_shield_description() -> str:
    return (
        "Surrounds you with a burning shield that absorbs $s1 damage for 15 sec. The absorption "
        "increases based on your current Fervor and does not consume Fervor."
    )


def fervor_damage_taken_pct(stacks: int) -> int:
    return max(0, stacks - 2) * 8


def fervor_aura_description(stacks: int) -> str:
    return f"Damage taken +{fervor_damage_taken_pct(stacks)}%."


def owned_spell_ids() -> list[int]:
    return [
        SPELL_INNER_FERVOR,
        *range(SPELL_FERVOR_AURA_FIRST, SPELL_FERVOR_AURA_LAST + 1),
        *[SPELL_FLAME_OF_JUDGMENT_FIRST + rank - 1 for rank, *_ in FLAME_OF_JUDGMENT_RANKS],
        *[SPELL_MARK_OF_SIN_FIRST + rank - 1 for rank, *_ in MARK_OF_SIN_RANKS],
        *[SPELL_DIVINE_JUDGMENT_FIRST + rank - 1 for rank, *_ in DIVINE_JUDGMENT_RANKS],
        *[SPELL_RADIANT_STRIKE_FIRST + rank - 1 for rank, *_ in RADIANT_STRIKE_RANKS],
        *[SPELL_HOLY_CHASTISEMENT_FIRST + rank - 1 for rank, *_ in HOLY_CHASTISEMENT_RANKS],
        *[SPELL_STEP_OF_LIGHT_FIRST + rank - 1 for rank, *_ in STEP_OF_LIGHT_RANKS],
        *[SPELL_JUDGES_GAZE_FIRST + rank - 1 for rank, *_ in JUDGES_GAZE_RANKS],
        *[SPELL_PURIFYING_GLARE_FIRST + rank - 1 for rank, *_ in PURIFYING_GLARE_RANKS],
        *[SPELL_BURNING_SHIELD_FIRST + rank - 1 for rank, *_ in BURNING_SHIELD_RANKS],
    ]


def owned_skilllineability_ids() -> list[int]:
    return [
        SKILLLINEABILITY_INNER_FERVOR,
        SKILLLINEABILITY_FERVOR_AURA,
        *[SKILLLINEABILITY_FLAME_OF_JUDGMENT_FIRST + rank - 1 for rank, *_ in FLAME_OF_JUDGMENT_RANKS],
        *[SKILLLINEABILITY_MARK_OF_SIN_FIRST + rank - 1 for rank, *_ in MARK_OF_SIN_RANKS],
        *[SKILLLINEABILITY_DIVINE_JUDGMENT_FIRST + rank - 1 for rank, *_ in DIVINE_JUDGMENT_RANKS],
        *[SKILLLINEABILITY_RADIANT_STRIKE_FIRST + rank - 1 for rank, *_ in RADIANT_STRIKE_RANKS],
        *[SKILLLINEABILITY_HOLY_CHASTISEMENT_FIRST + rank - 1 for rank, *_ in HOLY_CHASTISEMENT_RANKS],
        *[SKILLLINEABILITY_STEP_OF_LIGHT_FIRST + rank - 1 for rank, *_ in STEP_OF_LIGHT_RANKS],
        *[SKILLLINEABILITY_JUDGES_GAZE_FIRST + rank - 1 for rank, *_ in JUDGES_GAZE_RANKS],
        *[SKILLLINEABILITY_PURIFYING_GLARE_FIRST + rank - 1 for rank, *_ in PURIFYING_GLARE_RANKS],
        *[SKILLLINEABILITY_BURNING_SHIELD_FIRST + rank - 1 for rank, *_ in BURNING_SHIELD_RANKS],
    ]


def patch_spellicon(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    dbc.delete_ids([SPELLICON_REDIANCE, SPELLICON_FERVOR, SPELLICON_FLAME_OF_JUDGMENT, SPELLICON_MARK_OF_SIN, SPELLICON_DIVINE_JUDGMENT, SPELLICON_RADIANT_STRIKE, SPELLICON_HOLY_CHASTISEMENT, SPELLICON_STEP_OF_LIGHT, SPELLICON_JUDGES_GAZE, SPELLICON_PURIFYING_GLARE, SPELLICON_BURNING_SHIELD])
    for id_, texture in [
        (SPELLICON_REDIANCE, "Interface\\Icons\\Rediance_spellbook"),
        (SPELLICON_FERVOR, "Interface\\Icons\\Fervor"),
        (SPELLICON_FLAME_OF_JUDGMENT, "Interface\\Icons\\flame_of_judgment"),
        (SPELLICON_MARK_OF_SIN, "Interface\\Icons\\Mark_of_Sin"),
        (SPELLICON_DIVINE_JUDGMENT, "Interface\\Icons\\Divine_Judgment"),
        (SPELLICON_RADIANT_STRIKE, "Interface\\Icons\\Radiant_Strike"),
        (SPELLICON_HOLY_CHASTISEMENT, "Interface\\Icons\\Holy_Chastisement"),
        (SPELLICON_STEP_OF_LIGHT, "Interface\\Icons\\Step_of_Light"),
        (SPELLICON_JUDGES_GAZE, "Interface\\Icons\\Judges_Gaze"),
        (SPELLICON_PURIFYING_GLARE, "Interface\\Icons\\Purifying_Glare"),
        (SPELLICON_BURNING_SHIELD, "Interface\\Icons\\Burning_Shield"),
    ]:
        row = list(dbc.find(237))
        row[0] = id_
        row[1] = dbc.add_string(texture)
        dbc.append(row)
    dbc.write(dst)


def patch_skillline(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    dbc.delete_ids([SKILLLINE_REDIANCE])
    row = list(dbc.find(56))
    row[0] = SKILLLINE_REDIANCE
    row[1] = 7
    row[2] = 0
    dbc.set_loc(row, 3, 19, "Rediance")
    dbc.set_loc(row, 20, 36, "Priest Rediance specialization.")
    row[37] = SPELLICON_REDIANCE
    row[55] = 0
    dbc.append(row)
    dbc.write(dst)


def patch_skilllineability(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    spells = set(owned_spell_ids())
    dbc.delete_ids(owned_skilllineability_ids())
    dbc.rows = [row for row in dbc.rows if row[2] not in spells]
    template = dbc.find_by_field(2, 588)
    entries = [
        (SKILLLINEABILITY_INNER_FERVOR, SPELL_INNER_FERVOR),
    ]
    entries.extend((SKILLLINEABILITY_FLAME_OF_JUDGMENT_FIRST + rank - 1, SPELL_FLAME_OF_JUDGMENT_FIRST + rank - 1) for rank, *_ in FLAME_OF_JUDGMENT_RANKS)
    entries.extend((SKILLLINEABILITY_MARK_OF_SIN_FIRST + rank - 1, SPELL_MARK_OF_SIN_FIRST + rank - 1) for rank, *_ in MARK_OF_SIN_RANKS)
    entries.extend((SKILLLINEABILITY_DIVINE_JUDGMENT_FIRST + rank - 1, SPELL_DIVINE_JUDGMENT_FIRST + rank - 1) for rank, *_ in DIVINE_JUDGMENT_RANKS)
    entries.extend((SKILLLINEABILITY_RADIANT_STRIKE_FIRST + rank - 1, SPELL_RADIANT_STRIKE_FIRST + rank - 1) for rank, *_ in RADIANT_STRIKE_RANKS)
    entries.extend((SKILLLINEABILITY_HOLY_CHASTISEMENT_FIRST + rank - 1, SPELL_HOLY_CHASTISEMENT_FIRST + rank - 1) for rank, *_ in HOLY_CHASTISEMENT_RANKS)
    entries.extend((SKILLLINEABILITY_STEP_OF_LIGHT_FIRST + rank - 1, SPELL_STEP_OF_LIGHT_FIRST + rank - 1) for rank, *_ in STEP_OF_LIGHT_RANKS)
    entries.extend((SKILLLINEABILITY_JUDGES_GAZE_FIRST + rank - 1, SPELL_JUDGES_GAZE_FIRST + rank - 1) for rank, *_ in JUDGES_GAZE_RANKS)
    entries.extend((SKILLLINEABILITY_PURIFYING_GLARE_FIRST + rank - 1, SPELL_PURIFYING_GLARE_FIRST + rank - 1) for rank, *_ in PURIFYING_GLARE_RANKS)
    entries.extend((SKILLLINEABILITY_BURNING_SHIELD_FIRST + rank - 1, SPELL_BURNING_SHIELD_FIRST + rank - 1) for rank, *_ in BURNING_SHIELD_RANKS)
    for id_, spell in entries:
        row = list(template)
        row[0] = id_
        row[1] = SKILLLINE_REDIANCE
        row[2] = spell
        row[3] = ALL_RACES_MASK
        row[4] = PRIEST_CLASSMASK
        row[5] = 0
        row[6] = 0
        row[7] = 0
        row[8] = 0
        row[9] = 2  # AcquireMethod: learned together with skill
        row[10] = 0
        row[11] = 0
        row[12] = 0
        row[13] = 0
        dbc.append(row)
    dbc.write(dst)


def patch_skillraceclass(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    dbc.delete_ids([SKILLRACECLASS_REDIANCE])
    template = dbc.find_by_field(1, 56)  # clone Holy priest entry
    row = list(template)
    row[0] = SKILLRACECLASS_REDIANCE
    row[1] = SKILLLINE_REDIANCE
    row[2] = ALL_RACES
    row[3] = PRIEST_CLASSMASK
    row[4] = 1040
    row[5] = 0
    row[6] = 0
    row[7] = 0
    dbc.append(row)
    dbc.write(dst)


def patch_spell(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    dbc.delete_ids(owned_spell_ids())

    passive = list(dbc.find(14752))
    passive[0] = SPELL_INNER_FERVOR
    passive[4] = (passive[4] | 64) & ~128
    passive[40] = 0
    passive[49] = 0
    for idx in [71, 72, 73, 80, 81, 82, 95, 96, 97]:
        passive[idx] = 0
    passive[133] = SPELLICON_FERVOR
    passive[134] = SPELLICON_FERVOR
    dbc.set_loc(passive, 136, 152, "Inner Fervor")
    passive[46] = 1   # RangeIndex: self (no range displayed)
    passive[204] = 0  # ManaCostPct: 0 (no mana cost)
    dbc.set_loc(passive, 153, 169, "Passive")
    dbc.set_loc(passive, 170, 186, "Your Rediance spells build Fervor, up to 5 stacks. After 6 sec without generating or consuming Fervor, 1 stack is lost.")
    dbc.set_loc(passive, 187, 203, "Fervor is generated by Flame of Judgment and Mark of Sin, and consumed by Divine Judgment.")
    passive[208] = 6
    passive[213] = 0
    passive[214] = 0
    passive[225] = 2
    dbc.append(passive)

    for stacks in range(1, 6):
        aura = list(dbc.find(14752))
        aura[0] = SPELL_FERVOR_AURA_FIRST + stacks - 1
        aura[4] = aura[4] & ~128 & ~64
        aura[40] = 32
        aura[49] = 5
        aura[71] = 6
        aura[72] = 0
        aura[73] = 0
        aura[80] = 0
        aura[81] = 0
        aura[82] = 0
        aura[86] = 1
        aura[87] = 0
        aura[88] = 0
        aura[95] = 4
        aura[96] = 0
        aura[97] = 0
        aura[133] = SPELLICON_FERVOR
        aura[134] = SPELLICON_FERVOR
        dbc.set_loc(aura, 136, 152, "Fervor")
        dbc.set_loc(aura, 153, 169, "")
        dbc.set_loc(aura, 170, 186, fervor_aura_description(stacks))
        dbc.set_loc(aura, 187, 203, fervor_aura_description(stacks))
        aura[208] = 6
        aura[213] = 0
        aura[214] = 0
        aura[225] = 2
        dbc.append(aura)

    for rank, level, damage_min, damage_max in FLAME_OF_JUDGMENT_RANKS:
        spell = list(dbc.find(585))
        spell_id = SPELL_FLAME_OF_JUDGMENT_FIRST + rank - 1
        spell[0] = spell_id
        spell[28] = 5
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 0
        spell[46] = 4
        spell[49] = 0
        for idx in [72, 73, 81, 82, 87, 88, 95, 96, 97, 98, 99, 100, 116, 117, 118]:
            spell[idx] = 0
        spell[71] = 2
        spell[74] = damage_max - damage_min + 1
        spell[77] = f32(0.0)
        spell[80] = damage_min - 1
        spell[86] = 6
        spell[131] = 128
        spell[132] = 0
        spell[133] = SPELLICON_FLAME_OF_JUDGMENT
        spell[134] = SPELLICON_FLAME_OF_JUDGMENT
        dbc.set_loc(spell, 136, 152, "Flame of Judgment")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, flame_description())
        dbc.set_loc(spell, 187, 203, "Deals $s1 Radiant damage. Generates 1 Fervor.")
        spell[204] = 13
        spell[205] = 133
        spell[206] = 1500
        spell[208] = 6
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = SPELL_SCHOOL_RADIANT
        spell[229] = f32(0.571)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    for rank, level, tick_damage, explosion_damage in MARK_OF_SIN_RANKS:
        spell = list(dbc.find(589))
        spell_id = SPELL_MARK_OF_SIN_FIRST + rank - 1
        spell[0] = spell_id
        spell[28] = 16
        spell[31] = spell[31] & ~0x1
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 8
        spell[46] = 4
        spell[49] = 0
        for idx in [72, 73, 81, 82, 87, 88, 96, 97, 99, 100, 116, 117, 118]:
            spell[idx] = 0
        spell[71] = 6
        spell[74] = 1
        spell[77] = f32(0.0)
        spell[80] = tick_damage - 1
        spell[86] = 6
        spell[95] = 3
        spell[98] = 3000
        spell[131] = 71
        spell[132] = 0
        spell[133] = SPELLICON_MARK_OF_SIN
        spell[134] = SPELLICON_MARK_OF_SIN
        dbc.set_loc(spell, 136, 152, "Mark of Sin")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, mark_description(tick_damage, explosion_damage))
        dbc.set_loc(spell, 187, 203, f"$s1 Radiant damage every $t1 sec. Can be cast while moving. Natural expiration explodes for at least {explosion_damage} damage per snapshotted Fervor.")
        spell[204] = 15
        spell[205] = 133
        spell[206] = 1500
        spell[208] = 6
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = SPELL_SCHOOL_RADIANT
        spell[229] = f32(0.20)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    for rank, level, damage_per_fervor in DIVINE_JUDGMENT_RANKS:
        spell = list(dbc.find(585))
        spell_id = SPELL_DIVINE_JUDGMENT_FIRST + rank - 1
        spell[0] = spell_id
        spell[28] = 0
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 0
        spell[46] = 4
        spell[49] = 0
        for idx in [72, 73, 74, 81, 82, 87, 88, 95, 96, 97, 98, 99, 100, 116, 117, 118]:
            spell[idx] = 0
        spell[71] = 3
        spell[74] = 1
        spell[77] = f32(0.0)
        spell[80] = damage_per_fervor - 1
        spell[86] = 6
        spell[131] = 71
        spell[132] = 0
        spell[133] = SPELLICON_DIVINE_JUDGMENT
        spell[134] = SPELLICON_DIVINE_JUDGMENT
        dbc.set_loc(spell, 136, 152, "Divine Judgment")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, divine_judgment_description())
        dbc.set_loc(spell, 187, 203, "$s1 Radiant damage per Fervor consumed. Nearby enemies take 50%.")
        spell[204] = 4
        spell[205] = 133
        spell[206] = 0
        spell[208] = 6
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = SPELL_SCHOOL_RADIANT
        spell[229] = f32(0.21)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    for rank, level, base_damage in RADIANT_STRIKE_RANKS:
        spell = list(dbc.find(585))
        spell_id = SPELL_RADIANT_STRIKE_FIRST + rank - 1
        spell[0] = spell_id
        spell[1] = 0  # Category: 0 = independent cooldown, not shared with any other spell
        spell[28] = 1  # CastingTimeIndex: 1 = instant (0 is not a valid SpellCastTimes.dbc ID)
        spell[29] = 6000  # RecoveryTime: real per-spell cooldown in ms (verified via Frost Nova/Divine Shield)
        spell[30] = 0  # CategoryRecoveryTime: unused, no shared-category cooldown
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 0
        spell[46] = 4
        spell[49] = 0
        for idx in [72, 73, 81, 82, 87, 88, 95, 96, 97, 98, 99, 100, 116, 117, 118]:
            spell[idx] = 0
        spell[71] = 2
        spell[74] = 1
        spell[77] = f32(0.0)
        spell[80] = base_damage - 1
        spell[86] = 6
        spell[131] = 128
        spell[132] = 0
        spell[133] = SPELLICON_RADIANT_STRIKE
        spell[134] = SPELLICON_RADIANT_STRIKE
        dbc.set_loc(spell, 136, 152, "Radiant Strike")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, radiant_strike_description())
        dbc.set_loc(spell, 187, 203, "$s1 Radiant damage. Deals 50% more while you have 5 Fervor. Does not generate or consume Fervor.")
        spell[204] = 8
        spell[205] = 133
        spell[206] = 0
        spell[208] = 6
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = SPELL_SCHOOL_RADIANT
        spell[229] = f32(0.26)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    for rank, level, base_damage in HOLY_CHASTISEMENT_RANKS:
        spell = list(dbc.find(585))
        spell_id = SPELL_HOLY_CHASTISEMENT_FIRST + rank - 1
        spell[0] = spell_id
        spell[1] = 0  # Category: independent cooldown
        spell[28] = 1  # CastingTimeIndex: instant
        spell[29] = 20000  # RecoveryTime: 20 sec cooldown
        spell[30] = 0  # CategoryRecoveryTime: unused
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 27  # DurationIndex: 3000ms, drives both the silence aura and the interrupt lockout
        spell[46] = 3  # RangeIndex: 20 yd
        spell[49] = 0
        for idx in [75, 76, 89, 90, 91, 98, 99, 100, 116, 117, 118]:
            spell[idx] = 0
        spell[71] = 2    # Effect0: SCHOOL_DAMAGE
        spell[72] = 6    # Effect1: APPLY_AURA
        spell[73] = 68   # Effect2: INTERRUPT_CAST
        spell[74] = 1
        spell[77] = f32(0.0)
        spell[80] = base_damage - 1
        spell[81] = 0
        spell[82] = 0
        spell[86] = 6
        spell[87] = 6
        spell[88] = 6
        spell[95] = 0
        spell[96] = 27  # EffectAura1: MOD_SILENCE
        spell[97] = 0
        spell[131] = 128
        spell[132] = 0
        spell[133] = SPELLICON_HOLY_CHASTISEMENT
        spell[134] = SPELLICON_HOLY_CHASTISEMENT
        dbc.set_loc(spell, 136, 152, "Holy Chastisement")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, holy_chastisement_description())
        dbc.set_loc(spell, 187, 203, "Interrupts spellcasting and silences the target for 3 sec. Deals $s1 Radiant damage.")
        spell[204] = 9
        spell[205] = 133
        spell[206] = 0
        spell[208] = 6
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = SPELL_SCHOOL_RADIANT
        spell[229] = f32(0.15)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    for rank, level, radius_index, distance_yd in STEP_OF_LIGHT_RANKS:
        # Clone Blink (1953): SPELL_EFFECT_LEAP (29) + TARGET_DEST_CASTER_FRONT_LEAP (55, ImplicitTargetB[0])
        # is the engine's native forward-dash effect (Spell::EffectLeap / TARGET_DEST_CASTER_FRONT_LEAP in
        # Spell.cpp), including ground-collision-aware pathing. No custom C++ is needed for the movement.
        spell = list(dbc.find(1953))
        spell_id = SPELL_STEP_OF_LIGHT_FIRST + rank - 1
        spell[0] = spell_id
        spell[1] = 0        # Category: independent cooldown, not shared with Blink's category 44
        spell[28] = 1       # CastingTimeIndex: instant (inherited from Blink, kept explicit)
        spell[29] = 20000   # RecoveryTime: real per-spell cooldown in ms
        spell[30] = 0       # CategoryRecoveryTime: unused, no shared-category cooldown
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 0       # DurationIndex: no aura effect kept, no duration needed
        # Effect1/Effect2 on Blink apply a cosmetic aura during the leap; Step of Light only needs Effect0.
        spell[72] = 0
        spell[73] = 0
        spell[87] = 0
        spell[88] = 0
        spell[92] = radius_index
        spell[93] = 0
        spell[94] = 0
        spell[95] = 0
        spell[96] = 0
        spell[97] = 0
        spell[111] = 0
        spell[112] = 0
        spell[133] = SPELLICON_STEP_OF_LIGHT
        spell[134] = SPELLICON_STEP_OF_LIGHT
        dbc.set_loc(spell, 136, 152, "Step of Light")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, step_of_light_description(distance_yd))
        dbc.set_loc(spell, 187, 203, step_of_light_description(distance_yd))
        spell[204] = 3      # ManaCostPercentage: 3% of base mana
        spell[205] = 133
        spell[206] = 0
        spell[225] = 2      # SchoolMask: Holy
        dbc.append(spell)

    for rank, level, duration_index, fear_duration_sec in JUDGES_GAZE_RANKS:
        # Clone Fear (5782): already SPELL_EFFECT_APPLY_AURA + SPELL_AURA_MOD_FEAR (7) on a single
        # enemy target, with a 1.5 sec cast, 20 yd range and the native damage-breaks-effect interrupt
        # flags built in. No custom C++ is needed for the fear behaviour.
        spell = list(dbc.find(5782))
        spell_id = SPELL_JUDGES_GAZE_FIRST + rank - 1
        spell[0] = spell_id
        spell[1] = 0            # Category: independent cooldown, not shared with Fear's category
        spell[28] = 16          # CastingTimeIndex: 1.5 sec (inherited from Fear, kept explicit)
        spell[29] = 25000       # RecoveryTime: 25 sec real per-spell cooldown
        spell[30] = 0           # CategoryRecoveryTime: unused
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = duration_index
        spell[46] = 3           # RangeIndex: 20 yd (inherited from Fear, kept explicit)
        spell[133] = SPELLICON_JUDGES_GAZE
        spell[134] = SPELLICON_JUDGES_GAZE
        dbc.set_loc(spell, 136, 152, "Judge's Gaze")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, judges_gaze_description(fear_duration_sec))
        dbc.set_loc(spell, 187, 203, f"Fears the target for {fear_duration_sec} sec. Damage may break the effect.")
        spell[204] = 10          # ManaCostPercentage: 10% of base mana
        spell[205] = 133
        spell[206] = 0
        spell[208] = 6           # SpellFamilyName: Priest (overrides Fear's Warlock family)
        spell[209] = 0          # SpellFamilyFlags: cleared, Fear's Warlock-specific flags don't apply
        spell[210] = 0
        spell[211] = 0
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = 2           # SchoolMask: Holy (overrides Fear's Shadow school)
        dbc.append(spell)

    for rank, level, bonus_damage in PURIFYING_GLARE_RANKS:
        # Effect0 stays SPELL_EFFECT_DUMMY (3), same as Divine Judgment: the actual dispel attempt and
        # the conditional damage-only-on-success rule cannot be expressed as native DBC effects, so both
        # are implemented in reborn_rediance_spell_script (modules/mod-reborn/src/priest/Rediance.cpp).
        # EffectBasePoints[0]/EffectDamageMultiplier[0] below only drive the $s1 tooltip token.
        spell = list(dbc.find(585))
        spell_id = SPELL_PURIFYING_GLARE_FIRST + rank - 1
        spell[0] = spell_id
        spell[1] = 0        # Category: independent cooldown
        spell[28] = 1       # CastingTimeIndex: instant
        spell[29] = 8000    # RecoveryTime: 8 sec cooldown
        spell[30] = 0       # CategoryRecoveryTime: unused
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 0
        spell[46] = 4       # RangeIndex: 30 yd
        spell[49] = 0
        for idx in [72, 73, 81, 82, 87, 88, 95, 96, 97, 98, 99, 100, 116, 117, 118]:
            spell[idx] = 0
        spell[71] = 3       # Effect0: DUMMY
        spell[74] = 1       # EffectDieSides[0]: no roll variance (range 1..1). Left at 0 originally, which
                             # made the client tooltip render a reversed "max to min" spread instead of a
                             # single fixed number for the $s1 token.
        spell[80] = bonus_damage - 1
        spell[86] = 6       # ImplicitTargetA[0]: enemy
        spell[131] = 71
        spell[132] = 0
        spell[133] = SPELLICON_PURIFYING_GLARE
        spell[134] = SPELLICON_PURIFYING_GLARE
        dbc.set_loc(spell, 136, 152, "Purifying Glare")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, purifying_glare_description())
        dbc.set_loc(spell, 187, 203, "$s1 Radiant damage if a Magic effect is removed. Fails and costs no mana if the target has no dispellable Magic effect.")
        spell[204] = 12      # ManaCostPercentage: 12% of base mana
        spell[205] = 133
        spell[206] = 0
        spell[208] = 6       # SpellFamilyName: Priest
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = SPELL_SCHOOL_RADIANT
        spell[229] = f32(0.10)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    for rank, level, base_absorb, absorb_per_stack in BURNING_SHIELD_RANKS:
        # Clone Power Word: Shield (17): already SPELL_EFFECT_APPLY_AURA + SPELL_AURA_SCHOOL_ABSORB (69)
        # with EffectMiscValue[0]=127 (all schools), self-target, instant cast. The engine natively
        # computes EffectBasePoints + spell power coefficient into the absorb pool at apply time; the
        # additional Fervor-based bonus (which the DBC cannot know about) is added on top in
        # reborn_rediance_spell_script via AuraEffect::SetAmount after the aura is applied.
        spell = list(dbc.find(17))
        spell_id = SPELL_BURNING_SHIELD_FIRST + rank - 1
        spell[0] = spell_id
        spell[1] = 0        # Category: independent cooldown, not shared with Power Word: Shield
        spell[28] = 1       # CastingTimeIndex: instant (inherited from PW:Shield, kept explicit)
        spell[29] = 30000   # RecoveryTime: 30 sec real per-spell cooldown
        spell[30] = 0       # CategoryRecoveryTime: unused
        spell[37] = level
        spell[38] = level
        spell[39] = level
        spell[40] = 8       # DurationIndex: 15000ms (verified against SpellDuration.dbc ID 8)
        spell[46] = 1       # RangeIndex: Self Only
        spell[74] = 1       # EffectDieSides[0]: no roll variance, basePoints+1 = exact value
        spell[86] = 1       # ImplicitTargetA[0]: self
        spell[89] = 0       # ImplicitTargetB[0]: none (PW:Shield allows an ally target, we don't)
        spell[27] = 0       # ExcludeTargetAuraSpell: cleared. PW:Shield sets this to 6788 (Weakened Soul) so it
                             # can't be recast on a target that already has it; Burning Shield has nothing to do
                             # with Weakened Soul, but leaving 6788 here made the cast fail with
                             # SPELL_FAILED_TARGET_AURASTATE (generic "can't do that" client message) whenever
                             # the caster happened to have Weakened Soul from an unrelated real PW:Shield.
        spell[110] = 127    # EffectMiscValue[0]: absorb all schools (inherited from PW:Shield, kept explicit)
        spell[209] = 0      # SpellFamilyFlags: cleared, PW:Shield-specific flags (Rapture, Borrowed Time...) don't apply
        spell[210] = 0
        spell[211] = 0
        spell[133] = SPELLICON_BURNING_SHIELD
        spell[134] = SPELLICON_BURNING_SHIELD
        dbc.set_loc(spell, 136, 152, "Burning Shield")
        dbc.set_loc(spell, 153, 169, f"Rank {rank}")
        dbc.set_loc(spell, 170, 186, burning_shield_description())
        dbc.set_loc(spell, 187, 203, "Absorbs $s1 damage for 15 sec. Absorption scales with current Fervor but does not consume it.")
        spell[80] = base_absorb - 1
        spell[204] = 14      # ManaCostPercentage: 14% of base mana
        spell[205] = 133
        spell[206] = 0
        spell[208] = 6       # SpellFamilyName: Priest
        spell[213] = 1
        spell[214] = 1
        spell[216] = f32(1.0)
        spell[217] = f32(1.0)
        spell[218] = f32(1.0)
        spell[225] = 2       # SchoolMask: Holy
        spell[229] = f32(0.06)
        spell[230] = f32(0.0)
        spell[231] = f32(0.0)
        dbc.append(spell)

    dbc.write(dst)


def write_blp2_icon(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(src).convert("RGBA")
    if image.size != (64, 64):
        image = image.resize((64, 64), Image.Resampling.LANCZOS)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_png = Path(f.name)
    try:
        image.save(tmp_png)
        subprocess.run(
            [str(BLP_CONV), "--blp-version", "blp2", "--blp-format", "dxt5", "--alpha-bits", "8",
             str(tmp_png), str(dst)],
            check=True,
        )
    finally:
        tmp_png.unlink(missing_ok=True)


def crypt_table() -> list[int]:
    seed = 0x0010_0001
    table = [0] * 0x500
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp2 = seed & 0xFFFF
            table[index2] = (temp1 | temp2) & 0xFFFF_FFFF
            index2 += 0x100
    return table


CRYPT = crypt_table()


def mpq_hash(name: str, hash_type: int) -> int:
    seed1 = 0x7FED7FED
    seed2 = 0xEEEEEEEE
    for ch in name.upper().replace("/", "\\").encode("utf-8"):
        value = CRYPT[(hash_type << 8) + ch]
        seed1 = (value ^ (seed1 + seed2)) & 0xFFFF_FFFF
        seed2 = (ch + seed1 + seed2 + ((seed2 << 5) & 0xFFFF_FFFF) + 3) & 0xFFFF_FFFF
    return seed1


def encrypt_table(data: bytes, key_name: str) -> bytes:
    key = mpq_hash(key_name, 3)
    seed = 0xEEEEEEEE
    out = bytearray()
    for (value,) in struct.iter_unpack("<I", data):
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & 0xFFFF_FFFF
        encrypted = (value ^ (key + seed)) & 0xFFFF_FFFF
        key = (((~key << 21) & 0xFFFF_FFFF) + 0x11111111 | (key >> 11)) & 0xFFFF_FFFF
        seed = (value + seed + ((seed << 5) & 0xFFFF_FFFF) + 3) & 0xFFFF_FFFF
        out.extend(struct.pack("<I", encrypted))
    return bytes(out)


@dataclass
class MpqFile:
    path: str
    data: bytes


def next_power_of_two(value: int) -> int:
    return 1 << math.ceil(math.log2(max(1, value)))


def write_mpq(path: Path, files: list[MpqFile]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    listfile = "\r\n".join(file.path for file in files).encode("utf-8") + b"\r\n"
    files = [MpqFile("(listfile)", listfile)] + files
    hash_size = next_power_of_two(len(files) * 2)
    block_size = len(files)
    header_size = 32
    file_offset = header_size

    block_entries = []
    file_data = bytearray()
    for file in files:
        offset = file_offset + len(file_data)
        size = len(file.data)
        file_data.extend(file.data)
        block_entries.append((offset, size, size, 0x80000000 | 0x01000000))

    hash_entries = [(0xFFFF_FFFF, 0xFFFF_FFFF, 0xFFFF, 0xFFFF, 0xFFFF_FFFF) for _ in range(hash_size)]
    for block_index, file in enumerate(files):
        start = mpq_hash(file.path, 0) & (hash_size - 1)
        slot = start
        while hash_entries[slot][4] != 0xFFFF_FFFF:
            slot = (slot + 1) & (hash_size - 1)
            if slot == start:
                raise RuntimeError("MPQ hash table is full")
        hash_entries[slot] = (mpq_hash(file.path, 1), mpq_hash(file.path, 2), 0, 0, block_index)

    hash_pos = header_size + len(file_data)
    block_pos = hash_pos + hash_size * 16
    archive_size = block_pos + block_size * 16
    hash_raw = b"".join(struct.pack("<IIHHI", *entry) for entry in hash_entries)
    block_raw = b"".join(struct.pack("<IIII", *entry) for entry in block_entries)
    header = struct.pack("<4sIIHHIIII", b"MPQ\x1A", 32, archive_size, 0, 3, hash_pos, block_pos, hash_size, block_size)
    path.write_bytes(header + file_data + encrypt_table(hash_raw, "(hash table)") + encrypt_table(block_raw, "(block table)"))


def build(client: Path, repo: Path) -> None:
    dbc_src = client / "dbc"
    required = ["SpellIcon.dbc", "SkillLine.dbc", "SkillLineAbility.dbc", "SkillRaceClassInfo.dbc", "Spell.dbc"]
    missing = [name for name in required if not (dbc_src / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing extracted DBC files in {dbc_src}: {', '.join(missing)}")

    stage = repo / "var" / "reborn_client_patch"
    dbfiles = stage / "DBFilesClient"
    icons = stage / "Interface" / "Icons"
    patch_spellicon(dbc_src / "SpellIcon.dbc", dbfiles / "SpellIcon.dbc")
    patch_skillline(dbc_src / "SkillLine.dbc", dbfiles / "SkillLine.dbc")
    patch_skilllineability(dbc_src / "SkillLineAbility.dbc", dbfiles / "SkillLineAbility.dbc")
    patch_skillraceclass(dbc_src / "SkillRaceClassInfo.dbc", dbfiles / "SkillRaceClassInfo.dbc")
    patch_spell(dbc_src / "Spell.dbc", dbfiles / "Spell.dbc")
    for name in required:
        shutil.copy2(dbfiles / name, dbc_src / name)

    write_blp2_icon(repo / "icons_to_convert" / "Rediance_spellbook.png", icons / "Rediance_spellbook.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Fervor.png", icons / "Fervor.blp")
    write_blp2_icon(repo / "icons_to_convert" / "flame_of_judgment.png", icons / "flame_of_judgment.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Mark of Sin.png", icons / "Mark_of_Sin.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Divine Judgment.png", icons / "Divine_Judgment.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Radiant Strike.png", icons / "Radiant_Strike.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Holy Chastisement.png", icons / "Holy_Chastisement.blp")
    write_blp2_icon(repo / "icons_to_convert" / 'Step of Light".png', icons / "Step_of_Light.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Judge's Gaze.png", icons / "Judges_Gaze.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Purifying Glare.png", icons / "Purifying_Glare.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Burning Shield.png", icons / "Burning_Shield.blp")

    files = []
    for file in sorted(stage.rglob("*")):
        if file.is_file():
            rel = file.relative_to(stage).as_posix().replace("/", "\\")
            files.append(MpqFile(rel, file.read_bytes()))

    output = client / "Data" / "patch-4.MPQ"
    write_mpq(output, files)
    print(f"Wrote {output}")
    print(f"Staged files in {stage}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="ChromieCraft_3.3.5a", type=Path)
    parser.add_argument("--repo", default=".", type=Path)
    args = parser.parse_args()
    build(args.client.resolve(), args.repo.resolve())


if __name__ == "__main__":
    main()
