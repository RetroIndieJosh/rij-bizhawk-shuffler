local plugin = {}

plugin.name = "Josh's Countdown to Swap"
plugin.author = "retroindiejosh"
plugin.minversion = "2.6.2"

plugin.settings = {
    { name='threshold', type='number', label='Threshold (in seconds)', default=3 },
    { name='fontsize', type='number', datatype='UNSIGNED', label='Font Size', default=244 },
}

plugin.description = [[
Displays a large on-screen countdown showing seconds until the next swap.
- Shows "!!" for a few seconds before the threshold.
- Shows "!!!" when the time reaches 0.
- Skips display if only one game remains.
]]

plugin.state = {
    last_display = nil
}

function plugin.on_frame(state, settings)
    -- Do not display if only one game remains
    if #get_games_list() <= 1 then return end

    local seconds = (next_swap_time - config.frame_count) / 60
    local display_text = nil

    if seconds <= 0 then
        display_text = "!!!"
    elseif seconds <= settings.threshold then
        display_text = string.format("%d", math.ceil(seconds))
    elseif seconds <= settings.threshold * 2 then
        display_text = "!!"
    end

    -- Only redraw if the display text changed
    if display_text and display_text ~= state.last_display then
        gui.use_surface('client')
        gui.drawText(0, 0, display_text, 0xFFFFFFFF, 0xFF000000, settings.fontsize or 72)
        state.last_display = display_text
    end
end

return plugin
