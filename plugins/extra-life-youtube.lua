local plugin = {}

plugin.name = "Extra Life YouTube Chat Integration"
plugin.author = "retroindiejosh"
plugin.minversion = "2.6.2"

plugin.settings = {
    { name='chatfile', type='file', label='Chat File', default='youtube-chat.txt' },
    { name='fontsize_big', type='number', label='Big Font Size', default=128 },
    { name='fontsize_small', type='number', label='Corner Font Size', default=32 },
}

plugin.description = [[
Displays a SWAP message when a "!swap" message is detected in the chat file.
Shows big in the center for 2 seconds, then small in the corner for 3 seconds with fade-out.
]]

-- Plugin state
plugin.state = {
    last_line_index = 0,
    display_text = nil,
    display_frames_left = 0,
}

local CENTER_DURATION = 2 * 60 -- 2 seconds
local CORNER_DURATION = 3 * 60 -- 3 seconds

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

    local lines = read_file_lines(settings.chatfile)
    if #lines == 0 then return end

    local start_index = (state.last_line_index or 0) + 1
    for i = start_index, #lines do
        local line = lines[i]
        local msg = line:lower()

        -- Print all messages to console
        print(line)

        -- Only trigger for exact "!swap"
        if msg:find("!swap") then
            local username = line:match("^(.-):") or "Unknown"
            username = username:gsub("^@", "") -- remove @ if present

            -- Set display text for 2+3 seconds
            state.display_text = "SWAP\n" .. username
            state.display_frames_left = CENTER_DURATION + CORNER_DURATION

            -- Trigger swap safely
            if swap_game then
                pcall(swap_game)
            else
                print("[Chat Swap Plugin] swap_game() not found")
            end
        end
    end

    state.last_line_index = #lines

    -- Draw the message if any
    if state.display_frames_left > 0 and state.display_text then
        gui.use_surface('client')

        local width, height = client.getwindowsize()
        width = width or 800
        height = height or 600

        if state.display_frames_left > CORNER_DURATION then
            -- Big, centered for first 2 seconds
            gui.drawText(width/4, height/3, state.display_text, 0xFFFFFFFF, 0xFF000000, settings.fontsize_big or 128)
        else
            -- Small, corner with fade-out
            local fade_ratio = state.display_frames_left / CORNER_DURATION
            local alpha = math.floor(0xFF * fade_ratio)
            local color = (alpha << 24) | 0xFFFFFF -- ARGB, fading white
            gui.drawText(50, 50, state.display_text, color, 0xFF000000, settings.fontsize_small or 32)
        end

        state.display_frames_left = state.display_frames_left - 1

        -- Clear text when done
        if state.display_frames_left <= 0 then
            state.display_text = nil
        end
    end
end

return plugin
