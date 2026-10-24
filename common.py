import pygame, math, random, os, sys, json

TILE = 32
WORLD_W, WORLD_H = 260, 130
GRAVITY = 2000
PLAYER_SPEED = 220
JUMP_VEL = 680
DAY_LENGTH = 180.0
SMELTING_TIME = 4.0

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(SCRIPT_DIR, "assets")

BLOCK_DATA = {
    "grass": {"color":(94,157,70),"hardness":0.7,"tool":"shovel","level":0,"drop":"dirt","solid":True},
    "dirt": {"color":(134,96,67),"hardness":0.6,"tool":"shovel","level":0,"drop":"dirt","solid":True},
    "stone": {"color":(128,128,132),"hardness":1.6,"tool":"pickaxe","level":1,"drop":"cobblestone","solid":True},
    "cobblestone": {"color":(110,110,115),"hardness":1.8,"tool":"pickaxe","level":1,"drop":"cobblestone","solid":True},
    "wood": {"color":(122,86,50),"hardness":1.0,"tool":"axe","level":0,"drop":"wood","solid":False},
    "leaves": {"color":(60,140,60),"hardness":0.3,"tool":None,"level":0,"drop":None,"solid":False},
    "sand": {"color":(224,210,150),"hardness":0.5,"tool":"shovel","level":0,"drop":"sand","solid":True},
    "coal_ore": {"color":(95,95,100),"hardness":2.0,"tool":"pickaxe","level":1,"drop":"coal","solid":True},
    "iron_ore": {"color":(170,145,130),"hardness":2.6,"tool":"pickaxe","level":2,"drop":"iron_ore","solid":True},
    "diamond_ore": {"color":(90,200,200),"hardness":3.5,"tool":"pickaxe","level":3,"drop":"diamond","solid":True},
    "planks": {"color":(180,130,80),"hardness":0.9,"tool":"axe","level":0,"drop":"planks","solid":True},
    "crafting_table": {"color":(150,100,60),"hardness":1.0,"tool":"axe","level":0,"drop":"crafting_table","solid":True},
    "furnace": {"color":(90,90,95),"hardness":2.2,"tool":"pickaxe","level":1,"drop":"furnace","solid":True},
    "glass": {"color":(180,220,240),"hardness":0.4,"tool":None,"level":0,"drop":None,"solid":True},
    "torch": {"color":(200,170,80),"hardness":0.1,"tool":None,"level":0,"drop":"torch","solid":False},
}

ITEM_DATA = {
    "dirt":{"name":"泥土","kind":"block","block":"dirt","max_stack":64},
    "cobblestone":{"name":"圆石","kind":"block","block":"cobblestone","max_stack":64},
    "wood":{"name":"木头","kind":"block","block":"wood","max_stack":64},
    "planks":{"name":"木板","kind":"block","block":"planks","max_stack":64},
    "sand":{"name":"沙子","kind":"block","block":"sand","max_stack":64},
    "crafting_table":{"name":"工作台","kind":"block","block":"crafting_table","max_stack":64},
    "furnace":{"name":"熔炉","kind":"block","block":"furnace","max_stack":64},
    "glass":{"name":"玻璃","kind":"block","block":"glass","max_stack":64},
    "torch":{"name":"火把","kind":"block","block":"torch","max_stack":64},
    "stick":{"name":"木棍","kind":"material","max_stack":64},
    "coal":{"name":"煤炭","kind":"material","max_stack":64},
    "iron_ore":{"name":"铁矿石","kind":"material","max_stack":64},
    "iron_ingot":{"name":"铁锭","kind":"material","max_stack":64},
    "diamond":{"name":"钻石","kind":"material","max_stack":64},
    "raw_meat":{"name":"生肉","kind":"food","food":15,"max_stack":64},
    "cooked_meat":{"name":"熟肉","kind":"food","food":30,"max_stack":64},
    "apple":{"name":"苹果","kind":"food","food":8,"max_stack":64},
    "wood_pickaxe":{"name":"木镐","kind":"tool","tool":"pickaxe","level":1,"speed":2.0,"damage":2,"max_stack":1},
    "wood_axe":{"name":"木斧","kind":"tool","tool":"axe","level":1,"speed":2.0,"damage":3,"max_stack":1},
    "wood_shovel":{"name":"木铲","kind":"tool","tool":"shovel","level":1,"speed":2.0,"damage":2,"max_stack":1},
    "wood_sword":{"name":"木剑","kind":"tool","tool":"sword","level":1,"speed":1.0,"damage":4,"max_stack":1},
    "stone_pickaxe":{"name":"石镐","kind":"tool","tool":"pickaxe","level":2,"speed":3.5,"damage":3,"max_stack":1},
    "stone_axe":{"name":"石斧","kind":"tool","tool":"axe","level":2,"speed":3.5,"damage":4,"max_stack":1},
    "stone_shovel":{"name":"石铲","kind":"tool","tool":"shovel","level":2,"speed":3.5,"damage":2,"max_stack":1},
    "stone_sword":{"name":"石剑","kind":"tool","tool":"sword","level":2,"speed":1.0,"damage":6,"max_stack":1},
    "iron_pickaxe":{"name":"铁镐","kind":"tool","tool":"pickaxe","level":3,"speed":5.5,"damage":4,"max_stack":1},
    "iron_axe":{"name":"铁斧","kind":"tool","tool":"axe","level":3,"speed":5.5,"damage":5,"max_stack":1},
    "iron_shovel":{"name":"铁铲","kind":"tool","tool":"shovel","level":3,"speed":5.5,"damage":3,"max_stack":1},
    "iron_sword":{"name":"铁剑","kind":"tool","tool":"sword","level":3,"speed":1.0,"damage":8,"max_stack":1},
    "diamond_pickaxe":{"name":"钻石镐","kind":"tool","tool":"pickaxe","level":4,"speed":8.0,"damage":5,"max_stack":1},
    "diamond_axe":{"name":"钻石斧","kind":"tool","tool":"axe","level":4,"speed":8.0,"damage":6,"max_stack":1},
    "diamond_shovel":{"name":"钻石铲","kind":"tool","tool":"shovel","level":4,"speed":8.0,"damage":4,"max_stack":1},
    "diamond_sword":{"name":"钻石剑","kind":"tool","tool":"sword","level":4,"speed":1.0,"damage":10,"max_stack":1},
    "iron_helmet":{"name":"铁头盔","kind":"armor","slot":"head","armor":2,"max_stack":1},
    "iron_chestplate":{"name":"铁胸甲","kind":"armor","slot":"chest","armor":6,"max_stack":1},
    "iron_leggings":{"name":"铁护腿","kind":"armor","slot":"legs","armor":5,"max_stack":1},
    "iron_boots":{"name":"铁靴子","kind":"armor","slot":"feet","armor":2,"max_stack":1},
    "diamond_helmet":{"name":"钻石头盔","kind":"armor","slot":"head","armor":3,"max_stack":1},
    "diamond_chestplate":{"name":"钻石胸甲","kind":"armor","slot":"chest","armor":8,"max_stack":1},
    "diamond_leggings":{"name":"钻石护腿","kind":"armor","slot":"legs","armor":6,"max_stack":1},
    "diamond_boots":{"name":"钻石靴子","kind":"armor","slot":"feet","armor":3,"max_stack":1},
}
SMELTING = {"iron_ore":"iron_ingot","sand":"glass","raw_meat":"cooked_meat"}
FUEL = {"coal":8.0,"wood":3.0,"planks":1.5,"stick":0.5,"crafting_table":2.0}
ARMOR_SLOTS = ["head","chest","legs","feet"]

RECIPES = [
    {"pattern":["#"],"key":{"#":"wood"},"result":("planks",4),"size":2},
    {"pattern":["#","#"],"key":{"#":"planks"},"result":("stick",4),"size":2},
    {"pattern":["##","##"],"key":{"#":"planks"},"result":("crafting_table",1),"size":2},
    {"pattern":["C","S"],"key":{"C":"coal","S":"stick"},"result":("torch",4),"size":2},
    {"pattern":["###","# #","###"],"key":{"#":"cobblestone"},"result":("furnace",1),"size":3},
    {"pattern":["###"," S "," S "],"key":{"#":"planks","S":"stick"},"result":("wood_pickaxe",1),"size":3},
    {"pattern":["###"," S "," S "],"key":{"#":"cobblestone","S":"stick"},"result":("stone_pickaxe",1),"size":3},
    {"pattern":["###"," S "," S "],"key":{"#":"iron_ingot","S":"stick"},"result":("iron_pickaxe",1),"size":3},
    {"pattern":["###"," S "," S "],"key":{"#":"diamond","S":"stick"},"result":("diamond_pickaxe",1),"size":3},
    {"pattern":["##","#S"," S"],"key":{"#":"planks","S":"stick"},"result":("wood_axe",1),"size":3},
    {"pattern":["##","#S"," S"],"key":{"#":"cobblestone","S":"stick"},"result":("stone_axe",1),"size":3},
    {"pattern":["##","#S"," S"],"key":{"#":"iron_ingot","S":"stick"},"result":("iron_axe",1),"size":3},
    {"pattern":["##","#S"," S"],"key":{"#":"diamond","S":"stick"},"result":("diamond_axe",1),"size":3},
    {"pattern":["#","#","S"],"key":{"#":"planks","S":"stick"},"result":("wood_sword",1),"size":3},
    {"pattern":["#","#","S"],"key":{"#":"cobblestone","S":"stick"},"result":("stone_sword",1),"size":3},
    {"pattern":["#","#","S"],"key":{"#":"iron_ingot","S":"stick"},"result":("iron_sword",1),"size":3},
    {"pattern":["#","#","S"],"key":{"#":"diamond","S":"stick"},"result":("diamond_sword",1),"size":3},
    {"pattern":["#","S"],"key":{"#":"planks","S":"stick"},"result":("wood_shovel",1),"size":3},
    {"pattern":["#","S"],"key":{"#":"cobblestone","S":"stick"},"result":("stone_shovel",1),"size":3},
    {"pattern":["#","S"],"key":{"#":"iron_ingot","S":"stick"},"result":("iron_shovel",1),"size":3},
    {"pattern":["#","S"],"key":{"#":"diamond","S":"stick"},"result":("diamond_shovel",1),"size":3},
    {"pattern":["###","# #"],"key":{"#":"iron_ingot"},"result":("iron_helmet",1),"size":3},
    {"pattern":["# #","###","###"],"key":{"#":"iron_ingot"},"result":("iron_chestplate",1),"size":3},
    {"pattern":["###","# #","# #"],"key":{"#":"iron_ingot"},"result":("iron_leggings",1),"size":3},
    {"pattern":["# #","# #"],"key":{"#":"iron_ingot"},"result":("iron_boots",1),"size":3},
    {"pattern":["###","# #"],"key":{"#":"diamond"},"result":("diamond_helmet",1),"size":3},
    {"pattern":["# #","###","###"],"key":{"#":"diamond"},"result":("diamond_chestplate",1),"size":3},
    {"pattern":["###","# #","# #"],"key":{"#":"diamond"},"result":("diamond_leggings",1),"size":3},
    {"pattern":["# #","# #"],"key":{"#":"diamond"},"result":("diamond_boots",1),"size":3},
]

def match_recipe(grid, gs):
    cells = [(x,y,grid[y][x]) for y in range(gs) for x in range(gs) if grid[y][x]]
    if not cells: return None
    mx = min(c[0] for c in cells); xx = max(c[0] for c in cells)
    my = min(c[1] for c in cells); xy = max(c[1] for c in cells)
    w, h = xx-mx+1, xy-my+1
    for r in RECIPES:
        if r["size"] > gs: continue
        pat = r["pattern"]; pw = max(len(x) for x in pat); ph = len(pat)
        if pw != w or ph != h: continue
        ok = True
        for ry in range(ph):
            row = pat[ry]
            for rx in range(pw):
                ch = row[rx] if rx < len(row) else ' '
                cell = grid[my+ry][mx+rx]
                if ch == ' ' and cell is not None: ok = False; break
                if ch != ' ' and cell != r["key"][ch]: ok = False; break
            if not ok: break
        if ok: return r
    return None

def is_solid_tile(world, tx, ty):
    if tx < 0 or tx >= world.w: return True
    if ty < 0: return False
    if ty >= world.h: return True
    b = world.tiles[ty][tx]
    if b is None: return False
    return BLOCK_DATA[b]["solid"]

def resolve_entity_x(e, world):
    r = e.rect(); x0, x1 = r.x//TILE, (r.x+r.w-1)//TILE
    y0, y1 = r.y//TILE, (r.y+r.h-1)//TILE
    mn = mx = None
    for ty in range(y0, y1+1):
        for tx in range(x0, x1+1):
            if is_solid_tile(world, tx, ty):
                if mn is None or tx < mn: mn = tx
                if mx is None or tx > mx: mx = tx
    if mn is None: return
    if e.vx > 0: e.x = mn*TILE - e.w; e.vx = 0
    elif e.vx < 0: e.x = (mx+1)*TILE; e.vx = 0

def resolve_entity_y(e, world):
    r = e.rect(); x0, x1 = r.x//TILE, (r.x+r.w-1)//TILE
    y0, y1 = r.y//TILE, (r.y+r.h-1)//TILE
    mn = mx = None
    for ty in range(y0, y1+1):
        for tx in range(x0, x1+1):
            if is_solid_tile(world, tx, ty):
                if mn is None or ty < mn: mn = ty
                if mx is None or ty > mx: mx = ty
    if mn is None: return
    if e.vy > 0: e.y = mn*TILE - e.h; e.vy = 0; e.on_ground = True
    elif e.vy < 0: e.y = (mx+1)*TILE; e.vy = 0

class World:
    def __init__(self, w, h, seed=None):
        self.w, self.h = w, h
        self.seed = seed if seed is not None else random.randint(1,10**9)
        self.tiles = [[None]*w for _ in range(h)]
        self.changes = {}
        self.heights = []
        self.generate()

    def generate(self):
        rng = random.Random(self.seed)
        p1,p2,p3 = rng.random()*6.28, rng.random()*6.28, rng.random()*6.28
        for x in range(self.w):
            h = int(58 + 14*math.sin(x*0.021+p1) + 6*math.sin(x*0.055+p2) + 2.5*math.sin(x*0.14+p3))
            self.heights.append(h)
            for y in range(self.h):
                if y < h: self.tiles[y][x] = None
                elif y == h: self.tiles[y][x] = "grass"
                elif y <= h+4: self.tiles[y][x] = "dirt"
                else: self.tiles[y][x] = "stone"
        q1,q2,q3 = rng.random()*6.28, rng.random()*6.28, rng.random()*6.28
        for y in range(self.h):
            for x in range(self.w):
                if self.tiles[y][x] != "stone" or y < self.heights[x]+6: continue
                n = math.sin(x*0.09+q1)*math.cos(y*0.13+q2) + math.sin(x*0.045+y*0.07+q3)
                if n > 1.15: self.tiles[y][x] = None
        for y in range(self.h):
            for x in range(self.w):
                if self.tiles[y][x] != "stone": continue
                r = rng.random()
                if r < 0.013: self.tiles[y][x] = "coal_ore"
                elif r < 0.019: self.tiles[y][x] = "iron_ore"
                elif r < 0.023 and y > 95: self.tiles[y][x] = "diamond_ore"
        x = 5
        while x < self.w-5:
            x += 4 + rng.randint(0,7)
            if x >= self.w-5: break
            h = self.heights[x]
            if self.tiles[h][x] != "grass": continue
            th = 4 + rng.randint(0,3)
            for i in range(1,th+1):
                if h-i >= 0: self.tiles[h-i][x] = "wood"
            top = h-th
            for dy in range(-2,3):
                for dx in range(-2,3):
                    if dx*dx+dy*dy > 5: continue
                    ax, ay = x+dx, top+dy
                    if 0 <= ax < self.w and 0 <= ay < self.h and self.tiles[ay][ax] is None:
                        self.tiles[ay][ax] = "leaves"

    def apply_changes(self, changes):
        for k, v in changes.items():
            try: x, y = map(int, k.split(","))
            except: continue
            if 0 <= x < self.w and 0 <= y < self.h:
                self.tiles[y][x] = v; self.changes[k] = v

    def set(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.tiles[y][x] = v
            self.changes[f"{x},{y}"] = v

    def surface_y(self, x):
        for y in range(self.h):
            if self.tiles[y][x] is not None: return y
        return self.h-1

class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.w, self.h = 22, 42
        self.vx = self.vy = 0
        self.on_ground = False
        self.facing = 1
        self.health = self.max_health = 100
        self.hunger = self.max_hunger = 100
        self.hotbar = [None]*9
        self.backpack = [None]*27
        self.armor = {"head":None,"chest":None,"legs":None,"feet":None}
        self.selected = 0
        self.hurt_timer = 0
        self.attack_cd = 0
        self.regen_timer = 0
        self.flying = False
        self.gamemode = "survival"
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.w, self.h)
    def selected_item(self): return self.hotbar[self.selected]
    def get_tool(self):
        it = self.selected_item()
        if it and ITEM_DATA[it["id"]]["kind"] == "tool": return ITEM_DATA[it["id"]]
        return None
    def armor_value(self):
        return sum(ITEM_DATA[self.armor[s]["id"]].get("armor",0) for s in ARMOR_SLOTS if self.armor[s])
    def take_damage(self, dmg):
        if self.gamemode == "creative": return
        red = min(0.8, self.armor_value()/25.0)
        self.health -= dmg*(1-red)
        self.hurt_timer = 0.4
    def mining_speed(self, bid):
        if self.gamemode == "creative": return 999
        b = BLOCK_DATA[bid]; t = self.get_tool()
        if t:
            if b["tool"] and t["tool"] == b["tool"]:
                return t["speed"] if t["level"] >= b["level"] else 0.4
            return 0.4
        return 0.5
    def can_harvest(self, bid):
        if self.gamemode == "creative": return True
        b = BLOCK_DATA[bid]
        if b["level"] == 0: return True
        t = self.get_tool()
        return bool(t and b["tool"] and t["tool"] == b["tool"] and t["level"] >= b["level"])
    def attack_damage(self):
        t = self.get_tool()
        return t["damage"] if t else 1
    def give_item(self, item):
        ms = ITEM_DATA[item["id"]]["max_stack"]
        for inv in (self.hotbar, self.backpack):
            for i in range(len(inv)):
                s = inv[i]
                if s and s["id"] == item["id"] and s["count"] < ms:
                    take = min(ms-s["count"], item["count"])
                    s["count"] += take; item["count"] -= take
                    if item["count"] <= 0: return True
        for inv in (self.hotbar, self.backpack):
            for i in range(len(inv)):
                if inv[i] is None:
                    inv[i] = item; return True
        return False
    def add_item_id(self, iid, n=1):
        return self.give_item({"id":iid,"count":n})

class Monster:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.w, self.h = 24, 42
        self.vx = self.vy = 0
        self.on_ground = False
        self.health = self.max_health = 20
        self.hurt_timer = 0; self.attack_cd = 0; self.knockback_vx = 0
        self.facing = 1; self.dead = False; self.burn_timer = 0
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.w, self.h)
    def update(self, game, dt):
        p = game.player
        if game.light_factor > 0.7:
            self.burn_timer += dt
            if self.burn_timer > 0.8: self.health -= dt*9
        else: self.burn_timer = 0
        dx = (p.x+p.w/2)-(self.x+self.w/2); dy = (p.y+p.h/2)-(self.y+self.h/2)
        dist = math.hypot(dx, dy); speed = 90
        if dist < 600:
            if abs(dx) > 4:
                self.vx = speed if dx > 0 else -speed
                self.facing = 1 if dx > 0 else -1
            else: self.vx = 0
            if self.on_ground and abs(dx) < 90 and dy < -40: self.vy = -600
        else: self.vx = 0
        if abs(self.knockback_vx) > 1: self.vx = self.knockback_vx; self.knockback_vx *= 0.85
        else: self.knockback_vx = 0
        self.vy = min(self.vy + GRAVITY*dt, 1200)
        self.x += self.vx*dt; resolve_entity_x(self, game.world)
        self.y += self.vy*dt; self.on_ground = False; resolve_entity_y(self, game.world)
        self.attack_cd -= dt
        if dist < 36 and self.attack_cd <= 0:
            p.take_damage(4); self.attack_cd = 1.0
            p.vx = 220 if dx > 0 else -220
        if self.hurt_timer > 0: self.hurt_timer -= dt
        if self.health <= 0: self.dead = True
    def draw(self, screen, cam_x, cam_y):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        skin = (255,120,120) if (self.hurt_timer > 0 and int(self.hurt_timer*20)%2==0) else (110,160,100)
        pygame.draw.rect(s, skin, (4,0,16,13))
        pygame.draw.rect(s, (200,40,40), (7,6,3,3)); pygame.draw.rect(s, (200,40,40), (14,6,3,3))
        pygame.draw.rect(s, (50,90,70), (3,13,18,16))
        pygame.draw.rect(s, (40,60,50), (4,29,6,13)); pygame.draw.rect(s, (40,60,50), (14,29,6,13))
        pygame.draw.rect(s, skin, (0,14,3,12)); pygame.draw.rect(s, skin, (21,14,3,12))
        if self.facing < 0: s = pygame.transform.flip(s, True, False)
        screen.blit(s, (int(self.x)-cam_x, int(self.y)-cam_y))
        bx = int(self.x)-cam_x; by = int(self.y)-cam_y-8
        pygame.draw.rect(screen, (60,20,20), (bx, by, self.w, 4))
        hp = max(0, self.health/self.max_health)
        pygame.draw.rect(screen, (220,60,60), (bx, by, int(self.w*hp), 4))

class Animal:
    def __init__(self, x, y, kind):
        self.x, self.y = x, y; self.kind = kind
        self.w, self.h = 26, 22
        self.vx = self.vy = 0; self.on_ground = False
        self.facing = random.choice([-1,1])
        self.health = self.max_health = 10
        self.hurt_timer = 0; self.knockback_vx = 0; self.flee_timer = 0
        self.wander_timer = random.uniform(0.5,3.0); self.dead = False
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.w, self.h)
    def update(self, game, dt):
        p = game.player
        if self.hurt_timer > 0: self.hurt_timer -= dt
        dx = (p.x+p.w/2)-(self.x+self.w/2)
        if self.flee_timer > 0:
            self.flee_timer -= dt
            d = -1 if dx > 0 else 1; self.facing = d; self.vx = d*140
            if self.on_ground and random.random() < 0.02: self.vy = -450
        else:
            self.wander_timer -= dt
            if self.wander_timer <= 0:
                self.wander_timer = random.uniform(1.5,4.0)
                r = random.random()
                if r < 0.35: self.vx = 0
                else:
                    d = 1 if r < 0.68 else -1; self.facing = d; self.vx = d*55
            if self.on_ground and self.vx != 0 and random.random() < 0.008: self.vy = -420
        if abs(self.knockback_vx) > 1: self.vx = self.knockback_vx; self.knockback_vx *= 0.85
        else: self.knockback_vx = 0
        self.vy = min(self.vy + GRAVITY*dt, 1200)
        old_x = self.x
        self.x += self.vx*dt; resolve_entity_x(self, game.world)
        if self.vx != 0 and abs(self.x-old_x) < 0.6:
            self.facing *= -1; self.vx = 0; self.wander_timer = random.uniform(0.4,1.2)
        self.y += self.vy*dt; self.on_ground = False; resolve_entity_y(self, game.world)
        if self.health <= 0: self.dead = True
    def draw(self, screen, cam_x, cam_y):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        if self.kind == "pig": body_col=(240,155,160); head_col=(250,175,180)
        else: body_col=(235,235,235); head_col=(250,250,250)
        pygame.draw.ellipse(s, body_col, (2,5,20,13))
        pygame.draw.rect(s, body_col, (6,16,4,6)); pygame.draw.rect(s, body_col, (15,16,4,6))
        if self.facing > 0:
            pygame.draw.rect(s, head_col, (17,2,9,11)); pygame.draw.rect(s, (30,30,30), (22,5,2,2))
        else:
            pygame.draw.rect(s, head_col, (0,2,9,11)); pygame.draw.rect(s, (30,30,30), (3,5,2,2))
        if self.hurt_timer > 0 and int(self.hurt_timer*20)%2==0:
            tint = pygame.Surface(s.get_size(), pygame.SRCALPHA); tint.fill((255,80,80,130)); s.blit(tint,(0,0))
        screen.blit(s, (int(self.x)-cam_x, int(self.y)-cam_y))

class Drop:
    def __init__(self, x, y, iid, count=1):
        self.x, self.y = x, y; self.item_id = iid; self.count = count
        self.vx = random.uniform(-90,90); self.vy = random.uniform(-260,-100)
        self.age = 0.0; self.on_ground = False; self.w = self.h = 14
    def update(self, world, dt):
        self.age += dt
        self.vy = min(self.vy + GRAVITY*dt, 1200)
        self.x += self.vx*dt; self.y += self.vy*dt
        r = pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        x0, x1 = r.x//TILE, (r.x+r.w-1)//TILE; y0, y1 = r.y//TILE, (r.y+r.h-1)//TILE
        for ty in range(y0, y1+1):
            for tx in range(x0, x1+1):
                if is_solid_tile(world, tx, ty):
                    if self.vy > 0:
                        self.y = ty*TILE - self.h; self.vy = 0; self.on_ground = True; self.vx *= 0.7
                    break
        if self.on_ground:
            self.vx *= 0.9
            if abs(self.vx) < 4: self.vx = 0
    def draw(self, screen, cam_x, cam_y):
        bob = math.sin(self.age*4)*3
        icon = ITEM_ICONS.get(self.item_id)
        if icon:
            small = pygame.transform.scale(icon, (20,20))
            screen.blit(small, (int(self.x)-cam_x-3, int(self.y)-cam_y+bob-3))

# --- 资源加载 ---
BLOCK_TEX = {}
ITEM_ICONS = {}

def load_image(name, size, fallback=None):
    p = os.path.join(ASSET_DIR, name + ".png")
    if os.path.isfile(p):
        try:
            img = pygame.image.load(p).convert_alpha()
            return pygame.transform.scale(img, size)
        except: pass
    if fallback is None:
        fallback = pygame.Surface(size, pygame.SRCALPHA); fallback.fill((200,0,200,120))
    return pygame.transform.scale(fallback, size) if fallback.get_size() != size else fallback

def make_fallback_block(color):
    s = pygame.Surface((TILE,TILE), pygame.SRCALPHA); s.fill(color)
    for _ in range(80):
        x, y = random.randrange(TILE), random.randrange(TILE); d = random.randint(-20,20)
        c = (max(0,min(255,color[0]+d)), max(0,min(255,color[1]+d)), max(0,min(255,color[2]+d)))
        pygame.draw.rect(s, c, (x,y,2,2))
    pygame.draw.rect(s, (0,0,0,60), (0,0,TILE,TILE), 1)
    return s

def make_item_fallback(iid, data):
    s = pygame.Surface((36,36), pygame.SRCALPHA)
    if data.get("kind") == "food":
        if iid == "apple":
            pygame.draw.circle(s, (220,40,40), (18,22), 10)
            pygame.draw.circle(s, (255,90,90), (14,18), 4)
            pygame.draw.rect(s, (100,60,20), (16,6,3,10))
            pygame.draw.ellipse(s, (80,160,60), (19,4,8,5))
        elif iid == "raw_meat":
            pygame.draw.ellipse(s, (200,80,80), (4,8,28,20))
            pygame.draw.ellipse(s, (235,150,150), (9,12,14,9))
        elif iid == "cooked_meat":
            pygame.draw.ellipse(s, (140,70,40), (4,8,28,20))
            pygame.draw.ellipse(s, (180,110,70), (9,12,14,9))
        return s
    if data.get("kind") == "armor":
        if "iron" in iid: mat = (200,200,210)
        elif "diamond" in iid: mat = (140,240,240)
        else: mat = (170,130,90)
        slot = data.get("slot","head")
        if slot == "head":
            pygame.draw.arc(s, mat, (8,6,20,20), math.pi, 2*math.pi, 4)
            pygame.draw.line(s, mat, (8,16), (28,16), 4)
        elif slot == "chest": pygame.draw.rect(s, mat, (8,8,20,22), 3)
        elif slot == "legs":
            pygame.draw.rect(s, mat, (10,10,6,20), 3); pygame.draw.rect(s, mat, (20,10,6,20), 3)
            pygame.draw.line(s, mat, (10,12), (26,12), 3)
        elif slot == "feet":
            pygame.draw.rect(s, mat, (8,20,8,10), 3); pygame.draw.rect(s, mat, (20,20,8,10), 3)
        return s
    tool = data.get("tool")
    if "wood_" in iid: mat = (160,110,60)
    elif "stone_" in iid: mat = (140,140,150)
    elif "iron_" in iid: mat = (220,220,230)
    elif "diamond_" in iid: mat = (120,240,240)
    else: mat = (200,200,200)
    if tool == "pickaxe":
        pygame.draw.line(s, (139,90,43), (8,28), (26,10), 4); pygame.draw.line(s, mat, (18,16), (32,8), 4)
    elif tool == "sword":
        pygame.draw.line(s, (139,90,43), (8,28), (14,22), 4); pygame.draw.line(s, mat, (12,24), (30,6), 5)
    elif tool == "axe":
        pygame.draw.line(s, (139,90,43), (8,28), (24,10), 4); pygame.draw.rect(s, mat, (20,4,11,11))
    elif tool == "shovel":
        pygame.draw.line(s, (139,90,43), (8,28), (24,10), 4); pygame.draw.rect(s, mat, (22,4,9,11))
    else:
        col = (200,200,200)
        if iid == "stick": col = (139,90,43)
        elif iid == "coal": col = (40,40,40)
        elif iid == "iron_ingot": col = (210,210,220)
        elif iid == "iron_ore": col = (170,145,130)
        elif iid == "diamond": col = (120,240,240)
        pygame.draw.rect(s, col, (7,12,22,12)); pygame.draw.rect(s, (0,0,0), (7,12,22,12), 1)
    return s

def build_assets():
    BLOCK_TEX.clear(); ITEM_ICONS.clear()
    for bid, data in BLOCK_DATA.items():
        fb = make_fallback_block(data["color"])
        if bid == "grass": pygame.draw.rect(fb, (110,185,85), (0,0,TILE,7))
        elif bid == "wood":
            for x in range(4,TILE,8): pygame.draw.line(fb, (90,60,30), (x,0), (x,TILE), 1)
        elif bid == "planks":
            for y in range(6,TILE,8): pygame.draw.line(fb, (150,100,60), (0,y), (TILE,y), 1)
        elif bid in ("coal_ore","iron_ore","diamond_ore"):
            dot = {"coal_ore":(30,30,30),"iron_ore":(215,180,150),"diamond_ore":(120,240,240)}[bid]
            for _ in range(6):
                pygame.draw.circle(fb, dot, (random.randint(4,28), random.randint(4,28)), random.randint(2,4))
        elif bid == "crafting_table":
            pygame.draw.rect(fb, (100,60,30), (4,4,TILE-8,TILE-8), 2)
            pygame.draw.line(fb, (60,30,10), (TILE//2,4), (TILE//2,TILE-4), 2)
            pygame.draw.line(fb, (60,30,10), (4,TILE//2), (TILE-4,TILE//2), 2)
        elif bid == "furnace":
            pygame.draw.rect(fb, (60,60,65), (4,4,TILE-8,TILE-8), 2)
            pygame.draw.rect(fb, (30,30,30), (8,TILE-14,TILE-16,10))
            pygame.draw.rect(fb, (255,150,40), (10,TILE-12,TILE-20,6))
        elif bid == "glass":
            fb.fill((0,0,0,0))
            pygame.draw.rect(fb, (170,220,240,140), (0,0,TILE,TILE), 2)
            pygame.draw.line(fb, (220,240,250,200), (4,4), (TILE-6,TILE-6), 1)
        elif bid == "torch":
            fb.fill((0,0,0,0))
            pygame.draw.rect(fb, (120,80,40), (TILE//2-3, TILE//2, 6, TILE//2))
            pygame.draw.circle(fb, (255,200,50), (TILE//2, TILE//2), 6)
            pygame.draw.circle(fb, (255,240,150), (TILE//2, TILE//2), 3)
        BLOCK_TEX[bid] = load_image("block_"+bid, (TILE,TILE), fb)
    for iid, data in ITEM_DATA.items():
        if data["kind"] == "block": ITEM_ICONS[iid] = BLOCK_TEX[data["block"]]
        else: ITEM_ICONS[iid] = load_image("item_"+iid, (36,36), make_item_fallback(iid, data))

def max_stack(iid): return ITEM_DATA[iid]["max_stack"]