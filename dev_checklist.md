# reborn Custom Content Checklist

Promemoria operativo per contenuti custom AzerothCore 3.3.5a che toccano quest, reputazioni, titoli, aura, item e patch client.

## Struttura progetto custom

```
custom/
├── sql/                            # SQL migrations, numbered, English names only
│   ├── 01_paladin_wolf_chain.sql       # Wolf Pack quest chain (Fourth Oath prereq)
│   ├── 02_paladin_fourth_oath.sql      # Fourth Oath unlock quests + NPC + progression table
│   └── 03_paladin_twilight_combat.sql  # Twilight spell_script bindings
│
├── tools/
│   ├── dbc_patch_reborn.py           # Master DBC generator (Spell, Talent, SkillLine, …)
│   ├── build_client_patch.sh       # Runs DBC patcher then packs patch-4.MPQ / patch-enUS-4.MPQ
│   ├── mpq_pack / mpq_pack.cpp     # MPQ packer (compiled on first run)
│   └── mpq_inspect / mpq_inspect.cpp
│
├── client/
│   ├── original_dbc/               # Unmodified Blizzard DBC files (never edit these)
│   ├── patch-reborn/                 # Staged content for MPQ packing
│   │   ├── DBFilesClient/          # Generated DBC files (output of dbc_patch_reborn.py)
│   │   ├── Interface/Icons/        # Custom BLP icons
│   │   ├── Interface/TalentFrame/  # Twilight talent tree background tiles
│   │   └── Interface/AddOns/       # Modified Blizzard AddOns (Blizzard_TalentUI)
│   └── dist/                       # Ready-to-install MPQ files
│       ├── patch-4.MPQ             # Global: DBC + icons
│       └── patch-enUS-4.MPQ        # Locale: Blizzard_TalentUI FrameXML
│
├── docs/
│   ├── dev_checklist.md            # This file
│   └── paladin/                    # Twilight spec design docs and source art
│       ├── paladin.json
│       ├── paladin_tenebra_twilight_specialization.json
│       └── Twlight icons/          # Source PNG files for BLP conversion
│
└── client/addons/
    └── Reborn/                       # Unified Reborn client addon
        ├── Reborn.toc
        ├── Reborn.lua
        └── modules/
            └── DynamicSpellTooltips.lua # Dynamic custom spell tooltip calculations

core/modules/mod-reborn/              # Single custom C++ module, organized by domain
└── src/
    ├── rarity/
    │   ├── QuestRarityMgr.h/cpp    # Quest rarity DB singleton
    │   └── QuestRarity.cpp         # WorldScript load + rarity chat notify (cosmetics only)
    ├── world/
    │   └── WolfChain.cpp           # Wolf Pack chain, beast-damage mark, Selvara NPC
    ├── paladin/
    │   ├── FourthOath.h            # Tenebra shared IDs / talent prerequisites
    │   ├── FourthOath.cpp          # Tenebra unlock + talent gating (PlayerScript)
    │   └── TwilightSpells.cpp      # Twilight ability behaviour (SpellScript)
    └── mod_reborn_loader.cpp         # Addmod_rebornScripts() -> calls each domain's AddX()
```

AzerothCore collects module sources recursively (`CollectSourceFiles`), so new
`.cpp` files in any `src/` subfolder are picked up automatically — but adding or
renaming a module **directory** requires a cmake reconfigure (`cmake .` in
`build/`), because the module list is globbed at configure time, not build time.

### Architecture: every thing at its own level

The golden rule for all future content (paladin talents, other classes, quests,
items): **never put logic in the wrong layer.** Pick the layer, not the habit.

| Layer                                             | Tool                                 | What goes here                                                            |
| ------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------- |
| Client data (spell, talent, icon, item visual)    | `dbc_patch_reborn.py` → MPQ          | DBC definitions. **Talents that grant an ability: here, via LEARN_SPELL** |
| Server data (quest, creature, item, loot, gossip) | `custom/sql/NN_*.sql`                | Anything that is an `acore_world` table                                   |
| Behaviour (custom damage, proc, AI)               | C++ `SpellScript` / `CreatureScript` | ONLY logic the DBC/SQL cannot express                                     |
| Client UI                                         | addon `Reborn/modules/*.lua`         | Interface only, including dynamic tooltip calculations                    |

### Talent-granted abilities — do it in the DBC, not in C++

A WotLK talent can teach a spell natively. Set the talent's rank spell in
`Spell.dbc` to `SPELL_EFFECT_LEARN_SPELL (36)` with `EffectTriggerSpell` = the
ability spell ID (see `TALENT_TAUGHT_SPELLS` in `dbc_patch_reborn.py`). Then:

- spend the talent point → core learns the rank spell → ability appears in the
  spellbook **immediately** (no relog);
- reset talents → core unlearns the rank spell → the taught ability is removed
  **automatically**;
- login → state always derived from the talent, never desynced.

**Never** grant/remove a talent-gated spell from a `PlayerScript` hook
(`learnSpell`/`removeSpell` keyed on `HasTalent`). It desyncs: the spell shows
without the talent, or only disappears after logout. The C++ `SpellScript` must
implement *only* the ability's gameplay (damage, stacks, procs), never its
learn/unlearn. A spell granted by a *quest/flag* (e.g. Judgement of Twilight)
may still be learned server-side, because it is not gated by a talent.

### Naming conventions

- SQL files: `NN_feature_name.sql` — zero-padded number, English snake_case. Never Italian.
- Python/shell tools: `snake_case.py / snake_case.sh`, English.
- DBC-generated content: always re-run `dbc_patch_reborn.py` + `build_client_patch.sh` together.
- New content areas: add a new numbered SQL file; do not reuse or append to existing ones.

### How to add new content (any class / system)

1. **DBC changes** (new spell, talent, icon): edit `custom/tools/dbc_patch_reborn.py`, then run `bash custom/tools/build_client_patch.sh /path/to/client`. For a talent that grants an ability, add it to `TALENT_TAUGHT_SPELLS` — do NOT learn it from C++.
2. **Server script** (custom damage/proc/AI only): add a `.cpp` in the right `core/modules/mod-reborn/src/<domain>/` subfolder, expose an `AddX()` and call it from `mod_reborn_loader.cpp`, then rebuild worldserver. New file in an existing module = build only; new module directory = `cmake .` reconfigure first.
3. **SQL** (quest template, NPC spawn, spell_script binding): create `custom/sql/NN_name.sql` and apply with: `/opt/homebrew/opt/mysql@8.4/bin/mysql --protocol=TCP -h127.0.0.1 -P3306 -uacore -pacore acore_world < custom/sql/NN_name.sql`
4. **Client addon**: add Reborn-wide UI helpers in source path `client/addons/Reborn/modules/`, register them in `client/addons/Reborn/Reborn.toc`, then copy/install the addon to the client as `Interface/AddOns/Reborn/`.

### Dynamic spell tooltips

DBC tooltip substitutions can show only static values from `Spell.dbc`; they
cannot calculate player-state-dependent values such as current spell power,
temporary buffs, equipped gear, or custom resources like Fervor. If a custom
spell needs to show a live total, put that calculation in the Reborn client
addon:

- Source file: `client/addons/Reborn/modules/DynamicSpellTooltips.lua`.
- Installed client file: `Interface/AddOns/Reborn/modules/DynamicSpellTooltips.lua`.
- Register the module in `client/addons/Reborn/Reborn.toc`.
- Keep the DBC tooltip as a sane fallback for players without the addon.
- Store custom spell IDs, base values, coefficients, and resource rules in a
  table in the module; do not hard-code one-off tooltip patches in unrelated
  addons.
- Example: Divine Judgment displays `(base damage + 0.21 * spell power) *
  current Fervor` dynamically in the tooltip, while the server remains the
  source of truth for actual damage.

### Update checklist (in order)

1. Apply SQL migration to `acore_world` (or `acore_characters`).
2. Rebuild worldserver if C++ changed:
   ```bash
   cmake --build build -j8 --target worldserver
   ```
3. Stop worldserver, deploy new binary, restart:
   ```bash
   # Trova il PID
   ps aux | grep worldserver | grep -v grep
   # Ferma (prima SIGTERM, poi SIGKILL se non risponde)
   kill <PID>
   sleep 3
   kill -9 <PID> 2>/dev/null
   # Copia il binario nuovo (solo a server fermo)
   cp build/src/server/apps/worldserver server/bin/worldserver
   # Riavvia in background mantenendo stdin aperto (senza tail il worldserver muore per EOF)
   cd server/bin && tail -f /dev/null | ./worldserver \
     --config /Volumes/Biagio/Biagio/reborn/server/etc/worldserver.conf \
     > /Volumes/Biagio/Biagio/reborn/server/worldserver.log 2>&1 &
   ```
4. Run `bash custom/tools/build_client_patch.sh /path/to/client` to regenerate MPQs and install.
5. Clear client cache: `mv /path/to/client/Cache /path/to/client/Cache.bak`.
6. Relaunch `Wow.exe`.
7. Log out / log in with the character to trigger `PlayerScript::OnLogin` sync.

## Regola principale

Il gioco deve funzionare nel client senza comandi strani per il player. I comandi GM servono solo per testare velocemente, ma non devono essere il modo normale di fruire il contenuto.

## Prima di implementare

- Definire tutti gli ID custom e controllare che non esistano gia:
  - quest: `90000-99999`
  - creature/NPC/item/gameobject: `900000-999999`
  - faction/title/spell: controllare collisioni reali nei DBC e nel DB.
- Se una feature deve apparire nel client, verificare se e' server-only o client+server:
  - Quest, creature, item base: DB server.
  - Nome reputazione nuova: `Faction.dbc` server e client.
  - Titolo nuovo: `CharTitles.dbc` server e client.
  - Icone/spell visuali nuove: DBC client e spesso asset/addon aggiuntivi.
- Non patchare sopra un DBC gia patchato senza pulire le vecchie righe. Ripartire sempre da backup originali o rimuovere anche gli ID legacy.

## SQL

- Rendere ogni migrazione idempotente:
  - `DELETE` solo sugli ID posseduti dalla migrazione.
  - In caso di cambio ID, cancellare anche l'ID vecchio.
  - Se un DBC usa indici unici di fatto, pulire anche l'indice. Esempio: `ReputationIndex`.
- Dopo aver applicato SQL, verificare con query mirate:
  - quest presenti e concatenate;
  - NPC spawnati;
  - reward, title, faction e requisiti corretti;
  - righe reputation-on-kill corrette.

## DBC e client patch

- Per nuove reputazioni/titoli il server e il client devono vedere lo stesso DBC.
- Per una reputazione nuova visibile nella scheda personaggio:
  - usare un `ReputationIndex` libero e stabile;
  - impostare `ReputationFlags_1 = 16` per renderla visibile;
  - impostare `ParentFactionID` a una categoria esistente se deve comparire sotto una sezione del pannello reputazione. Esempio WotLK: `1097`.
  - verificare anche il DBC binario, non solo la tabella SQL mirror.
- Generare la patch partendo dai DBC originali:
  - input pulito: `custom/client/original_dbc/*.dbc`
  - output server: `client_data/dbc/*.dbc`
  - output client MPQ: `custom/client/dist/patch-4.MPQ`
- Controllare sempre duplicati per ID e per indice funzionale:
  - `Faction.dbc`: nessun doppio `ID` e nessun doppio `ReputationIndex` custom.
  - `CharTitles.dbc`: nessun doppio `ID` e nessun doppio bit custom.
- Copiare `patch-4.MPQ` nella cartella `Data` del client. Per WoW 3.3.5a usare un nome numerico `patch-N.MPQ`; nomi custom come `patch-reborn.MPQ` possono non essere caricati da alcuni client.
- Se una patch custom non viene letta dal client, prima provare un nome numerico libero (`patch-4.MPQ`, `patch-5.MPQ`, ecc.) invece di nomi descrittivi.
- Non lasciare vecchi MPQ descrittivi attivi insieme al patch numerico. Esempio: se esiste `patch-reborn.MPQ`, rinominarlo in `.disabled` quando il contenuto viene spostato in `patch-4.MPQ`.
- Chiudere completamente il client WoW e riaprirlo. I DBC non si ricaricano a caldo.
- Dopo ogni modifica DBC client, svuotare o rinominare la cartella `Cache` del client. Esempio:

```bash
mv /percorso/client/Cache /percorso/client/Cache.before-reborn-patch
```

- Verifica minima per reputazioni nuove:

```sql
SELECT ID, ReputationIndex, ParentFactionID, ReputationFlags_1, Name_Lang_enUS
FROM faction_dbc
WHERE ID = 9000;
```

Il risultato atteso per la reputazione Ora dei Lupi e':

```txt
ID=9000, ReputationIndex=105, ParentFactionID=1097, ReputationFlags_1=16
```

## Talent tree custom e nuove specializzazioni

Caso verificato: ramo paladino custom `Tenebra` su client WotLK 3.3.5a.

### Regole DBC

- `TalentTab.dbc` e `Talent.dbc` devono essere patchati sia lato server (`client_data/dbc`) sia lato client (`DBFilesClient` dentro MPQ).
- Per una tab classe custom:
  - usare un `TalentTabID` libero, esempio `9001`;
  - `ClassMask` deve essere quello della classe. Paladino = `2`;
  - `tabpage` e' 0-based. Holy/Protection/Retribution usano `0/1/2`; una quarta tab usa `3`;
  - `petTalentMask = 0` per classi player;
  - impostare i flag come le tab originali della stessa classe. Per paladino WotLK: `row[17] = LOCALE_MASK`, `row[19] = 2047`;
  - riusare un background valido, esempio `PaladinCombat`, finche non si aggiunge art custom corretta;
  - per un background custom nativo, il nome in `TalentTab.dbc` deve corrispondere a quattro texture in `Interface\TalentFrame`: `<Nome>-TopLeft.blp`, `<Nome>-TopRight.blp`, `<Nome>-BottomLeft.blp`, `<Nome>-BottomRight.blp`.
- Per `Talent.dbc`:
  - ogni talento deve puntare alla tab custom;
  - `row` e `col` sono le coordinate visuali;
  - i rank spell devono esistere in `Spell.dbc`;
  - non lasciare spell rank mancanti: se `Talent.dbc` punta a `900100`, `Spell.dbc` deve contenere `900100`.
- Se il client mostra `Error, this layout is undrawable N` aprendo il ramo custom, controllare prima i prerequisiti/frecce del `Talent.dbc`:
  - i campi `DependsOn_1..3` e `DependsOnRank_1..3` fanno disegnare rami tra talenti;
  - alcuni collegamenti diagonali, laterali o troppo complessi possono mandare in errore il renderer Blizzard anche se i talenti sono visibili;
  - per una fase solo grafica, senza logica talenti, lasciare i prerequisiti a `0` e mantenere solo coordinate, rank spell e tooltip;
  - se servono prerequisiti reali, aggiungerli uno alla volta e verificare nel client dopo ogni build.
- Non riordinare fisicamente `Talent.dbc` o `TalentTab.dbc` quando si aggiungono righe custom. Mantenere l'ordine Blizzard originale e appendere le righe custom in fondo. Il client 3.3.5a puo' enumerare i talenti in base all'ordine fisico del DBC; riordinare per ID puo' far sparire o ridurre i talenti visibili anche se i record sono presenti.

Verifica rapida dell'ordine e del numero talenti:

```bash
python3 - <<'PY'
import struct
from pathlib import Path

root = Path(".")

def rows(path):
    data = path.read_bytes()
    rc, fc, rs, ss = struct.unpack_from("<4I", data, 4)
    rec = data[20:20 + rc * rs]
    return [struct.unpack_from(f"<{fc}i", rec, i * rs) for i in range(rc)]

orig = rows(root / "custom/client/original_dbc/Talent.dbc")
patched = rows(root / "custom/client/patch-reborn/DBFilesClient/Talent.dbc")

for tab in [382, 383, 381, 9001]:
    print("tab", tab)
    print("orig", [r[0] for r in orig if r[1] == tab])
    print("new ", [r[0] for r in patched if r[1] == tab])
PY
```

Per le tab paladino originali ci si aspetta ancora 26 talenti ciascuna e lo stesso ordine del DBC originale.

### Spell rank dei talenti

- Per talenti passivi custom, clonare spell passivi esistenti e sovrascrivere solo gli effetti necessari.
- Gli spell dei rank custom devono essere nel `Spell.dbc` usato dal server e nel `Spell.dbc` client.
- Se il server permette di imparare il talento ma il client mostra tooltip vuoti, icone mancanti o righe invisibili, controllare prima `Spell.dbc` e i rank referenziati in `Talent.dbc`.
- Se il click su un talento custom non incrementa il rank e tutto resta a `0`, controllare anche il tipo usato dal core per mappare spell -> talento:
  - caso verificato: Tenebra usa TalentID `90010+`;
  - AzerothCore aveva `TalentSpellPos::talent_id` come `uint16` in `core/src/server/shared/DataStores/DBCStructure.h`;
  - un TalentID sopra `65535` veniva troncato, quindi `Player::addTalent()` trovava lo spell ma poi falliva su `sTalentStore.LookupEntry(talentPos->talent_id)`;
  - fix verificato: portare `TalentSpellPos` a `uint32` sia nel costruttore sia nel campo `talent_id`, ricompilare `worldserver`, copiare il binario aggiornato in `server/bin/worldserver` e riavviare.
- Dopo il fix del tipo `TalentSpellPos`, verificare il click lato DB:

```bash
/opt/homebrew/opt/mysql@8.4/bin/mysql -h 127.0.0.1 -P 3306 -u acore -pacore acore_characters \
  -e 'SELECT guid,spell,specMask FROM character_talent WHERE spell BETWEEN 900100 AND 900399 ORDER BY guid,spell;'
```

Se il click funziona, il rank passa da `0` a `1` nel client e compare una riga `900xxx` in `character_talent`.

### FrameXML e Blizzard_TalentUI

Per aggiungere una quarta tab classe nel client 3.3.5a non basta il DBC. Serve anche patchare `Blizzard_TalentUI`:

- `Interface/AddOns/Blizzard_TalentUI/Blizzard_TalentUI.xml`:
  - tab 4 diventa una talent tab normale;
  - la tab Glyphs viene spostata a tab 5;
  - la tab Glyphs deve mantenere `text="GLYPHS"` o viene disegnata/cliccata male.

Esempio:

```xml
<Button name="PlayerTalentFrameTab4" inherits="PlayerTalentTabTemplate" id="4">
  ...
</Button>
<Button name="PlayerTalentFrameTab5" inherits="PlayerGlyphTabTemplate" text="GLYPHS" id="5">
  ...
</Button>
```

- `Blizzard_TalentUI.lua`:
  - usare una costante locale/custom, esempio `reborn_MAX_TALENT_TABS = 4`;
  - impostare `GLYPH_TALENT_TAB = reborn_MAX_TALENT_TABS + 1`;
  - aggiornare solo i loop/locali della UI talenti che devono vedere 4 tab;
  - non sovrascrivere il globale Blizzard `MAX_TALENT_TABS`. `TalentFrame.lua` lo usa per layout ed enumerazione interni; forzarlo a 4 puo' far sparire talenti o mostrarne pochi in alcune tab.

Pattern corretto:

```lua
reborn_MAX_TALENT_TABS = 4;
GLYPH_TALENT_TAB = reborn_MAX_TALENT_TABS + 1;
```

Pattern da evitare:

```lua
MAX_TALENT_TABS = 4;
```

### Tooltip custom per talenti che insegnano spell attive (LEARN_SPELL)

Caso verificato: i 6 talenti attivi del Runemaster (DK Twilight tree) usano `SPELL_EFFECT_LEARN_SPELL (36)` come rank spell. Il motore C del client 3.3.5a salta sistematicamente costo/CD/range per questo tipo di spell, anche se i campi sono popolati in `Spell.dbc`.

**Comportamento del motore:**
- `GameTooltip:SetTalent()` mostra nome + descrizione per i rank spell LEARN_SPELL, ma **non mostra mai** costo risorsa, range, cast time o cooldown.
- Non esiste workaround a livello DBC: il problema e' nel codice C del client, non nei dati.

**Soluzione verificata:** sovrascrivere `PlayerTalentFrameTalent_OnEnter` in `Blizzard_TalentUI.lua` e costruire il tooltip da zero con `AddLine`/`AddDoubleLine` per i talenti interessati, saltando `SetTalent()`.

**Schema colori tooltip talenti WoW 3.3.5a** (diverso dai tooltip spell da action bar):

| Elemento                           | Colore | RGB             |
| ---------------------------------- | ------ | --------------- |
| Nome spell                         | Bianco | `1, 1, 1`       |
| Costo risorsa (sx)                 | Bianco | `1, 1, 1`       |
| Range (dx)                         | Bianco | `1, 1, 1`       |
| Cast time (sx)                     | Bianco | `1, 1, 1`       |
| Cooldown (dx)                      | Bianco | `1, 1, 1`       |
| Descrizione                        | Giallo | `1, 0.82, 0`    |
| Prerequisito punti soddisfatto     | Grigio | `0.5, 0.5, 0.5` |
| Prerequisito punti NON soddisfatto | Rosso  | `1, 0, 0`       |
| Requisito arma soddisfatto         | Bianco | `1, 1, 1`       |
| Requisito arma NON soddisfatto     | Rosso  | `1, 0, 0`       |

**Errore verificato:** confondere i colori dei tooltip spell (nome giallo, desc bianca) con i colori dei tooltip talenti (nome bianco, desc gialla). Sono schemi opposti.

**Pattern Lua verificato:**

```lua
local reborn_RM_TAB = 4;  -- indice tab nel talent frame (1-based)

local reborn_RM_ACTIVE = {
    -- req = "melee" → mostra "Requires Melee Weapons" con check equipaggiamento
    -- req = nil     → riga omessa completamente
    [7] = {
        cost = "30 Runic Power", range = "Melee range",
        cast = "Instant",        cd    = nil,
        req  = "melee",
        desc = "Descrizione spell...",
    },
    -- ...
};

local function reborn_HasMeleeWeapon()
    -- GetInventoryItemID vuole due argomenti: ("unit", slotID).
    -- Chiamarlo con un solo argomento restituisce sempre nil silenziosamente.
    -- Per un DK, qualsiasi oggetto in main hand e' un'arma melee (DK non puo'
    -- equipaggiare archi, pistole, bacchette, scudi).
    return GetInventoryItemID("player", INVSLOT_MAINHAND) ~= nil;
end

function PlayerTalentFrameTalent_OnEnter(self)
    local tabIndex = PanelTemplates_GetSelectedTab(PlayerTalentFrame);
    GameTooltip:SetOwner(self, "ANCHOR_RIGHT");

    if tabIndex == reborn_RM_TAB then
        local d = reborn_RM_ACTIVE[self:GetID()];
        if d then
            local tName, _, tier = GetTalentInfo(tabIndex, self:GetID(),
                PlayerTalentFrame.inspect, PlayerTalentFrame.pet,
                PlayerTalentFrame.talentGroup);

            GameTooltip:AddLine(tName, 1, 1, 1);  -- nome: bianco

            -- Prerequisito punti: tier e' 1-based; tier 1 = 0 punti richiesti.
            -- GetTalentTabInfo restituisce: name, iconTexture, pointsSpent, background.
            local pts = (tier - 1) * 5;
            if pts > 0 then
                local tabName, _, pointsSpent = GetTalentTabInfo(tabIndex,
                    PlayerTalentFrame.inspect, PlayerTalentFrame.pet,
                    PlayerTalentFrame.talentGroup);
                local r, g, b = 0.5, 0.5, 0.5;  -- grigio se soddisfatto
                if pointsSpent < pts then r, g, b = 1, 0, 0; end  -- rosso se non soddisfatto
                GameTooltip:AddLine(string.format("Requires %d points in %s", pts, tabName), r, g, b);
            end

            -- Costo + range sulla stessa riga: entrambi bianchi
            GameTooltip:AddDoubleLine(d.cost or "", d.range or "", 1, 1, 1, 1, 1, 1);
            -- Cast + CD sulla stessa riga: entrambi bianchi
            GameTooltip:AddDoubleLine(d.cast or "", d.cd or "", 1, 1, 1, 1, 1, 1);

            -- Requisito arma: bianco se soddisfatto, rosso se no, omesso se nil
            if d.req == "melee" then
                if reborn_HasMeleeWeapon() then
                    GameTooltip:AddLine("Requires Melee Weapons", 1, 1, 1);
                else
                    GameTooltip:AddLine("Requires Melee Weapons", 1, 0, 0);
                end
            end

            -- Descrizione: giallo (NON aggiungere AddLine(" ") vuota prima)
            GameTooltip:AddLine(d.desc, 1, 0.82, 0, 1);
            GameTooltip:Show();
            return;
        end
    end

    -- Per tutti gli altri talenti, comportamento Blizzard standard
    GameTooltip:SetTalent(tabIndex, self:GetID(),
        PlayerTalentFrame.inspect, PlayerTalentFrame.pet,
        PlayerTalentFrame.talentGroup, GetCVarBool("previewTalents"));
end
```

**Errori API verificati:**

- `GetInventoryItemID(slotID)` — **SBAGLIATO**: un argomento, restituisce sempre nil.
- `GetInventoryItemID("player", slotID)` — **CORRETTO**: due argomenti, unit + slot.
- `GetItemInfo(link)` puo' restituire nil per tutti i campi se i dati dell'item non sono ancora in cache al momento dell'OnEnter. Per check sincroni preferire `GetInventoryItemID`.
- `GetTalentTabInfo` restituisce `name, iconTexture, pointsSpent, background` — il terzo valore e' i punti spesi nella tab, utile per il check prerequisito.

**Nota sulle descrizioni:** poiche' non esiste API Lua per leggere la descrizione di una spell custom per ID, il testo va memorizzato nella tabella Lua. I tooltip costruiti da zero in `PlayerTalentFrameTalent_OnEnter` sono l'unica fonte di verita' per costo/CD/range/req/desc delle spell attive insegnate da talenti.

### MPQ locale, TOC e firma Blizzard

`Blizzard_TalentUI` e' un addon Blizzard locale. Per patcharlo in WotLK 3.3.5a:

- mettere DBC e icone in un patch globale, esempio `Data/patch-4.MPQ`;
- mettere `Blizzard_TalentUI.toc/xml/lua` in un patch locale, esempio `Data/enUS/patch-enUS-4.MPQ`;
- se si installa anche la copia loose in `Interface/AddOns/Blizzard_TalentUI`, deve contenere almeno:
  - `Blizzard_TalentUI.toc`;
  - `Blizzard_TalentUI.xml`;
  - `Blizzard_TalentUI.lua`.
- Il `.toc` non deve dichiarare file mancanti. Se contiene `Localization.lua`, quel file deve esistere. Altrimenti il client mostra `Blizzard_TalentUI: Corrupt`.
- Per file Blizzard modificati, rimuovere il flag `## Secure: 1` dal `.toc`.
- Disabilitare la firma `.pub` originale dell'addon, perche' firma i file Blizzard originali e puo' marcare come `Corrupt` i file modificati:

```bash
mv Interface/AddOns/Blizzard_TalentUI/Blizzard_TalentUI.pub \
   Interface/AddOns/Blizzard_TalentUI/Blizzard_TalentUI.pub.disabled
```

Tenere un backup se serve ripristinare:

```bash
cp Interface/AddOns/Blizzard_TalentUI/Blizzard_TalentUI.pub \
   Interface/AddOns/Blizzard_TalentUI/Blizzard_TalentUI.pub.backup
```

TOC minimo funzionante:

```toc
## Interface: 30300
## Title: Blizzard Talent UI
## LoadOnDemand: 1
Blizzard_TalentUI.xml
```

### Installazione e debug nel client

- Copiare sempre entrambe le patch:
  - `custom/client/dist/patch-4.MPQ` -> `Data/patch-4.MPQ`;
  - `custom/client/dist/patch-enUS-4.MPQ` -> `Data/enUS/patch-enUS-4.MPQ`.
- Se si usa anche la cartella loose `Interface/AddOns/Blizzard_TalentUI`, aggiornarla insieme all'MPQ locale o si rischia di testare file vecchi.
- Verificare gli hash sorgente/destinazione:

```bash
shasum -a 256 custom/client/dist/patch-4.MPQ /percorso/client/Data/patch-4.MPQ
shasum -a 256 custom/client/dist/patch-enUS-4.MPQ /percorso/client/Data/enUS/patch-enUS-4.MPQ
```

- Se appare ancora `Blizzard_TalentUI: Corrupt`, controllare nell'ordine:
  1. il `.toc` non dichiara file mancanti;
  2. non c'e' `## Secure: 1`;
  3. `Blizzard_TalentUI.pub` e' disabilitato;
  4. la cartella loose `Blizzard_TalentUI` esiste solo se contiene `toc/xml/lua` completi;
  5. il client e' stato chiuso e riaperto da `Wow.exe`, non dal launcher.
- Se le tab sono allineate ma i talenti spariscono:
  1. controllare di non aver sovrascritto `MAX_TALENT_TABS`;
  2. controllare che `Talent.dbc` mantenga l'ordine originale;
  3. controllare che le tab originali abbiano ancora tutti i talenti;
  4. controllare `Logs/FrameXML.log` per errori Lua.

## Icone custom item e spell

Le icone custom in WoW 3.3.5a non sono solo PNG dentro l'MPQ. Servono asset BLP validi e righe DBC coerenti.

- Formato asset consigliato:
  - sorgente PNG quadrato power-of-two, preferibilmente `64x64` per icone;
  - output `.blp`;
  - BLP2 + DXT5 + alpha 8 bit + mipmap per icone/UI;
  - path MPQ: `Interface\Icons\<NomeIcona>.blp`.
- Sorgenti asset:
  - preferire sorgenti versionabili dentro repo, esempio `custom/docs/paladin/Twlight icons/`;
  - evitare dipendenze da `/Volumes/Biagio/Downloads/...` per asset permanenti, perche' una build futura potrebbe fallire se i download vengono spostati.
- Background talenti:
  - non e' una `SpellIcon.dbc`: il TalentFrame legge il nome dal campo background di `TalentTab.dbc`;
  - caso verificato: `TalentTab.dbc` background `Twilight` + texture `Interface\TalentFrame\Twilight-TopLeft.blp`, `Twilight-TopRight.blp`, `Twilight-BottomLeft.blp`, `Twilight-BottomRight.blp`;
  - il converter BLP puo' fallire su texture rettangolari con mipmap. Per i pezzi del TalentFrame usare `--no-mipmaps`; per le icone continuare a usare mipmap.
- Non generare BLP a mano con writer improvvisati. Usare un converter reale. In questo progetto il tool verificato e':

```bash
cargo install blp-conv
/Users/biagiogennuso/.cargo/bin/blp-conv \
  --blp-version blp2 \
  --blp-format dxt5 \
  --alpha-bits 8 \
  input_64.png output.blp
```

- Verificare sempre il roundtrip del BLP prima di fare il patch:

```bash
/Users/biagiogennuso/.cargo/bin/blp-conv output.blp /tmp/check.png
file /tmp/check.png
```

### Clonare spell esistenti in Spell.dbc

Quando si crea una spell custom clonando una spell Blizzard, i campi di Spell.dbc 3.3.5a (234 campi, 936 byte per record) NON corrispondono ai nomi intuitivi. Errori qui causano comportamenti invisibili e difficili da debuggare.

**Mappa campi verificata empiricamente su 3.3.5a:**

| Campo (indice 0-based) | Nome                         | Note                                                        |
| ---------------------- | ---------------------------- | ----------------------------------------------------------- |
| 0                      | ID                           |                                                             |
| 4                      | Attributes                   | bit flags comportamento principale                          |
| 5                      | AttributesEx                 |                                                             |
| 6                      | AttributesEx2                | **NON e' SchoolMask**                                       |
| 7                      | AttributesEx3                |                                                             |
| 28                     | CastingTimeIndex             | 1 = istantanea                                              |
| 34                     | procFlags                    | quando scatta il proc                                       |
| 35                     | procChance                   | percentuale (0-100)                                         |
| 40                     | DurationIndex                | riferimento a SpellDuration.dbc                             |
| 71,72,73               | Effect[0..2]                 | 6 = APPLY_AURA, 2 = SCHOOL_DAMAGE                           |
| 86,87,88               | ImplicitTargetA[0..2]        | 1 = self, 6 = nemico                                        |
| 95,96,97               | EffectAura[0..2]             | **3 = PERIODIC_DAMAGE**, 4 = DUMMY, 42 = PROC_TRIGGER_SPELL |
| 116,117,118            | EffectTriggerSpell[0..2]     | spell ID da triggerare                                      |
| 133                    | SpellIconID                  |                                                             |
| 134                    | ActiveIconID                 |                                                             |
| 136                    | Name offset (stringa)        | spellbook e tooltip                                         |
| 153                    | Rank offset (stringa)        |                                                             |
| 170                    | Description offset (stringa) | testo long nella scheda spell                               |
| **187**                | **Tooltip offset (stringa)** | **testo breve nel buff/debuff al hover**                    |
| **225**                | **SchoolMask**               | **Shadow=32, Holy=2, Physical=1**                           |

**Errore verificato e corretto:**

Impostare `spell[6] = 32` pensando di settare "Shadow school mask" aggiunge invece il flag `SPELL_ATTR2_AUTO_REPEAT_FLAG` (0x20) su `AttributesEx2`. Il risultato e' che la spell si comporta come un auto-shot: non applica il buff, non mostra l'icona in alto a destra, e il client mostra "Interrupted".

```python
# SBAGLIATO - imposta AUTO_REPEAT flag su AttributesEx2
spell[6] = 32

# CORRETTO - imposta Shadow school mask al campo giusto
SP_SCHOOLMASK = 225
spell[SP_SCHOOLMASK] = 32   # Shadow
spell[SP_SCHOOLMASK] = 2    # Holy
spell[SP_SCHOOLMASK] = 1    # Physical
```

**Come verificare il campo SchoolMask:**

```bash
python3 - << 'EOF'
import struct
from pathlib import Path

DBC = Path("custom/client/original_dbc/Spell.dbc")
data = DBC.read_bytes()
rc, fc, rs, _ = struct.unpack_from("<4I", data, 4)

# Cerca spell Holy e Shadow note per trovare il campo SchoolMask
holy = {20375, 20154, 20165}   # Paladino seals = Holy = 2
shadow = {686, 8092, 589}      # Shadow Bolt, Mind Blast, SWP = Shadow = 32

for i in range(rc):
    row = list(struct.unpack_from(f"<{fc}i", data, 20 + i * rs))
    if row[0] in holy:
        print(f"Holy spell {row[0]}: campi con valore 2 in [200-234]: "
              f"{[fi for fi in range(200, fc) if row[fi] == 2]}")
    if row[0] in shadow:
        print(f"Shadow spell {row[0]}: campi con valore 32 in [200-234]: "
              f"{[fi for fi in range(200, fc) if row[fi] == 32]}")
EOF
```

Risultato atteso: tutti i campi convergono a `[225]`.

**Come verificare la spell custom dopo la patch:**

```bash
python3 - << 'EOF'
import struct
from pathlib import Path

DBC = Path("client_data/dbc/Spell.dbc")
data = DBC.read_bytes()
rc, fc, rs, _ = struct.unpack_from("<4I", data, 4)

for i in range(rc):
    row = list(struct.unpack_from(f"<{fc}i", data, 20 + i * rs))
    if row[0] in (900403, 900404):
        print(f"Spell {row[0]}:")
        print(f"  effect[0]={row[71]}  applyaura[0]={row[95]}  trigger[0]={row[116]}")
        print(f"  durationIndex={row[40]}  castingTime={row[28]}")
        print(f"  schoolMask[225]={row[225]}  attributesEx2[6]={row[6]}")
EOF
```

Per una spell-buff (tipo Seal), i valori attesi sono:
- `effect[0]=6` (APPLY_AURA)
- `applyaura[0]=42` (PROC_TRIGGER_SPELL)
- `durationIndex=30` (30 minuti, ereditato dal clone)
- `schoolMask[225]=32` (Shadow)
- `attributesEx2[6]=0` (nessun flag errato)

**Terzo errore verificato: SpellTooltip (field 187) e' separato da SpellDesc (field 170):**

Il client WoW usa il campo `SpellTooltip` (field 187, stringa) per il testo breve che appare nel buff/debuff al hover. `SpellDesc` (field 170) appare invece nella scheda spell del libro incantesimi. Sono due stringhe indipendenti.

Quando si clona una spell, il campo 187 eredita il testo originale. Esempio verificato: clonando Holy Vengeance (31803) per Twilight Mark (900401), il tooltip rimaneva "Holy damage every $t1 sec." anche dopo aver impostato `schoolmask=32`. Clonando Seal of Command (20375) per Seal of Twilight (900403), rimaneva "Melee attacks deal additional Holy damage."

Il debugger: `python3` sul DBC estratto dal MPQ, campo `s[187]`. Non basta verificare field[225].

```python
SP_TOOLTIP = 187  # aggiungere alle costanti del patch script

# Per un DoT shadow:
mark_tooltip = add_string(strings, "$s1 Shadow damage every $t1 seconds.")
mark[SP_TOOLTIP] = mark_tooltip
for col in range(SP_TOOLTIP + 1, SP_TOOLTIP + 16):
    mark[col] = 0

# Per un buff proc shadow:
seal_tooltip = add_string(strings, "Melee attacks deal additional Shadow damage.")
seal[SP_TOOLTIP] = seal_tooltip
for col in range(SP_TOOLTIP + 1, SP_TOOLTIP + 16):
    seal[col] = 0
```

Regola: **ogni volta che si clona una spell, sovrascrivere sempre tutti e tre i campi stringa: SP_NAME (136), SP_DESC (170), SP_TOOLTIP (187)** e azzerare i 15 campi locale successivi per ciascuno.

**Secondo errore verificato: SPELL_AURA_PERIODIC_DAMAGE = 3, NON 35:**

Il numero dell'aura PERIODIC_DAMAGE e' `3`. Confonderlo con `35` (= `SPELL_AURA_MOD_INCREASE_ENERGY`) causa:
- nessun danno periodico applicato al target;
- il client mostra il debuff ma senza numeri di danno;
- `applyaura=35` aumenta energia/mana del target invece di fare danno.

Verifica empirica: Shadow Word: Pain (ID 589) ha `applyaura[0]=3`. Curse of Agony (ID 980) ha `applyaura[0]=3`.

```python
# SBAGLIATO
mark[SP_APPLYAURA[0]] = 35  # SPELL_AURA_MOD_INCREASE_ENERGY — danno zero

# CORRETTO
mark[SP_APPLYAURA[0]] = 3   # SPELL_AURA_PERIODIC_DAMAGE — danno ogni tick
```

Aure frequenti in Spell.dbc:

| Valore | Costante AzerothCore           |
| ------ | ------------------------------ |
| 3      | SPELL_AURA_PERIODIC_DAMAGE     |
| 4      | SPELL_AURA_DUMMY               |
| 8      | SPELL_AURA_PERIODIC_HEAL       |
| 35     | SPELL_AURA_MOD_INCREASE_ENERGY |
| 42     | SPELL_AURA_PROC_TRIGGER_SPELL  |

**Regola operativa per clonare seal Paladino:**

- Usare come base `Seal of Command` (ID 20375): ha gia' APPLY_AURA + PROC_TRIGGER_SPELL + 30 min + instant cast.
- Sovrascrivere solo: ID, SchoolMask (campo 225), TriggerSpell (campo 116), icon (133/134), stringhe nome/desc.
- NON toccare il campo 6 (AttributesEx2) se non si sa esattamente cosa fa.
- Dopo ogni cambio DBC **riavviare il worldserver** (i DBC sono caricati in RAM all'avvio).

### Spell/aura icon

Per cambiare l'icona di un'aura esistente:

- `SpellIcon.dbc`: aggiungere una riga con ID custom e path completo, esempio `Interface\Icons\Spell_BrokenMoon_Mark`.
- `Spell.dbc`: nel record dello spell, aggiornare:
  - campo `133` = `SpellIconID`;
  - campo `134` = `ActiveIconID`.
- Dopo la patch, testare con:

```text
.unaura <spell_id>
.aura <spell_id>
```

Se l'aura sparisce dalla UI dopo la modifica, ripristinare `Spell.dbc` e controllare prima che il BLP sia valido.

### Item icon

Per item custom non basta `item_template.displayid`.

Servono entrambi i DBC client/server:

- `ItemDisplayInfo.dbc`:
  - creare un nuovo display ID custom;
  - copiare una riga base compatibile;
  - cambiare il campo icona corretto.
- Nel formato WotLK usato da questo core, `ItemDisplayTemplateEntryfmt = "nxxxxsxxxxxxxxxxxxxxxxxxx"`, quindi il campo icona e' il campo `5`, non il `7`.
- `Item.dbc`:
  - aggiungere una riga per l'item custom;
  - campi: `id`, `class`, `subclass`, `sound override`, `material`, `display id`, `inventory type`, `sheathe type`.
  - Senza `Item.dbc`, l'item puo' vedersi equipaggiato correttamente ma apparire con `?` nello zaino, nel reward frame, o non equipaggiarsi via right-click.

Esempio per guanti leather custom:

```txt
Item.dbc row:
900020, 4, 2, -1, 6, 900080, 10, 0

ItemDisplayInfo.dbc:
ID 900080, icon field 5 = INV_Gauntlets_BrokenMoon
```

Anche il DB server deve essere coerente:

```sql
SELECT entry, class, subclass, displayid, InventoryType, Material, sheath
FROM item_template
WHERE entry = 900020;
```

Valori attesi per i guanti Ora dei Lupi (leather agility-melee):

```txt
entry=900020, class=4, subclass=2, displayid=900080, InventoryType=10, Material=6, sheath=0
```

### Cache item

Gli item sono cacheati in `Cache/WDB/<locale>/itemcache.wdb`. Dopo ogni cambio a `item_template`, `Item.dbc` o `ItemDisplayInfo.dbc`:

- chiudere completamente il client;
- rinominare o rimuovere `Cache`;
- riaprire il client;
- se l'item era gia' in borsa, ricrearlo durante il test:

```text
.delitem 900020
.additem 900020
```

### Reward quest e box icona

Ci sono due modi diversi di dare item reward:

- `RewardItem1`: reward fisso. Il client lo mostra nella sezione "You will receive". Il player non sceglie nulla.
- `RewardChoiceItemID1`: reward selezionabile. Il client usa il layout "Choose one of these rewards" con box cliccabile.

Per una singola ricompensa obbligatoria, `RewardItem1` e' semanticamente corretto. Se si vuole forzare il box selezionabile classico, usare `RewardChoiceItemID1` con quantita' `1`, sapendo che il player dovra' selezionare/confermare quel reward nel completamento quest.

## Spellbook custom per specializzazioni sbloccabili

Caso verificato: spellbook tab `Twilight` per il ramo paladino custom Tenebra/Twilight.

### DBC necessari

Per far comparire una nuova tab nello spellbook non basta creare una spell in `Spell.dbc` o impararla via C++.

Servono tutti questi DBC patchati lato server (`client_data/dbc`) e lato client (`DBFilesClient` dentro `patch-4.MPQ`):

- `Spell.dbc`: record della spell custom.
  - esempio verificato: `900400` = `Judgement of Twilight`;
  - campo `133` = `SpellIconID`;
  - campo `134` = `ActiveIconID`;
  - per una prima versione castabile si puo' clonare una spell Blizzard simile, poi sovrascrivere ID, nome, descrizione e icona.
- `SpellIcon.dbc`: riga icona custom.
  - esempio verificato: `9013` = `Interface\Icons\Spell_Twilight_Judgement`;
  - il BLP deve essere presente nell'MPQ in `Interface\Icons\Spell_Twilight_Judgement.blp`.
- `SkillLine.dbc`: nuova tab spellbook.
  - esempio verificato: `9002`, categoria `7` class skill, nome `Twilight`, icona `9017`;
  - tenere separata l'icona della tab spellbook dall'icona della tab talenti se si vogliono visuali diverse. Caso verificato: spellbook `9017 = Spell_Twilight_Spellbook`, talent tab `9010 = Spell_Twilight_Aura`;
  - senza questa riga il client non ha una sezione spellbook in cui mettere la spell.
- `SkillLineAbility.dbc`: associa spell -> tab spellbook.
  - esempio verificato: ID riga `900400`, `SkillLine = 9002`, `Spell = 900400`, `ClassMask = 2`, `MinSkillLineRank = 1`;
  - `AcquireMethod = 2` significa "learned together with entire skill";
  - se si aggiungono altre spell Twilight, aggiungere una riga per ogni spell e puntarla alla stessa `SkillLine = 9002`.
- `SkillRaceClassInfo.dbc`: rende valida la skill line per razza/classe.
  - esempio verificato: ID riga `9002`, `SkillID = 9002`, `RaceMask = -1`, `ClassMask = 2`, `Flags = 1040`;
  - senza questa riga il server puo' considerare la skill non valida per il paladino e non mostrarla/salvarla correttamente.

Nel progetto questi DBC sono generati da:

```bash
python3 custom/tools/dbc_patch_reborn.py
bash custom/tools/build_client_patch.sh /percorso/client
```

### Sblocco server della tab spellbook

Quando una specializzazione e' sbloccata da una quest o flag custom, la logica C++ deve sincronizzare sia la skill line sia le spell.

Pattern verificato in `mod-reborn` (`src/paladin/FourthOath.cpp`):

```cpp
if (!player->HasSkill(9002))
    player->SetSkill(9002, 0, 1, 1);

if (!player->HasSpell(900400))
    player->learnSpell(900400, false);
```

Regole operative:

- chiamare questa sync quando il player completa la quest di unlock;
- chiamarla anche a login se il flag server-side e' gia' presente o la quest finale e' gia rewarded;
- non basarsi solo su `RewardSpell` se lo sblocco dipende da flag custom: e' meglio una sync idempotente lato `PlayerScript`;
- per Tenebra/Twilight il flag verificato e' `custom_reborn_quarto_giuramento_progress.tenebra_unlocked = 1`;
- se il player ha gia' completato la quest finale prima della patch, al login va riallineato il flag e va imparata la spell.

### Verifica DBC rapida

Controllare le righe custom nei DBC patchati:

```bash
python3 - <<'PY'
import struct
from pathlib import Path

def read(path):
    data = Path(path).read_bytes()
    rc, fc, rs, ss = struct.unpack_from("<4I", data, 4)
    records = data[20:20 + rc * rs]
    strings = data[20 + rc * rs:]
    rows = [struct.unpack_from(f"<{fc}i", records, i * rs) for i in range(rc)]
    return rows, strings

def s(strings, off):
    if not off:
        return ""
    end = strings.find(b"\0", off)
    return strings[off:end].decode("utf8", "replace")

sl, ss = read("custom/client/patch-reborn/DBFilesClient/SkillLine.dbc")
print([ (r[0], r[1], s(ss, r[3]), r[37]) for r in sl if r[0] == 9002 ])

sla, _ = read("custom/client/patch-reborn/DBFilesClient/SkillLineAbility.dbc")
print([ r[:12] for r in sla if r[1] == 9002 ])

srci, _ = read("custom/client/patch-reborn/DBFilesClient/SkillRaceClassInfo.dbc")
print([ r for r in srci if r[1] == 9002 ])
PY
```

Risultato atteso per Twilight:

```txt
SkillLine: ID 9002, category 7, name Twilight, icon 9017
SkillLineAbility: SkillLine 9002, Spell 900400, ClassMask 2, MinSkillLineRank 1, AcquireMethod 2
SkillRaceClassInfo: SkillID 9002, RaceMask -1, ClassMask 2, Flags 1040
```

### Debug se non si vede nulla

Se la nuova tab/spell non compare:

1. controllare che `patch-4.MPQ` nel client contenga `SkillLine.dbc`, `SkillLineAbility.dbc`, `SkillRaceClassInfo.dbc`, `Spell.dbc`, `SpellIcon.dbc` e i BLP;
2. confrontare hash sorgente/destinazione:

```bash
shasum -a 256 custom/client/dist/patch-4.MPQ /percorso/client/Data/patch-4.MPQ
```

3. controllare che `server/bin/worldserver` sia il binario appena compilato:

```bash
shasum -a 256 build/src/server/apps/worldserver server/bin/worldserver
```

4. se gli hash differiscono, fermare `worldserver`, copiare il binario nuovo e riavviare;
5. controllare che `worldserver` stia ascoltando ed abbia caricato i DBC senza errori:

```bash
lsof -nP -iTCP:8085 -sTCP:LISTEN
tail -n 120 server/logs/world-stack.out
```

6. chiudere completamente il client, rinominare/rimuovere `Cache`, riaprire `Wow.exe`;
7. fare logout/login col personaggio gia' sbloccato, per far partire la sync lato `PlayerScript`.

## C++

- Ricompilare `worldserver` quando si toccano script o logica custom C++.
- Installare il binario compilato in `server/bin/worldserver` solo a server fermo.
- Dopo installazione, riavviare la stack e verificare i log:
  - server ready;
  - modulo custom caricato;
  - nessun errore DBC o SQL.
- Non fidarsi di una build riuscita se il server sta ancora usando un binario vecchio. Confrontare hash o timestamp del binario in `build/.../worldserver` e `server/bin/worldserver`.

### Velocizzare il build con ccache

Il build completo richiede 40-60 min. Con ccache, dopo il primo build, ricompilare un singolo `.cpp` costa ~30-60 sec.

**Setup (una volta sola):**

```bash
brew install ccache
```

Aggiungere queste due flag al comando cmake di configurazione (già presente in `build/CMakeCache.txt` da giugno 2026):

```
-DCMAKE_C_COMPILER_LAUNCHER=ccache
-DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

Comando completo di riconfigurazione con ccache:

```bash
cd /Volumes/Biagio/Biagio/reborn/build && cmake /Volumes/Biagio/Biagio/reborn/core \
  -DCMAKE_INSTALL_PREFIX=/Volumes/Biagio/Biagio/reborn/server \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DTOOLS_BUILD=all \
  -DSCRIPTS=static \
  -DMODULES=static \
  -DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl \
  -DBoost_ROOT=/opt/homebrew/opt/boost \
  -DMYSQL_ROOT_DIR=/opt/homebrew/opt/mysql@8.4 \
  -DMYSQL_INCLUDE_DIR=/opt/homebrew/opt/mysql@8.4/include/mysql \
  -DMYSQL_LIBRARY=/opt/homebrew/opt/mysql@8.4/lib/libmysqlclient.dylib \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

Verificare che ccache sia attivo:

```bash
grep "COMPILER_LAUNCHER" build/CMakeCache.txt
# Atteso: CMAKE_CXX_COMPILER_LAUNCHER:UNINITIALIZED=ccache
```

Statistiche ccache:

```bash
ccache -s   # hit rate, dimensione cache
ccache -C   # svuota cache (forza rebuild completo)
```

Note:
- Il primo build dopo la configurazione è ancora lento (popola la cache).
- Aggiungere una **nuova directory** modulo richiede `cmake .` (riconfigura), ma non invalida la cache dei `.o` già compilati.
- Aggiungere un **nuovo `.cpp`** in una directory esistente non richiede riconfigurazione.
- Usare `-j8` (o più su Apple Silicon M-series) invece di `-j4`.

## Moduli pesanti

- Spegnere un modulo dal file `.conf` riduce il lavoro runtime, ma non riduce i tempi di compilazione.
- Se un modulo non serve durante lo sviluppo, disabilitarlo da CMake. Esempio per `mod-playerbots`:

```bash
cmake -S core -B build -DMODULE_MOD-PLAYERBOTS=disabled
cmake --build build -j8 --target worldserver
```

- Per riattivarlo in futuro:

```bash
cmake -S core -B build -DMODULE_MOD-PLAYERBOTS=default
cmake --build build -j8 --target worldserver
```

- Dopo aver cambiato configurazione CMake, controllare l'output "Modules configuration" e verificare che il modulo sia nella sezione giusta.

## Test GM corretti

- Se una quest e' gia attiva, `.quest add <id>` non rilancia sempre la logica di accettazione. Prima rimuoverla:
  - `.quest remove 90023`
  - `.quest add 90023`
- Per testare l'accettazione dell'ultima quest:
  - `.quest remove 90026`
  - `.quest add 90026`
- Per testare il requisito Exalted:
  - uccidere i mob previsti se si vuole testare il flusso reale;
  - usare `.modify reputation 9000 42000` solo per saltare il farming durante debug.
- Per forzare il refresh lato server di una reputazione custom durante debug:
  - `.modify reputation 9000 42000`
  - aprire/chiudere il pannello reputazioni;
  - se ancora non compare ma il DB e' corretto, il problema e' quasi sempre client DBC/MPQ/cache.
- Dopo test su aura/reputazioni, fare logout/login quando serve verificare persistenza o ricarica stato.

## Quando qualcosa non funziona

Checklist rapida:

1. La SQL e' stata applicata al DB giusto?
2. Il server e' stato riavviato dopo SQL DBC o C++?
3. Il binario in esecuzione e' quello appena compilato?
4. Il client ha il nuovo `patch-4.MPQ` in `Data`?
5. Il client e' stato chiuso e riaperto?
6. La cartella `Cache` e' stata svuotata/rinominata?
7. La quest era gia attiva, quindi l'hook di accept non e' ripartito?
8. Ci sono righe legacy duplicate nel DB o nei DBC?
9. Per reputazioni nuove: `ParentFactionID` punta a una categoria esistente?
10. Il nome MPQ e' numerico (`patch-N.MPQ`) e non descrittivo?

## Comandi utili

Applicare la migrazione:

```bash
/opt/homebrew/opt/mysql@8.4/bin/mysql --protocol=TCP -h127.0.0.1 -P3306 -uacore -pacore acore_world -e "source custom/sql/01_paladin_wolf_chain.sql"
```

Rigenerare patch client:

```bash
bash custom/tools/build_client_patch.sh /percorso/del/client
```

Ricompilare worldserver:

```bash
cmake --build build -j8 --target worldserver
```

Avviare worldserver in background (con stdin aperto per evitare morte per EOF):

```bash
cd /Volumes/Biagio/Biagio/reborn/server/bin && \
  tail -f /dev/null | ./worldserver \
    --config /Volumes/Biagio/Biagio/reborn/server/etc/worldserver.conf \
    > /Volumes/Biagio/Biagio/reborn/server/worldserver.log 2>&1 &
```

Seguire il log:

```bash
tail -f /Volumes/Biagio/Biagio/reborn/server/worldserver.log
```
