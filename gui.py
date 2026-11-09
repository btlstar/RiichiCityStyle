"""RiichiStyle standalone desktop manager."""
import os
from pathlib import Path
from queue import Queue, Empty
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import service
from tool_version import TOOL_VERSION


class Application(ttk.Frame):
    def __init__(self, window):
        super().__init__(window, padding=24)
        self.pack(fill="both", expand=True)
        self.events = Queue()
        self.busy = False
        self.backup_dir = None
        self.game = tk.StringVar(value=service.load_game())
        self.message = tk.StringVar(value="选择游戏目录后查看状态。")
        self.location = tk.StringVar(value="安装前会先校验并备份原始文件。")
        ttk.Label(self, text="RiichiStyle", font=("Microsoft YaHei UI", 23, "bold")).pack(anchor="w")
        ttk.Label(self, text=f"一番街本地装扮 · {TOOL_VERSION}").pack(anchor="w", pady=(4, 24))
        ttk.Label(self, text="游戏本体目录（包含 Mahjong-JP.exe）").pack(anchor="w")
        picker = ttk.Frame(self); picker.pack(fill="x", pady=(8, 20))
        self.path_entry = ttk.Entry(picker, textvariable=self.game)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4)
        browse = ttk.Button(picker, text="选择目录…", command=self.browse)
        browse.pack(side="right", padx=(10, 0))
        status_box = ttk.LabelFrame(self, text="兼容与安装状态", padding=16)
        status_box.pack(fill="x")
        ttk.Label(status_box, textvariable=self.message, wraplength=630, justify="left").pack(anchor="w")
        self.progress = ttk.Progressbar(status_box, mode="indeterminate")
        self.progress.pack(fill="x", pady=(14, 0))
        controls = ttk.Frame(self); controls.pack(fill="x", pady=(22, 16))
        self.inputs = [self.path_entry, browse]
        for title, action in [("查看状态", "status"), ("安装 / 更新", "install"), ("还原游戏文件", "restore")]:
            button = ttk.Button(controls, text=title, command=lambda selected=action: self.start(selected))
            button.pack(side="left", padx=(0, 12), ipadx=10, ipady=5)
            self.inputs.append(button)
        ttk.Label(self, text="先完成官方资源更新并退出游戏。安装后正常启动一番街，在游戏原有界面选择装扮。", wraplength=650).pack(anchor="w", pady=(0, 12))
        ttk.Label(self, text="进桌后皮肤恢复默认时，请检查游戏的安全模式是否包含自己。", wraplength=650).pack(anchor="w", pady=(0, 16))
        ttk.Label(self, textvariable=self.location, wraplength=650, foreground="#666666").pack(anchor="w")
        self.folder_button = ttk.Button(self, text="打开备份目录", command=self.show_backup, state="disabled")
        self.folder_button.pack(anchor="w", pady=(10, 0))
        ttk.Label(self, text="本地装扮选择按账号保存。此管理工具无需运行网络代理。", wraplength=650, foreground="#666666").pack(anchor="w", pady=(20, 0))
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.receive)
        if self.game.get():
            self.after(200, lambda: self.start("status"))

    def browse(self):
        selected = filedialog.askdirectory(parent=self, title="选择一番街 Game 目录", initialdir=self.game.get() or None)
        if selected:
            self.game.set(selected)
            self.start("status")

    def start(self, action):
        if self.busy:
            return
        path = self.game.get().strip()
        if not path:
            self.message.set("请先选择游戏本体目录。")
            return
        self.busy = True
        for widget in self.inputs + [self.folder_button]:
            widget.configure(state="disabled")
        self.progress.start(12)
        self.message.set({"status": "正在检查…", "install": "正在校验、备份并安装…", "restore": "正在校验并还原…"}[action])
        def run():
            try:
                self.events.put((True, service.perform(action, path)))
            except Exception as error:
                self.events.put((False, service.friendly_error(error)))
        threading.Thread(target=run, daemon=True).start()

    def receive(self):
        try:
            success, result = self.events.get_nowait()
        except Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            for widget in self.inputs:
                widget.configure(state="normal")
            if success:
                self.game.set(result["game"])
                self.message.set(result["message"])
                self.backup_dir = Path(result["state"])
                self.location.set("备份位置：" + result["state"])
            else:
                self.message.set("操作未完成：" + result)
            if self.backup_dir and self.backup_dir.is_dir():
                self.folder_button.configure(state="normal")
        self.after(100, self.receive)

    def show_backup(self):
        if self.backup_dir and self.backup_dir.is_dir():
            os.startfile(self.backup_dir)

    def close(self):
        if self.busy:
            self.message.set("当前操作正在进行，完成后可以关闭窗口。")
        else:
            self.master.destroy()


def main():
    window = tk.Tk()
    window.title(f"RiichiStyle {TOOL_VERSION}")
    window.geometry("780x640"); window.minsize(740, 620)
    style = ttk.Style(window)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure(".", font=("Microsoft YaHei UI", 10))
    Application(window)
    window.mainloop()


if __name__ == "__main__":
    main()
