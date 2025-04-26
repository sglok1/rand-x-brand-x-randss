import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
whitelisted = {OWNER_ID}
LINK_PATTERN = re.compile(r"(https?://\S+|www\.\S+)")

def create_log_embed(title, color, fields):
    embed = discord.Embed(title=title, color=color, timestamp=datetime.utcnow())
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=False)
    return embed

async def get_log_channel(guild):
    log_channel = discord.utils.get(guild.text_channels, name="security-logs")
    if log_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=False),
            guild.me: discord.PermissionOverwrite(send_messages=True)
        }
        log_channel = await guild.create_text_channel(
            "security-logs",
            overwrites=overwrites,
            reason="Automatic log channel creation"
        )
    return log_channel

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    for guild in bot.guilds:
        await get_log_channel(guild)

# Channel Creation/Deletion Ban
@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        if entry.user.id not in whitelisted:
            await channel.delete()
            await entry.user.ban(reason="Unauthorized channel creation")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚫 Channel Created & User Banned", discord.Color.red(), {
                "User": entry.user.mention,
                "Action": "Created channel",
                "Channel": channel.name
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized channel deletion")
            log_channel = await get_log_channel(channel.guild)
            embed = create_log_embed("🚫 Channel Deleted & User Banned", discord.Color.red(), {
                "User": entry.user.mention,
                "Action": "Deleted channel",
                "Channel": channel.name
            })
            await log_channel.send(embed=embed)

# Role Creation/Deletion Ban
@bot.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        if entry.user.id not in whitelisted:
            await role.delete()
            await entry.user.ban(reason="Unauthorized role creation")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚫 Role Created & User Banned", discord.Color.red(), {
                "User": entry.user.mention,
                "Action": "Created role",
                "Role": role.name
            })
            await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id not in whitelisted:
            await entry.user.ban(reason="Unauthorized role deletion")
            log_channel = await get_log_channel(role.guild)
            embed = create_log_embed("🚫 Role Deleted & User Banned", discord.Color.red(), {
                "User": entry.user.mention,
                "Action": "Deleted role",
                "Role": role.name
            })
            await log_channel.send(embed=embed)

# Role Assignment Ban and Timeout
@bot.event
async def on_member_update(before, after):
    # Check for role additions
    added_roles = [role for role in after.roles if role not in before.roles]
    if added_roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            if entry.user.id not in whitelisted and entry.user != after:
                # Ban the user who assigned the roles
                await entry.user.ban(reason="Unauthorized role assignment")
                
                # Remove the added roles from the target user
                for role in added_roles:
                    await after.remove_roles(role, reason="Unauthorized role assignment")
                
                # Timeout the user who received the roles (1 day timeout)
                try:
                    timeout_duration = timedelta(days=1)
                    await after.timeout(timeout_duration, reason="Received unauthorized roles")
                except discord.Forbidden:
                    pass  # If we can't timeout, just continue
                
                # Log the action
                log_channel = await get_log_channel(after.guild)
                embed = create_log_embed("🚫 Unauthorized Role Assignment", discord.Color.red(), {
                    "Assigner": entry.user.mention,
                    "Assigner Action": "Banned",
                    "Target": after.mention,
                    "Target Action": "Roles removed + 1 day timeout",
                    "Roles": ', '.join([role.name for role in added_roles])
                })
                await log_channel.send(embed=embed)
    
    # Check for role permission changes
    if before.roles != after.roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update, limit=1):
            if entry.user.id not in whitelisted:
                # Ban the user who modified the role
                await entry.user.ban(reason="Unauthorized role modification")
                
                # Log the action
                log_channel = await get_log_channel(after.guild)
                embed = create_log_embed("🚫 Unauthorized Role Modification", discord.Color.red(), {
                    "User": entry.user.mention,
                    "Action": "Modified role permissions",
                    "Role": entry.target.name if hasattr(entry, 'target') else "Unknown"
                })
                await log_channel.send(embed=embed)

# Bot Addition Ban
@bot.event
async def on_member_join(member):
    if member.bot:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id not in whitelisted:
                # Ban the user who added the bot
                await entry.user.ban(reason="Unauthorized bot addition")
                
                # Kick the unauthorized bot
                await member.kick(reason="Unauthorized bot")
                
                # Log the action
                log_channel = await get_log_channel(member.guild)
                embed = create_log_embed("🚫 Unauthorized Bot Added", discord.Color.red(), {
                    "User": entry.user.mention,
                    "Action": "Banned for adding bot",
                    "Bot": member.mention
                })
                await log_channel.send(embed=embed)

# Whitelist Commands
@bot.command()
@commands.is_owner()
async def whitelist(ctx, member: discord.Member):
    whitelisted.add(member.id)
    await ctx.send(f"✅ {member} has been added to the whitelist!")

@bot.command()
@commands.is_owner()
async def whitelist_remove(ctx, member: discord.Member):
    whitelisted.discard(member.id)
    await ctx.send(f"❌ {member} has been removed from the whitelist!")

@bot.command()
@commands.is_owner()
async def whitelist_show(ctx):
    members = []
    for user_id in whitelisted:
        user = bot.get_user(user_id)
        members.append(f"{user.mention if user else 'Unknown user'} (ID: {user_id})")
    
    embed = discord.Embed(title="Whitelisted Users", color=discord.Color.blue())
    embed.description = "\n".join(members) if members else "No whitelisted users"
    await ctx.send(embed=embed)

bot.run(TOKEN)
