local plugin = {}

plugin.name = "Extra Life YouTube Chat Integration"
plugin.author = "retroindiejosh"
plugin.minversion = "2.6.2"

plugin.settings = {
    { name='chatfile', type='file', label='Chat File', default='youtube-chat.txt' },
    { name='fontsize_big', type='number', label='Big Font Size', default=128 },
    { name='fontsize_small', type='number', label='Corner Font Size', default=32 },
    { name='gamesfile', type='file', label='Games List File', default='games/.games-list.txt' },
}

plugin.description = [[
Detects !play and !swap commands in chat.
Prints the game to be played, then calls swap_game(game_name) for !play or swap_game() for !swap.
Displays messages big in the center, then smaller in the corner with fade.
]]

-- Plugin state
plugin.state = {
    last_line_index = 0,
    display_text = nil,
    display_frames_left = 0,
    games = {},
}

local CENTER_DURATION = 2 * 60 -- 2 seconds
local CORNER_DURATION = 3 * 60 -- 3 seconds

local function read_file_lines(file_path)
    local lines = {}
    local fp = io.open(file_path, "r")
    if fp then
        for line in fp:lines() do
            table.insert(lines, line)
        end
        fp:close()
    end
    return lines
end

local function load_games(file_path)
    local games = {}
    local lines = read_file_lines(file_path)
    for _, line in ipairs(lines) do
        if line:sub(1,1) ~= "." and line:match("%S") then
            table.insert(games, line)
        end
    end
    return games
end

local function normalize(str)
    return str:lower():gsub("%.[^%.]+$", ""):gsub("[^a-z0-9]", "")
end

-- exact match first, then fuzzy
local function match_game(input, games)
    local norm_input = normalize(input)
    -- exact match
    for _, game in ipairs(games) do
        if normalize(game) == norm_input then
            return game
        end
    end
    -- partial match
    for _, game in ipairs(games) do
        if normalize(game):find(norm_input) then
            return game
        end
    end
    return nil
end

plugin.state.games = load_games(plugin.settings.gamesfile or "games/.games-list.txt")
print("[INFO] Games loaded from file:")
for _, g in ipairs(plugin.state.games) do
    print("  " .. g)
end

local swap_game_global = _G.swap_game

function plugin.on_frame(state, settings)
    if not settings.chatfile or settings.chatfile == "" then return end

    local lines = read_file_lines(settings.chatfile)
    if #lines == 0 then return end

    local start_index = (state.last_line_index or 0) + 1
    for i = start_index, #lines do
        local line = lines[i]
        local msg = line:lower()
        print(line)

        local username = line:match("^(.-):") or "Unknown"
        username = username:gsub("^@", "")

        if msg:find("!swap") then
            state.display_text = "SWAP\n" .. username
            state.display_frames_left = CENTER_DURATION + CORNER_DURATION
            if swap_game_global then
                pcall(swap_game_global)
            else
                print("[WARN] swap_game() not found")
            end
        end

        if msg:find("!play") then
            local input = line:match("!play%s+(.+)")
            if input then
                state.games = load_games(settings.gamesfile or "games/.games-list.txt")
                local matched_game = match_game(input, state.games)
                if matched_game then
                    print(string.format("[PLAY] User '%s' requested game: %s", username, matched_game))
                    state.display_text = "PLAY\n" .. matched_game
                    state.display_frames_left = CENTER_DURATION + CORNER_DURATION
                    if swap_game_global then
                        pcall(swap_game_global, matched_game)
                    else
                        print("[WARN] swap_game() not found")
                    end
                else
                    print(string.format("[PLAY] No match found for '%s' from '%s'", input, username))
                    -- Do NOT display any message
                end
            end
        end
    end

    state.last_line_index = #lines

    -- Draw messages
    gui.use_surface('client')
    if state.display_frames_left > 0 and state.display_text then
        local width, height = client.getwindowsize()
        width = width or 800
        height = height or 600

        if state.display_frames_left > CORNER_DURATION then
            gui.drawText(width/4, height/3, state.display_text, 0xFFFFFFFF, 0xFF000000, settings.fontsize_big or 128)
        else
            local fade_ratio = state.display_frames_left / CORNER_DURATION
            local alpha = math.floor(0xFF * fade_ratio)
            local color = (alpha << 24) | 0xFFFFFF
            gui.drawText(50, 50, state.display_text, color, 0xFF000000, settings.fontsize_small or 32)
        end

        state.display_frames_left = state.display_frames_left - 1
        if state.display_frames_left <= 0 then
            state.display_text = nil
        end
    else
        -- ensure display_text cleared after fade
        state.display_text = nil
    end
end

return plugin
