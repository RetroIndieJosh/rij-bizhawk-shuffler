# RIJ BizHawk Shuffler
With additional plugins by [Retro Indie Josh](retroindiejosh.itch.io)

## TODO - Extra Life / YouTube
- don't reset per-user cooldown when a match for !play fails
- warn the user when they're trying to use a command but they're on cooldown
- give a user a "strike" when they're warned about cooldown
- add a !timeout <user> command which puts the user on timeout for "timeout multiplier" (defined in yaml) times per-user cooldown (meaning their commands will be ignored)
- update the !ban command so it doesn't do anything locally but instead uses the YouTube API to properly ban the chatter
- give a strike for any of the following:
    - using a command during cooldown: 
        - warn that if they reach X strikes, they'll be put in timeout
        - tell them how much time is left in the cooldown
    - using a command during timeout
        - warn that if they reach X strikes, they'll be banned
        - tell them how much time is left in their timeout
- after X strikes (defined in yaml), apply !timeout to the chatter
    - if the chatter is already timed out, !ban them
- options in yaml
    - global cooldown (seconds, default 5)
    - per-user cooldown (seconds, default 60)
    - number of strikes before timeout (default 3)
    - timeout multiplier (default 10)
    - number of timeouts before ban (default 3)
    - enable/disable consecutive commands from same chatter
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
