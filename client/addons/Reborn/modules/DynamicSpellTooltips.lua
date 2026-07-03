-- DynamicSpellTooltips.lua
-- Generic tooltip rewrites for custom spells whose live values depend on player state.

local M = {}

local FERVOR_AURA_FIRST = 900202
local FERVOR_AURA_LAST = 900206

local SPELLS = {
    [900210] = { name = "Flame of Judgment", kind = "direct", minDamage = 34, maxDamage = 40, spellPowerCoefficient = 0.571 },
    [900211] = { name = "Flame of Judgment", kind = "direct", minDamage = 68, maxDamage = 80, spellPowerCoefficient = 0.571 },
    [900212] = { name = "Flame of Judgment", kind = "direct", minDamage = 137, maxDamage = 160, spellPowerCoefficient = 0.571 },
    [900213] = { name = "Flame of Judgment", kind = "direct", minDamage = 238, maxDamage = 276, spellPowerCoefficient = 0.571 },
    [900214] = { name = "Flame of Judgment", kind = "direct", minDamage = 371, maxDamage = 430, spellPowerCoefficient = 0.571 },
    [900215] = { name = "Flame of Judgment", kind = "direct", minDamage = 542, maxDamage = 628, spellPowerCoefficient = 0.571 },
    [900216] = { name = "Flame of Judgment", kind = "direct", minDamage = 759, maxDamage = 879, spellPowerCoefficient = 0.571 },
    [900217] = { name = "Flame of Judgment", kind = "direct", minDamage = 1002, maxDamage = 1162, spellPowerCoefficient = 0.571 },
    [900218] = { name = "Flame of Judgment", kind = "direct", minDamage = 1211, maxDamage = 1405, spellPowerCoefficient = 0.571 },
    [900219] = { name = "Flame of Judgment", kind = "direct", minDamage = 1410, maxDamage = 1636, spellPowerCoefficient = 0.571 },
    [900230] = { name = "Mark of Sin", kind = "periodic", tickDamage = 24, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 45, explosionCoefficient = 0.14 },
    [900231] = { name = "Mark of Sin", kind = "periodic", tickDamage = 46, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 90, explosionCoefficient = 0.14 },
    [900232] = { name = "Mark of Sin", kind = "periodic", tickDamage = 74, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 140, explosionCoefficient = 0.14 },
    [900233] = { name = "Mark of Sin", kind = "periodic", tickDamage = 106, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 190, explosionCoefficient = 0.14 },
    [900234] = { name = "Mark of Sin", kind = "periodic", tickDamage = 140, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 235, explosionCoefficient = 0.14 },
    [900235] = { name = "Mark of Sin", kind = "periodic", tickDamage = 168, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 275, explosionCoefficient = 0.14 },
    [900236] = { name = "Mark of Sin", kind = "periodic", tickDamage = 180, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 320, explosionCoefficient = 0.14 },
    [900237] = { name = "Mark of Sin", kind = "periodic", tickDamage = 205, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 355, explosionCoefficient = 0.14 },
    [900238] = { name = "Mark of Sin", kind = "periodic", tickDamage = 230, ticks = 5, spellPowerCoefficient = 0.20, explosionDamage = 390, explosionCoefficient = 0.14 },
    [900250] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 100, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900251] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 160, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900252] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 220, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900253] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 280, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900254] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 330, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900255] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 380, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900256] = { name = "Divine Judgment", kind = "fervor_total", baseDamage = 430, spellPowerCoefficient = 0.21, resource = "fervor" },
    [900260] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 95, spellPowerCoefficient = 0.26 },
    [900261] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 150, spellPowerCoefficient = 0.26 },
    [900262] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 220, spellPowerCoefficient = 0.26 },
    [900263] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 300, spellPowerCoefficient = 0.26 },
    [900264] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 380, spellPowerCoefficient = 0.26 },
    [900265] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 450, spellPowerCoefficient = 0.26 },
    [900266] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 535, spellPowerCoefficient = 0.26 },
    [900267] = { name = "Radiant Strike", kind = "radiant_strike", baseDamage = 620, spellPowerCoefficient = 0.26 },
    [900270] = { name = "Holy Chastisement", kind = "direct", minDamage = 120, maxDamage = 120, spellPowerCoefficient = 0.15 },
    [900271] = { name = "Holy Chastisement", kind = "direct", minDamage = 210, maxDamage = 210, spellPowerCoefficient = 0.15 },
    [900272] = { name = "Holy Chastisement", kind = "direct", minDamage = 300, maxDamage = 300, spellPowerCoefficient = 0.15 },
    [900273] = { name = "Holy Chastisement", kind = "direct", minDamage = 390, maxDamage = 390, spellPowerCoefficient = 0.15 },
    [900300] = { name = "Purifying Glare", kind = "direct", minDamage = 100, maxDamage = 100, spellPowerCoefficient = 0.10 },
    [900301] = { name = "Purifying Glare", kind = "direct", minDamage = 165, maxDamage = 165, spellPowerCoefficient = 0.10 },
    [900302] = { name = "Purifying Glare", kind = "direct", minDamage = 250, maxDamage = 250, spellPowerCoefficient = 0.10 },
    [900303] = { name = "Purifying Glare", kind = "direct", minDamage = 340, maxDamage = 340, spellPowerCoefficient = 0.10 },
    [900310] = { name = "Burning Shield", kind = "burning_shield", baseAbsorb = 220, spellPowerCoefficient = 0.06, absorbPerFervorStack = 70 },
    [900311] = { name = "Burning Shield", kind = "burning_shield", baseAbsorb = 310, spellPowerCoefficient = 0.06, absorbPerFervorStack = 100 },
    [900312] = { name = "Burning Shield", kind = "burning_shield", baseAbsorb = 400, spellPowerCoefficient = 0.06, absorbPerFervorStack = 150 },
    [900313] = { name = "Burning Shield", kind = "burning_shield", baseAbsorb = 520, spellPowerCoefficient = 0.06, absorbPerFervorStack = 180 },
}

local function Round(value)
    return math.floor(value + 0.5)
end

local function GetCurrentFervor()
    for i = 1, 40 do
        local name, _, _, count, _, _, _, _, _, _, spellId = UnitBuff("player", i)
        if not name then break end
        if spellId and spellId >= FERVOR_AURA_FIRST and spellId <= FERVOR_AURA_LAST then
            if count and count > 0 then
                return count
            end
            return spellId - FERVOR_AURA_FIRST + 1
        end
    end
    return 0
end

local function GetRadiantSpellPower()
    local holy = GetSpellBonusDamage and GetSpellBonusDamage(2) or 0
    local fire = GetSpellBonusDamage and GetSpellBonusDamage(3) or 0
    return math.max(holy or 0, fire or 0)
end

local function GetResourceAmount(resource)
    if resource == "fervor" then
        return GetCurrentFervor()
    end
    return 0
end

local function CalculatePrimaryDamage(def)
    if def.kind == "direct" then
        local spellPower = GetRadiantSpellPower()
        local bonus = spellPower * def.spellPowerCoefficient
        local minDamage = Round(def.minDamage + bonus)
        local maxDamage = Round(def.maxDamage + bonus)
        if minDamage == maxDamage then
            return tostring(minDamage)
        end
        return string.format("%d to %d", minDamage, maxDamage)
    end

    if def.kind == "periodic" then
        local spellPower = GetRadiantSpellPower()
        return Round((def.tickDamage + (spellPower * def.spellPowerCoefficient)) * def.ticks)
    end

    if def.kind == "radiant_strike" then
        local spellPower = GetRadiantSpellPower()
        local damage = def.baseDamage + (spellPower * def.spellPowerCoefficient)
        if GetCurrentFervor() >= 5 then
            damage = damage * 1.5
        end
        return tostring(Round(damage))
    end

    local amount = GetResourceAmount(def.resource)
    local displayedAmount = math.max(amount, 1)
    local spellPower = GetRadiantSpellPower()
    local perResource = def.baseDamage + (spellPower * def.spellPowerCoefficient)
    return Round(perResource * displayedAmount)
end

local function CalculateTickDamage(def)
    local spellPower = GetRadiantSpellPower()
    return Round(def.tickDamage + (spellPower * def.spellPowerCoefficient))
end

local function CalculateExplosionDamage(def)
    local spellPower = GetRadiantSpellPower()
    return Round(def.explosionDamage + (spellPower * def.explosionCoefficient))
end

local function CalculateBurningShieldAbsorb(def)
    local spellPower = GetRadiantSpellPower()
    local fervor = GetCurrentFervor()
    return Round(def.baseAbsorb + (spellPower * def.spellPowerCoefficient) + (fervor * def.absorbPerFervorStack))
end

local function ReplaceLastDamageBefore(text, phrase, value)
    local startIndex = text:find(phrase, 1, true)
    if not startIndex then
        return text, false
    end

    local prefix = text:sub(1, startIndex - 1)
    local suffix = text:sub(startIndex)
    local replaced = false

    prefix = prefix:gsub("(%d+%s+to%s+%d+)%s*$", function()
        replaced = true
        return tostring(value)
    end)

    if not replaced then
        prefix = prefix:gsub("(%d+)%s*$", function()
            replaced = true
            return tostring(value)
        end)
    end

    return prefix .. suffix, replaced
end

local function RewriteDamageLine(tooltip, def)
    for i = 2, tooltip:NumLines() do
        local line = _G[tooltip:GetName() .. "TextLeft" .. i]
        local text = line and line:GetText()
        if text then
            local rewritten = text
            local changed = false

            if def.kind == "direct" or def.kind == "radiant_strike" then
                rewritten, changed = ReplaceLastDamageBefore(text, "Radiant damage", CalculatePrimaryDamage(def))
            elseif def.kind == "periodic" then
                if text:find("over", 1, true) then
                    rewritten, changed = ReplaceLastDamageBefore(text, "Radiant damage over", CalculatePrimaryDamage(def))
                elseif text:find("every", 1, true) then
                    rewritten, changed = ReplaceLastDamageBefore(text, "Radiant damage every", CalculateTickDamage(def))
                end

                if def.explosionDamage and rewritten:find("Radiant damage per snapshotted Fervor", 1, true) then
                    rewritten = (rewritten:gsub("(%d+)( Radiant damage per snapshotted Fervor)", tostring(CalculateExplosionDamage(def)) .. "%2", 1))
                    changed = true
                elseif def.explosionDamage and rewritten:find("damage per snapshotted Fervor", 1, true) then
                    rewritten = (rewritten:gsub("(%d+)( damage per snapshotted Fervor)", tostring(CalculateExplosionDamage(def)) .. "%2", 1))
                    changed = true
                end
            elseif def.kind == "fervor_total" and text:find("Radiant damage per Fervor consumed", 1, true) then
                rewritten = text:gsub("(%d+)( Radiant damage per Fervor consumed)", tostring(CalculatePrimaryDamage(def)) .. "%2", 1)
                changed = true
            elseif def.kind == "burning_shield" then
                rewritten, changed = ReplaceLastDamageBefore(text, "damage for 15 sec", CalculateBurningShieldAbsorb(def))
            end

            if changed then
                line:SetText(rewritten)
            end
        end
    end

    tooltip:Show()
end

local function HandleTooltip(tooltip)
    if not tooltip or not tooltip.GetSpell then return end
    local _, _, spellId = tooltip:GetSpell()
    local def = SPELLS[spellId]
    if not def then return end
    RewriteDamageLine(tooltip, def)
end

function M:OnInit()
    GameTooltip:HookScript("OnTooltipSetSpell", HandleTooltip)
    if ItemRefTooltip then
        ItemRefTooltip:HookScript("OnTooltipSetSpell", HandleTooltip)
    end
end

function M:PrintHelp()
    DEFAULT_CHAT_FRAME:AddMessage("  /reborn modules - shows dynamic spell tooltip module status")
end

Reborn:RegisterModule("DynamicSpellTooltips", M)
