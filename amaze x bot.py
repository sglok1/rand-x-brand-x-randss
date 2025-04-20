import discord
from discord.ext import commands
import asyncio

TOKEN = "MTM1NTc5MjIzMzIzMTU0ODU5Nw.G77Wwi.HtMVaQ55_PvooI-dglf6wV-v_7iV9MHqAiLpo0"
OWNER_ID = 1229802108463743036  

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}

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
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel is None:
            log_channel = await guild.create_text_channel("security-logs")
            print(f"Created log channel in {guild.name}")

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
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        deleter = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            embed = create_log_embed("❌ Channel Deleted", discord.Color.red(), {
                "Channel": f"{channel.name}",
                "Deleted By": f"{deleter.mention} ({deleter.id})"
            })
            await log_channel.send(embed=embed)
        if deleter.id not in whitelisted:
            await channel.guild.ban(deleter, reason="Unauthorized channel deletion")

@bot.event
async def on_message_delete(message):
    log_channel = discord.utils.get(message.guild.text_channels, name="security-logs")
    async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
        if entry.target.id == message.author.id:  # Ensure the deleted message belongs to the correct user
            deleter = entry.user
            break
    else:
        deleter = "Unknown"
        

@bot.event
async def on_message_edit(before, after):
    log_channel = discord.utils.get(before.guild.text_channels, name="security-logs")
    if log_channel:
        embed = create_log_embed("✏️ Message Edited", discord.Color.blue(), {
            "Before": before.content,
            "After": after.content,
            "Edited By": f"{before.author.mention} ({before.author.id})",
            "Channel": before.channel.mention
        })
        await log_channel.send(embed=embed)
    if log_channel:
        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.orange())
        embed.add_field(name="Deleted Message", value=message.content or "Embed/Attachment", inline=False)
        embed.add_field(name="Deleted By", value=f"{deleter.mention} ({deleter.id})" if deleter != "Unknown" else "Could not determine", inline=False)
        embed.add_field(name="Message Author", value=f"{message.author.mention} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
        
        await log_channel.send(embed=embed)
        

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for guild in bot.guilds:
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel is None:
            log_channel = await guild.create_text_channel("security-logs")
            print(f"Created log channel in {guild.name}")

@bot.event
async def on_member_join(member):
    if member.bot:
        await member.ban(reason="Bot auto-ban enabled")
        print(f"Banned bot {member}")

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            giver = entry.user
            if giver.id not in whitelisted:
                for role in after.roles:
                    if role not in before.roles:
                        await after.remove_roles(role)
                        print(f"Removed role {role} from {after}")
                await after.guild.ban(giver, reason="Unauthorized role grant")
                print(f"Banned {giver} for granting roles")
                log_channel = discord.utils.get(after.guild.text_channels, name="security-logs")
                if log_channel:
                    await log_channel.send(f"{giver} tried to give a role, action reverted and user banned!")

@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        creator = entry.user
        if creator.id not in whitelisted:
            await channel.delete()
            await channel.guild.ban(creator, reason="Unauthorized channel creation")
            print(f"Deleted channel {channel} created by {creator}")
            log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
            if log_channel:
                await log_channel.send(f"{creator} created a channel {channel.name}, action reverted and user banned!")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        deleter = entry.user
        if deleter.id not in whitelisted:
            await channel.guild.ban(deleter, reason="Unauthorized channel deletion")
            print(f"Banned {deleter} for deleting {channel}")
            log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
            if log_channel:
                await log_channel.send(f"{deleter} deleted channel {channel.name}, user banned!")

@bot.event
async def on_message_delete(message):
    async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
        deleter = entry.user
        log_channel = discord.utils.get(message.guild.text_channels, name="security-logs")
        if log_channel:
            await log_channel.send(f"{deleter} deleted a message: '{message.content}' in {message.channel}")

@bot.event
async def on_message_edit(before, after):
    log_channel = discord.utils.get(before.guild.text_channels, name="security-logs")
    if log_channel:
        await log_channel.send(f"Message edited in {before.channel} by {before.author}\nBefore: '{before.content}'\nAfter: '{after.content}'")

@bot.event
async def on_voice_state_update(member, before, after):
    log_channel = discord.utils.get(member.guild.text_channels, name="security-logs")
    if before.channel != after.channel:
        if after.channel and log_channel:
            await log_channel.send(f"{member} joined voice channel {after.channel}")
        elif before.channel and log_channel:
            await log_channel.send(f"{member} left voice channel {before.channel}")
    if before.self_mute != after.self_mute:
        action = "muted" if after.self_mute else "unmuted"
        if log_channel:
            await log_channel.send(f"{member} was {action} in voice chat.")
    if before.self_deaf != after.self_deaf:
        action = "deafened" if after.self_deaf else "undeafened"
        if log_channel:
            await log_channel.send(f"{member} was {action} in voice chat.")
    async for entry in member.guild.audit_logs(limit=1):
        if entry.action == discord.AuditLogAction.member_update:
            if before.mute != after.mute:
                action = "server muted" if after.mute else "server unmuted"
                if log_channel:
                    await log_channel.send(f"{member} was {action} by {entry.user}.")
            if before.deaf != after.deaf:
                action = "server deafened" if after.deaf else "server undeafened"
                if log_channel:
                    await log_channel.send(f"{member} was {action} by {entry.user}.")

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

@bot.command()
async def check_whitelist(ctx):
    await ctx.send(f"Whitelisted Users: {', '.join(str(user) for user in whitelisted)}")

@bot.command()
async def join_vc(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined voice channel {channel}")
    else:
        await ctx.send("You need to be in a voice channel for me to join!")

@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        creator = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            embed = discord.Embed(title="🆕 Channel Created", color=discord.Color.green())
            embed.add_field(name="Channel", value=f"{channel.name} ({channel.mention})", inline=False)
            embed.add_field(name="Created By", value=f"{creator.mention} ({creator.id})", inline=False)
            embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
            await log_channel.send(embed=embed)
        if creator.id not in whitelisted:
            await channel.delete()
            await channel.guild.ban(creator, reason="Unauthorized channel creation")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        deleter = entry.user
        log_channel = discord.utils.get(channel.guild.text_channels, name="security-logs")
        if log_channel:
            embed = discord.Embed(title="❌ Channel Deleted", color=discord.Color.red())
            embed.add_field(name="Channel", value=f"{channel.name}", inline=False)
            embed.add_field(name="Deleted By", value=f"{deleter.mention} ({deleter.id})", inline=False)
            embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
            await log_channel.send(embed=embed)
        if deleter.id not in whitelisted:
            await channel.guild.ban(deleter, reason="Unauthorized channel deletion")

@bot.event
async def on_message_delete(message):
    async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
        deleter = entry.user
        log_channel = discord.utils.get(message.guild.text_channels, name="security-logs")
        if log_channel:
            embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.orange())
            embed.add_field(name="Deleted Message", value=message.content, inline=False)
            embed.add_field(name="Deleted By", value=f"{deleter.mention} ({deleter.id})", inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)
            embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
            await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    log_channel = discord.utils.get(before.guild.text_channels, name="security-logs")
    if log_channel:
        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.blue())
        embed.add_field(name="Before", value=before.content, inline=False)
        embed.add_field(name="After", value=after.content, inline=False)
        embed.add_field(name="Edited By", value=f"{before.author.mention} ({before.author.id})", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=False)
        embed.set_footer(text=f"Today at {discord.utils.utcnow().strftime('%H:%M')}")
        await log_channel.send(embed=embed)
@bot.command()
async def unwhitelist(ctx, user: discord.Member):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You do not have permission to use this command!")
        return

    if user.id in whitelisted:
        whitelisted.remove(user.id)
        await ctx.send(f"✅ {user.mention} has been removed from the whitelist.")
    else:
        await ctx.send(f"❌ {user.mention} is not in the whitelist.")

async def ban_user(guild, user, reason="Violation of server rules"):
    """Bans a user and sends them a DM notification."""
    try:
        # Attempt to send a DM before banning
        dm_message = discord.Embed(title="🚨 BSDK SERVER KO MAT CHED TERA PAPA KA HA SAMJA", color=discord.Color.red())
        dm_message.add_field(name="PAPA", value=guild.name, inline=False)
        dm_message.add_field(name="FUCK YOU!", value=reason, inline=False)
        dm_message.set_footer(text="MIL GAYA NA BAN JO KAR RAHA THA USSE LAWDE")
        
        try:
            await user.send(embed=dm_message)  # Send DM before banning
        except discord.Forbidden:
            print(f"⚠️ Could not send DM to {user} (DMs may be closed).")
        
        # Ban the user
        await guild.ban(user, reason=reason)
        
        # Log the ban in a security channel
        log_channel = discord.utils.get(guild.text_channels, name="security-logs")
        if log_channel:
            embed = discord.Embed(title="⛔ User Banned", color=discord.Color.red())
            embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text=f"Banned at {discord.utils.utcnow().strftime('%H:%M')}")
            await log_channel.send(embed=embed)

    except discord.Forbidden:
        print(f"❌ Missing permissions to ban {user} in {guild.name}!")
    except Exception as e:
        print(f"❌ Unexpected error banning {user}: {e}")

bot.run(TOKEN)
