#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# @Author  :   Arthals
# @File    :   main.py
# @Time    :   2024/08/10 03:06:58
# @Contact :   zhuozhiyongde@126.com
# @Software:   Visual Studio Code


import argparse
import time
from datetime import datetime, timedelta

import yaml
import schedule
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from loguru import logger

from session import BarkNotifier, Session

# 配置rich控制台
console = Console()

# 配置loguru日志
logger.remove()  # 移除默认处理器
logger.add(
    "reservation.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)


def load_config(config_file):
    """加载配置文件"""
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


def make_reservation(appointment_config, student_config):
    """执行单个预约任务"""
    date = appointment_config["yyrq"]
    student_id = student_config["username"]
    task_tag = f"appointment_{student_id}_{appointment_config['yyrq']}"

    # 检查是否到了预约开放时间
    target_day = datetime.strptime(str(appointment_config["yyrq"]), "%Y%m%d")
    open_time = (target_day - timedelta(days=3)).replace(
        hour=8, minute=0, second=1, microsecond=0
    )
    current_time = datetime.now()

    if current_time < open_time:
        return

    logger.info(f"开始执行预约 - 学生: {student_id}, 日期: {date}")
    console.print(f"[bold blue]🔄 正在为学生 {student_id} 执行预约任务...[/bold blue]")

    # 创建通知器
    bark_token = student_config.get("bark", None)
    notifier = BarkNotifier(bark_token)

    # 合并配置信息
    session_config = {
        "username": student_config["username"],
        "password": student_config["password"],
        "phone": student_config["phone"],
        "yyrq": appointment_config["yyrq"],
        "yyxm": appointment_config["yyxm"],
        "yysj": appointment_config["yysj"],
        "yysy": appointment_config["yysy"],
        "mode": appointment_config["mode"],
        "auto": student_config["auto"],
        "appointments": appointment_config["visitors"],
        "totp_mode": student_config.get("totp_mode", "shortcut"),
        "totp_secret": student_config.get("totp_secret", None),
    }

    s = Session(config=session_config, notifier=notifier)

    try:
        if not s.login():
            error_msg = "验证登录失败，请检查配置"
            logger.error(f"学生 {student_id}: {error_msg}")
            console.print(f"[bold red]✗ 学生 {student_id}: {error_msg}[/bold red]")
            if notifier.valid:
                notifier.send(f"Student {student_id}: {error_msg}")
            # 移除失败的调度任务
            schedule.clear(task_tag)
            logger.info(f"已移除失败任务的调度: {task_tag}")
            return

        logger.info(f"学生 {student_id} 登录成功，开始提交预约")
        s.submit_all()

        success_msg = "所有预约提交成功"
        logger.success(f"学生 {student_id}: {success_msg}")
        console.print(
            f"[bold green]✓ 学生 {student_id} ({date}): {success_msg}[/bold green]"
        )

        if notifier.valid:
            notifier.send(f"Student {student_id}: All Succeed")

        # 预约成功后移除调度任务
        schedule.clear(task_tag)
        logger.info(f"预约完成，已移除调度: {task_tag}")

    except AssertionError as e:
        error_msg = f"预约失败 - {str(e)}"
        logger.error(f"学生 {student_id}: {error_msg}")
        console.print(f"[bold red]✗ 学生 {student_id} ({date}): {error_msg}[/bold red]")
        if notifier.valid:
            notifier.send(f"Student {student_id}: Failed - {e}")
        # 移除失败的调度任务
        schedule.clear(task_tag)
        logger.info(f"已移除失败任务的调度: {task_tag}")
    except Exception as e:
        error_msg = f"意外错误 - {str(e)}"
        logger.error(f"学生 {student_id}: {error_msg}")
        console.print(f"[bold red]✗ 学生 {student_id} ({date}): {error_msg}[/bold red]")
        if notifier.valid:
            notifier.send(f"Student {student_id}: Error - {e}")
        # 移除失败的调度任务
        schedule.clear(task_tag)
        logger.info(f"已移除失败任务的调度: {task_tag}")


def schedule_appointment(appointment_config, student_config):
    """为单个预约安排调度"""
    student_id = student_config["username"]
    target_day = datetime.strptime(str(appointment_config["yyrq"]), "%Y%m%d")
    now = datetime.now()

    # 计算到预约开放时间的差值（预约日期前3天的08:00:01）
    open_time = (target_day - timedelta(days=3)).replace(
        hour=8, minute=0, second=1, microsecond=0
    )

    time_diff = (open_time - now).total_seconds()

    # 显示调度信息
    schedule_table = Table(show_header=False, box=None, padding=(0, 1))
    schedule_table.add_column("字段", style="cyan")
    schedule_table.add_column("值", style="white")
    schedule_table.add_row("学生ID", str(student_id))
    schedule_table.add_row("预约日期", target_day.strftime("%Y-%m-%d"))
    schedule_table.add_row("开放时间", open_time.strftime("%Y-%m-%d %H:%M:%S"))

    # 创建通知器用于调度通知
    bark_token = student_config.get("bark", None)
    notifier = BarkNotifier(bark_token)

    if time_diff > 0:
        # 还没到预约开放时间，安排定时任务
        wait_hours = time_diff / 3600
        schedule_table.add_row("等待时间", f"{wait_hours:.1f}小时")
        schedule_table.add_row("状态", "[yellow]已调度[/yellow]")

        console.print(
            Panel(schedule_table, title="[bold blue]📅 预约调度信息[/bold blue]")
        )
        logger.info(
            f"学生 {student_id} - 调度成功，将在 {open_time.strftime('%Y-%m-%d %H:%M:%S')} 执行"
        )

        # 发送启动通知
        if notifier.valid:
            notifier.send(
                f"Student {student_id}: 已安排自动预约任务，将在 {open_time.strftime('%Y-%m-%d %H:%M:%S')} 开始"
            )

        # 使用schedule安排任务
        schedule.every().day.at(open_time.strftime("%H:%M:%S")).do(
            make_reservation, appointment_config, student_config
        ).tag(f"appointment_{student_id}_{appointment_config['yyrq']}")

    else:
        # 预约时间已过或不足3天，立即执行
        schedule_table.add_row("状态", "[green]立即执行[/green]")
        console.print(
            Panel(schedule_table, title="[bold green]⚡ 立即执行[/bold green]")
        )
        logger.info(f"学生 {student_id} - 预约时间已过或不足3天，立即执行")

        if notifier.valid:
            notifier.send(f"Student {student_id}: 立即开始预约")

        # 为立即执行的任务也添加相同的清理逻辑
        make_reservation(appointment_config, student_config)


def validate_config(data):
    """验证配置文件格式"""
    if "appointments" not in data or "username" not in data or "password" not in data:
        raise ValueError("配置文件缺少必要的字段: appointments, username, password")

    appointments = data["appointments"]

    # 创建验证结果表格
    validation_table = Table()
    validation_table.add_column("类型", style="cyan")
    validation_table.add_column("数量", style="magenta")
    validation_table.add_column("状态", style="green")

    validation_table.add_row("学生", "1", "✓ 验证成功")
    validation_table.add_row("预约", str(len(appointments)), "✓ 验证成功")

    console.print(
        Panel(validation_table, title="[bold green]✓ 配置验证结果[/bold green]")
    )
    logger.info(f"配置验证成功 - 1 个学生, {len(appointments)} 个预约")


def test_logins(data):
    """测试学生的登录配置"""
    console.print("[bold blue]🔍 正在验证学生的登录配置...[/bold blue]")

    login_results = []
    student_id = data["username"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"验证学生 {student_id}...", total=None)

        # 创建临时配置用于测试
        test_config = {
            "username": data["username"],
            "password": data["password"],
            "phone": data["phone"],
            "yyrq": "20240101",  # 临时日期
            "yyxm": "东南门",
            "yysj": "10:00",
            "yysy": "测试",
            "mode": "燕园",
            "auto": data["auto"],
            "appointments": [],
            "totp_mode": data.get("totp_mode", "shortcut"),
            "totp_secret": data.get("totp_secret", None),
        }

        bark_token = data.get("bark", None)
        notifier = BarkNotifier(bark_token)
        s = Session(config=test_config, notifier=notifier)

        try:
            if not s.login():
                login_results.append(
                    (student_id, False, "登录失败，请检查用户名和密码")
                )
                logger.error(f"学生 {student_id} 登录失败")
            else:
                login_results.append((student_id, True, "登录验证成功"))
                logger.success(f"学生 {student_id} 登录成功")
        except Exception as e:
            login_results.append((student_id, False, f"错误: {str(e)}"))
            logger.error(f"学生 {student_id} 遇到错误: {e}")

        progress.remove_task(task)

    # 显示登录测试结果
    login_table = Table()
    login_table.add_column("学生ID", style="cyan")
    login_table.add_column("状态", style="bold")
    login_table.add_column("说明")

    all_success = True
    for student_id, success, message in login_results:
        status = "[green]✓ 成功[/green]" if success else "[red]✗ 失败[/red]"
        login_table.add_row(str(student_id), status, message)
        if not success:
            all_success = False

    title_color = "green" if all_success else "red"
    title_icon = "✓" if all_success else "✗"
    console.print(
        Panel(
            login_table,
            title=f"[bold {title_color}]{title_icon} 登录测试结果[/bold {title_color}]",
        )
    )

    return all_success


if __name__ == "__main__":
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description="北京大学自动预约系统")
    parser.add_argument(
        "-f",
        "--config",
        type=str,
        default="config.yaml",
        help="指定配置文件路径 (默认: config.yaml)",
    )
    args = parser.parse_args()

    # 加载配置
    data = load_config(args.config)

    # 显示启动标题
    console.print(
        Panel(
            Text("🎓 北京大学自动预约系统", style="bold blue", justify="center"),
            subtitle=f"[italic]v2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Config: {args.config}[/italic]",
        )
    )

    try:
        # 验证配置文件
        validate_config(data)

        # 测试学生的登录
        if not test_logins(data):
            console.print("[bold red]✗ 登录测试失败，请检查配置后重试[/bold red]")
            logger.error("登录测试失败")
            exit(1)

        appointments = data["appointments"]
        student_config = {
            "username": data["username"],
            "password": data["password"],
            "phone": data["phone"],
            "bark": data.get("bark", None),
            "auto": data["auto"],
            "totp_mode": data.get("totp_mode", "shortcut"),
            "totp_secret": data.get("totp_secret", None),
        }

        # 显示预约总览
        overview_table = Table()
        overview_table.add_column("项目", style="cyan")
        overview_table.add_column("数值", style="white")
        overview_table.add_row("学生数量", "1")
        overview_table.add_row("预约任务", str(len(appointments)))
        overview_table.add_row("自动模式", "✓ 开启" if data["auto"] else "✗ 关闭")

        console.print(
            Panel(overview_table, title="[bold magenta]📈 系统概览[/bold magenta]")
        )

        # 为每个预约安排调度 - 按配置顺序串行处理
        immediate_tasks = 0
        scheduled_tasks = 0

        with console.status("[bold blue]正在安排预约任务..."):
            for appointment in appointments:
                target_day = datetime.strptime(str(appointment["yyrq"]), "%Y%m%d")
                now = datetime.now()
                open_time = (target_day - timedelta(days=3)).replace(
                    hour=8, minute=0, second=1, microsecond=0
                )
                time_diff = (open_time - now).total_seconds()

                if time_diff <= 0:
                    immediate_tasks += 1
                else:
                    scheduled_tasks += 1

                schedule_appointment(appointment, student_config)

        # 如果所有任务都是立即执行的，程序应该立即退出
        if immediate_tasks > 0 and scheduled_tasks == 0:
            console.print(
                Panel(
                    "[green]✓ 所有预约任务已立即执行完成，程序即将退出[/green]",
                    title="[bold green]🎉 任务完成[/bold green]",
                )
            )
            logger.info("所有预约任务均为立即执行且已完成，程序正常退出")
            exit(0)

        console.print(
            Panel(
                f"[green]✓ 调度器启动成功，正在监控 {scheduled_tasks} 个预约任务...[/green]\n"
                + "[yellow]⚠️ 请保持程序运行，按 Ctrl+C 停止[/yellow]",
                title="[bold green]🚀 系统运行中[/bold green]",
            )
        )

        logger.info(
            f"系统启动成功 - 立即执行: {immediate_tasks}, 调度任务: {scheduled_tasks}"
        )

        # 主循环
        while True:
            schedule.run_pending()

            # 检查是否还有待执行的任务
            if len(schedule.jobs) == 0:
                console.print(
                    Panel(
                        "[green]✓ 所有预约任务已完成，程序即将退出[/green]",
                        title="[bold green]🎉 任务完成[/bold green]",
                    )
                )
                logger.info("所有预约任务已完成，程序正常退出")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]👋 程序已由用户中断[/bold yellow]")
        logger.info("程序被用户中断")
    except Exception as e:
        console.print(f"[bold red]✗ 系统错误: {str(e)}[/bold red]")
        logger.error(f"系统错误: {e}")
        exit(1)
