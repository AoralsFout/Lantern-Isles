# 《灯屿行记》 Blender 资产制作规范 v1

> 目标：为一款 2.5D 斜视角、昼夜柔光、低多边形箱庭探索游戏制作可组装的 3D 小资产。
> 交付必须经过 Blender 渲染预览并人工目检，不接受“只导出没看效果”。

## 0. 环境

- Blender：`D:\BlenderPortable\blender-4.2.9-windows-x64\blender.exe`（4.2.9 LTS，已安装，可 headless）
- Python：`C:\Users\32506\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（有 Pillow / numpy）
- 工程根目录：`E:\GodotProjects\xiang-ting-game`
- 运行示例：
  ```powershell
  & 'D:\BlenderPortable\blender-4.2.9-windows-x64\blender.exe' -b --python tools/blender/flora_spring.py
  ```
- 只写自己负责的模型目录、预览目录和 `tools/blender/<你的批次>.py`；不要改游戏脚本、其他组资产、不要碰 `project.godot`。
- 不要调用任何图像生成 API，不要下载外部模型；全部用 Blender 程序化建模。

## 1. 美术方向

**一句话**：一盒被晨雾包围的、会发光的微缩箱庭。造型圆润敦实、切面清楚；颜色是低饱和的绘本色，靠暖灯与冷影形成对比。不是写实，不是 MMO 素材，不是平滑高模。

- **低多边形**：所有面 flat shading（`polygon.use_smooth = False`）。球体用 ico_sphere subdivisions=1~2，圆柱 6~8 边，不要 32 边。
- **体块语言**：略夸张、上宽下窄或带一点歪斜，避免死板对称。树冠由 3~6 个多面体块组成；石头有清晰的斜切面。
- **尺度和比例**：主角高约 1.5 m。树 5~10 m，草 0.3~0.5 m，小屋 4~6 m 宽，鸟居 5 m 高，灯塔 15 m。比例要有“玩具箱庭”的可爱感。
- **配色**：每个部件最多 4~5 种主色；整体低饱和。用暖色（灯火、花、沙）做视觉焦点，冷色（苔、雪、夜）做底。
- **不要**：贴图、PBR 花纹、文字、logo、人物写实脸、过细的雕花、透明玻璃（除非指定）、下载素材。

### 四章色板

| 章 | 主色 | 辅色 | 光 |
|---|---|---|---|
| 苔庭·春眠 | 苔绿 `#4F765B`、浅苔 `#86A87C` | 樱粉 `#E7B0AE` / `#F4D3CE`、树皮 `#5D4A3E`、石灰 `#8C9480` | 清晨金 `#F2D49A` |
| 琥珀沙海 | 沙金 `#DDBB7E`、砂岩 `#C07C52` | 深赭 `#8A4F3A`、棕榈绿 `#5E7D4E`、绿洲青 `#4E9A8F` | 黄昏琥珀 `#F0B968` |
| 霜枝谷 | 雪白 `#ECF2EF`、冰蓝 `#B8D9DF` | 松墨 `#2F5450` / `#47706A`、木色 `#6B5548` | 窗口暖光 `#F2B15E` |
| 星坠之穹 | 夜蓝 `#242A48`、岩紫 `#4A4664` | 紫 `#6A5790`、青绿 `#72D6CD`、古金 `#E6C07A` | 星辉青 `#8FE6DC` |

## 2. 技术规范（必须遵守）

1. **单位**：米。场景 unit scale 1.0。
2. **原点**：位于资产底面中心，底面在 Blender `z=0`（桥类见各自说明）。资产朝向 Blender `-Y`（导出到 Godot 后朝 `+Z`）。
3. **应用变换**：`bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)`，object 原点保持在 (0,0,0) 或底面中心。
4. **合并**：一个资产尽可能合并成一个 mesh 对象（多材质槽可以）；发光装饰可保留为独立对象但命名清楚。导出时选中所有属于该资产的物体，或整个场景只放这个资产。
5. **材质**：Principled BSDF，Base Color 用 sRGB hex 对应的线性值；Roughness 0.75~0.95；Metallic 0（金属件可用 0.3）。发光件：Emission Color + Emission Strength 2.5~5。**不要使用图像纹理。**
6. **命名**：对象名 = 资产名（如 `cherry_tree_a`）；mesh 数据同名；材质名有语义（`Bark`, `Leaf`, `Blossom`, `Stone`, `Glow` 等）。叶冠材质名请以 `Leaf` 或 `Blossom` 或 `Grass` 开头，游戏里会自动加风摆 shader。
7. **面数预算**：普通小资产 150~1500 tris；树/建筑 800~3500 tris；英雄资产（灯塔、鲸、鲸骨）≤ 8000 tris。总资产面数尽量低。
8. **导出**：
   ```python
   bpy.ops.export_scene.gltf(
       filepath=out_path,
       export_format='GLB',
       use_selection=True,          # 或 export_selected
       export_apply=True,
       export_yup=True,
       export_animations=False,
   )
   ```
   确保导出后的 GLB 用 Godot 4.7 能直接实例化。导出前清理孤立数据、删除 default cube/camera/light。
9. **碰撞**：不用在 Blender 里做碰撞体，游戏侧会加简单碰撞。
10. **不要烘焙动画**（鲸、鸟等如果需要摆尾，导出为整体静态，Godot 里整体浮动即可）。

## 3. 每个资产的验收

- 打开 GLB 的预览图（Blender 渲染），目检：
  - 轮廓清楚，低角度看也成立；
  - 没有明显穿插、悬空、破面、黑面；
  - 颜色和谐，和同组资产像同一个世界；
  - 底部贴合地面，原点正确；
  - 面数合理。
- 每个资产输出：`assets/models/<类别>/<name>.glb` + `assets/previews/<批次>/<name>.png`
- 整批输出：`assets/previews/<批次>/contact_sheet.png`（带英文标签，4 列，米色背景）和 `assets/models/<类别>/manifest.json`（name, file, bounds, tris, tags, suggested_use）。
- 最后在回复里给出：资产数量、contact sheet 路径、任何未完成/有问题项。

## 4. 预览渲染建议

用 Cycles CPU（headless 稳定），24~32 samples，512×512，透明或浅米灰背景。三灯：暖 key + 冷 fill + 轮廓 rim。相机 3/4 视角看向包围盒中心，自动计算距离。每个资产单独渲染，渲染完再切下一个资产。
示例核心：

```python
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.render.resolution_x = scene.render.resolution_y = 512
scene.render.film_transparent = False
scene.world.color = (0.82, 0.80, 0.75)
```

用 `camera.data.lens = 50`，计算所有物体的世界包围盒，取 `center` 与 `radius`，相机距离约为 `radius * 3.2`。
渲染文件名与资产名一致。Pillow 拼 contact sheet：

```python
from PIL import Image, ImageDraw
```

## 5. 交付后不要删中间产物

保留 `tools/blender/<batch>.py` 和预览图，方便重新生成与复查。
