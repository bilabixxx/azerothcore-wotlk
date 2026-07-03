#include "AllSpellScript.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "PlayerScript.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "Unit.h"
#include "UnitScript.h"
#include <algorithm>
#include <array>
#include <unordered_map>

namespace
{
constexpr uint32 SPELL_INNER_FERVOR = 900201;
constexpr uint32 SPELL_FERVOR_AURA_FIRST = 900202;
constexpr uint32 SPELL_FERVOR_AURA_LAST = 900206;
constexpr uint8 REDIANCE_UNLOCK_LEVEL = 30;
constexpr uint8 MAX_FERVOR_STACKS = 5;
constexpr uint32 FERVOR_DECAY_MS = 6 * IN_MILLISECONDS;

constexpr uint32 SPELL_FLAME_OF_JUDGMENT_FIRST = 900210;
constexpr uint32 SPELL_FLAME_OF_JUDGMENT_LAST = 900219;
constexpr uint32 SPELL_MARK_OF_SIN_FIRST = 900230;
constexpr uint32 SPELL_MARK_OF_SIN_LAST = 900238;
constexpr uint32 SPELL_DIVINE_JUDGMENT = 0;

struct FervorState
{
    uint8 stacks = 0;
    uint32 decayTimer = FERVOR_DECAY_MS;
};

struct MarkOfSinRankData
{
    uint32 spellId;
    uint32 explosionDamagePerFervor;
};

struct MarkSnapshotKey
{
    ObjectGuid::LowType target;
    ObjectGuid::LowType caster;
    uint32 spellId;

    bool operator==(MarkSnapshotKey const& other) const
    {
        return target == other.target && caster == other.caster && spellId == other.spellId;
    }
};

struct MarkSnapshotKeyHash
{
    std::size_t operator()(MarkSnapshotKey const& key) const
    {
        return std::hash<ObjectGuid::LowType>()(key.target)
            ^ (std::hash<ObjectGuid::LowType>()(key.caster) << 1)
            ^ (std::hash<uint32>()(key.spellId) << 2);
    }
};

std::unordered_map<ObjectGuid::LowType, FervorState> FervorByPlayer;
std::unordered_map<MarkSnapshotKey, uint8, MarkSnapshotKeyHash> MarkSnapshots;

constexpr std::array<MarkOfSinRankData, 9> MarkOfSinRanks =
{{
    {900230, 45},
    {900231, 90},
    {900232, 140},
    {900233, 190},
    {900234, 235},
    {900235, 275},
    {900236, 320},
    {900237, 355},
    {900238, 390},
}};

bool IsFlameOfJudgment(uint32 spellId)
{
    return spellId >= SPELL_FLAME_OF_JUDGMENT_FIRST && spellId <= SPELL_FLAME_OF_JUDGMENT_LAST;
}

bool IsMarkOfSin(uint32 spellId)
{
    return spellId >= SPELL_MARK_OF_SIN_FIRST && spellId <= SPELL_MARK_OF_SIN_LAST;
}

bool IsGenerator(uint32 spellId)
{
    return IsFlameOfJudgment(spellId) || IsMarkOfSin(spellId);
}

bool IsConsumer(uint32 spellId)
{
    return spellId != 0 && spellId == SPELL_DIVINE_JUDGMENT;
}

MarkOfSinRankData const* GetMarkOfSinRank(uint32 spellId)
{
    auto itr = std::find_if(MarkOfSinRanks.begin(), MarkOfSinRanks.end(), [spellId](MarkOfSinRankData const& rank)
    {
        return rank.spellId == spellId;
    });

    return itr != MarkOfSinRanks.end() ? &*itr : nullptr;
}

FervorState& GetState(Player* player)
{
    return FervorByPlayer[player->GetGUID().GetCounter()];
}

uint32 FervorAuraForStacks(uint8 stacks)
{
    if (!stacks)
        return 0;

    return SPELL_FERVOR_AURA_FIRST + std::min<uint8>(stacks, MAX_FERVOR_STACKS) - 1;
}

void RemoveFervorAuras(Player* player, uint32 exceptSpellId = 0)
{
    for (uint32 spellId = SPELL_FERVOR_AURA_FIRST; spellId <= SPELL_FERVOR_AURA_LAST; ++spellId)
        if (spellId != exceptSpellId)
            player->RemoveAurasDueToSpell(spellId);
}

void SyncAura(Player* player, FervorState const& state, bool refreshDuration)
{
    if (!state.stacks)
    {
        RemoveFervorAuras(player);
        return;
    }

    uint32 auraSpellId = FervorAuraForStacks(state.stacks);
    RemoveFervorAuras(player, auraSpellId);

    Aura* aura = player->GetAura(auraSpellId);
    if (!aura)
        aura = player->AddAura(auraSpellId, player);

    if (aura)
    {
        aura->SetStackAmount(state.stacks);

        if (refreshDuration)
        {
            aura->SetMaxDuration(FERVOR_DECAY_MS);
            aura->SetDuration(FERVOR_DECAY_MS);
        }
    }
}

void SetStacks(Player* player, uint8 stacks, bool refreshDuration = true)
{
    FervorState& state = GetState(player);
    state.stacks = std::min<uint8>(stacks, MAX_FERVOR_STACKS);
    state.decayTimer = FERVOR_DECAY_MS;
    SyncAura(player, state, refreshDuration);
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

uint32 DamageTakenBonusPct(Player* player)
{
    FervorState const& state = GetState(player);
    if (state.stacks < 3)
        return 0;

    return (state.stacks - 2) * 8;
}

bool HasMarkOfSin(Unit* target)
{
    if (!target)
        return false;

    for (MarkOfSinRankData const& rank : MarkOfSinRanks)
        if (target->HasAura(rank.spellId))
            return true;

    return false;
}

void DetonateMarkOfSin(Unit* target, Player* caster, uint32 spellId, uint8 snapshottedFervor)
{
    if (!target || !caster || !target->IsAlive() || !snapshottedFervor)
        return;

    MarkOfSinRankData const* rank = GetMarkOfSinRank(spellId);
    SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(spellId);
    if (!rank || !spellInfo)
        return;

    uint32 baseDamage = rank->explosionDamagePerFervor * snapshottedFervor;
    uint32 spellPowerDamage = uint32(float(caster->SpellBaseDamageBonusDone(SpellSchoolMask(SPELL_SCHOOL_MASK_HOLY | SPELL_SCHOOL_MASK_FIRE))) * 0.14f * float(snapshottedFervor));
    uint32 damage = baseDamage + spellPowerDamage;

    caster->SendSpellNonMeleeDamageLog(target, spellInfo, damage, spellInfo->GetSchoolMask(), 0, 0, false, 0);
    Unit::DealDamage(caster, target, damage, nullptr, SPELL_DIRECT_DAMAGE, spellInfo->GetSchoolMask(), spellInfo, true);
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

        for (auto itr = MarkSnapshots.begin(); itr != MarkSnapshots.end();)
        {
            if (itr->first.caster == player->GetGUID().GetCounter())
                itr = MarkSnapshots.erase(itr);
            else
                ++itr;
        }
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

        SetStacks(player, state.stacks - 1);
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

        if (IsConsumer(spellInfo->Id))
            ConsumeFervor(player);
    }
};

class reborn_rediance_damage_script : public UnitScript
{
public:
    reborn_rediance_damage_script() : UnitScript("reborn_rediance_damage_script", true,
        {
            UNITHOOK_ON_DAMAGE
        })
    {
    }

    void OnDamage(Unit* /*attacker*/, Unit* victim, uint32& damage) override
    {
        Player* player = victim ? victim->ToPlayer() : nullptr;
        if (!player)
            return;

        if (uint32 bonusPct = DamageTakenBonusPct(player))
            damage += CalculatePct(damage, bonusPct);
    }
};

class reborn_rediance_mark_script : public UnitScript
{
public:
    reborn_rediance_mark_script() : UnitScript("reborn_rediance_mark_script", true,
        {
            UNITHOOK_ON_AURA_APPLY,
            UNITHOOK_ON_AURA_REMOVE,
            UNITHOOK_MODIFY_SPELL_DAMAGE_TAKEN
        })
    {
    }

    void OnAuraApply(Unit* unit, Aura* aura) override
    {
        if (!unit || !aura || !IsMarkOfSin(aura->GetId()))
            return;

        Player* caster = ObjectAccessor::FindPlayer(aura->GetCasterGUID());
        if (!caster || caster->getClass() != CLASS_PRIEST)
            return;

        GenerateFervor(caster);

        MarkSnapshotKey key{ unit->GetGUID().GetCounter(), caster->GetGUID().GetCounter(), aura->GetId() };
        MarkSnapshots[key] = GetState(caster).stacks;
    }

    void OnAuraRemove(Unit* unit, AuraApplication* aurApp, AuraRemoveMode mode) override
    {
        if (!unit || !aurApp || !aurApp->GetBase() || !IsMarkOfSin(aurApp->GetBase()->GetId()))
            return;

        Aura* aura = aurApp->GetBase();
        MarkSnapshotKey key{ unit->GetGUID().GetCounter(), aura->GetCasterGUID().GetCounter(), aura->GetId() };
        auto itr = MarkSnapshots.find(key);
        if (itr == MarkSnapshots.end())
            return;

        uint8 snapshottedFervor = itr->second;
        MarkSnapshots.erase(itr);

        if (mode != AURA_REMOVE_BY_EXPIRE)
            return;

        Player* caster = ObjectAccessor::FindPlayer(aura->GetCasterGUID());
        DetonateMarkOfSin(unit, caster, aura->GetId(), snapshottedFervor);
    }

    void ModifySpellDamageTaken(Unit* target, Unit* attacker, int32& damage, SpellInfo const* spellInfo) override
    {
        if (!target || !spellInfo || damage <= 0 || !IsFlameOfJudgment(spellInfo->Id))
            return;

        if (Player* player = attacker ? attacker->ToPlayer() : nullptr)
            if (player->getClass() == CLASS_PRIEST)
                GenerateFervor(player);

        if (HasMarkOfSin(target))
            damage += CalculatePct(damage, 15);
    }
};

void Addmod_rebornScripts()
{
    new reborn_rediance_player_script();
    new reborn_rediance_spell_script();
    new reborn_rediance_damage_script();
    new reborn_rediance_mark_script();
}
