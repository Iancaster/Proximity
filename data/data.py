

#Import-ant Libraries
from discord import Intents


#Variables
intents = Intents.none()
intents.guilds = True
intents.guild_messages = True
intents.members = True
intents.message_content = True
intents.webhooks = True

owner_id = 985699127742582846

activity = 'the angles.'
