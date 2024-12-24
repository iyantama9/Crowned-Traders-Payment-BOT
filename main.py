import discord
from discord.ext import commands, tasks
import requests
import asyncio
import base64
import time
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Constants and configuration
JSON_FILE_URL = os.getenv('JSON_FILE_URL')
TOKEN = os.getenv('DISCORD_TOKEN')
MIDTRANS_SERVER_KEY = os.getenv('MIDTRANS_SERVER_KEY')
MIDTRANS_CLIENT_KEY = os.getenv('MIDTRANS_CLIENT_KEY')
MIDTRANS_ENDPOINT = os.getenv('MIDTRANS_ENDPOINT')
GUILD_ID = int(os.getenv('GUILD_ID'))
PROJECT_ID = os.getenv('PROJECT_ID')
BUCKET_NAME = os.getenv('BUCKET_NAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Base64 encode the Midtrans server key
encoded_key = base64.b64encode((MIDTRANS_SERVER_KEY + ':').encode()).decode()

# Discord bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
user_emails = {}
user_names = {}
user_phone_numbers = {}
payment_status = {}
role_expiry = {}

# Google Sheets setup
def load_serviceaccount(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

service_account_json = load_serviceaccount(JSON_FILE_URL)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials = service_account.Credentials.from_service_account_info(service_account_json, scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)

# Function to write data to Google Sheets
def gsheet(user_id, email, name, phone, role_name, order_id, payment_status, sheet_name):
    values = [
        [user_id, email, name, phone, role_name, order_id, payment_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    ]
    body = {'values': values}
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=f'{sheet_name}!A1',
        valueInputOption='RAW', body=body).execute()
    print(f"{result.get('updates').get('updatedCells')} cells appended.")

# Registration and role management
START_REGISTRATION_DATE = datetime(2024, 12, 25)
REGISTRATION_PERIOD_DAYS = 7
CLASS_DURATION_DAYS = 30
ROLE_DURATION_DAYS = [30, 29, 28, 27, 26, 25, 24]

async def remove_role(guild):
    now = time.time()  
    for user_id, (role, expiry_time) in list(role_expiry.items()):
        if now >= expiry_time:  
            member = guild.get_member(user_id)
            if member and role:
                await member.remove_roles(role)
                print(f"Role {role.name} telah dihapus dari {member.name}")
            del role_expiry[user_id] 

@tasks.loop(hours=24)
async def schedule_role_removal():
    global START_REGISTRATION_DATE
    now = datetime.now()
    if now >= START_REGISTRATION_DATE + timedelta(days=REGISTRATION_PERIOD_DAYS + CLASS_DURATION_DAYS):
        guild = bot.get_guild(GUILD_ID)
        await remove_role(guild)
        START_REGISTRATION_DATE += timedelta(days=30)

async def add_fellows(guild, user_id, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    member = guild.get_member(user_id)
    
    if member and role:
        try:
            await member.add_roles(role)
            print(f"Role {role_name} telah ditambahkan ke {member.name}") 
            
            if role_name == "THE FELLOWS MONTHLY":
                registration_day = (datetime.now() - START_REGISTRATION_DATE).days
                if 0 <= registration_day < len(ROLE_DURATION_DAYS):
                    expiry_time = time.time() + ROLE_DURATION_DAYS[registration_day] * 24 * 60 * 60
                    role_expiry[user_id] = (role, expiry_time)
                else:
                    print("Hari pendaftaran di luar jangkauan.")
            else:
                expiry_time = time.time() + 30 * 24 * 60 * 60
                role_expiry[user_id] = (role, expiry_time)
        except RuntimeError as e:
            print(f"Kesalahan saat menambahkan role: {e}")
    else:
        print("Member atau role tidak ditemukan.")

# FastAPI setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Discord bot commands
@bot.command()
async def beli(ctx):
    now = datetime.now()
    if now < START_REGISTRATION_DATE or now >= START_REGISTRATION_DATE + timedelta(days=REGISTRATION_PERIOD_DAYS):
        next_registration_date = START_REGISTRATION_DATE + timedelta(days=30)
        await ctx.send(f"📅 Pendaftaran untuk bulan ini sudah ditutup, silahkan mendaftar lagi pada periode selanjutnya pada {next_registration_date.strftime('%d-%m-%Y')}.")
        return

    await ctx.send("🎉 **Pembayaran Role**\nHalo! 👋 Silakan masukkan email kamu untuk memulai proses pembayaran:")
    
    def check_email(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        email_msg = await bot.wait_for('message', check=check_email, timeout=60.0)
        email = email_msg.content
        if "@" not in email or "." not in email:
            await ctx.send("❌ **Oops!** Masukkan email yang valid, ya!")
            return
        user_emails[ctx.author.id] = email

        await ctx.send("📋 **Masukkan Nama Lengkap**\nSilakan masukkan nama lengkap kamu:")
        
        def check_name(m):
            return m.author == ctx.author and m.channel == ctx.channel

        name_msg = await bot.wait_for('message', check=check_name, timeout=60.0)
        name = name_msg.content
        user_names[ctx.author.id] = name

        await ctx.send("📞 **Masukkan Nomor Telepon**\nSilakan masukkan nomor telepon kamu:\n*Data kamu akan Yumi gunakan ketika ada kesalahan dalam pembayaran atau sistem kami.*")
        
        def check_phone(m):
            return m.author == ctx.author and m.channel == ctx.channel

        phone_msg = await bot.wait_for('message', check=check_phone, timeout=60.0)
        phone = phone_msg.content
        user_phone_numbers[ctx.author.id] = phone

        options = [
            discord.SelectOption(label="THE WARRIORS MONTHLY", value="THE WARRIORS MONTHLY", description="Role buat kamu yang udah bisa trading tapi butuh profile trading harian!!"),
            discord.SelectOption(label="THE FELLOWS MONTHLY", value="THE FELLOWS MONTHLY", description="Role buat kamu yang pengen belajar intensif dari awal sampai bisa trading!!"),
        ]

        select = discord.ui.Select(placeholder="Pilih role yang ingin kamu beli...", options=options)

        async def select_callback(interaction):
            role_name = select.values[0]
            order_id = f'order-{ctx.author.id}-{int(time.time())}'
            print(f"Email: {email}, Name: {name}, Phone: {phone}")

            price = 150000
            payload = {
                "transaction_details": {
                    "order_id": order_id,
                    "gross_amount": price
                },
                "item_details": [{
                    "id": "item-123",
                    "price": price,
                    "quantity": 1,
                    "name": role_name
                }],
                "customer_details": {
                    "first_name": ctx.author.name,
                    "email": email
                }
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {encoded_key}"
            }

            try:
                response = requests.post(MIDTRANS_ENDPOINT, json=payload, headers=headers)
                response.raise_for_status()
                payment_url = response.json().get('redirect_url')

                if payment_url:
                    payment_status[order_id] = {'status': 'pending', 'role': role_name, 'user_id': ctx.author.id}
                    
                    button = discord.ui.Button(label="💳 Bayar di sini", url=payment_url, style=discord.ButtonStyle.success)
                    view = discord.ui.View()
                    view.add_item(button)
                    
                    await interaction.response.send_message("🎊 **Pembayaran Diperlukan**\nSilakan lakukan pembayaran di sini:", view=view, ephemeral=True)
                else:
                    await interaction.response.send_message("❌ **Kesalahan**\nTerjadi kesalahan saat membuat pembayaran. Tidak ada URL pembayaran yang diterima.", ephemeral=True)
            except requests.exceptions.RequestException as e:
                await interaction.response.send_message("❌ **Kesalahan**\nTerjadi kesalahan saat menghubungi Midtrans API. Coba lagi nanti, ya!", ephemeral=True)
                print(f"Error: {e}")
                print(f"Response: {response.text}")

            select.disabled = True
            await interaction.message.edit(view=view)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await ctx.send("🔍 **Pilih Role**\nSilakan pilih role yang ingin kamu beli:", view=view)

    except asyncio.TimeoutError:
        await ctx.send("⏰ **Waktu Habis**\nWaktu habis! Silakan coba lagi dengan `!beli`.")

@bot.command()
async def check_payment(ctx):
    order_id_prefix = f'order-{ctx.author.id}-'
    matching_orders = [oid for oid in payment_status.keys() if oid.startswith(order_id_prefix)]
    
    if matching_orders:
        status = payment_status[matching_orders[0]]['status']
        await ctx.send(f"📜 **Status Pembayaran**\nStatus pembayaran untuk order ID `{matching_orders[0]}`: **{status}**")
    else:
        await ctx.send("❌ **Belum Ada Pembayaran**\nBelum ada pembayaran yang dilakukan. Yuk, beli role premium sekarang!")

@bot.command()
async def hello(ctx):
    await ctx.send(f"👋 **Selamat Datang**\nHollaaa, {ctx.author.name}! Welcome to Crowned Traders 🎉")

@bot.command()
async def info(ctx):
    await ctx.send("ℹ️ **Hollaaa Yumi Di sini!**\nYumi berfungsi untuk membantu kamu membeli role premium di sini! 🎊")

# FastAPI payment notification endpoint
@app.post('/payment-notification')
async def payment_notification(request: Request):
    data = await request.json()
    
    if 'order_id' in data and 'transaction_status' in data:
        order_id = data['order_id']
        transaction_status = data['transaction_status']
        
        print(f"Received order_id: {order_id}")
        print(f"Transaction status: {transaction_status}")
        
        if order_id in payment_status:
            if transaction_status in ['settlement', 'capture']:
                user_id = order_id.split('-')[1]
                guild = bot.get_guild(GUILD_ID)
                role_name = payment_status[order_id]['role']
                
                bot.loop.create_task(add_fellows(guild, user_id, role_name))
                
                payment_status[order_id]['status'] = 'settled'
                print(f"Update payment status for order_id {order_id}: settled")
                
                user = await bot.fetch_user(payment_status[order_id]['user_id'])
                await user.send(f"✅ **Pembayaran Berhasil**\nPembayaran untuk order ID `{order_id}` telah berhasil! Role `{role_name}` telah ditambahkan")
                
                email = user_emails.get(int(user_id))
                name = user_names.get(int(user_id))
                phone = user_phone_numbers.get(int(user_id))
                sheet_name = 'FELLOWS' if role_name == "THE FELLOWS MONTHLY" else 'WARRIORS'
                gsheet(user_id, email, name, phone, role_name, order_id, 'settled', sheet_name)
                
                return JSONResponse(content={"status": "success"})
        else:
            print(f"Order ID {order_id} not found in payment_status.")
    
    return JSONResponse(content={"status": "ignored"})

# FastAPI server startup
async def start_fastapi():
    port = int(os.getenv('PORT', 8080)) 
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# Main function to run the bot and FastAPI
async def main():
    schedule_role_removal.start()
    fastapi_task = asyncio.create_task(start_fastapi())
    await bot.start(TOKEN)
    await fastapi_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
