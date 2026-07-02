# mod-reborn

Single custom gameplay module for this server.

Keep future server-side custom content in this module, split by domain under
`src/`:

- `src/priest/`: Priest Rediance and future priest systems.
- `src/paladin/`: Paladin custom specializations and spells.
- `src/world/`: World, quest, NPC, and event scripts.
- `src/items/`: Item-specific custom behavior.

Current Rediance IDs:

- SkillLine `90020`: Rediance
- Spell `900201`: Inner Fervor
- Spell `900202`: Fervor stack aura
- Client SpellIcon `90020`: `Interface\\Icons\\Rediance_spellbook`
- Client SpellIcon `90021`: `Interface\\Icons\\Fervor`

`Flame of Judgment`, `Mark of Sin`, and `Divine Judgment` are not present in
this checkout yet. Their IDs must be filled in `src/priest/Rediance.cpp` when
those spells are added.

Client patch requirements:

Run:

```bash
python3 tools/build_reborn_client_patch.py --client ChromieCraft_3.3.5a --repo .
```

The script patches `SpellIcon.dbc`, `SkillLine.dbc`,
`SkillLineAbility.dbc`, and `Spell.dbc`, converts the Rediance/Fervor PNG
icons to BLP, stages the files in `var/reborn_client_patch`, and writes
`ChromieCraft_3.3.5a/Data/patch-4.MPQ`.

Clear the WoW client `Cache` directory after replacing the MPQ.
