# 前言
* 本项目参考了这个库[MapleStoryAutoLevelUp](https://github.com/KenYu910645/MapleStoryAutoLevelUp) 
* 只要是市面上的079版本的冒险岛都可以使用，测试过的版本有：wingms, mapleStoryGo。
* 还有，开挂是不对的，本人已经被封了3个号。

# 功能
 * [x] mini地图识别 (还有问题，需要调试)
 * [x] 角色识别 
 * [x] 怪物识别
 * [ ] 地图绘制 
 * [x] 自动打怪
 * [x] 自动吃药
 * [x] 测谎报警 + 谎言探测仪跟随（白形粘滞，褪色后跟旋转目标；绿框只做干扰，auto_follow 可关）
 * [x] F1 / F2 / F3 / F4 / F5 多模式挂机（启动空闲，按键切换）

# F1 / F2 / F3 / F4 / F5 挂机逻辑与按键

配置见 `config/config_custom.yaml` → `profiles:`。启动后默认**空闲**，按对应功能键加载配置并开始，**再按同键关闭**。

## 公共按键（`key:`）

| 按键 | 作用 |
|------|------|
| ← / → | 左右移动 / 巡逻换向 |
| ↑ / ↓ | 上下（F2 在平台偏高时会按 ↓） |
| `A` | 群攻（`aoe_skill`） |
| `Z` | 闪现（仅 F1 开启） |
| `End` | HP 药水（全局）；F2 另作养宠物 |
| `Home` | MP 药水 |
| `F1` / `F2` / `F3` / `F4` / `F5` | 切换对应挂机配置 |
| `F11` | 检测/猎杀相关开关（日志提示） |

测谎弹出时会暂停挂机；`auto_follow=true` 时会自动跟形（需 bot 与游戏同为管理员权限，鼠标才能动）。

---

## F1 — 甩锅侠12139 · 全图黄点边缘巡逻

**定位**：名字牌 `character/name.png`（甩锅侠12139）

**挂机逻辑**
- `flash_patrol`：左右巡逻
- 用小地图**黄点 X** 判断是否到地图左右边缘（约 6%）再换向
- 边缘卡住才按「顶墙」逻辑换向；中区不靠怪物左右数转向
- **不开**怪物模板识别

**攻击**
- 只按 `A`，间隔约 **0.5–0.75s**
- **开 Z 闪现**，约每 7.5–8.5s 闪一次（左右移动时）

**Buff**（施法会停顿移动/攻击约 2.5s；开挂先加完再开战）
| 键 | 间隔 |
|----|------|
| `W` | 2 分钟 |
| `Shift` | 5 分钟 |
| `End` | 25 分钟 |

---

## F2 — 甩锅侠12138 · 云彩公园中区巡逻（跳 A）

**定位**：名字牌 `character/name_12138.png`（甩锅侠12138）

**挂机逻辑**
- `flash_patrol`：左右巡逻，小地图黄点 **约 10%～90%** 中区来回；每 **10 次往返**后下一段扫 **全图 0%～100%**，再回到中区
- 黄点 Y 偏高（平台）时按住 `↓`
- **不开 Z**（本图不能闪现）
- **不开**怪物识别 / 怪物转向
- **不加战斗 Buff**，开挂即打

**攻击**
- 连招 `S` → 0.1s → `A`（每轮都是 S→A）
- 每轮间隔 **固定 0.8s**

**养宠物**（无施法动作，**不停顿**）
| 键 | 间隔 |
|----|------|
| `End` | 15 分钟（开 F2 约 2s 先喂一次） |

---

## F3 — 甩锅侠12139 · 通天塔定点站桩

**定位**：名字牌 `character/name.png`（甩锅侠12139）

**挂机逻辑**
- **定点站桩**：开启瞬间锁定小地图黄点为中心
- 偏离中心超过约 **6px** 才走回，不左右扫图
- **不开**闪现、**不开**怪物识别

**攻击**
- 只按 `A`，间隔约 **1.5–2.0s**

**Buff**：无（开挂即攻击）

**宠物**：`End` 每 **12 分钟**喂一次（开 F3 约 2s 先喂一次）

---

## F4 — 牧师 · 遗迹之墓1 底层治愈术巡逻

**定位**：小地图黄点（名字牌 `character/name_alfred.png` 只作监视窗标注，不参与转向）

**挂机逻辑**
- `flash_patrol`：在**底层平台**左右**完整巡逻**，但移动被切成 **2–5s 的随机小段**
  （`search_leg_min/max_seconds`）：每段走完**不掉头**，站住 `search_leg_pause_s: 0.35s`
  放一次治愈术，再继续同一方向；日志是 `[Patrol] leg burst 3.12s → 停 0.35s 继续 right`
- 一路扫到地图左右边缘（黄点 X 进 `search_edge_ratio: 0.02` ≈ 2%）才**掉头**
- 单方向最多走 `search_max_leg_seconds: 30s`（卡墙兜底，超了也掉头，不会一直顶墙）
- **掉头后瞬移一次**：`flip_teleport_key: "x"`，等 0.18s 让转身生效，
  然后 `teleport_in_dir()` **先把方向键补按住**再按住 X 0.12s —— 瞬移只在方向键按着时
  才朝那个方向飞，之前先松方向键再按 X 会按空（日志有 `flip teleport` 但人不动）
  - `flip_teleport_press_s: 0.12`（被吞就加到 0.2）；`flip_teleport_cooldown_s: 1.0` 防连按
  - `walk_teleport.enable=false`，不走 Z
- `search_bottom_y_min_ratio: 0.60`：黄点 Y 跑到 60% 以上（人到了上层）时补一次
  「短暂 `↓` + 跳」穿平台，**不是**一直按住 `↓`（按住 ↓ 人物是蹲着的，根本不会走）
  - `bottom_drop_timeout_s: 3.0` 内 Y 没往下走就停手，`bottom_drop_retry_s: 20.0` 后再试
- **不开** Z 闪现、**不开**怪物识别（`monster_detect.enable=false`，不需要骷髅狗素材）

> 想要「不起整层、只在原地附近小碎步」：把 `search_leg_keep_dir` 设 `false`，
> 每小段走完就掉头+瞬移，左右抵消只在附近晃。

**攻击**
- 治愈术挂在 `A`（`key.aoe_skill`），只按 `A`、不连招，一轮约 **1.5–1.9s**
- 每次按 A 会**按住 0.8s**（`aoe_skill.press_duration`），不是 50ms 轻点——轻点经常被吞招
- 治愈术本来就是自身中心的群疗 + 对不死系（骷髅狗）伤害，所以边走边按即可边巡逻边清怪

**Buff**：无（`buff_skill.keys: []`，开挂即打）

> 小地图坐标（重要）：`minimap` 的固定框按 **1920x1080 客户端**写成 `(7,69,128,85)`，
> 但**面板高度是随地图变的**——遗迹之墓1 是 85、云彩公园4 是 **131**。固定框会把云彩公园
> 底部的玩家黄点裁掉、锁到标题栏那颗金色图标上（x 永远不动 → 到边缘也不回头）。
> 所以 `auto_detect_interval_s: 2.0` 会按地图自动探测面板框，固定框只作兜底，
> `ref_width/ref_height` 负责别的窗口尺寸按比例缩放。
>
> 还有一道兜底：`search_dot_stall_s: 4.0` —— 一直在走、但黄点 X 连续 4 秒完全不动
> （顶墙、或识别失灵锁到静态图标），就强制掉头，日志 `[Patrol] dot stall ...`。
>
> 调参：清怪慢就把 `aoe_skill.cooldown_min/max` 往下调（别低于 0.8s，会被施法动作吃掉）；
> 卡在上层回不来就把 `search_bottom_y_min_ratio` 调大（更早触发掉层），
> 或者确认游戏里的跳跃键确实是 `S`（`bottom_drop_jump_key`）。
>
> 蓝量：治愈术费蓝，`health_monitor.enable` 现在是 `false`（不自动喝药，F6/F7 也没注册）。
> 想自动喝蓝要把它改成 `true`（启动时生效，不是按 F4 生效），再调 `add_mp_percent`。

---

## F5 — 火枪手 · 云彩公园4 底层巡逻清怪

**定位**：小地图黄点（名字牌 `character/name_gunner.png` 只作监视窗标注）

**挂机逻辑**（和 F4 同一套底层巡逻骨架）
- `flash_patrol`：底层左右**完整巡逻**，移动切成 **2–5s 随机小段**
  （`search_leg_min/max_seconds`）：每段走完**不掉头**，站住 `search_leg_pause_s: 0.15s` 打一下，
  再继续同一方向；到左右边缘（黄点进 `search_edge_ratio: 0.03` ≈ 3%）才掉头
- 单方向最多走 `search_max_leg_seconds: 30s`（卡墙兜底）
- `search_bottom_y_min_ratio: 0.55`：黄点 Y 跑到 55% 以上（人到了上层）时补一次
  「短暂 `↓` + 跳」穿平台，3s 没往下走就停手 20s
- **不瞬移**（`flip_teleport_key: ""`）、**不加 buff**、**不养宠物**、**不开**怪物识别

**攻击**（A 是技能宏，所以要"打完先站住"）
- 沿用全局 `key.aoe_skill` = `A`，只按 `A`、不连招，点按 0.08s
- **按完 A 先站桩 `post_attack_freeze_s: 0.6s`**：技能宏没放完就走路会被打断，这段时间内
  方向键会被强制松开（`_move_pause_until`）。宏更长就调到 0.8–1.2
- **站桩结束后接一套 `Z → 转身 → X → 转回` 连招**（轻羽鞋 + 激退射击，往前窜很远很快）：
  激退射击是**反冲**，必须朝后放才把人往前推，所以中间要翻一次面向：
  ```
  Z(轻羽鞋) → 点一下反方向(转身) → X(激退射击) → 点回原方向 → 继续走
  ```
  - `followup_keys: ["z", "x"]`；`followup_gap` 要 ≥ 站桩时间（等宏跑完再起手）
  - **放 Z 之前先走起来**：`followup_settle_s: 0.05`（站着放 Z 常常不生效，只剩 X）
  - **Z 没按出去就不放 X**：`followup_skip_on_fail: true`，日志会打
    `[Combo] 起手键 'z' 没按出去 → 跳过后面的 x，避免单放`——这就是"单放一个 X"的拦截
  - **Z 之后先等 `followup_step_gap: 0.20`**（等轻羽鞋落地/起跳）再转身 → X；
    太小会出现"X 把人从空中打断，看起来只放了 X"
  - `followup_turn_tap_s: 0.05` 是转身点按的时长（够翻面向就行，按久了会走起来）
  - **X 放完再等 `followup_turn_back_delay_s: 0.30`** 才转回原方向——
    提前转回会把激退射击的反冲吃掉
  - 每个键按 `followup_press_duration: 0.12`；放不出就加到 0.2~0.3
  - **连招内部是固定节拍**（`combo_step_jitter: 0.0`）：Z→转身→X = `followup_step_gap 0.20` + 转身 0.05，
    X→转回 = `followup_turn_back_delay_s 0.30`，每套都一样，实测 Z→X 恒为 0.250s
  - 外层仍然随机：`timing_jitter: 0.35` 只管站桩、A→Z 的等待（×(1±35%)）
  - 走路停顿也随机：`search_leg_pause_jitter: 0.6`（每段之间停 0.15s × (1±60%)）
  - 走路本身长度本来就是随机的（`search_leg_min/max_seconds: 2–5s`），
    攻击间隔也是（`cooldown_min/max: 0.5–0.8s`）
  - `combo_debug: true` 会每套连招打一行 `[Combo] z@0.00 turn@0.25 x@0.25 turn_back@0.60`
    方便核对时序（调好可以关掉）
  - 嫌太频繁：`followup_cooldown_s: 1.5`（两套连招至少隔 1.5s）；想关掉：`followup_keys: []`
- 如果火枪手的攻击键不是 A：改全局 `key.aoe_skill`，或在 f5 profile 里覆盖
  `key: { aoe_skill: "你的键" }`；要走连招就写 `aoe_skill.attack_combo: ["s", "a"]`

---

## F4 — 牧师 · 遗迹之墓1 底层治愈术巡逻

**定位**：小地图黄点（名字牌 `character/name_alfred.png` 只作监视窗标注，不参与转向）

**挂机逻辑**
- `flash_patrol`：在**底层平台**左右**完整巡逻**，但移动被切成 **2–5s 的随机小段**
  （`search_leg_min/max_seconds`）：每段走完**不掉头**，站住 `search_leg_pause_s: 0.35s`
  放一次治愈术，再继续同一方向；日志是 `[Patrol] leg burst 3.12s → 停 0.35s 继续 right`
- 一路扫到地图左右边缘（黄点 X 进 `search_edge_ratio: 0.02` ≈ 2%）才**掉头**
- 单方向最多走 `search_max_leg_seconds: 30s`（卡墙兜底，超了也掉头，不会一直顶墙）
- **掉头后瞬移一次**：`flip_teleport_key: "x"`，等 0.18s 让转身生效，
  然后 `teleport_in_dir()` **先把方向键补按住**再按住 X 0.12s —— 瞬移只在方向键按着时
  才朝那个方向飞，之前先松方向键再按 X 会按空（日志有 `flip teleport` 但人不动）
  - `flip_teleport_press_s: 0.12`（被吞就加到 0.2）；`flip_teleport_cooldown_s: 1.0` 防连按
  - `walk_teleport.enable=false`，不走 Z
- `search_bottom_y_min_ratio: 0.60`：黄点 Y 跑到 60% 以上（人到了上层）时补一次
  「短暂 `↓` + 跳」穿平台，**不是**一直按住 `↓`（按住 ↓ 人物是蹲着的，根本不会走）
  - `bottom_drop_timeout_s: 3.0` 内 Y 没往下走就停手，`bottom_drop_retry_s: 20.0` 后再试
- **不开** Z 闪现、**不开**怪物识别（`monster_detect.enable=false`，不需要骷髅狗素材）

> 想要「不起整层、只在原地附近小碎步」：把 `search_leg_keep_dir` 设 `false`，
> 每小段走完就掉头+瞬移，左右抵消只在附近晃。

**攻击**
- 治愈术挂在 `A`（`key.aoe_skill`），只按 `A`、不连招，一轮约 **1.5–1.9s**
- 每次按 A 会**按住 0.8s**（`aoe_skill.press_duration`），不是 50ms 轻点——轻点经常被吞招
- 治愈术本来就是自身中心的群疗 + 对不死系（骷髅狗）伤害，所以边走边按即可边巡逻边清怪

**Buff**：无（`buff_skill.keys: []`，开挂即打）

> 小地图坐标（重要）：`minimap` 的固定框按 **1920x1080 客户端**写成 `(7,69,128,85)`，
> 但**面板高度是随地图变的**——遗迹之墓1 是 85、云彩公园4 是 **131**。固定框会把云彩公园
> 底部的玩家黄点裁掉、锁到标题栏那颗金色图标上（x 永远不动 → 到边缘也不回头）。
> 所以 `auto_detect_interval_s: 2.0` 会按地图自动探测面板框，固定框只作兜底，
> `ref_width/ref_height` 负责别的窗口尺寸按比例缩放。
>
> 还有一道兜底：`search_dot_stall_s: 4.0` —— 一直在走、但黄点 X 连续 4 秒完全不动
> （顶墙、或识别失灵锁到静态图标），就强制掉头，日志 `[Patrol] dot stall ...`。
>
> 调参：清怪慢就把 `aoe_skill.cooldown_min/max` 往下调（别低于 0.8s，会被施法动作吃掉）；
> 卡在上层回不来就把 `search_bottom_y_min_ratio` 调大（更早触发掉层），
> 或者确认游戏里的跳跃键确实是 `S`（`bottom_drop_jump_key`）。
>
> 蓝量：治愈术费蓝，`health_monitor.enable` 现在是 `false`（不自动喝药，F6/F7 也没注册）。
> 想自动喝蓝要把它改成 `true`（启动时生效，不是按 F4 生效），再调 `add_mp_percent`。

---

## F5 — 火枪手 · 云彩公园4 底层巡逻清怪

**定位**：小地图黄点（名字牌 `character/name_gunner.png` 只作监视窗标注）

**挂机逻辑**（和 F4 同一套底层巡逻骨架）
- `flash_patrol`：底层左右**完整巡逻**，移动切成 **2–5s 随机小段**
  （`search_leg_min/max_seconds`）：每段走完**不掉头**，站住 `search_leg_pause_s: 0.15s` 打一下，
  再继续同一方向；到左右边缘（黄点进 `search_edge_ratio: 0.03` ≈ 3%）才掉头
- 单方向最多走 `search_max_leg_seconds: 30s`（卡墙兜底）
- `search_bottom_y_min_ratio: 0.55`：黄点 Y 跑到 55% 以上（人到了上层）时补一次
  「短暂 `↓` + 跳」穿平台，3s 没往下走就停手 20s
- **不瞬移**（`flip_teleport_key: ""`）、**不加 buff**、**不养宠物**、**不开**怪物识别

**攻击**（A 是技能宏，所以要"打完先站住"）
- 沿用全局 `key.aoe_skill` = `A`，只按 `A`、不连招，点按 0.08s
- **按完 A 先站桩 `post_attack_freeze_s: 0.6s`**：技能宏没放完就走路会被打断，这段时间内
  方向键会被强制松开（`_move_pause_until`）。宏更长就调到 0.8–1.2
- **站桩结束后接一套 `Z → 转身 → X → 转回` 连招**（轻羽鞋 + 激退射击，往前窜很远很快）：
  激退射击是**反冲**，必须朝后放才把人往前推，所以中间要翻一次面向：
  ```
  Z(轻羽鞋) → 点一下反方向(转身) → X(激退射击) → 点回原方向 → 继续走
  ```
  - `followup_keys: ["z", "x"]`；`followup_gap` 要 ≥ 站桩时间（等宏跑完再起手）
  - **放 Z 之前先走起来**：`followup_settle_s: 0.05`（站着放 Z 常常不生效，只剩 X）
  - **Z 没按出去就不放 X**：`followup_skip_on_fail: true`，日志会打
    `[Combo] 起手键 'z' 没按出去 → 跳过后面的 x，避免单放`——这就是"单放一个 X"的拦截
  - **Z 之后先等 `followup_step_gap: 0.20`**（等轻羽鞋落地/起跳）再转身 → X；
    太小会出现"X 把人从空中打断，看起来只放了 X"
  - `followup_turn_tap_s: 0.05` 是转身点按的时长（够翻面向就行，按久了会走起来）
  - **X 放完再等 `followup_turn_back_delay_s: 0.30`** 才转回原方向——
    提前转回会把激退射击的反冲吃掉
  - 每个键按 `followup_press_duration: 0.12`；放不出就加到 0.2~0.3
  - **连招内部是固定节拍**（`combo_step_jitter: 0.0`）：Z→转身→X = `followup_step_gap 0.20` + 转身 0.05，
    X→转回 = `followup_turn_back_delay_s 0.30`，每套都一样，实测 Z→X 恒为 0.250s
  - 外层仍然随机：`timing_jitter: 0.35` 只管站桩、A→Z 的等待（×(1±35%)）
  - 走路停顿也随机：`search_leg_pause_jitter: 0.6`（每段之间停 0.15s × (1±60%)）
  - 走路本身长度本来就是随机的（`search_leg_min/max_seconds: 2–5s`），
    攻击间隔也是（`cooldown_min/max: 0.5–0.8s`）
  - `combo_debug: true` 会每套连招打一行 `[Combo] z@0.00 turn@0.25 x@0.25 turn_back@0.60`
    方便核对时序（调好可以关掉）
  - 嫌太频繁：`followup_cooldown_s: 1.5`（两套连招至少隔 1.5s）；想关掉：`followup_keys: []`
- 如果火枪手的攻击键不是 A：改全局 `key.aoe_skill`，或在 f5 profile 里覆盖
  `key: { aoe_skill: "你的键" }`；要走连招就写 `aoe_skill.attack_combo: ["s", "a"]`

---

## 对照一览

| | F1 | F2 | F3 | F4 | F5 |
|--|----|----|-----|-----|-----|
| 角色 | 12139 | 12138 | 12139 | 牧师 | 火枪手 |
| 移动 | 全图边缘巡逻 | 中区 10%～90%（每 10 往返全图一次） | 定点站桩 | 底层整层巡逻，2–5s 随机小段（段间站 0.35s 放治愈术），到边 2% 才掉头；偏上会 ↓+跳 | 底层整层巡逻，2–5s 随机小段（段间站 0.15s），到边 3% 才掉头；偏上会 ↓+跳 |
| 攻击 | `A` 0.5–0.75s | `S`+`A` 0.8s | `A` 0.7–1.0s | `A`（治愈术）按住 0.8s，每 1.5–1.9s 一次 | `A` 0.5–0.8s（点按） |
| `Z` 闪现 | 开 | 关 | 关 | 关 | 关 |
| 掉头瞬移 | 无 | 无 | 无 | `X` 一次（等 0.18s 再按） | 无 |
| Buff | 无 | 无 | 无 | 无 | 无 |
| 养宠物 | 无 | End 每 15 分 | End 每 12 分 | 无 | 无 |

## 警报误报（商城 / 上层平台云层）

进商城、或者人站在上层平台（背景是云）时反复响"小游戏出现提醒"，是两个阈值问题，已修：

| 现象 | 原因 | 处理 |
|--|--|--|
| 上层平台/商城一直报警 | `lie_intro_banner.png`（开场说明窗）阈值 `intro_match_threshold: 0.025` 太松，云层/商城图标在 **0.026** 就命中 | 降到 `0.008`（真说明窗是静态白窗，得分 ≈0.00x），代码里夹紧下限也从 0.012 放到 0.004 |
| 进商城报"掉线提醒" | 商城界面的「重新登录」文字被 OCR 命中 | 两个 alert 都加了 `suppress_keywords`（商城 / 现金商城 / CASH SHOP / SHOP），OCR 认到这些词就整帧跳过 |

被误报时的日志长这样，可以对照确认：

```
[ALERT] 小游戏出现提醒 via tmpl:lie_intro_banner.png (score=0.026, ...)
[ALERT] 掉线提醒 via ocr:重新登录 (score=0.000, ...)
```

如果哪天真的开场说明窗漏报了（几乎不会），把 `intro_match_threshold` 调回 `0.012` 试试。

# 环境依赖（含 CUDA 测谎 YOLO）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**有 NVIDIA 显卡（如 RTX 4070）时**，先装 CUDA 版 PyTorch，再装项目依赖：

```powershell
.\tools\setup_cuda_torch.bat
```

或手动：

```powershell
pip uninstall -y torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

验证：

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

启动后日志应出现：`[LieAlert] YOLO device=cuda:0 (...)`。配置项 `lie_alert.fade_yolo_device: auto`（可强制 `cpu` / `cuda:0`）。

离线测谎闸门（改代码后先跑这个再上号）：

```powershell
.\.venv\Scripts\python.exe tools\test_lie_follow_video.py --no-preview --video _debug_out\bilibili\BV1UWHz61ETm_game.mp4 --out _debug_out\lie_gate.mp4
```

看结尾 `VERDICT PASS/FAIL`。

# 1、识别角色 + 怪物 + miniMap
## 1-1、演示
![识别怪物演示](demo_gif/recognize_user_map_monster.gif)
## 1-2、素材库找到怪物素材
* [素材下载地址](https://maplestory.wiki/GMS/83/mob/1110101)
* 把走动的素材下载下载，放到`monster/下载的怪物名称`文件夹下
* 大概长这样![下载的怪物素材demo](demo_gif/monster.png)
* 如何调整配置
  * 打开`config/config_data.yaml`，找到`mob`字段
  * 添加新的怪物配置，示例如下：只要改这三个字段就行
```yaml
monsters: ["black_axe_stump"]  # 指定怪物文件夹，数组可多个
diff_thres: 0.46               # 匹配阈值（越小越严格）
scales: [1]                    # 缩放比例，官方素材不匹配时改: [0.7, 0.85, 1.0, 1.15]            # 每N帧检测一次 (1=每帧, 3=流畅优先)
  ```

# 2、地图绘制
TODO

# 3、单独测试称号定位

如果你只想验证 `character/title.png` 能不能定位到角色，不想直接跑完整挂机流程，可以先跑：

```powershell
python .\test\test_title_locator.py
```

默认会读取：

- `config/config_default.yaml`
- `config/config_custom.yaml`
- `test/test_image/screenshot.png`

并输出：

- `score`
- 是否命中 `hit=True/False`
- `title_loc`
- `player_loc`

同时会生成调试图：

- `screenshot/title_locator_debug.png`

如果要换测试图：

```powershell
python .\test\test_title_locator.py --image test\test_image\screenshot.png
```

## Star History

<a href="https://www.star-history.com/?repos=zhoufanglu%2Fmaplestory-auto-ds&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=zhoufanglu/maplestory-auto-ds&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=zhoufanglu/maplestory-auto-ds&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=zhoufanglu/maplestory-auto-ds&type=date&legend=top-left" />
 </picture>
</a>
