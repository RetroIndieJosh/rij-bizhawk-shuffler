local plugin = {}

plugin.name = "YouTube Chat Swap Trigger"
plugin.author = "retroindiejosh"
plugin.minversion = "2.6.2"

plugin.settings = {
    { name='chatfile', type='file', label='Chat File' },
    { name='cooldown', type='number', label='Swap cooldown (seconds)', default=10, min=1 },
}

plugin.description = [[
Triggers a game swap when a chat message "!swap" is detected in a text file.
- The file path is configurable via a file picker.
- Respects a cooldown period to prevent multiple swaps in quick succession.
]]

plugin.state = {
    last_messages = {},
    last_swap_frame = -math.huge, -- ensures arithmetic works on first frame
}

-- Utility: read chat file into a table
local function read_chat_file(file_path)
    local messages = {}
    if not file_path or file_path == "" then return messages end

    local fp = io.open(file_path, "r")
    if fp then
        for line in fp:lines() do
            table.insert(messages, line)
        end
        fp:close()
    end
    return messages
end

function plugin.on_frame(state, settings)
    -- Ensure state fields exist
    state.last_messages = state.last_messages or {}
    state.last_swap_frame = state.last_swap_frame or -math.huge

    local chat_file = settings.chatfile
    if not chat_file or chat_file == "" then return end

    local messages = read_chat_file(chat_file)
    if #messages == 0 then return end

    -- Only process new messages
    local last_index = #state.last_messages
    local new_messages = {}
    for i = last_index + 1, #messages do
        table.insert(new_messages, messages[i])
    end

    -- Convert cooldown to frames (BizHawk ~60 FPS)
    local cooldown_frames = (settings.cooldown or 10) * 60

    -- Check for "!swap" commands
    for _, msg in ipairs(new_messages) do
        if msg:lower():find("!swap") then
            if (config.frame_count - state.last_swap_frame) >= cooldown_frames then
                swap_game() -- call shuffler's swap function
                state.last_swap_frame = config.frame_count
                break -- only trigger once per frame
            end
        end
    end

    -- Update state
    state.last_messages = messages
end

return plugin
