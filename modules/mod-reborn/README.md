# mod-reborn

Single custom gameplay module for this server.

Keep future server-side custom content in this module, split by domain under
`src/`:

- `src/priest/`: Priest Rediance and future priest systems.
- `src/paladin/`: Paladin custom specializations and spells.
- `src/world/`: World, quest, NPC, and event scripts.
- `src/items/`: Item-specific custom behavior.

Current Rediance IDs:

- SkillLine `9003`: Rediance
- Spell `900201`: Inner Fervor
- Technical auras `900202-900206`: Fervor stack display, not spellbook-learned
- Spell `900210-900219`: Flame of Judgment ranks 1-10
- Spell `900230-900238`: Mark of Sin ranks 1-9
- Spell `900250-900256`: Divine Judgment ranks 1-7
- Client SpellIcon `90020`: `Interface\\Icons\\Rediance_spellbook`
- Client SpellIcon `90021`: `Interface\\Icons\\Fervor`
- Client SpellIcon `90022`: `Interface\\Icons\\flame_of_judgment`
- Client SpellIcon `90023`: `Interface\\Icons\\Mark_of_Sin`
- Client SpellIcon `90024`: `Interface\\Icons\\Divine_Judgment`

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
