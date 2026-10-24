import socket, threading, json, time, random, argparse, math, os, sys

TILE = 32
WORLD_W, WORLD_H = 260, 130
DAY_LENGTH = 180.0

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SAVE_DIR = os.path.join(SCRIPT_DIR, "serversaves")
os.makedirs(SAVE_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(SCRIPT_DIR, "server_config.json")
DEFAULT_CONFIG = {
    "motd": "欢迎来到 2D 生存沙盒服务器！",
    "whitelist_enabled": False,
    "whitelist": ["Player"],
    "interact_distance": 192,
    "attack_distance": 200
}

class ClientConn:
    def __init__(self, conn, addr, cid):
        self.conn, self.addr, self.id = conn, addr, cid
        self.name = f"Player_{cid}"
        self.x = WORLD_W * TILE / 2
        self.y = 100
        self.facing = 1
        self.gamemode = "survival"
        self.alive = True
        self.buf = b""
        self.send_lock = threading.Lock()

class GameServer:
    def __init__(self, host, port, seed=None):
        self.host, self.port = host, port
        self.save_file = os.path.join(SAVE_DIR, f"world_{port}.json")
        self.player_file = os.path.join(SAVE_DIR, f"players_{port}.json")
        
        self.load_config()

        self.seed = seed
        self.world_size = [WORLD_W, WORLD_H]
        self.day_time = 0.25
        self.changes = {}
        
        # 尝试加载世界存档
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if self.seed is None:
                    self.seed = data.get("seed", random.randint(1, 10**9))
                self.world_size = data.get("world_size", [WORLD_W, WORLD_H])
                self.day_time = data.get("day_time", 0.25)
                self.changes = data.get("changes", {})
                print(f"[服务器] 已加载世界存档 {self.save_file}")
            except Exception as e:
                print(f"[服务器] 加载世界存档失败: {e}")
        
        if self.seed is None:
            self.seed = random.randint(1, 10**9)

        # 加载玩家位置存档
        self.player_positions = self.load_players()

        self.clients = []
        self.lock = threading.RLock()
        self.running = True
        self.next_id = 1
        self.sock = None

    def load_players(self):
        if os.path.exists(self.player_file):
            try:
                with open(self.player_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[服务器] 加载玩家位置失败: {e}")
        return {}

    def save_players(self):
        try:
            with open(self.player_file, "w", encoding="utf-8") as f:
                json.dump(self.player_positions, f, ensure_ascii=False)
        except Exception as e:
            print(f"[服务器] 保存玩家位置失败: {e}")

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=4)
                print(f"[服务器] 已生成默认配置文件: {CONFIG_FILE}")
            except Exception as e:
                print(f"[服务器] 写入默认配置失败: {e}")
                
        self.config = DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    self.config.update(user_cfg)
            except Exception as e:
                print(f"[服务器] 读取配置失败: {e}")
                
        self.motd = self.config.get("motd", "")
        self.whitelist_enabled = self.config.get("whitelist_enabled", False)
        self.whitelist = self.config.get("whitelist", [])
        self.interact_distance = self.config.get("interact_distance", 192)
        self.attack_distance = self.config.get("attack_distance", 200)
        
        print(f"[服务器] MOTD: {self.motd}")
        if self.whitelist_enabled:
            print(f"[服务器] 白名单已开启，允许名单: {self.whitelist}")

    def save_world(self):
        try:
            data = {
                "seed": self.seed,
                "world_size": self.world_size,
                "day_time": self.day_time,
                "changes": self.changes
            }
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[服务器] 保存世界失败: {e}")

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(10)
        print(f"[服务器] 监听 {self.host}:{self.port} 种子={self.seed}")
        print(f"[服务器] 世界存档: {self.save_file}")
        print(f"[服务器] 玩家存档: {self.player_file}")
        threading.Thread(target=self.time_loop, daemon=True).start()
        try:
            while self.running:
                conn, addr = self.sock.accept()
                with self.lock:
                    cid = self.next_id
                    self.next_id += 1
                    c = ClientConn(conn, addr, cid)
                    self.clients.append(c)
                print(f"[服务器] 连接 {addr} id={cid}")
                threading.Thread(target=self.handle_client, args=(c,), daemon=True).start()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def time_loop(self):
        while self.running:
            time.sleep(3)
            with self.lock:
                self.day_time = (self.day_time + 3 / DAY_LENGTH) % 1.0
                dt = self.day_time
            self.broadcast({"t": "time", "dt": dt})
            self.save_world()
            self.save_players()

    def broadcast(self, obj, exclude=None):
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            dead = []
            for c in self.clients:
                if c is exclude: continue
                try:
                    with c.send_lock:
                        c.conn.sendall(data)
                except Exception:
                    dead.append(c)
            for c in dead:
                c.alive = False

    def handle_client(self, c):
        try:
            while c.alive and self.running:
                data = c.conn.recv(4096)
                if not data: break
                c.buf += data
                while b"\n" in c.buf:
                    line, c.buf = c.buf.split(b"\n", 1)
                    line = line.strip()
                    if not line: continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue
                    self.on_message(c, msg)
        except Exception as e:
            print(f"[服务器] 异常 {c.addr}: {e}")
        finally:
            self.on_disconnect(c)

    def check_dist(self, c, tx, ty, max_dist_px=None):
        if max_dist_px is None:
            max_dist_px = self.interact_distance
        cx = c.x + 11
        cy = c.y + 21
        px = tx * TILE + 16
        py = ty * TILE + 16
        return math.hypot(px - cx, py - cy) <= max_dist_px

    def on_message(self, c, msg):
        t = msg.get("t")
        
        if t == "ping":
            try:
                data = json.dumps({"t": "pong", "motd": self.motd, "online": len(self.clients)}, ensure_ascii=False) + "\n"
                with c.send_lock:
                    c.conn.sendall(data.encode("utf-8"))
            except Exception:
                pass
            c.alive = False
            return

        if t == "join":
            c.name = (msg.get("name") or c.name)[:20]
            
            if self.whitelist_enabled and c.name not in self.whitelist:
                try:
                    c.conn.sendall((json.dumps({"t": "kick", "reason": "你不在服务器白名单中"}, ensure_ascii=False) + "\n").encode("utf-8"))
                except Exception:
                    pass
                c.alive = False
                print(f"[服务器] 拒绝 {c.name} 连接：不在白名单中")
                return

            # 恢复玩家位置
            if c.name in self.player_positions:
                c.x = self.player_positions[c.name]["x"]
                c.y = self.player_positions[c.name]["y"]
            else:
                c.x = WORLD_W * TILE / 2
                c.y = 100

            with self.lock:
                players = [{"id": o.id, "name": o.name, "x": o.x, "y": o.y,
                            "facing": o.facing, "gm": o.gamemode}
                           for o in self.clients if o is not c]
                welcome = json.dumps({
                    "t": "welcome", "my_id": c.id, "seed": self.seed,
                    "ws": self.world_size, "changes": self.changes,
                    "players": players, "day_time": self.day_time,
                    "motd": self.motd,
                    "my_x": c.x, "my_y": c.y
                }, ensure_ascii=False) + "\n"
            try:
                with c.send_lock:
                    c.conn.sendall(welcome.encode("utf-8"))
            except Exception:
                c.alive = False
                return
            self.broadcast({"t": "join", "id": c.id, "name": c.name, "x": c.x, "y": c.y,
                            "facing": c.facing, "gm": c.gamemode}, exclude=c)
            print(f"[服务器] {c.name} 加入 (坐标 {c.x:.1f}, {c.y:.1f})")

        elif t == "move":
            c.x = msg.get("x", c.x)
            c.y = msg.get("y", c.y)
            c.facing = msg.get("facing", c.facing)
            c.gamemode = msg.get("gm", c.gamemode)
            
            self.player_positions[c.name] = {"x": c.x, "y": c.y}
            
            self.broadcast({"t": "move", "id": c.id, "x": c.x, "y": c.y,
                            "facing": c.facing, "gm": c.gamemode}, exclude=c)

        elif t == "mine":
            x, y = msg.get("x"), msg.get("y")
            if x is not None and y is not None and self.check_dist(c, x, y):
                key = f"{x},{y}"
                with self.lock:
                    self.changes.pop(key, None)
                self.broadcast({"t": "block", "x": x, "y": y, "b": None}, exclude=c)
                try:
                    with c.send_lock:
                        c.conn.sendall((json.dumps({"t": "block", "x": x, "y": y, "b": None}) + "\n").encode())
                except Exception:
                    c.alive = False

        elif t == "place":
            x, y, b = msg.get("x"), msg.get("y"), msg.get("b")
            if x is not None and y is not None and b in ["dirt", "cobblestone", "wood", "planks", "sand",
                                                          "crafting_table", "furnace", "glass", "torch"]:
                if self.check_dist(c, x, y):
                    key = f"{x},{y}"
                    with self.lock:
                        self.changes[key] = b
                    self.broadcast({"t": "block", "x": x, "y": y, "b": b}, exclude=c)
                    try:
                        with c.send_lock:
                            c.conn.sendall((json.dumps({"t": "block", "x": x, "y": y, "b": b}) + "\n").encode())
                    except Exception:
                        c.alive = False

        elif t == "attack":
            x, y = msg.get("x"), msg.get("y")
            if x is not None and y is not None and self.check_dist(c, x, y, self.attack_distance):
                self.broadcast({"t": "attack", "id": c.id, "x": x, "y": y}, exclude=c)

        elif t == "chat":
            self.broadcast({"t": "chat", "name": c.name, "m": str(msg.get("m", ""))[:200]})

    def on_disconnect(self, c):
        c.alive = False
        with self.lock:
            if c in self.clients:
                self.clients.remove(c)
            if c.name:
                self.player_positions[c.name] = {"x": c.x, "y": c.y}
                self.save_players()
        self.broadcast({"t": "leave", "id": c.id})
        try: c.conn.close()
        except Exception: pass
        print(f"[服务器] {c.name} 断开 (保存坐标 {c.x:.1f}, {c.y:.1f})")

    def shutdown(self):
        self.running = False
        self.save_world()
        self.save_players()
        with self.lock:
            for c in self.clients:
                try: c.conn.close()
                except Exception: pass
            self.clients.clear()
        if self.sock:
            try: self.sock.close()
            except Exception: pass
        print("[服务器] 已关闭并保存存档")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=25565)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    GameServer(args.host, args.port, args.seed).start()