# Proximity
For a complete RP overhaul.

## TL;DR
1. Built-in Tupper Proxying, set by admins. No prefix needed.
2. Fully dynamic map making of the RP world through Slash Commands.
3. Prevent metagaming. Players only hear what their character hears.
4. Players have a presence. You /look and you see nearby people.
5. Players only see one channel, their personal one. Neat and tidy.
6. Someone leaves? You see what way they went.
7. That person also sees (and is seen by) everyone they pass by.
8. Eavesdrop on people talking in nearby locations, discretely.
9. Built in /help. Tutorials and guides for players and hosts.

## Kinda Long; Read Some
1. Players have a dedicated RP channel where their messages are
automatically proxied as their character (which is set by admins.)
2. Create, edit, inventory, and delete the locations in your RP
world through slash commands, complete with whitelists and paths.
3. Players "hear" messages sent by characters who are near the same
location as them. If their character wouldn't have heard it, neither
does the player. No honor system, no conflict of interest.
4. Players are only ever "inside" one location at a time. They can
be noticed by anyone else in the same location, online or offline.
5. While there are channels for each location, like normal, these
are just for the admins to review. Players can enjoy a minimal server.
6. Instead of teleporting from place to place by just switching
what channel you're talking in, your character actually moves.
7. You can't go straight from LA to NYC. Locations have "paths"
to adjacent locations, and you go from one to the next til you're there.
8. Players hear that people are talking in other locations nearby
and can secretly overhear what's being said, word for word.
9. The /help command contains options for players and for hosts, to
flip through page-by-page. Includes a glossary for term lookups.

## Not Long, Read allows
1. When you register a player, the bot automatically creates a player
channel exclusive to them and the admins. All RP is routed through
that-- the bot has a sort of Tupper-like "proxying" of messages where
other player's messages are repeated in that channel, while messages
sent in this channel are repeated by the bot in *their* respective
channels.
    Besides neater organization and a clear delineation of
what's IC and what's OOC, it also means that the players and the
admins can follow their own POV to a T, regardless of their hopping
between locations-- just scroll through that channel.

2. This bot uses Graph Theory to establish locations as nodes.
Each location is (or at least should be) connected to other locations
that are canonically adjacent, like a kitchen being connected to a
dining room. Players can move along these connections to travel
around the RP world. Everything is automatic and with minimal input
needed from the admins. Let the bot do the work for you.

3. Metagaming is a significant problem in the world of roleplay,
especially when attempting to facilitate a mystery of some kind.
To combat this, messages are not sent in a channel to be viewed by
every player. Attempting to manage a level of discretion for who
"should" see that is downright impossible.

    Instead, messages are sent in the Player Channel so that they
never reach other players to begin with, not directly. The bot
"hears" the player's message, knows internally what other players
should hear that player, based on their locations and whether
they're eavesdropping on the player's location. Then, it selectively
repeats the message only to those who ought to have heard it.

4. Because players can only really be cognizant of what's happening
in one location, secrecy and scheming and plotting can occur if
you verify nobody is nearby to hear.

    It also means you have a solid alibi: players are sent a message
in their Player Channel the moment that they notice someone entering
or leaving their vicinity, which ensures that you can truly assure
someone could not have been able to kill another player/ steal a
certain item/ sabotage a certain vehicle/ etc. if they have witnesses
to testify that they were elsewhere while the crime transpired.

5. Location Channels (a.k.a. Node Channels) keep a record of all
that is said and done within their own location. That means that
all messages sent by players are actually repeated a number of times:
    - The original message, sent by the player in their Player Channel.
    - The message (proxied under the character username and profile
        picture) logged in the Node Channel that the player was
        located in when they sent that message.
    - The Player Channel(s) (also proxied) of other players who
        are occupants in the same location, if any.
    - The Player Channels(s) (proxied) of other players in an
        adjacent location, who are eavesdropping on the speakers
        location.
    - Indirectly, it is also repeated somewhat to the Player Channels
        of players in nearby locations who are not eavesdropping on
        the speaker's location. For these players, they only hear
        *that* the speaker is saying something, from what direction
        they hear the speaker, and whose voice it is.

6. Players call /move when they want to go someplace: this displays
a map generated by the bot itself that shows all the locations they
can reach, and a dropdown that they can choose from for where they
want to go to as their destination. It computes the fastest way to
that place and they travel along that path.

    That said, people who are in any of the locations along that
path (including the origin and destination) can see where the player
entered from and exited to, alerted in their Player Channels by a
text from the bot.

7. Each location, as well as each path between locations, can have
a whitelist for who's allowed to access it. You can set which people,
which roles, or some combination where any of the people as well as
any of the members who hold that role, can access it.

    This allows for the unique ability to restrict certain doorways,
roads, bridges, elevators, hidden passageways, or any other connections
between locations where only certain people can pass through it:
however, there's no limitation on who can simply exist on either side.
Consider a club: one door at the front that only VIPs can walk into,
and one backdoor that anyone can sneak into.

    Needless to say, this greatly impacts the number of roleplay
opportunities beyond the the standard "restrict location to certain
members" method of access management that's that status quo without
this bot.

8. Since players will instantly notice if/when other people come
into the same location as them, it seems impossible to hear what
is being said by someone without them knowing that you're listening.
However, this is circumvented by players who eavesdrop: by listening
closely, you can hear if other people are in locations adjacent to
you. From there, you can pick a location to eavesdrop on.

    Anything said by other players in that location are repeated
to you, word for word, without their awareness. However, they may
still themselves hear/see things from their perspective that you
as an eavesdropper don't hear from yours.

9. The /help command has an immensely simplified "what" of the bot's
functions for players to understand, as well as a more in-depth
"how" for the admins; a tutorial for setup of a server, complete
with a server template, annotated screenshots for what settings to
edit in the server, and how to set up the bot for their roleplay.

    Throughout the two sides of this /help command, certain words
are underlined. If you call /help (underlined word here), you can
see a glossary definition of that word in the context of the bot,
with that definition also having its own underlining if you need
to get a deeper understanding of *that* defintion (and so on).
