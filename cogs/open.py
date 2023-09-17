

#Import-ant Libraries
from discord import Option, ApplicationContext, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import Button

from libraries.universal import mbd
from libraries.classes import DialogueView, Player, Paginator


#Classes
class OpenCommands(commands.Cog):

    @commands.slash_command(
        name = 'help',
        description = 'Definitions, usage, and a tutorial.',
        guild_ids = [1114005940392439899])
    async def help(
        self,
        ctx: ApplicationContext,
        word: Option(
            str,
            description = 'Get help on a specific term?',
            required = False)):

        await ctx.defer(ephemeral = True)
        word = word.lower() if word else ''
        if word:

            glossary_terms = {
                'graph' : "A __graph__ (a.k.a. __network__), is a math thing: basically, there's\
                    dots (__nodes__) and there may or may not be connections between those dots\
                    (__edges__). That's basically it.\n\nFor us, though, all that matters is that\
                    __nodes__ are __locations__ and __edges__ are connections between them.",
                'network' : "See __graph__.",
                'node' : "A __node__ is a dot on a __graph__. If it's connected to any other\
                __node__s, that's called an __edge__. For us, a \"__node__\" has a couple things--\
                the __location__ is represents, the __permissions__ for it, and the Discord channel\
                for that __node__, which isn't visible to the players.",
                'location' : "The actual place represented by a __node__, like a kitchen. These\
                must be big enough to fit the __player__s, and small enough that anyone in one part of\
                the node can reasonably be expected to hear/see anything in any other part of the\
                __location__. Every __player__ is located in some __location__ at any point in time.",
                'permissions' : "Who's allowed to travel into/through a __node__ or an __edge__.\
                This mostly affects __movement__, where a __player__ is denied access to a place\
                because there's no route to their destination after accounting for their __permissions__.",
                'edges' : "Connections between __node__s on a __graph__. Any time two __locations__ are\
                connected for __movement__ or __sound__, an __edge__ should exist. Usually a door,\
                but it can be a hallway, bridge, elevator, portal... Can only let people through who\
                satisfy the __permissions__, but sound can travel freely.",
                'movement' : "The way that __player__s change which __location__ along the __graph__\
                their __presence__ is in. When they try to move to a new __location__, they need a\
                path along the __edges__ from where they are to their destination __node__, such that\
                they have permission to access every node and edge along the way.",
                'presence' : "The __location__ that a __player__ will hear all __sound__ in. Anytime\
                someone speaks in the same __location__, the __player__s who are present will hear.\
                __Presence__ also means that you'll see everyone in a room when you walk in, and\
                they'll see you.",
                'sound' : "Everything that __player__s are notified of. Includes everything spoken\
                by a __player__ in the same __location__, but may include __indirect__ sound from\
                __neighbor__ __node__s. Note that you trasmit all the same kind of noise as they do.",
                'indirect' : "As opposed to __sound__ that is __direct__, __indirect__ sound can only\
                by faintly made out, and only voices or small segments of the speech may be heard.\
                __Indirect__ sound is usually heard through __edges__ to __neighbor__ __nodes__,\
                and can be heard __direct__ly by __eavesdropping__.",
                'direct' : "As opposed to __sound__ that is __indirect__, __direct__ sound can be\
                fully heard, including identifying the speaker and what they're saying. Usually heard\
                through the __player__ being in the same __location__ as the speaker, or by __eavesdropping__.",
                'neighbor' : "A __node__ that is connected to another __node__ along one of its __edges__.\
                Fun fact: if a __node__ has an edge that points *to* another one, and it's only one-way,\
                they're not technically neighbors (even though this `/help` command defines them as such).\
                Instead, the origin would be the \"ancestor\" and the destination would be its \"successor.\"",
                'player' : 'People who have __presence__ at a __location__, can hear __sound__ from __node__s\
                they __neighbor__ as well as from other people in the same place. Capable of __movement__\
                and __eavesdropping__. In short, everyone who is placed in the __graph__.',
                'underlined' : "What-- no, \"__underlined__\" was so you can see what an __underlined__\
                word looked like, you're not supposed to actually search it. Goof."}

            if word in glossary_terms:
                embed, _ = await mbd(
                    f'Help for "{word}"',
                    glossary_terms[word],
                    "Clear things up, I hope?")
            else:
                embed, _ = await mbd(
                    'What was that?',
                    f"I'm sorry. I have a glossay for {len(glossary_terms)} words," + \
                        " but not for that. Perhaps start with the tutorials with" + \
                        " just a standard `/help` and go from there.",
                    "Sorry I couldn't do more.")

            await ctx.respond(embed = embed)
            return

        async def player_tutorial(interaction: Interaction):

            await interaction.response.defer()

            title_prefix = 'Player Tutorial, Page'
            page_content = {'Intro' : "Welcome, this guide" + \
                                    " will tell you everything you need to know as" + \
                                    " a player. Let's begin.",
                            'Player Channels': "Players have their own channel" + \
                                    " for roleplaying. All speech and movement, etc, is" + \
                                    " done through there.",
                            'Locations': "Your character exists in some location." + \
                                    " You can check where you are with `/look`.",
                            'Movement': "You can `/move` to a new place. Certain" + \
                                    " places or routes might have limits on who's allowed" + \
                                    " in.",
                            'Visibility': "You're able to see people in the same" + \
                                    " location as you, even if they're only passing by.",
                            'Sound': "Normally, you can only hear people in the" + \
                                    " same location as you, and vice versa.",
                            'Eavesdropping': "If you want, you can `/eavesdrop` on" + \
                                    " people in a location next to you to hear what's going on.",
                            'Fin': "And that's about it! Enjoy the game."}

            if interaction.guild_id:
                player_data = Player(interaction.user.id, ctx.guild_id)
                if player_data.location:
                    page_content['Player Channels'] += " You're a" + \
                        " player in this server, so you'll use" + \
                        f" <#{player_data.channelID}>."
                    page_content['Locations'] += " Right now, you're" + \
                        f" in **#{player_data.location}**."

            paginator = Paginator(
                interaction,
                title_prefix,
                page_content)
            await paginator.refresh_embed()
            return

        async def host_tutorial(interaction: Interaction):

            await interaction.response.defer()

            title_prefix = 'Host Tutorial, Page'
            page_content = {'Intro': "Buckle up, this guide is" + \
                                " a little longer than the Player one. I trust" + \
                                " you brought snacks. Let's begin.",
                            'The Goal': "I let the players move around" + \
                                    " between places, so your job is to tell me" + \
                                    " what the places are and how players can" + \
                                    " move around between them.",
                            'Nodes': "Locations that the players" + \
                                " can go inside are called nodes. Nodes should" + \
                                " be about the size of a room. Use `/node new`" + \
                                " to make them.",
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

            paginator = Paginator(
                interaction,
                title_prefix,
                page_content)
            await paginator.refresh_embed()
            return

        embed, _ = await mbd(
            'Hello!',
            "This command will help you learn what the bot does and how it" + \
                " can be used. Additionally, if you want to learn more about any" + \
                " __underlined__ words I use, just say `/help (underlined word)`.",
            "I'll be here if/when you need me.")

        view = DialogueView()
        player_button = Button(
            label = 'Help for Players',
            style = ButtonStyle.success)
        player_button.callback = player_tutorial
        view.add_item(player_button)

        host_button = Button(
            label = 'Help for Hosts',
            style = ButtonStyle.success)
        host_button.callback = host_tutorial
        view.add_item(host_button)

        await view.add_cancel()
        await ctx.respond(embed = embed, view = view)
        return

def setup(prox):
    prox.add_cog(OpenCommands(prox), override = True)
