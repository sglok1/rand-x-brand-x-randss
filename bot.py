import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}

# Store last 50 messages per channel before deletion
channel_messages_backup = {}

# Utility function to create embeds
def create_log_embed(title, color, fields):
    embed = discord.Embed(title=title, color=color)
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
    return embed

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    for guild in bot.guilds:
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel is None:
            log_channel = await guild.create_text_channel("security-logs")
            print(f"⚠️ Created log channel in {guild.name}")

@bot.event
async def on_member_join(member):
    if member.bot:
        guild = member.guild
        async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            adder = entry.user
            await guild.ban(member, reason="Unauthorized bot added")
            if adder and adder.id not in whitelisted:
                await guild.ban(adder, reason="Added an unauthorized bot")
            log_channel = discord.utils.get(guild.text_channels, name="security-logs")
            if log_channel:
                embed = create_log_embed("🚨 Unauthorized Bot Added", discord.Color.red(), {
                    "Bot": f"{member.mention} ({member.id})",
                    "Added By": f"{adder.mention} ({adder.id})"
                })
                await log_channel.send(embed=embed)
            print(f"🚨 {member} was banned for being an unauthorized bot, added by {adder}.")

@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        creator = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            embed = create_log_embed("🆕 Channel Created", discord.Color.green(), {
                "Channel": f"{channel.name} ({channel.mention})",
                "Created By": f"{creator.mention} ({creator.id})"
            })
            await log_channel.send(embed=embed)
        if creator.id not in whitelisted:
            await channel.delete()
            await channel.guild.ban(creator, reason="Unauthorized channel creation")

@bot.event
async def on_message(message):
    # Store message backups for channel restoration
    if message.channel.id not in channel_messages_backup:
        channel_messages_backup[message.channel.id] = []
    
    channel_messages_backup[message.channel.id].append({
        "author": message.author.name,
        "content": message.content
    })

    # Limit to last 50 messages per channel
    if len(channel_messages_backup[message.channel.id]) > 50:
        channel_messages_backup[message.channel.id].pop(0)

    await bot.process_commands(message)

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild

    async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        deleter = entry.user

        # Recreate channel with same settings
        new_channel = await guild.create_text_channel(
            name=channel.name,
            category=channel.category,
            topic=channel.topic,
            position=channel.position,
            overwrites=channel.overwrites
        )

        # Restore messages if backed up
        if channel.id in channel_messages_backup:
            messages = channel_messages_backup[channel.id]
            for msg in messages:
                await asyncio.sleep(0.5)  # Prevent rate limits
                await new_channel.send(f"**{msg['author']}:** {msg['content']}")
            del channel_messages_backup[channel.id]  # Clear after restoration

        # Log deletion & restoration
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel:
            embed = create_log_embed("❌ Channel Deleted & Restored", discord.Color.red(), {
                "Deleted Channel": f"{channel.name}",
                "Deleted By": f"{deleter.mention} ({deleter.id})",
                "Recreated As": f"{new_channel.mention}"
            })
            await log_channel.send(embed=embed)

        # Ban the user who deleted the channel
        if deleter.id not in whitelisted:
            await guild.ban(deleter, reason="Unauthorized channel deletion")

@bot.event
async def on_message_delete(message):
    log_channel = discord.utils.get(message.guild.text_channels, name="security-logs")
    async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
        if entry.target.id == message.author.id:
            deleter = entry.user
            break
    else:
        deleter = "Unknown"
    if log_channel:
        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.orange())
        embed.add_field(name="Deleted Message", value=message.content or "Embed/Attachment", inline=False)
        embed.add_field(name="Deleted By", value=f"{deleter.mention} ({deleter.id})" if deleter != "Unknown" else "Could not determine", inline=False)
        embed.add_field(name="Message Author", value=f"{message.author.mention} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
        await log_channel.send(embed=embed)

@bot.command()
async def whitelist(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.add(member.id)
        await ctx.send(f"✅ {member} has been added to the whitelist!")
    else:
        await ctx.send("⛔ You are not authorized to use this command.")

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.discard(member.id)
        await ctx.send(f"✅ {member} has been removed from the whitelist!")
    else:
        await ctx.send("⛔ You are not authorized to use this command.")

bot.run(TOKEN)
