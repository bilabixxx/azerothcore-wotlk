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
SPELLICON_REDIANCE = 90020
SPELLICON_FERVOR = 90021
SPELLICON_FLAME_OF_JUDGMENT = 90022
SPELLICON_MARK_OF_SIN = 90023
SKILLLINEABILITY_INNER_FERVOR = 900200
SKILLLINEABILITY_FERVOR_AURA = 900201
SKILLLINEABILITY_FLAME_OF_JUDGMENT_FIRST = 900210
SKILLLINEABILITY_MARK_OF_SIN_FIRST = 900230
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
        "Recasting before expiration prevents the explosion."
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
    ]


def owned_skilllineability_ids() -> list[int]:
    return [
        SKILLLINEABILITY_INNER_FERVOR,
        SKILLLINEABILITY_FERVOR_AURA,
        *[SKILLLINEABILITY_FLAME_OF_JUDGMENT_FIRST + rank - 1 for rank, *_ in FLAME_OF_JUDGMENT_RANKS],
        *[SKILLLINEABILITY_MARK_OF_SIN_FIRST + rank - 1 for rank, *_ in MARK_OF_SIN_RANKS],
    ]


def patch_spellicon(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    dbc.delete_ids([SPELLICON_REDIANCE, SPELLICON_FERVOR, SPELLICON_FLAME_OF_JUDGMENT, SPELLICON_MARK_OF_SIN])
    for id_, texture in [
        (SPELLICON_REDIANCE, "Interface\\Icons\\Rediance_spellbook"),
        (SPELLICON_FERVOR, "Interface\\Icons\\Fervor"),
        (SPELLICON_FLAME_OF_JUDGMENT, "Interface\\Icons\\flame_of_judgment"),
        (SPELLICON_MARK_OF_SIN, "Interface\\Icons\\Mark_of_Sin"),
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
        dbc.set_loc(spell, 187, 203, f"$s1 Radiant damage every $t1 sec. Natural expiration explodes for at least {explosion_damage} damage per snapshotted Fervor.")
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
