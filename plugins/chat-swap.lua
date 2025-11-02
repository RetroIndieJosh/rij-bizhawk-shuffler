local plugin = {}

plugin.name = "YouTube Chat Swap Trigger"
plugin.author = "retroindiejosh"
plugin.minversion = "2.6.2"

plugin.settings = {
    { name='chatfile', type='file', label='Chat File', default='youtube-chat.txt' },
    { name='fontsize', type='number', label='Font Size', default=32 },
    { name='displaytime', type='number', label='Display Username Time (frames)', default=120 },
}

plugin.description = [[
Triggers a game swap when a "!swap" message is detected in the chat file.
Displays the username who triggered the swap on-screen for a short time.
Prints all new messages to the console.
]]

-- Plugin state
plugin.state = {
    last_line_index = 0,
    display_username = nil,
    display_frames_left = 0,
}

-- Read file into table of lines
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

function plugin.on_frame(state, settings)
    if not settings.chatfile or settings.chatfile == "" then return end

    -- Read all lines
    local lines = read_file_lines(settings.chatfile)
    if #lines == 0 then return end

    -- Process new lines
    local start_index = (state.last_line_index or 0) + 1
    for i = start_index, #lines do
        local line = lines[i]
        local msg = line:lower()

        -- Print all new messages
        print("[Chat] " .. line)

        -- Check for !swap
        if msg:find("!swap") then
            -- Extract username if format is "Username: !swap"
            local username = line:match("^(.-):") or "Unknown"

            -- Display username on-screen
            state.display_username = username
            state.display_frames_left = settings.displaytime or 120

            -- Trigger swap safely
            if swap_game then
                pcall(swap_game)
            else
                print("[Chat Swap Plugin] swap_game() not found")
            end
        end
    end

    -- Update last line index
    state.last_line_index = #lines

    -- Draw the username if display_frames_left > 0
    if state.display_frames_left > 0 and state.display_username then
        gui.use_surface('client')
        gui.drawText(50, 50, "Swap triggered by: " .. state.display_username,
                     0xFFFFFFFF, 0xFF000000, settings.fontsize or 32)
        state.display_frames_left = state.display_frames_left - 1
    end
end

return plugin
