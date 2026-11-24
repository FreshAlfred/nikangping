测谎 / 谎言探测仪
================

路径：
  assets/lie_detector/lie.png           英文 LIE DETECTOR 标题
  assets/lie_detector/lie_en.png        同上备份
  assets/lie_detector/lie_cn_title.png  盛趣「谎言探测仪」标题
  assets/lie_detector/shapes/           ★ 任意图形裁图目录（不限星形）
      star.png / star_faded.png         已有示例；可再加 heart.png、diamond.png…
  assets/lie_detector/ref_cn_dialog.jpg 盛趣弹窗参考截图

检测：
  - 模板匹配标题栏 + OCR 关键词
  - 命中后：响铃、暂停挂机
  - 默认自动录像：触发前约 2 秒 + 整段测谎 → _debug_out/lie_clips/lie_时间戳.mp4
    关闭：lie_alert.record_clip: false

鼠标跟随（lie_alert.auto_follow）——对标 gostart 高级模式：
  1) 弹窗/intro 结束
  2) 连续确认开局白形（opening_confirm_frames）后才首次移鼠
  3) 热力图因果跟踪（lie_heatmap.onnx，自有权重）+ 白形/YOLO 回退
  4) fail-closed：低置信 / 多峰歧义不移鼠；短时预测用 predict_coast_s
  调试窗：红圈 = 当前跟踪中心

热力图模型：
  assets/lie_detector/lie_heatmap.onnx   # 缺失时会自动导出启发式头

补充其它图形模板（可选，更稳）：
  1. 小游戏里截一张清晰实心白图
  2. 只裁图形本身 → assets/lie_detector/shapes/随便命名.png
  3. 重启脚本即可自动加载

关闭跟随（只响铃）：
  lie_alert.auto_follow: false

灵敏度（对标 gostart「小游戏出现提醒」）：
  lie_alert.sensitivity: 50   # 0–100；越高越易命中

掉线提醒见：
  assets/disconnect/README.txt
  config → disconnect_alert

注意：跟随会移动系统鼠标；测谎时请勿同时手动抢鼠标。
