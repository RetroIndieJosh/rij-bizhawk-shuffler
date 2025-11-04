# RIJ BizHawk Shuffler
With additional plugins by [Retro Indie Josh](retroindiejosh.itch.io)

## TODO - Extra Life / YouTube
- failed match shouldn't reset per-user cooldown
- strike system for not respecting cooldown
    - after X strikes, timeout chatter for 10x cooldown
    - after X timeouts, ban chatter
- options in yaml
    - global cooldown
    - per-user cooldown
    - number of strikes before timeout
    - timeout multiplier (per-user cooldown x this value)
    - number of timeouts before ban
    - enable/disable consecutive command from same chatter
    - messages and whether to display them:
        - swap success
        - swap fail (cooldown, should show remaining time)
        - play success (and what game it matched)
        - play fail (cooldown, should show remaining time)
        - play fail (no match)
        - user timed out (and how long)
        - user banned

- ignore all chat commands if no game running

- visual indicator "LOCKED" when in lockdown
- somehow track !swaps and limit to $X/swap in donations
- stats tracking for YouTube swap, like # of swaps per viewer
- link to YouTube API so we can tell users when they need to donate more to unlock commands
    - if we're using the API we can also simplify by not writing to a file first
- add minimum required donation to youtube-chat commands
- prettier transitions for messages on screen (Josh's Countdown, swapper name for YouTube swap)

## Original Bizhawk Shuffler 2
* written by authorblues, inspired by [Brossentia's Bizhawk Shuffler](https://github.com/brossentia/BizHawk-Shuffler), based on slowbeef's original project
* [tested on Bizhawk v2.6.3-v2.10](https://github.com/TASVideos/BizHawk/releases/)  
* [click here to download the latest version](https://github.com/authorblues/bizhawk-shuffler-2/archive/refs/heads/main.zip)

## Additional Resources
* **[Setup Instructions](https://github.com/authorblues/bizhawk-shuffler-2/wiki/Setup-Instructions)**
* [Frequently Asked Questions](https://github.com/authorblues/bizhawk-shuffler-2/wiki/Frequently-Asked-Questions) - important info!
* [How to shuffle games with multiple discs](https://github.com/authorblues/bizhawk-shuffler-2/wiki/Multi-disc-games)
* [How to Create a Shuffler Plugin](https://github.com/authorblues/bizhawk-shuffler-2/wiki/How-to-Create-a-Shuffler-Plugin)
