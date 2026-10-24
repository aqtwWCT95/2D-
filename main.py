"""
2dmc.py / beifen.py — 2D 生存沙盒客户端（支持服务器列表）
依赖：common.py
"""
import pygame, math, random, os, sys, json, socket, threading, queue, time
from common import (
    TILE, WORLD_W, WORLD_H, GRAVITY, PLAYER_SPEED, JUMP_VEL, DAY_LENGTH,
    SMELTING_TIME, SCRIPT_DIR, BLOCK_DATA, ITEM_DATA, SMELTING, FUEL,
    ARMOR_SLOTS, match_recipe, is_solid_tile, resolve_entity_x, resolve_entity_y,
    World, Player, Monster, Animal, Drop, BLOCK_TEX, ITEM_ICONS, build_assets,
    max_stack,
)

pygame.init()

SCREEN_W, SCREEN_H = 1024, 640
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("2D 生存沙盒")
clock = pygame.time.Clock()
try:
    # 使用 SCRIPT_DIR 确保无论在哪里运行，都能找到同目录下的 ico.png
    icon_path = os.path.join(SCRIPT_DIR, "ico.png")
    if os.path.exists(icon_path):
        icon_surf = pygame.image.load(icon_path)
        pygame.display.set_icon(icon_surf)
    else:
        print(f"[警告] 找不到图标文件: {icon_path}，请确保图片命名为 ico.png 且放在代码同级目录！")
except Exception as e:
    print(f"[警告] 图标加载失败: {e}")




FONT_SM = pygame.font.SysFont("microsoftyahei,simhei,arial", 14)
FONT_MD = pygame.font.SysFont("microsoftyahei,simhei,arial", 16, bold=True)
FONT_LG = pygame.font.SysFont("microsoftyahei,simhei,arial", 22, bold=True)
FONT_XL = pygame.font.SysFont("microsoftyahei,simhei,arial", 32, bold=True)


def icon(iid):
    return ITEM_ICONS.get(iid)


def draw_btn(rect, text, base=(70, 110, 160), font=None):
    if font is None:
        font = FONT_MD
    mx, my = pygame.mouse.get_pos()
    c = tuple(min(255, v + 30) for v in base) if rect.collidepoint(mx, my) else base
    pygame.draw.rect(screen, c, rect)
    pygame.draw.rect(screen, (200, 200, 210), rect, 1)
    t = font.render(text, True, (255, 255, 255))
    screen.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))


def draw_slot_box(rect):
    pygame.draw.rect(screen, (40, 40, 46), rect)
    pygame.draw.rect(screen, (110, 110, 120), rect, 1)


def draw_slot_item(rect, item, scale=36):
    if not item:
        return
    ic = icon(item["id"])
    if ic:
        s = pygame.transform.scale(ic, (scale, scale))
        screen.blit(s, (rect.x + (rect.w - scale) // 2, rect.y + (rect.h - scale) // 2))
    if item["count"] > 1:
        t = FONT_SM.render(str(item["count"]), True, (255, 255, 255))
        screen.blit(t, (rect.right - t.get_width() - 3, rect.bottom - t.get_height() - 1))


# ============================================================
# 本地存档管理
# ============================================================
class SaveServer:
    def __init__(self):
        self.dir = os.path.join(SCRIPT_DIR, "saves")
        os.makedirs(self.dir, exist_ok=True)

    def list_saves(self):
        r = []
        for fn in sorted(os.listdir(self.dir)):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(self.dir, fn)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                r.append({
                    "file": fn,
                    "name": d.get("name", fn),
                    "mtime": os.path.getmtime(p),
                    "gamemode": d.get("gamemode", "survival"),
                })
            except Exception:
                continue
        r.sort(key=lambda s: s["mtime"], reverse=True)
        return r

    def create_save(self):
        i = 1
        while os.path.exists(os.path.join(self.dir, f"save_{i}.json")):
            i += 1
        fn = f"save_{i}.json"
        sx = WORLD_W // 2
        data = {
            "version": 1,
            "name": f"新世界 {i}",
            "seed": random.randint(1, 10 ** 9),
            "day_time": 0.25,
            "gamemode": "survival",
            "world_size": [WORLD_W, WORLD_H],
            "changes": {},
            "furnaces": {},
            "player": {
                "x": sx * TILE + 5, "y": 0,
                "health": 100, "hunger": 100,
                "hotbar": [None] * 9, "backpack": [None] * 27,
                "armor": {"head": None, "chest": None, "legs": None, "feet": None},
                "selected": 0,
            },
        }
        self.save(fn, data)
        return fn

    def load(self, fn):
        try:
            with open(os.path.join(self.dir, fn), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save(self, fn, data):
        with open(os.path.join(self.dir, fn), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    def delete(self, fn):
        try:
            os.remove(os.path.join(self.dir, fn))
            return True
        except Exception:
            return False


# ============================================================
# 服务器列表管理
# ============================================================
class ServerBook:
    def __init__(self):
        # 直接保存在脚本同目录的 playerinfo.json，不碰 serversaves
        self.path = os.path.join(SCRIPT_DIR, "playerinfo.json")

    def list(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save(self, servers):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(servers, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, name, host, port, motd=None):
        servers = self.list()
        for s in servers:
            if s["host"] == host and s["port"] == port:
                s["name"] = name
                if motd is not None:
                    s["motd"] = motd
                s["last"] = time.time()
                self.save(servers)
                return
        servers.append({"name": name, "host": host, "port": port, "last": time.time(), "motd": motd or ""})
        self.save(servers)

    def delete(self, idx):
        servers = self.list()
        if 0 <= idx < len(servers):
            servers.pop(idx)
            self.save(servers)


# ============================================================
# 网络客户端
# ============================================================
class NetClient:
    def __init__(self, host, port, name):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(8.0)
        try:
            self.sock.connect((host, port))
        except socket.timeout:
            raise ConnectionError("连接服务器超时，请检查IP和端口")
        except Exception as e:
            raise ConnectionError(f"无法连接: {e}")

        self.sock.sendall((json.dumps({"t": "join", "name": name}, ensure_ascii=False) + "\n").encode("utf-8"))
        self.buf = b""
        self.welcome = None

        handshake_start = time.time()
        while self.welcome is None:
            if time.time() - handshake_start > 8.0:
                raise ConnectionError("握手超时：未收到服务器欢迎包")
            try:
                d = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not d:
                raise ConnectionError("服务器主动断开连接")
            self.buf += d
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    m = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if m.get("t") == "welcome":
                    self.welcome = m
                    break

        self.my_id = self.welcome["my_id"]
        self.sock.settimeout(0.1)
        self.msg_queue = queue.Queue()
        self.send_lock = threading.Lock()
        self.alive = True
        threading.Thread(target=self.recv_loop, daemon=True).start()

    def recv_loop(self):
        while self.alive:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.buf += data
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    if line.strip():
                        try:
                            self.msg_queue.put(json.loads(line.decode("utf-8")))
                        except Exception:
                            pass
            except socket.timeout:
                continue
            except Exception:
                break
        self.alive = False

    def send(self, obj):
        if not self.alive:
            return
        try:
            with self.send_lock:
                self.sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception:
            self.alive = False

    def send_mine(self, x, y):
        self.send({"t": "mine", "x": x, "y": y})

    def send_place(self, x, y, b):
        self.send({"t": "place", "x": x, "y": y, "b": b})

    def send_attack(self, x, y):
        self.send({"t": "attack", "x": x, "y": y})

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except Exception:
            pass


# ============================================================
# 通用槽位
# ============================================================
class Slot:
    def __init__(self, rect, container, index):
        self.rect = rect
        self.container = container
        self.index = index

    def get(self):
        if self.index is None:
            return None
        return self.container[self.index]

    def set(self, v):
        if self.index is None:
            return
        self.container[self.index] = v


# ============================================================
# 背包 / 工作台
# ============================================================
class InventoryUI:
    def __init__(self, game):
        self.game = game
        self.open = False
        self.crafting_open = False
        self.held = None
        self.craft_grid = [None] * 9
        self.craft_result = None
        self.slots = []
        self.armor_slots = []
        self.result_slot = None
        self.panel = pygame.Rect(0, 0, 0, 0)
        self.arrow = pygame.Rect(0, 0, 0, 0)
        self.mode = 2

    def open_inventory(self):
        self.open = True
        self.crafting_open = False
        self.mode = 2
        self.layout()

    def open_crafting(self):
        self.open = True
        self.crafting_open = True
        self.mode = 3
        self.layout()

    def close(self):
        p = self.game.player
        for i in range(len(self.craft_grid)):
            if self.craft_grid[i]:
                p.give_item(self.craft_grid[i])
                self.craft_grid[i] = None
        if self.held:
            p.give_item(self.held)
            self.held = None
        self.craft_result = None
        self.open = False

    def layout(self):
        s = self.mode
        sl = 40
        g = 4
        pad = 22
        cw = s * sl + (s - 1) * g
        ch = s * sl + (s - 1) * g
        iw = 9 * sl + 8 * g
        pw = iw + pad * 2
        top = 40
        armor_h = 4 * sl + 3 * g
        craft_a = max(armor_h, ch) + 20
        inv_a = 3 * sl + 2 * g + 12
        hb = sl + 12
        ph = pad + top + craft_a + inv_a + hb + pad
        px = (SCREEN_W - pw) // 2
        py = (SCREEN_H - ph) // 2
        self.panel = pygame.Rect(px, py, pw, ph)
        self.slots = []
        self.armor_slots = []
        cy0 = py + pad + top
        for i, sn in enumerate(ARMOR_SLOTS):
            r = pygame.Rect(px + pad, cy0 + i * (sl + g), sl, sl)
            self.armor_slots.append((sn, Slot(r, self.game.player.armor, sn), r))
        cx0 = px + pad + 40 + 30
        for yy in range(s):
            for xx in range(s):
                r = pygame.Rect(cx0 + xx * (sl + g), cy0 + yy * (sl + g), sl, sl)
                self.slots.append(Slot(r, self.craft_grid, yy * s + xx))
        acx = cx0 + cw + 24
        acy = cy0 + ch // 2
        self.arrow = pygame.Rect(acx, acy - 10, 26, 20)
        rr = pygame.Rect(acx + 36, acy - sl // 2, sl, sl)
        self.result_slot = Slot(rr, self, -1)
        iy = cy0 + max(armor_h, ch) + 20
        for row in range(3):
            for col in range(9):
                r = pygame.Rect(px + pad + col * (sl + g), iy + row * (sl + g), sl, sl)
                self.slots.append(Slot(r, self.game.player.backpack, row * 9 + col))
        hby = iy + 3 * (sl + g) + 8
        for col in range(9):
            r = pygame.Rect(px + pad + col * (sl + g), hby, sl, sl)
            self.slots.append(Slot(r, self.game.player.hotbar, col))

    def update_result(self):
        s = self.mode
        grid = [[None] * s for _ in range(s)]
        for y in range(s):
            for x in range(s):
                it = self.craft_grid[y * s + x]
                grid[y][x] = it["id"] if it else None
        r = match_recipe(grid, s)
        self.craft_result = {"id": r["result"][0], "count": r["result"][1]} if r else None

    def take_result(self):
        if not self.craft_result:
            return
        res = self.craft_result
        if self.held:
            if self.held["id"] != res["id"]:
                return
            if self.held["count"] + res["count"] > max_stack(res["id"]):
                return
            self.held["count"] += res["count"]
        else:
            self.held = {"id": res["id"], "count": res["count"]}
        for i in range(self.mode * self.mode):
            s = self.craft_grid[i]
            if s:
                if s["count"] <= 1:
                    self.craft_grid[i] = None
                else:
                    self.craft_grid[i] = {"id": s["id"], "count": s["count"] - 1}
        self.update_result()

    def _click(self, slot, btn):
        it = slot.get()
        if btn == 1:
            if self.held is None:
                if it:
                    self.held = it
                    slot.set(None)
            else:
                if it is None:
                    slot.set(self.held)
                    self.held = None
                elif it["id"] == self.held["id"]:
                    ms = max_stack(it["id"])
                    total = it["count"] + self.held["count"]
                    if total <= ms:
                        it["count"] = total
                        self.held = None
                    else:
                        it["count"] = ms
                        self.held = {"id": self.held["id"], "count": total - ms}
                else:
                    slot.set(self.held)
                    self.held = it
        elif btn == 3:
            if self.held is None:
                if it:
                    h = (it["count"] + 1) // 2
                    self.held = {"id": it["id"], "count": h}
                    if it["count"] - h <= 0:
                        slot.set(None)
                    else:
                        it["count"] = it["count"] - h
            else:
                if it is None:
                    slot.set({"id": self.held["id"], "count": 1})
                    self.held["count"] -= 1
                    if self.held["count"] <= 0:
                        self.held = None
                elif it["id"] == self.held["id"] and it["count"] < max_stack(it["id"]):
                    it["count"] += 1
                    self.held["count"] -= 1
                    if self.held["count"] <= 0:
                        self.held = None
        self.update_result()

    def handle_event(self, ev):
        if not self.open:
            return False
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_e):
            self.close()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            mx, my = ev.pos
            if self.result_slot.rect.collidepoint(mx, my):
                self.take_result()
                return True
            for _, s, r in self.armor_slots:
                if r.collidepoint(mx, my):
                    self._click(s, ev.button)
                    return True
            for s in self.slots:
                if s.rect.collidepoint(mx, my):
                    self._click(s, ev.button)
                    return True
            return True
        return False

    def draw(self):
        if not self.open:
            return
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 130))
        screen.blit(ov, (0, 0))
        pygame.draw.rect(screen, (62, 62, 68), self.panel)
        pygame.draw.rect(screen, (140, 140, 150), self.panel, 2)
        t = FONT_MD.render("工作台（3x3）" if self.crafting_open else "背包（2x2 合成）", True, (235, 235, 235))
        screen.blit(t, (self.panel.x + 16, self.panel.y + 8))
        for _, s, r in self.armor_slots:
            draw_slot_box(r)
            draw_slot_item(r, s.get(), 32)
        ar = self.arrow
        pygame.draw.polygon(screen, (210, 210, 210), [
            (ar.x, ar.y + 4), (ar.x + 16, ar.y + 4), (ar.x + 16, ar.y - 2),
            (ar.x + 26, ar.y + 10), (ar.x + 16, ar.y + 22),
            (ar.x + 16, ar.y + 16), (ar.x, ar.y + 16)])
        for s in self.slots:
            draw_slot_box(s.rect)
            draw_slot_item(s.rect, s.get(), 32)
        draw_slot_box(self.result_slot.rect)
        draw_slot_item(self.result_slot.rect, self.craft_result, 32)
        mx, my = pygame.mouse.get_pos()
        hover = None
        for _, s, r in self.armor_slots:
            if r.collidepoint(mx, my):
                hover = s.get()
                break
        if not hover:
            for s in self.slots:
                if s.rect.collidepoint(mx, my):
                    hover = s.get()
                    break
        if not hover and self.result_slot.rect.collidepoint(mx, my):
            hover = self.craft_result
        if hover:
            name = ITEM_DATA[hover["id"]]["name"]
            tt = FONT_SM.render(name, True, (255, 255, 230))
            tip = pygame.Rect(mx + 14, my + 10, tt.get_width() + 10, tt.get_height() + 6)
            pygame.draw.rect(screen, (20, 20, 25), tip)
            pygame.draw.rect(screen, (150, 150, 160), tip, 1)
            screen.blit(tt, (tip.x + 5, tip.y + 3))
        if self.held:
            ic = icon(self.held["id"])
            if ic:
                screen.blit(pygame.transform.scale(ic, (36, 36)), (mx - 18, my - 18))
            if self.held["count"] > 1:
                tt = FONT_SM.render(str(self.held["count"]), True, (255, 255, 255))
                screen.blit(tt, (mx + 8, my + 6))


# ============================================================
# 熔炉
# ============================================================
class FurnaceUI:
    def __init__(self, game):
        self.game = game
        self.open = False
        self.furnace_pos = None
        self.held = None
        self.hotbar = []
        self.panel = pygame.Rect(0, 0, 0, 0)
        self.input_rect = pygame.Rect(0, 0, 0, 0)
        self.fuel_rect = pygame.Rect(0, 0, 0, 0)
        self.output_rect = pygame.Rect(0, 0, 0, 0)

    def furnace(self):
        if self.furnace_pos is None:
            return None
        return self.game.furnaces.get(self.furnace_pos)

    def open_furnace(self, pos):
        self.open = True
        self.furnace_pos = pos
        if pos not in self.game.furnaces:
            self.game.furnaces[pos] = {
                "input": None, "fuel": None, "output": None,
                "progress": 0.0, "burn": 0.0,
            }
        self.layout()

    def close(self):
        f = self.furnace()
        p = self.game.player
        if f:
            for k in ("input", "fuel", "output"):
                if f[k]:
                    p.give_item(f[k])
                    f[k] = None
        if self.held:
            p.give_item(self.held)
            self.held = None
        self.open = False
        self.furnace_pos = None

    def layout(self):
        sl = 44
        pw = 380
        ph = 360
        px = (SCREEN_W - pw) // 2
        py = (SCREEN_H - ph) // 2
        self.panel = pygame.Rect(px, py, pw, ph)
        cx = px + 80
        self.input_rect = pygame.Rect(cx, py + 60, sl, sl)
        self.fuel_rect = pygame.Rect(cx, py + 160, sl, sl)
        self.output_rect = pygame.Rect(px + pw - 100, py + 110, sl, sl)
        self.hotbar = []
        hy = py + ph - sl - 20
        tot = 9 * sl + 8 * 3
        hx = px + (pw - tot) // 2
        for i in range(9):
            r = pygame.Rect(hx + i * (sl + 3), hy, sl, sl)
            self.hotbar.append(Slot(r, self.game.player.hotbar, i))

    def _slot_at(self, mx, my):
        f = self.furnace()
        if f:
            if self.input_rect.collidepoint(mx, my):
                return Slot(self.input_rect, f, "input")
            if self.fuel_rect.collidepoint(mx, my):
                return Slot(self.fuel_rect, f, "fuel")
            if self.output_rect.collidepoint(mx, my):
                return Slot(self.output_rect, f, "output")
        for s in self.hotbar:
            if s.rect.collidepoint(mx, my):
                return s
        return None

    def _click(self, slot, btn):
        f = self.furnace()
        if f and slot.container is f and slot.index == "output":
            if btn == 1 and slot.get():
                if self.held is None:
                    self.held = slot.get()
                elif self.held["id"] == slot.get()["id"] and \
                        self.held["count"] + slot.get()["count"] <= max_stack(self.held["id"]):
                    self.held["count"] += slot.get()["count"]
                else:
                    return
                slot.set(None)
            return
        it = slot.get()
        if btn == 1:
            if self.held is None:
                if it:
                    self.held = it
                    slot.set(None)
            else:
                if it is None:
                    slot.set(self.held)
                    self.held = None
                elif it["id"] == self.held["id"]:
                    ms = max_stack(it["id"])
                    total = it["count"] + self.held["count"]
                    if total <= ms:
                        it["count"] = total
                        self.held = None
                    else:
                        it["count"] = ms
                        self.held = {"id": self.held["id"], "count": total - ms}
                else:
                    slot.set(self.held)
                    self.held = it
        elif btn == 3:
            if self.held is None:
                if it:
                    h = (it["count"] + 1) // 2
                    self.held = {"id": it["id"], "count": h}
                    if it["count"] - h <= 0:
                        slot.set(None)
                    else:
                        it["count"] = it["count"] - h
            else:
                if it is None:
                    slot.set({"id": self.held["id"], "count": 1})
                    self.held["count"] -= 1
                    if self.held["count"] <= 0:
                        self.held = None
                elif it["id"] == self.held["id"] and it["count"] < max_stack(it["id"]):
                    it["count"] += 1
                    self.held["count"] -= 1
                    if self.held["count"] <= 0:
                        self.held = None

    def handle_event(self, ev):
        if not self.open:
            return False
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_e):
            self.close()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            s = self._slot_at(*ev.pos)
            if s:
                self._click(s, ev.button)
            return True
        return False

    def draw(self):
        if not self.open:
            return
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 130))
        screen.blit(ov, (0, 0))
        pygame.draw.rect(screen, (62, 62, 68), self.panel)
        pygame.draw.rect(screen, (140, 140, 150), self.panel, 2)
        t = FONT_MD.render("熔炉", True, (235, 235, 235))
        screen.blit(t, (self.panel.x + 16, self.panel.y + 8))
        f = self.furnace()
        if not f:
            return
        for r in (self.input_rect, self.fuel_rect, self.output_rect):
            draw_slot_box(r)
        draw_slot_item(self.input_rect, f["input"], 36)
        draw_slot_item(self.fuel_rect, f["fuel"], 36)
        draw_slot_item(self.output_rect, f["output"], 36)
        fx = self.fuel_rect.centerx
        fy = self.fuel_rect.top - 22
        col = (255, 150, 30) if f["burn"] > 0 else (80, 80, 80)
        pygame.draw.polygon(screen, col, [(fx - 8, fy + 14), (fx, fy), (fx + 8, fy + 14)])
        ax = self.input_rect.right + 20
        ay = self.input_rect.centery
        pygame.draw.rect(screen, (100, 100, 100), (ax, ay - 6, 60, 12))
        prog = min(1.0, f["progress"] / SMELTING_TIME) if f["progress"] > 0 else 0
        pygame.draw.rect(screen, (230, 230, 230), (ax, ay - 6, int(60 * prog), 12))
        for s in self.hotbar:
            draw_slot_box(s.rect)
            draw_slot_item(s.rect, s.get(), 32)
        mx, my = pygame.mouse.get_pos()
        hover = None
        for r, k in [(self.input_rect, "input"), (self.fuel_rect, "fuel"), (self.output_rect, "output")]:
            if r.collidepoint(mx, my):
                hover = f[k]
                break
        if not hover:
            for s in self.hotbar:
                if s.rect.collidepoint(mx, my):
                    hover = s.get()
                    break
        if hover:
            name = ITEM_DATA[hover["id"]]["name"]
            tt = FONT_SM.render(name, True, (255, 255, 230))
            tip = pygame.Rect(mx + 14, my + 10, tt.get_width() + 10, tt.get_height() + 6)
            pygame.draw.rect(screen, (20, 20, 25), tip)
            pygame.draw.rect(screen, (150, 150, 160), tip, 1)
            screen.blit(tt, (tip.x + 5, tip.y + 3))
        if self.held:
            ic = icon(self.held["id"])
            if ic:
                screen.blit(pygame.transform.scale(ic, (36, 36)), (mx - 18, my - 18))
            if self.held["count"] > 1:
                tt = FONT_SM.render(str(self.held["count"]), True, (255, 255, 255))
                screen.blit(tt, (mx + 8, my + 6))


# ============================================================
# 聊天框
# ============================================================
class ChatUI:
    def __init__(self, game):
        self.game = game
        self.active = False
        self.text = ""
        self.messages = []
        self.life = []

    def log(self, msg):
        self.messages.append(msg)
        self.life.append(6.0)
        if len(self.messages) > 6:
            self.messages.pop(0)
            self.life.pop(0)

    def activate(self, prefix=""):
        self.active = True
        self.text = prefix
        pygame.key.start_text_input()

    def submit(self):
        text = self.text.strip()
        if text:
            self.log("> " + text)
            if self.game.net:
                self.game.net.send({"t": "chat", "m": text})
            elif text.startswith("/"):
                self.game.execute_command(text)
        self.text = ""
        self.active = False
        pygame.key.stop_text_input()

    def handle_event(self, ev):
        if not self.active:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_RETURN:
                self.submit()
                return True
            if ev.key == pygame.K_ESCAPE:
                self.text = ""
                self.active = False
                pygame.key.stop_text_input()
                return True
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
        elif ev.type == pygame.TEXTINPUT:
            self.text += ev.text
            return True
        return True

    def update(self, dt):
        for i in range(len(self.life) - 1, -1, -1):
            self.life[i] -= dt
            if self.life[i] <= 0:
                self.life.pop(i)
                self.messages.pop(i)

    def draw(self):
        y = SCREEN_H - 120
        for i, msg in enumerate(self.messages):
            a = min(1.0, max(0.0, self.life[i]))
            if a <= 0:
                continue
            s = FONT_SM.render(msg, True, (255, 255, 255))
            bg = pygame.Surface((s.get_width() + 8, s.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, int(120 * a)))
            screen.blit(bg, (20, y))
            s.set_alpha(int(255 * a))
            screen.blit(s, (24, y + 2))
            y += s.get_height() + 6
        if self.active:
            bg = pygame.Surface((SCREEN_W - 40, 30))
            bg.fill((0, 0, 0))
            screen.blit(bg, (20, SCREEN_H - 40))
            s = FONT_MD.render("> " + self.text + "_", True, (255, 255, 255))
            screen.blit(s, (24, SCREEN_H - 36))


# ============================================================
# 主菜单
# ============================================================
class MainMenuUI:
    def __init__(self):
        self.result = None
        self.running = True

    def run(self):
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    self.result = None
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = None
                    elif ev.key == pygame.K_1:
                        self.result = "single"
                        self.running = False
                    elif ev.key == pygame.K_2:
                        self.result = "multi_list"
                        self.running = False
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if pygame.Rect(412, 260, 200, 50).collidepoint(mx, my):
                        self.result = "single"
                        self.running = False
                    elif pygame.Rect(412, 330, 200, 50).collidepoint(mx, my):
                        self.result = "multi_list"
                        self.running = False
                    elif pygame.Rect(412, 400, 200, 50).collidepoint(mx, my):
                        self.running = False
                        self.result = None
            self.draw()
            pygame.display.flip()
            clock.tick(60)
        return self.result

    def draw(self):
        screen.fill((22, 28, 42))
        for i in range(20):
            pygame.draw.circle(screen, (30, 40, 60), (i * 60, 60 + i * 15), 20 + i * 3)
        t = FONT_XL.render("2D 生存沙盒", True, (240, 240, 240))
        screen.blit(t, ((SCREEN_W - t.get_width()) // 2, 120))
        sub = FONT_MD.render("Pygame · 生存 · 建造 · 探索", True, (170, 180, 200))
        screen.blit(sub, ((SCREEN_W - sub.get_width()) // 2, 170))
        draw_btn(pygame.Rect(412, 260, 200, 50), "单人游戏", (70, 150, 90), FONT_LG)
        draw_btn(pygame.Rect(412, 330, 200, 50), "多人游戏", (70, 110, 180), FONT_LG)
        draw_btn(pygame.Rect(412, 400, 200, 50), "退出", (120, 80, 80), FONT_LG)
        hint = FONT_SM.render("按 1 单人 · 按 2 多人 · ESC 退出", True, (140, 150, 170))
        screen.blit(hint, ((SCREEN_W - hint.get_width()) // 2, 480))


# ============================================================
# 存档选择
# ============================================================
class SaveSelectorUI:
    def __init__(self, srv):
        self.srv = srv
        self.entries = []
        self.selected = -1
        self.result = None
        self.running = True
        self.msg = ""
        self.refresh()

    def refresh(self):
        self.entries = self.srv.list_saves()
        if self.selected >= len(self.entries):
            self.selected = len(self.entries) - 1
        if self.selected < 0 and self.entries:
            self.selected = 0

    def run(self):
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    self.result = None
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = None
                    elif ev.key == pygame.K_UP:
                        self.selected = max(0, self.selected - 1)
                    elif ev.key == pygame.K_DOWN:
                        self.selected = min(len(self.entries) - 1, self.selected + 1)
                    elif ev.key == pygame.K_RETURN and self.selected >= 0:
                        self.result = self.entries[self.selected]["file"]
                        self.running = False
                    elif ev.key == pygame.K_n:
                        fn = self.srv.create_save()
                        self.refresh()
                        self.msg = "已创建新存档"
                        for i, e in enumerate(self.entries):
                            if e["file"] == fn:
                                self.selected = i
                                break
                    elif ev.key == pygame.K_DELETE and self.selected >= 0:
                        self.srv.delete(self.entries[self.selected]["file"])
                        self.refresh()
                        self.msg = "已删除存档"
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    lr = pygame.Rect(120, 120, 784, 340)
                    if lr.collidepoint(mx, my):
                        idx = (my - lr.y) // 60
                        if 0 <= idx < len(self.entries):
                            self.selected = idx
                    if pygame.Rect(200, 500, 150, 44).collidepoint(mx, my) and self.selected >= 0:
                        self.result = self.entries[self.selected]["file"]
                        self.running = False
                    elif pygame.Rect(380, 500, 150, 44).collidepoint(mx, my):
                        fn = self.srv.create_save()
                        self.refresh()
                        self.msg = "已创建新存档"
                        for i, e in enumerate(self.entries):
                            if e["file"] == fn:
                                self.selected = i
                                break
                    elif pygame.Rect(560, 500, 150, 44).collidepoint(mx, my) and self.selected >= 0:
                        self.srv.delete(self.entries[self.selected]["file"])
                        self.refresh()
                        self.msg = "已删除存档"
                    elif pygame.Rect(740, 500, 150, 44).collidepoint(mx, my):
                        self.running = False
                        self.result = None
            self.draw()
            pygame.display.flip()
            clock.tick(60)
        return self.result

    def draw(self):
        screen.fill((30, 34, 46))
        t = FONT_XL.render("选择存档", True, (240, 240, 240))
        screen.blit(t, ((SCREEN_W - t.get_width()) // 2, 40))
        s = FONT_SM.render(f"存档目录: {self.srv.dir}", True, (160, 170, 190))
        screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 84))
        lr = pygame.Rect(120, 120, 784, 340)
        pygame.draw.rect(screen, (20, 24, 32), lr)
        pygame.draw.rect(screen, (70, 80, 100), lr, 2)
        if not self.entries:
            t = FONT_MD.render("暂无存档，点击「新建存档」", True, (180, 180, 190))
            screen.blit(t, (lr.centerx - t.get_width() // 2, lr.centery - 10))
        else:
            old = screen.get_clip()
            screen.set_clip(lr)
            for i, e in enumerate(self.entries):
                y = lr.y + i * 60
                if y > lr.bottom:
                    break
                rr = pygame.Rect(lr.x, y, lr.w, 60)
                pygame.draw.rect(screen, (60, 90, 140) if i == self.selected else (35, 40, 52), rr)
                pygame.draw.line(screen, (50, 55, 70), (rr.x, rr.bottom - 1), (rr.right, rr.bottom - 1))
                n = FONT_MD.render(e["name"], True, (240, 240, 240))
                screen.blit(n, (rr.x + 16, rr.y + 8))
                gm = "创造" if e["gamemode"] == "creative" else "生存"
                info = f"{gm} · {time.strftime('%Y-%m-%d %H:%M', time.localtime(e['mtime']))}"
                s = FONT_SM.render(info, True, (170, 180, 200))
                screen.blit(s, (rr.x + 16, rr.y + 32))
            screen.set_clip(old)
        draw_btn(pygame.Rect(200, 500, 150, 44), "进入游戏", (70, 150, 90))
        draw_btn(pygame.Rect(380, 500, 150, 44), "新建存档")
        draw_btn(pygame.Rect(560, 500, 150, 44), "删除存档", (160, 80, 80))
        draw_btn(pygame.Rect(740, 500, 150, 44), "返回", (120, 100, 60))
        if self.msg:
            s = FONT_SM.render(self.msg, True, (200, 220, 180))
            screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 566))
        hint = FONT_SM.render("↑↓ 选择 · Enter 进入 · N 新建 · Del 删除 · ESC 返回", True, (140, 150, 170))
        screen.blit(hint, ((SCREEN_W - hint.get_width()) // 2, 600))


# ============================================================
# 服务器列表与连接
# ============================================================
class ServerListUI:
    def __init__(self):
        self.book = ServerBook()
        self.entries = []
        self.selected = -1
        self.result = None
        self.running = True
        self.msg = ""
        self.fetching = True
        self.refresh()
        # 启动后台线程去获取 MOTD
        threading.Thread(target=self.fetch_motds, daemon=True).start()

    def fetch_motds(self):
        servers = self.book.list()
        updated = False
        for s in servers:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.8)
                sock.connect((s["host"], s["port"]))
                sock.sendall(b'{"t":"ping"}\n')
                
                # 循环读取，防止粘包
                buf = b""
                while b"\n" not in buf:
                    chunk = sock.recv(1024)
                    if not chunk:
                        break
                    buf += chunk
                sock.close()
                
                if b"\n" in buf:
                    line = buf.split(b"\n")[0]
                    m = json.loads(line.decode("utf-8"))
                    if m.get("t") == "pong":
                        motd = m.get("motd", "")
                        if motd != s.get("motd"):
                            s["motd"] = motd
                            updated = True
            except Exception:
                pass
                
        if updated:
            self.book.save(servers)
        self.fetching = False
        self.refresh()

    def refresh(self):
        self.entries = self.book.list()
        self.entries.sort(key=lambda x: x.get("last", 0), reverse=True)
        if self.selected >= len(self.entries):
            self.selected = len(self.entries) - 1
        if self.selected < 0 and self.entries:
            self.selected = 0

    def run(self):
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    self.result = None
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = None
                    elif ev.key == pygame.K_UP:
                        self.selected = max(0, self.selected - 1)
                    elif ev.key == pygame.K_DOWN:
                        self.selected = min(len(self.entries) - 1, self.selected + 1)
                    elif ev.key == pygame.K_RETURN and self.selected >= 0:
                        e = self.entries[self.selected]
                        self.result = ("connect", e)
                        self.running = False
                    elif ev.key == pygame.K_r:
                        self.fetching = True
                        threading.Thread(target=self.fetch_motds, daemon=True).start()
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    lr = pygame.Rect(120, 120, 784, 320)
                    
                    # 【核心修改】：点击列表中的服务器条目，直接进入
                    if lr.collidepoint(mx, my):
                        idx = (my - lr.y) // 80
                        if 0 <= idx < len(self.entries):
                            self.selected = idx
                            e = self.entries[self.selected]
                            self.result = ("connect", e)
                            self.running = False
                            continue # 退出事件循环，准备返回连接信号
                            
                    # 判断是否点击了底部的按钮
                    if pygame.Rect(200, 480, 150, 44).collidepoint(mx, my) and self.selected >= 0:
                        e = self.entries[self.selected]
                        self.result = ("connect", e)
                        self.running = False
                    elif pygame.Rect(380, 480, 150, 44).collidepoint(mx, my):
                        self.result = ("add",)
                        self.running = False
                    elif pygame.Rect(560, 480, 150, 44).collidepoint(mx, my) and self.selected >= 0:
                        self.book.delete(self.selected)
                        self.refresh()
                        self.msg = "已删除"
                    elif pygame.Rect(740, 480, 150, 44).collidepoint(mx, my):
                        self.running = False
                        self.result = None
            self.draw()
            pygame.display.flip()
            clock.tick(60)
        return self.result

    def draw(self):
        screen.fill((22, 28, 42))
        t = FONT_XL.render("服务器列表", True, (240, 240, 240))
        screen.blit(t, ((SCREEN_W - t.get_width()) // 2, 40))
        s = FONT_SM.render(f"数据文件: {self.book.path}", True, (160, 170, 190))
        screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 84))
        
        lr = pygame.Rect(120, 120, 784, 320)
        pygame.draw.rect(screen, (20, 24, 32), lr)
        pygame.draw.rect(screen, (70, 80, 100), lr, 2)
        
        if not self.entries:
            t = FONT_MD.render("暂无服务器，点击「添加服务器」", True, (180, 180, 190))
            screen.blit(t, (lr.centerx - t.get_width() // 2, lr.centery - 10))
        else:
            old = screen.get_clip()
            screen.set_clip(lr)
            for i, e in enumerate(self.entries):
                y = lr.y + i * 80
                if y > lr.bottom:
                    break
                rr = pygame.Rect(lr.x, y, lr.w, 80)
                pygame.draw.rect(screen, (60, 90, 140) if i == self.selected else (35, 40, 52), rr)
                pygame.draw.line(screen, (50, 55, 70), (rr.x, rr.bottom - 1), (rr.right, rr.bottom - 1))
                
                # 1. 名字
                n = FONT_MD.render(e.get("name", "未命名"), True, (240, 240, 240))
                screen.blit(n, (rr.x + 16, rr.y + 4))
                
                # 2. IP 端口
                addr = f"{e['host']}:{e['port']}"
                s = FONT_SM.render(addr, True, (170, 180, 200))
                screen.blit(s, (rr.x + 16, rr.y + 28))

                # 3. MOTD
                motd = e.get("motd", "")
                if motd:
                    m = FONT_SM.render(motd, True, (180, 220, 180))
                    screen.blit(m, (rr.x + 16, rr.y + 52))
                else:
                    m = FONT_SM.render("（无 MOTD / 离线）", True, (120, 120, 130))
                    screen.blit(m, (rr.x + 16, rr.y + 52))
            screen.set_clip(old)
            
        if self.fetching:
            s = FONT_SM.render("正在获取服务器 MOTD...", True, (255, 220, 100))
            screen.blit(s, (120, 445))
            
        draw_btn(pygame.Rect(200, 480, 150, 44), "进入游戏", (70, 150, 90))
        draw_btn(pygame.Rect(380, 480, 150, 44), "添加服务器")
        draw_btn(pygame.Rect(560, 480, 150, 44), "删除", (160, 80, 80))
        draw_btn(pygame.Rect(740, 480, 150, 44), "返回", (120, 100, 60))
        
        if self.msg:
            s = FONT_SM.render(self.msg, True, (200, 220, 180))
            screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 546))
        hint = FONT_SM.render("单击条目进入 · ↑↓ 选择 · R 刷新 MOTD · ESC 返回", True, (140, 150, 170))
        screen.blit(hint, ((SCREEN_W - hint.get_width()) // 2, 590))

class ConnectUI:
    def __init__(self, default_srv_name="我的服务器", default_host="127.0.0.1",
                 default_port="25565", default_nick="Player", auto_connect=False):
        self.fields = [
            ("服务器名称", default_srv_name),
            ("IP 地址", default_host),
            ("端口", default_port),
            ("昵称", default_nick)
        ]
        self.values = [f[1] for f in self.fields]
        self.focus = 0
        self.result = None
        self.running = True
        self.msg = ""
        self.connecting = False
        self.connect_result = None
        self.connect_error = None
        self.book = ServerBook()
        self.auto_connect = auto_connect
        pygame.key.start_text_input()
        
        if self.auto_connect:
            self.try_connect()

    def run(self):
        while self.running:
            if self.connecting:
                if self.connect_result is not None:
                    try:
                        srv_name = self.values[0].strip() or "未命名服务器"
                        host = self.values[1].strip()
                        port = int(self.values[2])
                        motd = self.connect_result.welcome.get("motd", "")
                        self.book.add(srv_name, host, port, motd)
                    except Exception:
                        pass
                    self.result = self.connect_result
                    self.running = False
                    break
                elif self.connect_error is not None:
                    self.msg = f"连接失败: {self.connect_error}"
                    self.connecting = False

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    self.result = None
                elif ev.type == pygame.KEYDOWN:
                    if self.connecting:
                        continue
                    if ev.key == pygame.K_ESCAPE:
                        self.running = False
                        self.result = None
                    elif not self.auto_connect:
                        if ev.key == pygame.K_TAB:
                            self.focus = (self.focus + 1) % len(self.fields)
                        elif ev.key == pygame.K_RETURN:
                            self.try_connect()
                        elif ev.key == pygame.K_BACKSPACE:
                            self.values[self.focus] = self.values[self.focus][:-1]
                    else:
                        if ev.key == pygame.K_RETURN and not self.connecting:
                            self.try_connect()
                elif ev.type == pygame.TEXTINPUT:
                    if not self.auto_connect and not self.connecting and len(self.values[self.focus]) < 40:
                        self.values[self.focus] += ev.text
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.connecting:
                        continue
                    mx, my = ev.pos
                    if self.auto_connect:
                        # 自动连接模式下只有重试和取消按钮
                        if pygame.Rect(412, 460, 130, 44).collidepoint(mx, my):
                            self.try_connect()
                        elif pygame.Rect(560, 460, 130, 44).collidepoint(mx, my):
                            self.running = False
                            self.result = None
                    else:
                        for i in range(len(self.fields)):
                            if pygame.Rect(412, 200 + i * 60, 300, 40).collidepoint(mx, my):
                                self.focus = i
                        if pygame.Rect(412, 460, 130, 44).collidepoint(mx, my):
                            self.try_connect()
                        elif pygame.Rect(560, 460, 130, 44).collidepoint(mx, my):
                            self.running = False
                            self.result = None
            self.draw()
            pygame.display.flip()
            clock.tick(60)
        pygame.key.stop_text_input()
        return self.result

    def try_connect(self):
        if self.connecting:
            return
        try:
            port = int(self.values[2])
        except Exception:
            self.msg = "端口必须是数字"
            return
        self.msg = "正在连接服务器..."
        self.connecting = True
        self.connect_error = None
        self.connect_result = None

        def do_connect():
            try:
                net = NetClient(self.values[1], port, self.values[3])
                self.connect_result = net
            except Exception as e:
                self.connect_error = str(e)

        threading.Thread(target=do_connect, daemon=True).start()

    def draw(self):
        screen.fill((22, 28, 42))
        
        if self.auto_connect:
            # 极简的正在连接界面
            t = FONT_XL.render("正在连接服务器...", True, (240, 240, 240))
            screen.blit(t, ((SCREEN_W - t.get_width()) // 2, 180))
            
            info = f"{self.values[1]}:{self.values[2]}"
            s = FONT_LG.render(info, True, (170, 180, 200))
            screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 240))
            
            if self.msg:
                col = (150, 200, 255) if self.connecting else (230, 80, 80)
                s = FONT_MD.render(self.msg, True, col)
                screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 320))
            
            if not self.connecting:
                draw_btn(pygame.Rect(412, 460, 130, 44), "重试", (70, 150, 90))
                draw_btn(pygame.Rect(560, 460, 130, 44), "返回", (120, 80, 80))
            else:
                # 连接中时显示取消按钮（可选）
                pass
                
            hint = FONT_SM.render("ESC 返回", True, (140, 150, 170))
            screen.blit(hint, ((SCREEN_W - hint.get_width()) // 2, 540))
            return

        # 以下为“添加服务器”时的填表界面
        t = FONT_XL.render("服务器设置", True, (240, 240, 240))
        screen.blit(t, ((SCREEN_W - t.get_width()) // 2, 80))
        
        start_y = 200
        for i, (label, _) in enumerate(self.fields):
            y = start_y + i * 60
            lab = FONT_MD.render(label, True, (200, 200, 220))
            screen.blit(lab, (240, y + 8))
            r = pygame.Rect(412, y, 300, 40)
            pygame.draw.rect(screen, (60, 70, 90), r)
            border_col = (255, 220, 80) if i == self.focus and not self.connecting else (120, 130, 150)
            if self.connecting:
                border_col = (80, 80, 80)
            pygame.draw.rect(screen, border_col, r, 2)
            s = FONT_MD.render(self.values[i] + ("_" if i == self.focus and not self.connecting else ""), True, (255, 255, 255))
            screen.blit(s, (r.x + 8, r.y + 8))
        if self.msg:
            col = (150, 200, 255) if self.connecting else (230, 180, 100)
            s = FONT_SM.render(self.msg, True, col)
            screen.blit(s, ((SCREEN_W - s.get_width()) // 2, 420))
        btn_col = (80, 80, 80) if self.connecting else (70, 150, 90)
        draw_btn(pygame.Rect(412, 460, 130, 44), "连接中..." if self.connecting else "连接并保存", btn_col)
        draw_btn(pygame.Rect(560, 460, 130, 44), "取消", (120, 80, 80))
        hint = FONT_SM.render("Tab 切换 · Enter 连接 · ESC 返回", True, (140, 150, 170))
        screen.blit(hint, ((SCREEN_W - hint.get_width()) // 2, 540))


# ============================================================
# 游戏主逻辑
# ============================================================
# ============================================================
# 游戏主逻辑
# ============================================================
class Game:
    def __init__(self, srv=None, save_file=None, net=None):
        self.net = net
        self.srv = srv
        self.save_file = save_file
        self.furnaces = {}
        self.remote_players = {}
        self.net_move_timer = 0.0

        if net:
            w = net.welcome
            ws = w.get("ws", [WORLD_W, WORLD_H])
            self.world = World(ws[0], ws[1], seed=w.get("seed"))
            self.world.apply_changes(w.get("changes", {}))
            
            # ========== 核心修改：读取服务端传来的玩家坐标 ==========
            px = w.get("my_x", (WORLD_W // 2) * TILE + 5)
            py = w.get("my_y", 100)
            
            # 防呆：如果坐标不合法（比如没有存档默认给的100），则回归地表
            if py <= 0:
                sx = WORLD_W // 2
                sy = self.world.surface_y(sx)
                py = (sy - 3) * TILE
                
            self.player = Player(px, py)
            # =========================================================
            
            self.remote_players = {p["id"]: dict(p) for p in w.get("players", [])}
            self.day_time = w.get("day_time", 0.25)
        else:
            data = srv.load(save_file) or {}
            ws = data.get("world_size", [WORLD_W, WORLD_H])
            self.world = World(ws[0], ws[1], seed=data.get("seed"))
            self.world.apply_changes(data.get("changes", {}))
            for k, v in data.get("furnaces", {}).items():
                try:
                    x, y = map(int, k.split(","))
                    self.furnaces[(x, y)] = v
                except Exception:
                    pass
            pd = data.get("player", {})
            sx = WORLD_W // 2
            sy = self.world.surface_y(sx)
            px = pd.get("x", sx * TILE + 5)
            py = pd.get("y", (sy - 3) * TILE)
            if py <= 0:
                py = (sy - 3) * TILE
            self.player = Player(px, py)
            self.player.health = pd.get("health", 100)
            self.player.hunger = pd.get("hunger", 100)
            self.player.hotbar = pd.get("hotbar") or [None] * 9
            self.player.backpack = pd.get("backpack") or [None] * 27
            self.player.armor = pd.get("armor") or {"head": None, "chest": None, "legs": None, "feet": None}
            self.player.selected = pd.get("selected", 0)
            self.player.gamemode = data.get("gamemode", "survival")
            self.day_time = data.get("day_time", 0.25)

        self.light_factor = 1.0
        self.cam_x = self.cam_y = 0
        self.monsters = []
        self.animals = []
        self.drops = []
        self.spawn_timer = 0.0
        self.animal_timer = 0.0
        self.mining = None
        self.mining_progress = 0.0
        self.place_cd = 0.0
        self.running = True
        self.keys = {}
        self._last_space = 0.0

        self.inv_ui = InventoryUI(self)
        self.furnace_ui = FurnaceUI(self)
        self.chat = ChatUI(self)
        if self.net:
            self.chat.log(f"已连接服务器 (ID={net.my_id})")
            motd = self.net.welcome.get("motd", "")
            if motd:
                self.chat.log(f"[MOTD] {motd}")
        else:
            self.chat.log("按 / 或 T 打开聊天，/help 查看指令")
        for _ in range(4):
            self.spawn_animal()

    # ---------------- 存档 ----------------
    def save(self):
        if self.net or not self.save_file or not self.srv:
            return
        old = self.srv.load(self.save_file) or {}
        data = {
            "version": 1,
            "name": old.get("name", "存档"),
            "seed": self.world.seed,
            "day_time": self.day_time,
            "gamemode": self.player.gamemode,
            "world_size": [self.world.w, self.world.h],
            "changes": self.world.changes,
            "furnaces": {f"{k[0]},{k[1]}": v for k, v in self.furnaces.items()},
            "player": {
                "x": self.player.x, "y": self.player.y,
                "health": self.player.health, "hunger": self.player.hunger,
                "hotbar": self.player.hotbar, "backpack": self.player.backpack,
                "armor": self.player.armor, "selected": self.player.selected,
            },
        }
        self.srv.save(self.save_file, data)

    # ---------------- 指令 ----------------
    def execute_command(self, cmd):
        parts = cmd.lstrip("/").split()
        if not parts:
            return
        name = parts[0].lower()
        args = parts[1:]
        try:
            if name == "help":
                self.chat.log("指令: /give <物品> [n] · /gamemode s|c · /tp x y")
                self.chat.log("      /time day|night|0-1 · /kill · /clear · /save")
            elif name == "give":
                iid = args[0]
                if iid not in ITEM_DATA:
                    self.chat.log("未知物品: " + iid)
                    return
                n = int(args[1]) if len(args) > 1 else 1
                if self.player.add_item_id(iid, n):
                    self.chat.log(f"获得 {ITEM_DATA[iid]['name']} ×{n}")
                else:
                    self.chat.log("背包已满")
            elif name == "gamemode":
                m = (args[0] if args else "survival").lower()
                if m in ("s", "survival"):
                    self.player.gamemode = "survival"
                    self.player.flying = False
                    self.chat.log("模式: 生存")
                elif m in ("c", "creative"):
                    self.player.gamemode = "creative"
                    self.chat.log("模式: 创造（双击空格切换飞行）")
            elif name == "tp":
                self.player.x = float(args[0])
                self.player.y = float(args[1])
                self.player.vx = self.player.vy = 0
                self.chat.log(f"传送到 {args[0]},{args[1]}")
            elif name == "time":
                v = (args[0] if args else "day").lower()
                if v == "day":
                    self.day_time = 0.25
                elif v == "night":
                    self.day_time = 0.75
                else:
                    try:
                        self.day_time = float(v) % 1.0
                    except Exception:
                        return
                self.chat.log(f"时间设为 {self.day_time:.2f}")
            elif name == "kill":
                self.player.health = 0
            elif name == "clear":
                self.player.hotbar = [None] * 9
                self.player.backpack = [None] * 27
                self.chat.log("背包已清空")
            elif name == "save":
                self.save()
                self.chat.log("已保存")
            else:
                self.chat.log("未知指令，/help 查看")
        except Exception as e:
            self.chat.log(f"指令错误: {e}")

    # ---------------- 网络 ----------------
    def process_net(self):
        if not self.net:
            return
        while True:
            try:
                msg = self.net.msg_queue.get_nowait()
            except queue.Empty:
                break
            t = msg.get("t")
            if t == "join":
                self.remote_players[msg["id"]] = dict(msg)
                self.chat.log(f"{msg.get('name','?')} 加入")
            elif t == "leave":
                p = self.remote_players.pop(msg["id"], None)
                if p:
                    self.chat.log(f"{p.get('name','?')} 离开")
            elif t == "move":
                if msg["id"] in self.remote_players:
                    self.remote_players[msg["id"]].update(msg)
                else:
                    self.remote_players[msg["id"]] = dict(msg)
            elif t == "block":
                x, y = msg["x"], msg["y"]
                b = msg.get("b")
                if 0 <= x < self.world.w and 0 <= y < self.world.h:
                    self.world.tiles[y][x] = b
            elif t == "attack":
                if msg.get("id") != self.net.my_id:
                    ax, ay = msg["x"], msg["y"]
                    for m in self.monsters:
                        if not m.dead and math.hypot(m.x + m.w / 2 - ax, m.y + m.h / 2 - ay) < 50:
                            m.health -= 10
                            m.hurt_timer = 0.3
                    for a in self.animals:
                        if not a.dead and math.hypot(a.x + a.w / 2 - ax, a.y + a.h / 2 - ay) < 50:
                            a.health -= 10
                            a.hurt_timer = 0.3
            elif t == "time":
                self.day_time = msg.get("dt", self.day_time)
            elif t == "chat":
                self.chat.log(f"[{msg.get('name','?')}] {msg.get('m','')}")
        if not self.net.alive:
            self.chat.log("⚠ 与服务器断开连接")
            self.net = None

    # ---------------- 逻辑辅助 ----------------
    def respawn(self):
        sx = WORLD_W // 2
        sy = self.world.surface_y(sx)
        self.player.x = sx * TILE + 5
        self.player.y = (sy - 3) * TILE
        self.player.health = self.player.max_health
        self.player.hunger = self.player.max_hunger
        self.player.vx = self.player.vy = 0
        self.monsters.clear()

    def try_attack(self):
        mx, my = pygame.mouse.get_pos()
        wx = mx + self.cam_x
        wy = my + self.cam_y
        p = self.player
        pcx = p.x + p.w / 2
        pcy = p.y + p.h / 2
        dmg = (p.attack_damage() if p.gamemode != "creative" else 999)
        for m in self.monsters:
            if m.dead:
                continue
            mcx = m.x + m.w / 2
            mcy = m.y + m.h / 2
            if math.hypot(mcx - pcx, mcy - pcy) < 72 and math.hypot(mcx - wx, mcy - wy) < 50:
                m.health -= dmg
                m.hurt_timer = 0.3
                m.knockback_vx = 420 * (1 if mcx > pcx else -1)
                m.vy = -320
                p.attack_cd = 0.35
                if self.net:
                    self.net.send_attack(mcx, mcy)
                return True
        for a in self.animals:
            if a.dead:
                continue
            acx = a.x + a.w / 2
            acy = a.y + a.h / 2
            if math.hypot(acx - pcx, acy - pcy) < 72 and math.hypot(acx - wx, acy - wy) < 50:
                a.health -= dmg
                a.hurt_timer = 0.3
                a.knockback_vx = 380 * (1 if acx > pcx else -1)
                a.vy = -260
                a.flee_timer = 3.0
                p.attack_cd = 0.35
                if self.net:
                    self.net.send_attack(acx, acy)
                return True
        return False

    def try_eat(self):
        p = self.player
        it = p.selected_item()
        if not it:
            return False
        d = ITEM_DATA[it["id"]]
        if d.get("kind") != "food" or p.hunger >= p.max_hunger:
            return False
        p.hunger = min(p.max_hunger, p.hunger + d["food"])
        it["count"] -= 1
        if it["count"] <= 0:
            p.hotbar[p.selected] = None
        self.place_cd = 0.3
        return True

    def handle_mining(self, dt, mx, my):
        wx = (mx + self.cam_x) / TILE
        wy = (my + self.cam_y) / TILE
        tx, ty = int(wx), int(wy)
        if not (0 <= tx < self.world.w and 0 <= ty < self.world.h):
            return
        bid = self.world.tiles[ty][tx]
        if bid is None:
            self.mining = None
            self.mining_progress = 0
            return
        p = self.player
        pcx, pcy = p.x + p.w / 2, p.y + p.h / 2
        cx, cy = (tx + 0.5) * TILE, (ty + 0.5) * TILE
        if math.hypot(cx - pcx, cy - pcy) > 6 * TILE:
            return
        if self.mining != (tx, ty):
            self.mining = (tx, ty)
            self.mining_progress = 0
        speed = p.mining_speed(bid)
        self.mining_progress += dt * speed / BLOCK_DATA[bid]["hardness"]
        if self.mining_progress >= 1.0:
            can = p.can_harvest(bid)
            drop = BLOCK_DATA[bid]["drop"]
            if drop and can:
                self.drops.append(Drop(cx, cy, drop, 1))
            if bid == "leaves" and random.random() < 0.15:
                self.drops.append(Drop(cx, cy, "apple", 1))
            if bid == "furnace" and (tx, ty) in self.furnaces:
                f = self.furnaces.pop((tx, ty))
                for k in ("input", "fuel", "output"):
                    if f[k]:
                        self.drops.append(Drop(cx, cy, f[k]["id"], f[k]["count"]))
            
            self.world.tiles[ty][tx] = None
            if self.net:
                self.net.send_mine(tx, ty)
            
            self.mining = None
            self.mining_progress = 0

    def try_place(self, mx, my):
        p = self.player
        wx = (mx + self.cam_x) / TILE
        wy = (my + self.cam_y) / TILE
        tx, ty = int(wx), int(wy)
        if 0 <= tx < self.world.w and 0 <= ty < self.world.h:
            bid = self.world.tiles[ty][tx]
            if bid == "crafting_table":
                self.inv_ui.open_crafting()
                self.place_cd = 0.3
                return
            if bid == "furnace":
                self.furnace_ui.open_furnace((tx, ty))
                self.place_cd = 0.3
                return
        it = p.selected_item()
        if not it:
            return
        d = ITEM_DATA[it["id"]]
        if d["kind"] != "block":
            return
        if not (0 <= tx < self.world.w and 0 <= ty < self.world.h):
            return
        pcx, pcy = p.x + p.w / 2, p.y + p.h / 2
        cx, cy = (tx + 0.5) * TILE, (ty + 0.5) * TILE
        if math.hypot(cx - pcx, cy - pcy) > 6 * TILE:
            return
        if self.world.tiles[ty][tx] is not None:
            return
        br = pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
        if BLOCK_DATA[d["block"]]["solid"] and br.colliderect(p.rect()):
            return
        
        self.world.tiles[ty][tx] = d["block"]
        if self.net:
            self.net.send_place(tx, ty, d["block"])
        
        if p.gamemode != "creative":
            it["count"] -= 1
            if it["count"] <= 0:
                p.hotbar[p.selected] = None
        self.place_cd = 0.2

    def spawn_monster(self):
        p = self.player
        for _ in range(24):
            side = random.choice([-1, 1])
            dist = random.randint(400, 800)
            tx = int((p.x + side * dist) / TILE)
            if tx < 3 or tx >= self.world.w - 3:
                continue
            ty = self.world.surface_y(tx)
            if ty <= 2 or ty >= self.world.h - 3:
                continue
            if self.world.tiles[ty - 1][tx] is not None:
                continue
            if self.world.tiles[ty - 2][tx] is not None:
                continue
            self.monsters.append(Monster(tx * TILE, (ty - 2) * TILE))
            return

    def spawn_animal(self):
        p = self.player
        for _ in range(30):
            side = random.choice([-1, 1])
            dist = random.randint(300, 900)
            tx = int((p.x + side * dist) / TILE)
            if tx < 3 or tx >= self.world.w - 3:
                continue
            ty = self.world.surface_y(tx)
            if ty <= 2 or ty >= self.world.h - 3:
                continue
            if self.world.tiles[ty][tx] != "grass":
                continue
            if self.world.tiles[ty - 1][tx] is not None:
                continue
            if self.world.tiles[ty - 2][tx] is not None:
                continue
            kind = random.choice(["pig", "sheep"])
            self.animals.append(Animal(tx * TILE + 3, ty * TILE - 22, kind))
            return

    def update_furnaces(self, dt):
        for pos, f in list(self.furnaces.items()):
            if f["burn"] > 0:
                f["burn"] = max(0, f["burn"] - dt)
            can = False
            if f["input"] and f["input"]["id"] in SMELTING:
                rid = SMELTING[f["input"]["id"]]
                if f["output"] is None or (f["output"]["id"] == rid and f["output"]["count"] < 64):
                    can = True
            if can:
                if f["burn"] <= 0 and f["fuel"] and f["fuel"]["id"] in FUEL:
                    f["burn"] = FUEL[f["fuel"]["id"]]
                    f["fuel"]["count"] -= 1
                    if f["fuel"]["count"] <= 0:
                        f["fuel"] = None
                if f["burn"] > 0:
                    f["progress"] += dt
                    if f["progress"] >= SMELTING_TIME:
                        f["progress"] = 0
                        rid = SMELTING[f["input"]["id"]]
                        if f["output"] is None:
                            f["output"] = {"id": rid, "count": 1}
                        else:
                            f["output"]["count"] += 1
                        f["input"]["count"] -= 1
                        if f["input"]["count"] <= 0:
                            f["input"] = None
            else:
                f["progress"] = max(0, f["progress"] - dt * 0.5)

    # ---------------- 更新 ----------------
    def update(self, dt):
        self.process_net()
        self.chat.update(dt)
        if self.inv_ui.open or self.furnace_ui.open or self.chat.active:
            return

        self.day_time = (self.day_time + dt / DAY_LENGTH) % 1.0
        lf = 0.5 + 0.5 * math.cos((self.day_time - 0.5) * 2 * math.pi)
        self.light_factor = 0.12 + 0.88 * max(0, lf)
        self.update_furnaces(dt)
        if self.place_cd > 0:
            self.place_cd -= dt

        p = self.player
        creative = (p.gamemode == "creative")

        ax = 0
        if self.keys.get(pygame.K_a) or self.keys.get(pygame.K_LEFT):
            ax -= 1
            p.facing = -1
        if self.keys.get(pygame.K_d) or self.keys.get(pygame.K_RIGHT):
            ax += 1
            p.facing = 1
        p.vx = ax * PLAYER_SPEED

        if creative and p.flying:
            vy_in = 0
            if self.keys.get(pygame.K_w) or self.keys.get(pygame.K_UP) or self.keys.get(pygame.K_SPACE):
                vy_in -= 1
            if self.keys.get(pygame.K_s) or self.keys.get(pygame.K_DOWN):
                vy_in += 1
            p.vy = vy_in * PLAYER_SPEED * 1.2
        else:
            if (self.keys.get(pygame.K_SPACE) or self.keys.get(pygame.K_w) or
                    self.keys.get(pygame.K_UP)) and p.on_ground:
                p.vy = -JUMP_VEL
                p.on_ground = False
            p.vy = min(p.vy + GRAVITY * dt, 1400)

        p.x += p.vx * dt
        resolve_entity_x(p, self.world)
        p.y += p.vy * dt
        p.on_ground = False
        resolve_entity_y(p, self.world)
        p.x = max(0, min(p.x, self.world.w * TILE - p.w))

        if p.hurt_timer > 0:
            p.hurt_timer -= dt
        if p.attack_cd > 0:
            p.attack_cd -= dt

        if not creative:
            p.hunger = max(0, p.hunger - dt * 0.5)
            if p.hunger > 0:
                p.regen_timer += dt
                if p.regen_timer > 8 and p.health < p.max_health:
                    p.health = min(p.max_health, p.health + 2)
                    p.regen_timer = 0
            else:
                p.health -= dt * 2
        else:
            p.hunger = p.max_hunger

        if p.health <= 0:
            self.respawn()

        mx, my = pygame.mouse.get_pos()
        if pygame.mouse.get_pressed()[0]:
            if p.attack_cd <= 0 and self.try_attack():
                self.mining = None
                self.mining_progress = 0
            else:
                self.handle_mining(dt, mx, my)
        else:
            self.mining = None
            self.mining_progress = 0

        for d in self.drops[:]:
            d.update(self.world, dt)
            if d.age > 0.4:
                if math.hypot(d.x - (p.x + p.w / 2), d.y - (p.y + p.h / 2)) < 44:
                    if p.give_item({"id": d.item_id, "count": d.count}):
                        self.drops.remove(d)
                        continue
            if d.age > 180:
                self.drops.remove(d)

        for m in self.monsters[:]:
            m.update(self, dt)
            if m.dead:
                self.monsters.remove(m)

        for a in self.animals[:]:
            a.update(self, dt)
            if a.dead:
                cx, cy = a.x + a.w / 2, a.y + a.h / 2
                self.drops.append(Drop(cx, cy, "raw_meat", 2 if a.kind == "pig" else 1))
                self.animals.remove(a)

        self.spawn_timer -= dt
        if self.light_factor < 0.4 and self.spawn_timer <= 0 and len(self.monsters) < 8:
            self.spawn_timer = 3.0
            self.spawn_monster()
        self.animal_timer -= dt
        if self.animal_timer <= 0:
            self.animal_timer = 6.0
            if self.light_factor > 0.5 and len(self.animals) < 8:
                self.spawn_animal()

        if self.net:
            self.net_move_timer -= dt
            if self.net_move_timer <= 0:
                self.net.send({"t": "move", "x": p.x, "y": p.y,
                               "facing": p.facing, "gm": p.gamemode})
                self.net_move_timer = 0.1

        target_x = p.x + p.w / 2 - SCREEN_W / 2
        target_y = p.y + p.h / 2 - SCREEN_H / 2
        wpx = self.world.w * TILE
        wpy = self.world.h * TILE
        self.cam_x = (wpx - SCREEN_W) / 2 if wpx <= SCREEN_W else max(0, min(target_x, wpx - SCREEN_W))
        self.cam_y = (wpy - SCREEN_H) / 2 if wpy <= SCREEN_H else max(0, min(target_y, wpy - SCREEN_H))

    # ---------------- 绘制 ----------------
    def draw_player_like(self, x, y, facing, hurt, body_col=(60, 110, 190)):
        s = pygame.Surface((22, 42), pygame.SRCALPHA)
        pygame.draw.rect(s, (235, 200, 160), (4, 0, 14, 13))
        pygame.draw.rect(s, (30, 30, 30), (7, 6, 2, 3))
        pygame.draw.rect(s, (30, 30, 30), (13, 6, 2, 3))
        pygame.draw.rect(s, body_col, (3, 13, 16, 16))
        pygame.draw.rect(s, (50, 60, 90), (4, 29, 6, 13))
        pygame.draw.rect(s, (50, 60, 90), (12, 29, 6, 13))
        pygame.draw.rect(s, (235, 200, 160), (0, 14, 3, 12))
        pygame.draw.rect(s, (235, 200, 160), (19, 14, 3, 12))
        if facing < 0:
            s = pygame.transform.flip(s, True, False)
        if hurt > 0 and int(hurt * 20) % 2 == 0:
            tint = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            tint.fill((255, 80, 80, 120))
            s.blit(tint, (0, 0))
        screen.blit(s, (int(x) - int(self.cam_x), int(y) - int(self.cam_y)))

    def draw(self):
        sky = (
            int(10 + (110 - 10) * self.light_factor),
            int(15 + (180 - 15) * self.light_factor),
            int(40 + (240 - 40) * self.light_factor),
        )
        screen.fill(sky)
        cx, cy = int(self.cam_x), int(self.cam_y)
        x0 = max(0, cx // TILE)
        x1 = min(self.world.w - 1, (cx + SCREEN_W) // TILE)
        y0 = max(0, cy // TILE)
        y1 = min(self.world.h - 1, (cy + SCREEN_H) // TILE)
        for ty in range(y0, y1 + 1):
            row = self.world.tiles[ty]
            for tx in range(x0, x1 + 1):
                b = row[tx]
                if b:
                    screen.blit(BLOCK_TEX[b], (tx * TILE - cx, ty * TILE - cy))

        for d in self.drops:
            d.draw(screen, cx, cy)
        for a in self.animals:
            a.draw(screen, cx, cy)
        for m in self.monsters:
            m.draw(screen, cx, cy)

        for rid, pd in self.remote_players.items():
            self.draw_player_like(pd.get("x", 0), pd.get("y", 0),
                                  pd.get("facing", 1), 0, (200, 80, 80))
            name = pd.get("name", "")
            if name:
                t = FONT_SM.render(name, True, (255, 255, 200))
                screen.blit(t, (int(pd.get("x", 0)) - cx - t.get_width() // 2 + 11,
                                int(pd.get("y", 0)) - cy - 18))

        self.draw_player_like(self.player.x, self.player.y,
                              self.player.facing, self.player.hurt_timer)

        if self.mining and self.mining_progress > 0:
            tx, ty = self.mining
            sx = tx * TILE - cx
            sy = ty * TILE - cy
            h = int(TILE * min(1, self.mining_progress))
            ov = pygame.Surface((TILE, h), pygame.SRCALPHA)
            ov.fill((255, 255, 255, 90))
            screen.blit(ov, (sx, sy + TILE - h))

        na = int(210 * (1 - self.light_factor))
        if na > 0:
            ls = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ls.fill((0, 0, 22, na))
            px = int(self.player.x + self.player.w / 2 - self.cam_x)
            py = int(self.player.y + self.player.h / 2 - self.cam_y)
            for r in range(250, 0, -8):
                a = int(na * (r / 250) ** 1.6)
                pygame.draw.circle(ls, (0, 0, 22, a), (px, py), r)
            screen.blit(ls, (0, 0))

        if not self.inv_ui.open and not self.furnace_ui.open:
            mx, my = pygame.mouse.get_pos()
            tx = int((mx + self.cam_x) / TILE)
            ty = int((my + self.cam_y) / TILE)
            if 0 <= tx < self.world.w and 0 <= ty < self.world.h and self.world.tiles[ty][tx] is not None:
                pygame.draw.rect(screen, (255, 255, 255),
                                 (tx * TILE - cx, ty * TILE - cy, TILE, TILE), 2)

        self.draw_hud()
        self.inv_ui.draw()
        self.furnace_ui.draw()
        self.chat.draw()

    def draw_hud(self):
        p = self.player
        bw, bh = 200, 16
        x, y = 20, 20
        pygame.draw.rect(screen, (60, 20, 20), (x, y, bw, bh))
        pygame.draw.rect(screen, (220, 60, 60), (x, y, int(bw * p.health / p.max_health), bh))
        pygame.draw.rect(screen, (200, 200, 200), (x, y, bw, bh), 1)
        t = FONT_SM.render(f"生命 {int(p.health)}", True, (255, 255, 255))
        screen.blit(t, (x + 6, y + 1))

        y2 = y + bh + 6
        pygame.draw.rect(screen, (60, 40, 10), (x, y2, bw, bh))
        pygame.draw.rect(screen, (230, 150, 50), (x, y2, int(bw * p.hunger / p.max_hunger), bh))
        pygame.draw.rect(screen, (200, 200, 200), (x, y2, bw, bh), 1)
        t = FONT_SM.render(f"饥饿 {int(p.hunger)}", True, (255, 255, 255))
        screen.blit(t, (x + 6, y2 + 1))

        av = p.armor_value()
        if av > 0:
            t = FONT_SM.render(f"护甲 {av}", True, (200, 220, 255))
            screen.blit(t, (x, y2 + bh + 6))

        info = "创造" if p.gamemode == "creative" else "生存"
        if self.net:
            info += f" · 在线 {len(self.remote_players) + 1}"
        t = FONT_SM.render(info, True, (255, 255, 200))
        screen.blit(t, (SCREEN_W - t.get_width() - 20, 20))

        sl = 52
        g = 4
        tot = 9 * sl + 8 * g
        hx = (SCREEN_W - tot) // 2
        hy = SCREEN_H - sl - 16
        for i in range(9):
            r = pygame.Rect(hx + i * (sl + g), hy, sl, sl)
            pygame.draw.rect(screen, (40, 40, 46), r)
            border = (255, 220, 80) if i == p.selected else (120, 120, 130)
            pygame.draw.rect(screen, border, r, 2 if i == p.selected else 1)
            draw_slot_item(r, p.hotbar[i], 40)
        sel = p.hotbar[p.selected]
        if sel:
            t = FONT_MD.render(ITEM_DATA[sel["id"]]["name"], True, (255, 255, 255))
            screen.blit(t, ((SCREEN_W - t.get_width()) // 2, hy - 26))

    # ---------------- 主循环 ----------------
    def run(self):
        while self.running:
            dt = min(clock.tick(60) / 1000.0, 0.05)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN:
                    if self.inv_ui.open:
                        self.inv_ui.handle_event(ev)
                        continue
                    if self.furnace_ui.open:
                        self.furnace_ui.handle_event(ev)
                        continue
                    if self.chat.active:
                        self.chat.handle_event(ev)
                        continue
                    if ev.key == pygame.K_ESCAPE:
                        self.save()
                        self.running = False
                    elif ev.key == pygame.K_e:
                        self.inv_ui.open_inventory()
                    elif ev.key == pygame.K_SLASH:
                        self.chat.activate("/")
                    elif ev.key == pygame.K_t:
                        self.chat.activate()
                    elif pygame.K_1 <= ev.key <= pygame.K_9:
                        self.player.selected = ev.key - pygame.K_1
                    elif ev.key == pygame.K_SPACE and self.player.gamemode == "creative":
                        now = time.time()
                        if now - self._last_space < 0.3:
                            self.player.flying = not self.player.flying
                            self.player.vy = 0
                        self._last_space = now
                        self.keys[ev.key] = True
                    else:
                        self.keys[ev.key] = True
                elif ev.type == pygame.KEYUP:
                    self.keys[ev.key] = False
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    if self.inv_ui.open:
                        self.inv_ui.handle_event(ev)
                    elif self.furnace_ui.open:
                        self.furnace_ui.handle_event(ev)
                    elif self.chat.active:
                        self.chat.handle_event(ev)
                    elif ev.button == 3 and self.place_cd <= 0:
                        if not self.try_eat():
                            self.try_place(*ev.pos)
                elif ev.type == pygame.MOUSEWHEEL:
                    if not self.inv_ui.open and not self.furnace_ui.open and not self.chat.active:
                        self.player.selected = (self.player.selected - ev.y) % 9
                elif ev.type == pygame.TEXTINPUT and self.chat.active:
                    self.chat.handle_event(ev)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        if self.net:
            self.net.close()

# ============================================================
# 入口
# ============================================================
def main():
    build_assets()
    srv = SaveServer()
    while True:
        choice = MainMenuUI().run()
        if choice is None:
            break
        if choice == "single":
            fn = SaveSelectorUI(srv).run()
            if fn is None:
                continue
            Game(srv=srv, save_file=fn).run()
        elif choice == "multi_list":
            while True:
                res = ServerListUI().run()
                if res is None:
                    break
                elif res[0] == "add":
                    # 添加服务器：保留填表界面
                    net = ConnectUI().run()
                    if net is None:
                        continue
                    try:
                        Game(net=net).run()
                    except Exception as e:
                        print("[客户端] 异常:", e)
                    finally:
                        net.close()
                elif res[0] == "connect":
                    # 点击列表直接连接：进入纯加载界面
                    e = res[1]
                    cui = ConnectUI(
                        default_srv_name=e.get("name", "未命名"),
                        default_host=e.get("host", "127.0.0.1"),
                        default_port=str(e.get("port", 25565)),
                        default_nick="Player",
                        auto_connect=True  # 关键：启用自动连接
                    )
                    net = cui.run()
                    if net is None:
                        continue
                    try:
                        Game(net=net).run()
                    except Exception as e:
                        print("[客户端] 异常:", e)
                    finally:
                        net.close()
    pygame.quit()


if __name__ == "__main__":
    main()