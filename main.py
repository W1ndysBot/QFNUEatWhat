# script/QFNUEatWhat/main.py

import logging
import os
import sys
import re
import json
import random

# 添加项目根目录到sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import *
from app.api import *
from app.switch import load_switch, save_switch


# 数据存储路径，实际开发时，请将QFNUEatWhat替换为具体的数据存放路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "QFNUEatWhat",
)

# 在 DATA_DIR 定义后添加
MENU_FILE = os.path.join(DATA_DIR, "menu.json")


# 添加菜单数据操作函数
def load_menu():
    """加载菜单数据"""
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_menu(menu_data):
    """保存菜单数据"""
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=2)


def get_random_item(menu_data, restaurant=None, item_type="菜品"):
    """随机获取菜品或饮品，支持模糊匹配餐厅名"""
    if restaurant:
        # 精确匹配
        if restaurant in menu_data:
            items = menu_data[restaurant].get(item_type, [])
            if items:
                return restaurant, random.choice(items)

        # 模糊匹配
        matched_restaurants = []
        for rest_name in menu_data.keys():
            # 如果输入是餐厅名的子串，或餐厅名是输入的子串
            if restaurant in rest_name or rest_name in restaurant:
                items = menu_data[rest_name].get(item_type, [])
                if items:
                    matched_restaurants.append(rest_name)

        if matched_restaurants:
            # 随机选择一个匹配的餐厅
            chosen_rest = random.choice(matched_restaurants)
            items = menu_data[chosen_rest].get(item_type, [])
            return chosen_rest, random.choice(items)

    # 从所有餐厅中随机选择
    all_items = []
    for rest_name, rest_data in menu_data.items():
        items = rest_data.get(item_type, [])
        for item in items:
            all_items.append((rest_name, item))

    return random.choice(all_items) if all_items else (None, None)


# 查看功能开关状态
def load_function_status(group_id):
    return load_switch(group_id, "QFNUEatWhat")


# 保存功能开关状态
def save_function_status(group_id, status):
    save_switch(group_id, "QFNUEatWhat", status)


# 处理元事件，用于启动时确保数据目录存在
async def handle_meta_event(websocket, msg):
    """处理元事件"""
    os.makedirs(DATA_DIR, exist_ok=True)


# 处理开关状态
async def toggle_function_status(websocket, group_id, message_id, authorized):
    if not authorized:
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]❌❌❌你没有权限对QFNUEatWhat功能进行操作,请联系管理员。",
        )
        return

    if load_function_status(group_id):
        save_function_status(group_id, False)
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]🚫🚫🚫QFNUEatWhat功能已关闭",
        )
    else:
        save_function_status(group_id, True)
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]✅✅✅QFNUEatWhat功能已开启",
        )


# 群消息处理函数
async def handle_group_message(websocket, msg):
    """处理群消息"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        message_id = str(msg.get("message_id"))
        role = str(msg.get("role"))
        authorized = is_authorized(role, user_id)

        # 处理开关命令
        if raw_message == "qfnuew":
            await toggle_function_status(websocket, group_id, message_id, authorized)
            return

        # 检查功能是否开启
        if not load_function_status(group_id):
            return

        # 处理添加菜品/饮品的命令
        add_match = re.match(r"^添加(菜品|饮品)\s+([^\s]+)\s+(.+)$", raw_message)
        if add_match:
            item_type = "菜品" if add_match.group(1) == "菜品" else "饮品"
            restaurant = add_match.group(2)
            item_name = add_match.group(3)

            menu_data = load_menu()
            if restaurant not in menu_data:
                menu_data[restaurant] = {"菜品": [], "饮品": []}

            if item_name not in menu_data[restaurant][item_type]:
                menu_data[restaurant][item_type].append(item_name)
                save_menu(menu_data)
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]✅已添加{item_type}：{restaurant} {item_name}",
                )
            else:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]⚠️该{item_type}已存在",
                )
            return

        # 处理查询吃什么/喝什么
        eat_match = re.match(r"(.*)(吃什么|喝什么)$", raw_message)
        if eat_match:
            restaurant = eat_match.group(1).strip()
            item_type = "菜品" if eat_match.group(2) == "吃什么" else "饮品"

            menu_data = load_menu()
            if not menu_data:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]还没有添加任何菜品或饮品呢",
                )
                return

            rest_name, item = get_random_item(menu_data, restaurant, item_type)
            if rest_name and item:
                help_text = (
                    f"\n\n💡 添加{item_type}命令：添加{item_type} 店名 {item_type}名"
                    f"\n例如：添加{item_type} {rest_name} 新{item_type}"
                    f"\n\n💡 删除{item_type}命令：删除{item_type} 店名 {item_type}名"
                    f"\n例如：删除{item_type} {rest_name} {item}"
                )
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]{rest_name} {item}{help_text}",
                )
            else:
                help_text = (
                    f"\n\n💡 添加{item_type}命令：添加{item_type} 店名 {item_type}名"
                    f"\n💡 删除{item_type}命令：删除{item_type} 店名 {item_type}名"
                )
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]还没有添加任何{item_type}呢{help_text}",
                )
            return

        # 处理删除菜品/饮品的命令
        del_match = re.match(r"^删除(菜品|饮品)\s+([^\s]+)\s+(.+)$", raw_message)
        if del_match:
            if not authorized:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]❌你没有权限删除菜品/饮品",
                )
                return

            item_type = "菜品" if del_match.group(1) == "菜品" else "饮品"
            restaurant = del_match.group(2)
            item_name = del_match.group(3)

            menu_data = load_menu()
            if restaurant not in menu_data:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]⚠️未找到该店铺：{restaurant}",
                )
                return

            if item_name in menu_data[restaurant][item_type]:
                menu_data[restaurant][item_type].remove(item_name)
                # 如果餐厅的菜品和饮品都为空，删除该餐厅
                if (
                    not menu_data[restaurant]["菜品"]
                    and not menu_data[restaurant]["饮品"]
                ):
                    del menu_data[restaurant]
                save_menu(menu_data)
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]✅已删除{item_type}：{restaurant} {item_name}",
                )
            else:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]⚠️未找到该{item_type}：{restaurant} {item_name}",
                )
            return

    except Exception as e:
        logging.error(f"处理QFNUEatWhat群消息失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]处理QFNUEatWhat群消息失败，错误信息：{str(e)}",
        )
        return


# 私聊消息处理函数
async def handle_private_message(websocket, msg):
    """处理私聊消息"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        raw_message = str(msg.get("raw_message"))
        # 私聊消息处理逻辑
        pass
    except Exception as e:
        logging.error(f"处理QFNUEatWhat私聊消息失败: {e}")
        await send_private_msg(
            websocket,
            msg.get("user_id"),
            "处理QFNUEatWhat私聊消息失败，错误信息：" + str(e),
        )
        return


# 群通知处理函数
async def handle_group_notice(websocket, msg):
    """处理群通知"""
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        notice_type = str(msg.get("notice_type"))
        operator_id = str(msg.get("operator_id", ""))

    except Exception as e:
        logging.error(f"处理QFNUEatWhat群通知失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理QFNUEatWhat群通知失败，错误信息：" + str(e),
        )
        return


# 回应事件处理函数
async def handle_response(websocket, msg):
    """处理回调事件"""
    try:
        echo = msg.get("echo")
        if echo and echo.startswith("xxx"):
            # 回调处理逻辑
            pass
        return True
    except Exception as e:
        logging.error(f"处理QFNUEatWhat回调事件失败: {e}")
        await send_group_msg(
            websocket,
            msg.get("group_id"),
            f"处理QFNUEatWhat回调事件失败，错误信息：{str(e)}",
        )
        return False


# 统一事件处理入口
async def handle_events(websocket, msg):
    """统一事件处理入口"""
    post_type = msg.get("post_type", "response")  # 添加默认值
    try:
        # 处理回调事件
        if msg.get("status") == "ok":
            await handle_response(websocket, msg)
            return

        post_type = msg.get("post_type")

        # 处理元事件
        if post_type == "meta_event":
            await handle_meta_event(websocket, msg)

        # 处理消息事件
        elif post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await handle_group_message(websocket, msg)
            elif message_type == "private":
                await handle_private_message(websocket, msg)

        # 处理通知事件
        elif post_type == "notice":
            await handle_group_notice(websocket, msg)

    except Exception as e:
        error_type = {
            "message": "消息",
            "notice": "通知",
            "request": "请求",
            "meta_event": "元事件",
        }.get(post_type, "未知")

        logging.error(f"处理QFNUEatWhat{error_type}事件失败: {e}")

        # 发送错误提示
        if post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await send_group_msg(
                    websocket,
                    msg.get("group_id"),
                    f"处理QFNUEatWhat{error_type}事件失败，错误信息：{str(e)}",
                )
            elif message_type == "private":
                await send_private_msg(
                    websocket,
                    msg.get("user_id"),
                    f"处理QFNUEatWhat{error_type}事件失败，错误信息：{str(e)}",
                )
