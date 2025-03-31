import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}

# Regex pattern for detecting links
LINK_PATTERN = re.compile(r"(https?://\S+|www\.\S+)")

def create_log_embed(title, color, fields):
    embed = discord.Embed(title=title, color=color)
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
    return embed

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for guild in bot.guilds:
        # Check for text log channel
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel is None:
            log_channel = await guild.create_text_channel("security-logs")
            print(f"Created text log channel in {guild.name}")
        
        # Check for voice log channel
        vc_log_channel = discord.utils.get(guild.voice_channels, name="vc-logs")
        if vc_log_channel is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False)
            }
            vc_log_channel = await guild.create_voice_channel(
                "vc-logs",
                overwrites=overwrites,
                reason="Automatic VC logging channel creation"
            )
            print(f"Created VC log channel in {guild.name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check for links
    if LINK_PATTERN.search(message.content):
        if message.author.id not in whitelisted:
            await message.delete()
            await message.author.send("Fuck you teri beti chodo BEN KE LODE")
            
            log_channel = discord.utils.get(message.guild.text_channels, name="security-logs")
            if log_channel:
                embed = create_log_embed("🚨 Link Deleted", discord.Color.red(), {
                    "User": f"{message.author.mention} ({message.author.id})",
                    "Deleted Link": message.content
                })
                await log_channel.send(embed=embed)

    await bot.process_commands(message)

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
            channel_type = "Voice" if isinstance(channel, discord.VoiceChannel) else "Text"
            embed = create_log_embed("🆕 Channel Created", discord.Color.green(), {
                "Channel": f"{channel.name} ({channel.mention})",
                "Type": channel_type,
                "Created By": f"{creator.mention} ({creator.id})"
            })
            await log_channel.send(embed=embed)
        if creator.id not in whitelisted and not isinstance(channel, discord.VoiceChannel):
            await channel.delete()
            await channel.guild.ban(creator, reason="Unauthorized channel creation")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        deleter = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            channel_type = "Voice" if isinstance(channel, discord.VoiceChannel) else "Text"
            embed = create_log_embed("❌ Channel Deleted", discord.Color.red(), {
                "Channel": f"{channel.name}",
                "Type": channel_type,
                "Deleted By": f"{deleter.mention} ({deleter.id})"
            })
            await log_channel.send(embed=embed)
        if deleter.id not in whitelisted and not isinstance(channel, discord.VoiceChannel):
            await channel.guild.ban(deleter, reason="Unauthorized channel deletion")

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

# VC Logging Events
@bot.event
async def on_voice_state_update(member, before, after):
    log_channel = discord.utils.get(member.guild.text_channels, name="security-logs")
    vc_log_channel = discord.utils.get(member.guild.voice_channels, name="vc-logs")
    
    if not log_channel:
        return
    
    # User joined a voice channel
    if before.channel is None and after.channel is not None:
        if after.channel != vc_log_channel:  # Don't log joining the log channel
            embed = create_log_embed("🎤 Voice Channel Join", discord.Color.green(), {
                "User": f"{member.mention} ({member.id})",
                "Channel": after.channel.name,
                "Time": discord.utils.utcnow().strftime('%H:%M:%S')
            })
            await log_channel.send(embed=embed)
    
    # User left a voice channel
    elif before.channel is not None and after.channel is None:
        if before.channel != vc_log_channel:  # Don't log leaving the log channel
            embed = create_log_embed("🚪 Voice Channel Leave", discord.Color.blue(), {
                "User": f"{member.mention} ({member.id})",
                "Channel": before.channel.name,
                "Time": discord.utils.utcnow().strftime('%H:%M:%S')
            })
            await log_channel.send(embed=embed)
    
    # User moved between voice channels
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        embed = create_log_embed("🔄 Voice Channel Move", discord.Color.gold(), {
            "User": f"{member.mention} ({member.id})",
            "From": before.channel.name,
            "To": after.channel.name,
            "Time": discord.utils.utcnow().strftime('%H:%M:%S')
        })
        await log_channel.send(embed=embed)
    
    # User muted/unmuted/deafened/etc.
    elif before.channel is not None and after.channel is not None and before.channel == after.channel:
        changes = []
        if before.self_mute != after.self_mute:
            changes.append(f"Self Mute: {'🔴 On' if after.self_mute else '🟢 Off'}")
        if before.self_deaf != after.self_deaf:
            changes.append(f"Self Deafen: {'🔴 On' if after.self_deaf else '🟢 Off'}")
        if before.mute != after.mute:
            changes.append(f"Server Mute: {'🔴 On' if after.mute else '🟢 Off'}")
        if before.deaf != after.deaf:
            changes.append(f"Server Deafen: {'🔴 On' if after.deaf else '🟢 Off'}")
        if before.self_stream != after.self_stream:
            changes.append(f"Stream: {'🔴 On' if after.self_stream else '🟢 Off'}")
        if before.self_video != after.self_video:
            changes.append(f"Video: {'🔴 On' if after.self_video else '🟢 Off'}")
        
        if changes:
            embed = create_log_embed("🎙️ Voice State Update", discord.Color.purple(), {
                "User": f"{member.mention} ({member.id})",
                "Channel": before.channel.name,
                "Changes": "\n".join(changes),
                "Time": discord.utils.utcnow().strftime('%H:%M:%S')
            })
            await log_channel.send(embed=embed)

@bot.command()
async def whitelist(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.add(member.id)
        await ctx.send(f"{member} has been added to the whitelist!")
    else:
        await ctx.send("You are not authorized to use this command.")

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    if ctx.author.id == OWNER_ID:
        whitelisted.discard(member.id)
        await ctx.send(f"{member} has been removed from the whitelist!")
    else:
        await ctx.send("You are not authorized to use this command.")

bot.run(TOKEN)
