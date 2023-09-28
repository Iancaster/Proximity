

#Import-ant Libraries
from discord import Option, ApplicationContext, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import Button

from libraries.universal import mbd
from libraries.classes import DialogueView, Player, Paginator


#Classes
class OpenCommands(commands.Cog):
    """
    These are commands that are "open" to the public.
    They can be called anywhere and by anyone.
    """

    @commands.slash_command(name = 'help', description = 'Definitions, usage, and a tutorial.')
    async def help(self, ctx: ApplicationContext, word: Option( str, description = 'Get help on a specific term?', required = False)):

        await ctx.defer(ephemeral = True)
        word = word.lower() if word else ''
        if word:

            glossary_terms = {
                'graph' : "A __graph__ is just a collection of __node__s that are" +
                    " connected by __edge__s. Technically, a __graph__ could have" +
                    " only one __node__, or not even have any __edge__s. It's a" +
                    " whole branch of mathematics you can look up--__graph__ theory!",
                'network' : "A __network__ is another name for a __graph__. It's a" +
                    " little confusing considering '__graph__' makes you think of" +
                    " line __graph__s, and '__network__s' make you think of cell" +
                    " phone coverage. For this bot, we'll just call it a __graph__.",
                'node' : "A __node__ is a singular point on a __graph__. It may be" +
                    " connected to other __node__s; those paths are called" +
                    " __edge__s. In the context of this bot, a __node__ is a __location__" +
                    " in the roleplay environment that __player__s can exist within.",
                'edge' : "An __edge__ is a connection between two __node__s" +
                    " within a __graph__. Edges may be one-way only, so that" +
                    " __player__s can only __move__ along it in one __direct__ion, or" +
                    " it can be two way. Players use __edge__s for __move__ment" +
                    " as well as for __audio__.",
                'location' : "A __location__ is a place within the roleplay world" +
                    " that __player__s can __move__ to. They are represented with" +
                    "a Discord channel, a __node__, and any __edge__s that it may" +
                    " share that connect it to other __node__s. Locations are about" +
                    " the size of a room and everyone who's inside is __visible__ to" +
                    " everyone else.",
                'audio' : "When a __player__ speaks, every other __player__ in the" +
                    " same __location__ can hear __direct__ly. Players in __neighbor__" +
                    " __location__s can hear in__direct__ly-- unless that person is" +
                    " currently eavesdropping on that __location__ the speaker" +
                    " is in, in which case, they'll hear everything __direct__ly.",
                'direct' : "When a __player__ speaks, other occupants in the" +
                    " same __location__ will __direct__ly hear, as well as occupants" +
                    " in __neighbor__ing __location__s that are overhearing. These" +
                    " __direct__ listeners will hear word-for-word what was said.",
                'indirect' : "When a __player__ speaks, other __player__s in" +
                    " __neighbor__ing __location__s who are not eavesdropping on" +
                    " that __player__'s __location__ will in__direct__ly hear the speaker." +
                    " These listeners will be able to identify the speaker, " +
                    " and will be able to identify where it's coming from, but" +
                    " will not be able to make out the content of what was said.",
                'visible' : "When a __player__ chooses to look around their" +
                    " current __location__, they see every other __player__ around." +
                    " They also see (and are seen by) __player__s who enter" +
                    " their __location__, they see them as they leave (and what" +
                    " __direct__ion they go).",
                'move' : "Since __character__s have a presence inside their" +
                    "__location__, they can't instantly teleport between where they" +
                    " are and where they want to be. Instead, they '__move__' " +
                    " along the shortest path between these places, and " +
                    " __player__s along the way see the __character__ and where they " +
                    " came from, along with where they went to.",
                'character' : "A __character__ is the fictional roleplay figure who" +
                    " is acted out via a __player__'s text messages. When a __player__'s" +
                    " texts are 'proxied' by the bot into other __player__ channels, it " +
                    " is the __character__'s name and the __character__'s profile picture " +
                    " that is displayed. Characters occupy a __location__ in the __graph__.",
                'player' : "A __player__ is the nonfictitous user who roleplays on" +
                    " Discord. Players are only privy to what their __character__" +
                    " knows, and can /move, /look, and /eavesdrop," +
                    " among other things.",
                'whitelist' : "Nodes and __edge__s can have restrictions on what" +
                    " __player__s are allowed to __move__ through them on the __graph__." +
                    " They can restrict based on a list of approved __player__s," +
                    " approved roles, or both: anyone who's approved on" +
                    " either list may pass.",
                'neighbor' : "A __neighbor__ __node__ is one that's connected to a" +
                    " given __node__ with an __edge__. A __neighbor__ __player__ is one that's" +
                    " in a __neighbor__ __node__. Neighbors are usually talked about in" +
                    " the context of eavesdropping for __direct__ listening, or so that" +
                    " __neighbor__ __player__s are alerted when a __node__ gets deleted, for" +
                    "example.",
                'underlined' : "🤨"}

            if word in glossary_terms:
                embed, _ = await mbd(
                    f'{word.capitalize()} explanation:',
                    glossary_terms[word],
                    'Clear things up, I hope?')

            else:
                embed, _ = await mbd(
                    'What was that?',
                    f"I'm sorry. I have a glossay for {len(glossary_terms)} words," + \
                        " but not for that. Perhaps start with the tutorials with" + \
                        " just a standard `/help` and go from there.",
                    "Sorry I couldn't do more.")

            await ctx.respond(embed = embed)
            return

        async def leatherbound(interaction, title_prefix, page_content): #Because it wraps the paginators haha

            await interaction.response.defer()

            paginator = Paginator(
                interaction,
                title_prefix,
                page_content)
            await paginator.refresh_embed()

            return

        async def player_tutorial(interaction: Interaction):

            title_prefix = 'Player Tutorial, Page'
            page_content = {'Intro' : "Welcome, this guide" +
                                " will tell you everything you need to know as" +
                                " a __player__. Let's begin.",
                            'Player Channels': "Players have their own channel" +
                                " for roleplaying. All speech and __move__ment, etc, is" +
                                " done through there.",
                            'Locations': "Your __character__ exists in some __location__." +
                                " You can check where you are with /look.",
                            'Movement': "You can /move to a new place. Certain" +
                                " __location__s or routes might have limits on who's allowed" +
                                " in.",
                            'Visibility': "You're able to see people in the same" +
                                " __location__ as you, even if they're only passing by.",
                            'Sound': "Normally, you can only hear people in the" +
                                " same __location__ as you, and vice versa.",
                            'Eavesdropping': "If you want, you can /eavesdrop on" +
                                " people in a __location__ next to you to __direct__ly hear" +
                                " what's going on.",
                            'Fin': "And that's about it! Enjoy the game."}

            if interaction.guild_id:
                player_data = Player(interaction.user.id, ctx.guild_id)
                if player_data.location:
                    page_content['Player Channels'] += " You're a" + \
                        " player in this server, so you'll use" + \
                        f" <#{player_data.channel_ID}>."
                    page_content['Locations'] += " Right now, you're" + \
                        f" in **#{player_data.location}**."

            return await leatherbound(interaction, title_prefix, page_content)

        async def command_list(interaction: Interaction):
            title_prefix = 'Command List, Page'
            page_content = {
                'Intro' :
                    "Hello! The first few pages will be for __player__s, the next" + \
                    " few go over administrator/host commands, and then" + \
                    " there's some bonus commands at the end. Let's begin.",
                'Open' :
                    "Open (access) commands can be called by anyone," + \
                    " anywhere, at any time. For now, this only includes the" + \
                    " `/help` command, which covers the glossary, command" + \
                    " list, __player__ guide, and server setup tutorial.",
                'User' :
                    "**Limitations**" +  \
                        "\n• Must be within a server." + \
                        "\n• You must be a __player__." + \
                    "\n\n**Commands**" + \
                        "\n• `/look`: Shows you nearby __player__s, __location__s," + \
                            " and the __location__ description (if one is set)." + \
                        "\n• `/map`: Lets you see the places you can go." + \
                            " However, some places are restricted, and some" + \
                            " places might not have a way to them from here." + \
                            " Also, some servers limit the view distance." + \
                        "\n• `/move <location>`: Move somewhere." + \
                            " If you specify a __location__ when calling the command," + \
                            " you can skip straight to the confirmation." + \
                        "\n• `/eavesdrop`: By itself, this will tell you who you" + \
                            " hear nearby. Plus you can pick someplace" + \
                            " nearby to eavesdrop on. Walk away or call" + \
                            " it again to cancel.",
                'Node' :
                    "**Limitations**" + \
                        "\n• Must be within a server." + \
                        "\n• You must be an admin." +
                    "\n\n**Commands**" + \
                        "\n*These all have a <name> option, for you to " + \
                            " optionally name a __node__ as you call the command.*" + \
                        "\n\n• `/node new <name>`: Create a new __node__. If" + \
                            " no `<name>`, you'll can set one with the modal" + \
                            " dialogue. You can also set a __whitelist__." + \
                        "\n\n*If there's no `<name>` given, these next two commands" + \
                            " will check if you're in a __node__ channel and target that." + \
                            " If you're not, they will provide you a dropdown.*" + \
                        "\n\n• `/node delete <name>`: Delete a __node__ (if" + \
                            " no __player__s are inside)." + \
                        "\n• `/node review <name>`: Change a __node__'s" + \
                            " name and/or __whitelist__-- also shows you its occupants.",
                'Edge' :
                    "**Limitations**" + \
                        "\n• Must be within a server." + \
                        "\n• You must be an admin." + \
                        "\n• There must be more than one __node__." + \
                    "\n\n**Commands**" + \
                        "\n*Like before, you can <name> a __node__ to work on," + \
                            " call from within a __node__, or use the dropdown.*" + \
                        "\n\n• `/edge new <name>`: Create new __edge__s." + \
                            " You can set a __whitelist__, overwrite, and toggle" + \
                            " whether they're two-way or one-way." + \
                        "\n• `/edge delete <name>`: Delete __edge__ between" + \
                            " __node__s." + \
                        "\n• `/edge review <name>`: View or change" + \
                            " __whitelist__s.",
                'Player' :
                    "**Limitations**" + \
                        "\n• Must be within a server." + \
                        "\n• You must be an admin." + \
                    "\n\n**Commands**" + \
                        "\n*For these, you can <mention> a __player__.*" + \
                        "\n\n• `/player new <mention>`: Turn a user" + \
                            " into a __player__. You have to specify a __node__ for them" + \
                            " to start at." + \
                        "\n\n*These ones will give you the context-sensitivity" + \
                            " for calling from within a __player__ channel, like with __node__s." + \
                            " Otherwise, you can use the dropdown.*" + \
                        "\n• `/player delete <mention>`: Delete a __player__" + \
                            " and their channel." + \
                        "\n• `/player review <mention>`: See their @mention," + \
                            " __location__ __player__ channel, who they're eavesdropping on," + \
                            " change their __character__ name or avatar, all sorts of things." + \
                        "\n• `/player tp <mention>`: Teleport one or more" + \
                            " people to a __node__ of your choosing." + \
                        "\n• `/player find <mention>`: See the current" + \
                            " __location__ of all __player__s, or just the ones you choose.",
                'Server' :
                    "**Limitations**" + \
                        "\n• Must be within a server." + \
                        "\n• You must be an admin." + \
                    "\n\n**Commands**" + \
                        "\n• `/server view <node>`: View the whole __graph__" + \
                            " or just a part." + \
                        "\n• `/server clear`: Delete *everything*. Tread lightly." + \
                        "\n• `/server settings`: Adjust certain things about the" + \
                            " server, change defaults and overrides." + \
                        "\n• `/server debug`: View all server data, written out.",
                'Development' :
                    "**Limitations**" + \
                        "\n• Must be within a server." + \
                        "\n• You must be an admin." + \
                    "\n\n**Commands**" + \
                        "\n• `/test`: Just to esablish commands are online." + \
                        "\n• `/say <title> <body> <footer>`: Repeat something as an embed. Useful for devlogs." + \
                        "\n• `/refresh`: Reloads all commands, even this one."}

            await leatherbound(interaction, title_prefix, page_content)

        async def server_setup(interaction: Interaction):

            title_prefix = 'New Server, Step'
            page_content = {'Intro': "Hey! If you're interested in starting a" + \
                                " new roleplay, it's pretty simple. Let's start.",
                            'Template': "If you don't have a server established," + \
                                    " you can start with this template here," + \
                                    " which has the roles, channels, and settings" + \
                                    " prepared for you already:" + \
                                    " https://discord.new/4UXDgqfJ894a",
                            'Invite': "Once your server looks good, you can invite" + \
                                " me by clicking my profile. The big button under" + \
                                " my name will add me to whichever server you pick.",
                            'Edges': "Edges are the connections between nodes." + \
                                " An edge just means that there is a direct path" + \
                                " between two nodes that you can walk through. Maybe it's" + \
                                " a doorway or a bridge. Use `/edge new` to connect nodes.",
                            'Graph': "You can view a map of every node and the" + \
                                " edges between them. That's called a 'graph'. Nodes" + \
                                " are shown as just their name and the edges are" + \
                                " shown as arrows between them. Look at the graph" + \
                                " with `/server view`.",
                            'Quick Start': "If you want an example of a graph," + \
                                    " you can do `/server quick` to make a little house." + \
                                    " You can clear out the graph and the player data with" + \
                                    " `/server clear`.",
                            'Players': "Once you have somewhere to put the players," + \
                                " use `/player new` to add them to the game. You can also" + \
                                " move them with `/player tp` or find them with `/player find`.",
                            'Fixing': "If you mess with the channels, or if players leave," + \
                                " if might break the bot causing certain features not to work. Use" + \
                                " `/server fix` to automatically fix common issues.",
                            'Fin': "That's about all--you can figure the rest out. If you" + \
                                " have any issues or improvements to suggest, just let **davidlancaster**" + \
                                " know. Enjoy! :)"}
            # page_image = {
                # 'The Goal' : 'assets/overview.png',
                # 'Nodes' : 'assets/nodeExample.png',
                # 'Edges' : 'assets/edgeExample.png',
                # 'Graph' : 'assets/edgeIllustrated.png'}

            return await leatherbound(interaction, title_prefix, page_content)


        embed, _ = await mbd(
            'Hello!',
            "This command will help you learn what the bot does and how it" + \
                " can be used. Additionally, if you want to learn more about any" + \
                " __underlined__ words I use, just say `/help (underlined word)`.",
            "I'll be here if/when you need me.")

        buttons = {
            'Help for Players' : player_tutorial,
            'Commands' : command_list,
            'Server Setup' : server_setup}

        view = DialogueView()
        for button_label, button_callback in buttons.items():

            player_button = Button(
                label = button_label,
                style = ButtonStyle.success)
            player_button.callback = button_callback
            view.add_item(player_button)

        await view.add_cancel()
        await ctx.respond(embed = embed, view = view)
        return

def setup(prox):
    prox.add_cog(OpenCommands(prox), override = True)
