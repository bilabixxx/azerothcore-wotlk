#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
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
SPELL_FERVOR_AURA = 900202
SPELLICON_REDIANCE = 90020
SPELLICON_FERVOR = 90021
SKILLLINEABILITY_INNER_FERVOR = 900200
SKILLLINEABILITY_FERVOR_AURA = 900201
SKILLRACECLASS_REDIANCE = 9003
PRIEST_CLASSMASK = 16
ALL_RACES_MASK = 0
ALL_RACES = 0xFFFF_FFFF


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


def patch_spellicon(src: Path, dst: Path) -> None:
    dbc = Dbc(src)
    dbc.delete_ids([SPELLICON_REDIANCE, SPELLICON_FERVOR])
    for id_, texture in [
        (SPELLICON_REDIANCE, "Interface\\Icons\\Rediance_spellbook"),
        (SPELLICON_FERVOR, "Interface\\Icons\\Fervor"),
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
    dbc.delete_ids([SKILLLINEABILITY_INNER_FERVOR, SKILLLINEABILITY_FERVOR_AURA])
    dbc.rows = [row for row in dbc.rows if row[2] not in {SPELL_INNER_FERVOR, SPELL_FERVOR_AURA}]
    template = dbc.find_by_field(2, 588)
    for id_, spell in [
        (SKILLLINEABILITY_INNER_FERVOR, SPELL_INNER_FERVOR),
        (SKILLLINEABILITY_FERVOR_AURA, SPELL_FERVOR_AURA),
    ]:
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
    dbc.delete_ids([SPELL_INNER_FERVOR, SPELL_FERVOR_AURA])

    passive = list(dbc.find(14752))
    passive[0] = SPELL_INNER_FERVOR
    passive[4] = (passive[4] | 64) & ~128
    passive[49] = 0
    for idx in [71, 72, 73, 80, 81, 82, 95, 96, 97]:
        passive[idx] = 0
    passive[133] = SPELLICON_FERVOR
    passive[134] = SPELLICON_FERVOR
    dbc.set_loc(passive, 136, 152, "Inner Fervor")
    passive[46] = 1   # RangeIndex: self (no range displayed)
    passive[204] = 0  # ManaCostPct: 0 (no mana cost)
    dbc.set_loc(passive, 153, 169, "Passive")
    dbc.set_loc(passive, 170, 186, "Your Rediance spells build Fervor, up to 5 stacks. After 6 sec without generating or consuming Fervor, 1 stack is lost. At 3 or more stacks, direct melee and spell hits against you deal 8% additional damage for each stack above 2.")
    dbc.set_loc(passive, 187, 203, "Fervor is generated by Flame of Judgment and Mark of Sin, and consumed by Divine Judgment.")
    passive[208] = 6
    passive[213] = 0
    passive[214] = 0
    passive[225] = 2
    dbc.append(passive)

    aura = list(dbc.find(14752))
    aura[0] = SPELL_FERVOR_AURA
    aura[4] |= 128
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
    dbc.set_loc(aura, 170, 186, "Secondary resource. Maximum 5 stacks.")
    dbc.set_loc(aura, 187, 203, "At 3 or more stacks, direct melee and spell hits against you deal 8% additional damage for each stack above 2.")
    aura[208] = 6
    aura[213] = 0
    aura[214] = 0
    aura[225] = 2
    dbc.append(aura)

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
    write_blp2_icon(repo / "icons_to_convert" / "Rediance_spellbook.png", icons / "Rediance_spellbook.blp")
    write_blp2_icon(repo / "icons_to_convert" / "Fervor.png", icons / "Fervor.blp")

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
