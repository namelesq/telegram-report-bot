import re
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import TOKEN, GROUP_CHAT_ID
from pytz import timezone

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
moscow = timezone("Europe/Moscow")
scheduler = AsyncIOScheduler(timezone=moscow)

report_data = {}

def validate_employee_line(line):
    return bool(re.match(r'^[А-Яа-яA-Za-zёЁ\-]+\s[А-Яа-яA-Za-zёЁ\-]\s*-\s*\d+/\d+/\d+$', line.strip()))

def calculate_efficiency(pays, calls):
    pay_eff = min(pays / 4 * 100, 100)
    call_eff = min(calls / 60 * 100, 100)
    return round((pay_eff + call_eff) / 2)

async def send_scheduled_report():
    if not report_data:
        await bot.send_message(GROUP_CHAT_ID, "❗️На сегодня отчёт не предоставлен.")
        return

    total_pays = total_calls = total_plan = total_eff = 0
    lines = []

    for name, (pays, calls, plan) in report_data.items():
        eff = calculate_efficiency(pays, calls)
        total_pays += pays
        total_calls += calls
        total_plan += plan
        total_eff += eff
        lines.append(f"{name} - {eff}%")

    avg_eff = round(total_eff / len(report_data), 2)
    avg_plan = round(total_plan / len(report_data))
    summary = f"\nИТОГ ФИЛИАЛА:\n{total_pays}/{total_calls}/{avg_plan}\n{avg_eff}%"
    final_message = '\n'.join(lines) + summary

    await bot.send_message(GROUP_CHAT_ID, final_message)
    report_data.clear()

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    greeting = (
        "👋 Привет! Я бот для сбора отчётов сотрудников.\n\n"
        "📥 Каждый день до 18:30 отправьте мне данные о сотрудниках в формате:\n"
        "`Фамилия И - X/Y/Z`\n\n"
        "🔹 X — количество оплат\n"
        "🔹 Y — количество звонков\n"
        "🔹 Z — процент выполненного плана\n\n"
        "📌 Пример:\n"
        "`Иванов И - 2/45/87`\n\n"
        "✅ В 18:30 я автоматически отправлю итог в рабочую группу.\n"
        "Также можно вручную вызвать отчёт командой /отчет"
    )
    await message.reply(greeting, parse_mode="Markdown")

@dp.message_handler(commands=['chatid'])
async def get_chat_id(message: types.Message):
    await message.reply(f"🆔 Chat ID этой группы: `{message.chat.id}`", parse_mode="Markdown")

@dp.message_handler(commands=['отчет'])
async def manual_send_report(message: types.Message):
    await send_scheduled_report()
    await message.reply("✅ Отчёт отправлен в группу.")

@dp.message_handler()
async def receive_report(message: types.Message):
    if message.chat.type != "private":
        return

    lines = message.text.strip().split('\n')
    temp_data = {}
    valid = True

    for line in lines:
        if not validate_employee_line(line):
            valid = False
            break
        try:
            name, stats = line.split('-')
            pays, calls, plan = map(int, stats.strip().split('/'))
            temp_data[name.strip()] = (pays, calls, plan)
        except:
            valid = False
            break

    if not valid:
        await message.reply("❌ Неверный формат строки:\n`Фамилия И - X/Y/Z`", parse_mode="Markdown")
        return

    report_data.update(temp_data)
    await message.reply("✅ Данные сохранены. Итог будет отправлен в 18:30 или по команде /отчет.")

async def on_startup(_):
    scheduler.add_job(send_scheduled_report, 'cron', hour=18, minute=30)
    scheduler.start()
    print("✅ Бот запущен")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)