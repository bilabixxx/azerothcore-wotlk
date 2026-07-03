-- Reborn.lua - core addon for custom Reborn client helpers.

Reborn = { version = "1.0.0", modules = {} }

function Reborn:Print(msg, r, g, b)
    DEFAULT_CHAT_FRAME:AddMessage(
        "|cFFFF8000[Reborn]|r " .. tostring(msg),
        r or 1, g or 0.5, b or 0)
end

function Reborn:RegisterModule(name, mod)
    self.modules[name] = mod
    if mod.OnInit then mod:OnInit() end
end

local frame = CreateFrame("Frame", "RebornCoreFrame", UIParent)
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")

frame:SetScript("OnEvent", function(_, event, arg1)
    if event == "ADDON_LOADED" and arg1 == "Reborn" then
        RebornDB = RebornDB or {}
    elseif event == "PLAYER_LOGIN" then
        for _, mod in pairs(Reborn.modules) do
            if mod.OnLogin then mod:OnLogin() end
        end
    end
end)

SLASH_REBORN1 = "/reborn"
SlashCmdList["REBORN"] = function(msg)
    local cmd, arg = (msg or ""):match("^(%S+)%s*(.*)")
    cmd = (cmd or ""):lower()

    if cmd == "" or cmd == "help" then
        Reborn:Print("Commands:")
        DEFAULT_CHAT_FRAME:AddMessage("  /reborn version  - addon version")
        DEFAULT_CHAT_FRAME:AddMessage("  /reborn modules  - active modules")
        for _, mod in pairs(Reborn.modules) do
            if mod.PrintHelp then mod:PrintHelp() end
        end
        return
    end

    if cmd == "version" then
        Reborn:Print("v" .. Reborn.version)
        return
    end

    if cmd == "modules" then
        Reborn:Print("Active modules:")
        for name in pairs(Reborn.modules) do
            DEFAULT_CHAT_FRAME:AddMessage("  - " .. name)
        end
        return
    end

    for _, mod in pairs(Reborn.modules) do
        if mod.HandleCommand and mod:HandleCommand(cmd, arg) then
            return
        end
    end

    Reborn:Print("Unknown command: " .. cmd .. ". /reborn help for commands.")
end
