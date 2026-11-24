掉线提醒素材（可选）
====================

路径：assets/disconnect/

用途：
  DisconnectAlert 会扫描本目录下的 png/jpg，用模板匹配登录/选角界面。
  没有素材时仍可用：
    1) 连续丢帧（游戏窗最小化/关闭）→ 掉线提醒
    2) OCR 关键词（重新登录 / 选择角色 / 频道选择 / …）

建议裁图：
  - 选角色页标题条
  - 「重新登录」按钮附近文字
  - 登录器大标题

命名任意，例如：
  char_select_title.png
  relogin_btn.png

配置：
  config/config_custom.yaml → disconnect_alert:
    enable: true
    sensitivity: 50
    templates_dir: "assets/disconnect"
