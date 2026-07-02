#include "AllSpellScript.h"
#include "Player.h"
#include "PlayerScript.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "SpellInfo.h"
#include "Unit.h"
#include "UnitScript.h"
#include <algorithm>
#include <unordered_map>

namespace
{
constexpr uint32 SPELL_INNER_FERVOR = 900201;
constexpr uint32 SPELL_FERVOR_AURA = 900202;
constexpr uint8 REDIANCE_UNLOCK_LEVEL = 30;
constexpr uint8 MAX_FERVOR_STACKS = 5;
constexpr uint32 FERVOR_DECAY_MS = 6 * IN_MILLISECONDS;

// Fill these when the corresponding Rediance spells are added to Spell.dbc.
constexpr uint32 SPELL_FLAME_OF_JUDGMENT = 0;
constexpr uint32 SPELL_MARK_OF_SIN = 0;
constexpr uint32 SPELL_DIVINE_JUDGMENT = 0;

struct FervorState
{
    uint8 stacks = 0;
    uint32 decayTimer = FERVOR_DECAY_MS;
};

std::unordered_map<ObjectGuid::LowType, FervorState> FervorByPlayer;

bool IsGenerator(uint32 spellId)
{
    return spellId != 0 && (spellId == SPELL_FLAME_OF_JUDGMENT || spellId == SPELL_MARK_OF_SIN);
}

bool IsConsumer(uint32 spellId)
{
    return spellId != 0 && spellId == SPELL_DIVINE_JUDGMENT;
}

FervorState& GetState(Player* player)
{
    return FervorByPlayer[player->GetGUID().GetCounter()];
}

void SyncAura(Player* player, FervorState const& state)
{
    if (!state.stacks)
    {
        player->RemoveAurasDueToSpell(SPELL_FERVOR_AURA);
        return;
    }

    Aura* aura = player->GetAura(SPELL_FERVOR_AURA);
    if (!aura)
        aura = player->AddAura(SPELL_FERVOR_AURA, player);

    if (aura)
        aura->SetStackAmount(state.stacks);
}

void SetStacks(Player* player, uint8 stacks)
{
    FervorState& state = GetState(player);
    state.stacks = std::min<uint8>(stacks, MAX_FERVOR_STACKS);
    state.decayTimer = FERVOR_DECAY_MS;
    SyncAura(player, state);
}

void GenerateFervor(Player* player)
{
    FervorState& state = GetState(player);
    SetStacks(player, std::min<uint8>(state.stacks + 1, MAX_FERVOR_STACKS));
}

void ConsumeFervor(Player* player)
{
    FervorState& state = GetState(player);
    if (!state.stacks)
        return;

    SetStacks(player, state.stacks - 1);
}

uint32 DirectDamageTakenBonusPct(Player* player)
{
    FervorState const& state = GetState(player);
    if (state.stacks < 3)
        return 0;

    return (state.stacks - 2) * 8;
}
}

class reborn_rediance_player_script : public PlayerScript
{
public:
    reborn_rediance_player_script() : PlayerScript("reborn_rediance_player_script",
        {
            PLAYERHOOK_ON_LOGIN,
            PLAYERHOOK_ON_LOGOUT,
            PLAYERHOOK_ON_UPDATE,
            PLAYERHOOK_ON_LEVEL_CHANGED
        })
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        if (player->getClass() != CLASS_PRIEST)
            return;

        if (player->GetLevel() >= REDIANCE_UNLOCK_LEVEL && !player->HasSpell(SPELL_INNER_FERVOR))
            player->learnSpell(SPELL_INNER_FERVOR, false);
    }

    void OnPlayerLogout(Player* player) override
    {
        FervorByPlayer.erase(player->GetGUID().GetCounter());
    }

    void OnPlayerLevelChanged(Player* player, uint8 /*oldlevel*/) override
    {
        if (player->getClass() != CLASS_PRIEST)
            return;

        if (player->GetLevel() >= REDIANCE_UNLOCK_LEVEL && !player->HasSpell(SPELL_INNER_FERVOR))
            player->learnSpell(SPELL_INNER_FERVOR, false);
    }

    void OnPlayerUpdate(Player* player, uint32 diff) override
    {
        if (player->getClass() != CLASS_PRIEST)
            return;

        FervorState& state = GetState(player);
        if (!state.stacks)
            return;

        if (state.decayTimer > diff)
        {
            state.decayTimer -= diff;
            return;
        }

        state.stacks -= 1;
        state.decayTimer = FERVOR_DECAY_MS;
        SyncAura(player, state);
    }
};

class reborn_rediance_spell_script : public AllSpellScript
{
public:
    reborn_rediance_spell_script() : AllSpellScript("reborn_rediance_spell_script", { ALLSPELLHOOK_ON_CAST })
    {
    }

    void OnSpellCast(Spell* /*spell*/, Unit* caster, SpellInfo const* spellInfo, bool /*skipCheck*/) override
    {
        if (!caster || !spellInfo)
            return;

        Player* player = caster->ToPlayer();
        if (!player || player->getClass() != CLASS_PRIEST)
            return;

        if (IsGenerator(spellInfo->Id))
            GenerateFervor(player);
        else if (IsConsumer(spellInfo->Id))
            ConsumeFervor(player);
    }
};

class reborn_rediance_damage_script : public UnitScript
{
public:
    reborn_rediance_damage_script() : UnitScript("reborn_rediance_damage_script", true,
        {
            UNITHOOK_MODIFY_MELEE_DAMAGE,
            UNITHOOK_MODIFY_SPELL_DAMAGE_TAKEN
        })
    {
    }

    void ModifyMeleeDamage(Unit* target, Unit* /*attacker*/, uint32& damage) override
    {
        Player* player = target ? target->ToPlayer() : nullptr;
        if (!player)
            return;

        if (uint32 bonusPct = DirectDamageTakenBonusPct(player))
            damage += CalculatePct(damage, bonusPct);
    }

    void ModifySpellDamageTaken(Unit* target, Unit* /*attacker*/, int32& damage, SpellInfo const* /*spellInfo*/) override
    {
        if (damage <= 0)
            return;

        Player* player = target ? target->ToPlayer() : nullptr;
        if (!player)
            return;

        if (uint32 bonusPct = DirectDamageTakenBonusPct(player))
            damage += CalculatePct(damage, bonusPct);
    }
};

void Addmod_rebornScripts()
{
    new reborn_rediance_player_script();
    new reborn_rediance_spell_script();
    new reborn_rediance_damage_script();
}
