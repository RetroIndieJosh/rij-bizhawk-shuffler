local plugin = {}

plugin.name = "Time-Balanced Weighted Shuffle"
plugin.author = "retroindiejosh"
plugin.minversion = "2.6.3"
plugin.settings =
{
    { name='selection_bias', type='number', label='Selection Bias Strength', default=2 },
    { name='swap_bias', type='number', label='Swap Bias Strength', default=1.5 },
}

function plugin.on_setup(data, settings)
    data.selection_bias = settings.selection_bias or 2
    data.swap_bias = settings.swap_bias or 1.5
    data.prev_game = nil
    data.last_pick = nil
end

-- weighted pick logic
function plugin.pick_next_game(data)
    local all_games = get_games_list()
    if #all_games == 0 then return nil end

    -- remove current game to avoid repeats
    local current = config.current_game
    if current then
        for i = #all_games, 1, -1 do
            if all_games[i] == current then
                table.remove(all_games, i)
            end
        end
    end
    if #all_games == 0 then return current end

    local min_time, max_time = math.huge, 0
    for _, game in ipairs(all_games) do
        local t = config.game_frame_count[game] or 0
        if t < min_time then min_time = t end
        if t > max_time then max_time = t end
    end
    max_time = math.max(max_time, min_time)

    local weights = {}
    local total_weight = 0
    for _, game in ipairs(all_games) do
        local t = config.game_frame_count[game] or 0
        local normalized = (t - min_time) / (max_time - min_time + 1e-6)
        local weight = ((1 - normalized) ^ (data.selection_bias or 2))
        table.insert(weights, {game=game, weight=weight})
        total_weight = total_weight + weight
    end

    local r = math.random() * total_weight
    local cumulative = 0
    for _, w in ipairs(weights) do
        cumulative = cumulative + w.weight
        if r <= cumulative then
            data.last_pick = w
            return w.game
        end
    end

    data.last_pick = weights[1]
    return weights[1].game
end

-- override get_next_game to use weighted pick if shuffle_index < 0
local original_get_next_game = get_next_game
function get_next_game()
    if config.shuffle_index < 0 then
        return plugin.pick_next_game(plugin)
    else
        return original_get_next_game()
    end
end

-- adjust next swap time dynamically
function plugin.on_frame(data, settings)
    local current_game = config.current_game
    if not current_game then return end

    if data.prev_game ~= current_game then
        local all_games = get_games_list()
        local min_time, max_time = math.huge, 0
        for _, game in ipairs(all_games) do
            local t = config.game_frame_count[game] or 0
            if t < min_time then min_time = t end
            if t > max_time then max_time = t end
        end
        max_time = math.max(max_time, min_time)

        local game_time = config.game_frame_count[current_game] or 0
        local normalized = (game_time - min_time) / (max_time - min_time + 1e-6)
        local multiplier = ((1 - normalized) ^ (settings.swap_bias or 1.5))
        multiplier = math.max(0.1, math.min(1.5, multiplier))

        local min_frames = config.min_swap * 60
        local max_frames = config.max_swap * 60
        local base_swap = math.random(min_frames, max_frames)
        local adjusted_swap = math.floor(base_swap * multiplier)
        next_swap_time = math.max(min_frames, math.min(max_frames, adjusted_swap)) + config.frame_count

        data.prev_game = current_game
    end
end

return plugin
